#!/usr/bin/env python3
"""
Motor de Diagnóstico Territorial — Central Samir 2026

Cruza, de forma determinística:
1) histórico eleitoral de Samir (dados.csv);
2) eleitorado e território atuais de 2026 (eleitorado_2026_ac.csv);
3) base privada de apoiadores do Google Forms/Sheets.

PRIVACIDADE
-----------
- O script lê a planilha privada, mas NÃO exporta nomes, telefones,
  endereços pessoais ou qualquer identificador individual.
- Contagens territoriais menores que SUPPORTER_MIN_CELL (padrão 10)
  são suprimidas na saída.
- Pequenos volumes não são classificados como "organização baixa":
  recebem "SINAL INSUFICIENTE" para evitar falsas conclusões.

INTERPRETAÇÃO
-------------
- A base de apoiadores NÃO é pesquisa eleitoral.
- "Organização atual" mede presença cadastrada da campanha.
- "Histórico alto/baixo" é relativo ao próprio território de comparação,
  não uma previsão de voto em 2026.
- 2020/2024 só são usados em Rio Branco, onde Samir foi candidato a vereador.
- 2022 é usado em todo o Acre, por ter sido candidatura estadual/federal.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gspread
import numpy as np
import pandas as pd
from google.oauth2.service_account import Credentials

HISTORICO_PATH = Path(os.getenv("HISTORICO_PATH", "dados.csv"))
ELEITORADO_2026_PATH = Path(os.getenv("ELEITORADO_2026_PATH", "eleitorado_2026_ac.csv"))
OUTPUT_PATH = Path(os.getenv("DIAGNOSTICO_OUTPUT", "diagnostico_territorial.json"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
WORKSHEET_ENV = os.getenv("SUPPORTER_WORKSHEET", "").strip()
MIN_CELL = int(os.getenv("SUPPORTER_MIN_CELL", "10"))
ACRE_TZ = timezone(timedelta(hours=-5))


def norm(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def service_account_from_env() -> dict[str, Any]:
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("Defina GCP_SERVICE_ACCOUNT_JSON nos Secrets.")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        import tomllib
        obj = tomllib.loads(raw)
        obj = obj.get("gcp_service_account", obj)
    if not isinstance(obj, dict):
        raise RuntimeError("Credencial da conta de serviço inválida.")
    pk = obj.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        obj["private_key"] = pk.replace("\\n", "\n")
    return obj


def achar_coluna(headers: list[str], aliases: list[str], contem: list[str] | None = None) -> str | None:
    mapa = {norm(h): h for h in headers}
    for a in aliases:
        if norm(a) in mapa:
            return mapa[norm(a)]
    termos = [norm(x) for x in (contem or [])]
    for h in headers:
        nh = norm(h)
        if termos and all(t in nh for t in termos):
            return h
    return None


def escolher_aba(book):
    candidatos = [x for x in [
        WORKSHEET_ENV,
        "Samir Bestene - Apoiadores (Respostas)",
        "Samir Bestene – Apoiadores (Respostas)",
        "Form_Responses",
        "Form Responses",
    ] if x]
    mapa = {norm(ws.title): ws for ws in book.worksheets()}
    for nome in candidatos:
        if norm(nome) in mapa:
            return mapa[norm(nome)]
    raise RuntimeError(
        "Nenhuma aba de apoiadores encontrada. "
        f"Abas disponíveis: {[w.title for w in book.worksheets()]}"
    )


def carregar_apoiadores_privados() -> tuple[pd.DataFrame, dict]:
    if not SHEET_ID:
        raise RuntimeError("Defina GOOGLE_SHEET_ID nos Secrets.")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    gc = gspread.authorize(creds)
    ws = escolher_aba(gc.open_by_key(SHEET_ID))
    rows = ws.get_all_records(default_blank="")
    if not rows:
        raise RuntimeError("A aba de apoiadores está vazia.")

    headers = list(rows[0].keys())
    col_bairro = achar_coluna(headers, ["Bairro"]) or achar_coluna(headers, [], contem=["BAIRRO"])
    col_mun = (
        achar_coluna(headers, ["Município", "Municipio", "Cidade"])
        or achar_coluna(headers, [], contem=["MUNICIP"])
        or achar_coluna(headers, [], contem=["CIDADE"])
    )
    col_nome = achar_coluna(headers, ["Nome Completo", "Nome"])
    if not col_mun or not col_bairro:
        raise RuntimeError(
            "Não foi possível identificar Município e Bairro na planilha. "
            f"Município={col_mun!r}; Bairro={col_bairro!r}"
        )

    validos = []
    for r in rows:
        if col_nome and not str(r.get(col_nome, "")).strip() and not str(r.get(col_bairro, "")).strip():
            continue
        mun = norm(r.get(col_mun, ""))
        bairro = norm(r.get(col_bairro, ""))
        if not mun:
            mun = "MUNICIPIO NAO INFORMADO"
        if not bairro:
            bairro = "BAIRRO NAO INFORMADO"
        validos.append({"MUN_KEY": mun, "BAIRRO_KEY": bairro})

    return pd.DataFrame(validos), {
        "aba": ws.title,
        "coluna_municipio": col_mun,
        "coluna_bairro": col_bairro,
        "total_lido": len(validos),
    }


def carregar_bases() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not HISTORICO_PATH.exists():
        raise FileNotFoundError(f"Ausente: {HISTORICO_PATH}")
    if not ELEITORADO_2026_PATH.exists():
        raise FileNotFoundError(f"Ausente: {ELEITORADO_2026_PATH}")

    hist = pd.read_csv(HISTORICO_PATH, encoding="utf-8-sig")
    ele = pd.read_csv(ELEITORADO_2026_PATH, dtype={"CD_MUNICIPIO": "string"})

    obrig_hist = {
        "ANO_ELEICAO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
        "NM_LOCAL_VOTACAO", "QT_VOTOS_SAMIR"
    }
    obrig_ele = {
        "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NM_BAIRRO",
        "QT_ELEITOR_SECAO"
    }
    faltam_h = obrig_hist - set(hist.columns)
    faltam_e = obrig_ele - set(ele.columns)
    if faltam_h:
        raise RuntimeError(f"dados.csv sem colunas: {sorted(faltam_h)}")
    if faltam_e:
        raise RuntimeError(f"eleitorado_2026_ac.csv sem colunas: {sorted(faltam_e)}")

    hist["MUN_KEY"] = hist["NM_MUNICIPIO"].map(norm)
    ele["MUN_KEY"] = ele["NM_MUNICIPIO"].map(norm)
    ele["BAIRRO_KEY"] = ele["NM_BAIRRO"].fillna("").map(norm)
    ele.loc[ele["BAIRRO_KEY"].eq(""), "BAIRRO_KEY"] = "BAIRRO NAO INFORMADO"

    for c in ["NR_ZONA", "NR_SECAO"]:
        hist[c] = pd.to_numeric(hist[c], errors="coerce").astype("Int64")
        ele[c] = pd.to_numeric(ele[c], errors="coerce").astype("Int64")
    hist["QT_VOTOS_SAMIR"] = pd.to_numeric(hist["QT_VOTOS_SAMIR"], errors="coerce").fillna(0)
    ele["QT_ELEITOR_SECAO"] = pd.to_numeric(ele["QT_ELEITOR_SECAO"], errors="coerce").fillna(0)

    return hist, ele


def eleitorado_por_bairro(ele: pd.DataFrame) -> pd.DataFrame:
    return (
        ele.groupby(["MUN_KEY", "BAIRRO_KEY"], as_index=False)
        .agg(
            ELEITORES_2026=("QT_ELEITOR_SECAO", "sum"),
            SECOES_2026=("NR_SECAO", "nunique"),
            NM_MUNICIPIO=("NM_MUNICIPIO", "first"),
            NM_BAIRRO=("NM_BAIRRO", "first"),
        )
    )


def eleitorado_por_municipio(ele: pd.DataFrame) -> pd.DataFrame:
    return (
        ele.groupby("MUN_KEY", as_index=False)
        .agg(
            ELEITORES_2026=("QT_ELEITOR_SECAO", "sum"),
            SECOES_2026=("NR_SECAO", "nunique"),
            LOCAIS_2026=("NM_LOCAL_VOTACAO", "nunique"),
            NM_MUNICIPIO=("NM_MUNICIPIO", "first"),
        )
    )


def historico_mapeado_para_2026(hist: pd.DataFrame, ele: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    mapa = ele[[
        "MUN_KEY", "NR_ZONA", "NR_SECAO", "BAIRRO_KEY", "NM_BAIRRO"
    ]].drop_duplicates(["MUN_KEY", "NR_ZONA", "NR_SECAO"])

    h = hist.copy()
    # Fora de Rio Branco, 2020 e 2024 não representam ausência de apoio:
    # Samir não disputou cargo nesses municípios nesses anos.
    h = h[
        (h["ANO_ELEICAO"].eq(2022))
        | ((h["MUN_KEY"].eq("RIO BRANCO")) & h["ANO_ELEICAO"].isin([2020, 2024]))
    ].copy()

    m = h.merge(
        mapa,
        on=["MUN_KEY", "NR_ZONA", "NR_SECAO"],
        how="left",
        indicator=True,
        validate="many_to_one",
    )

    cobertura = []
    for ano, g in m.groupby("ANO_ELEICAO"):
        votos_total = float(g["QT_VOTOS_SAMIR"].sum())
        votos_match = float(g.loc[g["_merge"].eq("both"), "QT_VOTOS_SAMIR"].sum())
        cobertura.append({
            "ano": int(ano),
            "linhas_historicas": int(len(g)),
            "linhas_mapeadas_2026": int(g["_merge"].eq("both").sum()),
            "votos_historicos": int(votos_total),
            "votos_mapeados_2026": int(votos_match),
            "cobertura_votos_pct": round((votos_match / votos_total * 100) if votos_total else 0, 1),
        })

    return m[m["_merge"].eq("both")].drop(columns="_merge"), cobertura


def calcular_historico_bairro(
    hist_map: pd.DataFrame,
    ele_bairro: pd.DataFrame,
    ele_mun: pd.DataFrame,
) -> pd.DataFrame:
    hb = (
        hist_map.groupby(["ANO_ELEICAO", "MUN_KEY", "BAIRRO_KEY"], as_index=False)
        .agg(VOTOS_SAMIR=("QT_VOTOS_SAMIR", "sum"))
        .merge(ele_bairro[["MUN_KEY", "BAIRRO_KEY", "ELEITORES_2026"]], on=["MUN_KEY", "BAIRRO_KEY"], how="left")
    )

    totais = (
        hist_map.groupby(["ANO_ELEICAO", "MUN_KEY"], as_index=False)
        .agg(VOTOS_MUN=("QT_VOTOS_SAMIR", "sum"))
        .merge(ele_mun[["MUN_KEY", "ELEITORES_2026"]].rename(columns={"ELEITORES_2026": "ELEITORES_MUN"}), on="MUN_KEY", how="left")
    )
    hb = hb.merge(totais, on=["ANO_ELEICAO", "MUN_KEY"], how="left")
    hb["TAXA_BAIRRO"] = np.where(hb["ELEITORES_2026"] > 0, hb["VOTOS_SAMIR"] / hb["ELEITORES_2026"], np.nan)
    hb["TAXA_MUN"] = np.where(hb["ELEITORES_MUN"] > 0, hb["VOTOS_MUN"] / hb["ELEITORES_MUN"], np.nan)
    hb["INDICE_HIST_ANO"] = np.where(hb["TAXA_MUN"] > 0, hb["TAXA_BAIRRO"] / hb["TAXA_MUN"], np.nan)

    resumo = (
        hb.groupby(["MUN_KEY", "BAIRRO_KEY"], as_index=False)
        .agg(
            INDICE_HISTORICO=("INDICE_HIST_ANO", "median"),
            VOTOS_HISTORICOS=("VOTOS_SAMIR", "sum"),
            ELEICOES_COM_VOTO=("ANO_ELEICAO", "nunique"),
        )
    )
    return resumo


def calcular_historico_municipio(hist: pd.DataFrame, ele_mun: pd.DataFrame) -> pd.DataFrame:
    h22 = hist[hist["ANO_ELEICAO"].eq(2022)].groupby("MUN_KEY", as_index=False).agg(
        VOTOS_2022=("QT_VOTOS_SAMIR", "sum")
    )
    h22["TEM_REGISTRO_2022"] = True

    base = ele_mun.merge(h22, on="MUN_KEY", how="left")
    base["TEM_REGISTRO_2022"] = base["TEM_REGISTRO_2022"].fillna(False)

    # dados.csv contém apenas registros em que há votação do candidato.
    # Portanto, município ausente não é transformado silenciosamente em zero.
    comparaveis = base[base["TEM_REGISTRO_2022"]].copy()
    total_votos = comparaveis["VOTOS_2022"].sum()
    total_eleitores = comparaveis["ELEITORES_2026"].sum()
    taxa_referencia = total_votos / total_eleitores if total_eleitores else np.nan

    base["TAXA_HIST_2022"] = np.where(
        base["TEM_REGISTRO_2022"] & (base["ELEITORES_2026"] > 0),
        base["VOTOS_2022"] / base["ELEITORES_2026"],
        np.nan,
    )
    base["INDICE_HISTORICO"] = np.where(
        base["TEM_REGISTRO_2022"] & (taxa_referencia > 0),
        base["TAXA_HIST_2022"] / taxa_referencia,
        np.nan,
    )
    return base

def agregar_apoiadores(apoiadores: pd.DataFrame):
    ab = apoiadores.groupby(["MUN_KEY", "BAIRRO_KEY"], as_index=False).size().rename(columns={"size": "APOIADORES"})
    am = apoiadores.groupby("MUN_KEY", as_index=False).size().rename(columns={"size": "APOIADORES"})
    return ab, am


def classificar(hist_idx: float | None, org_idx: float | None, n_apoiadores: int) -> tuple[str, str]:
    hist_disponivel = hist_idx is not None and pd.notna(hist_idx)

    if not hist_disponivel:
        if n_apoiadores >= MIN_CELL and org_idx is not None and pd.notna(org_idx) and org_idx >= 1.0:
            return (
                "SINAL ATUAL SEM HISTÓRICO COMPARÁVEL",
                "Há organização cadastrada acima da referência, mas a base histórica atual não contém registro suficiente para classificar a penetração anterior."
            )
        return (
            "HISTÓRICO INSUFICIENTE",
            "A base histórica atual não contém registro suficiente para classificar este território como forte ou fraco."
        )

    hist_alto = hist_idx >= 1.0
    if n_apoiadores < MIN_CELL or org_idx is None or pd.isna(org_idx):
        if hist_alto:
            return "VERIFICAR ESTRUTURA", "Histórico acima da referência, mas a base cadastrada ainda é pequena demais para concluir sobre organização atual."
        return "SINAL INSUFICIENTE", "Há histórico comparável, mas a base cadastrada é pequena demais para inferir organização atual com segurança."

    org_alta = org_idx >= 1.0
    if hist_alto and org_alta:
        return "CONSOLIDAR", "Presença histórica e organização cadastrada estão acima da referência do território."
    if hist_alto and not org_alta:
        return "RECUPERAR ORGANIZAÇÃO", "O histórico é acima da referência, mas a organização cadastrada está abaixo da média territorial."
    if (not hist_alto) and org_alta:
        return "SINAL DE EXPANSÃO", "A organização cadastrada está acima da média apesar de um histórico eleitoral abaixo da referência."
    return "DIAGNOSTICAR", "Histórico e organização cadastrada estão abaixo das respectivas referências; investigar antes de priorizar recursos."

def montar_municipios(hist: pd.DataFrame, ele_mun: pd.DataFrame, apoiadores_mun: pd.DataFrame) -> list[dict]:
    base = calcular_historico_municipio(hist, ele_mun)
    base = base.merge(apoiadores_mun, on="MUN_KEY", how="left")
    base["APOIADORES"] = base["APOIADORES"].fillna(0).astype(int)

    total_apoiadores_localizados = int(base["APOIADORES"].sum())
    total_e = float(base["ELEITORES_2026"].sum())
    taxa_org_estado = total_apoiadores_localizados / total_e if total_e else np.nan
    base["TAXA_ORG"] = np.where(base["ELEITORES_2026"] > 0, base["APOIADORES"] / base["ELEITORES_2026"], np.nan)
    base["INDICE_ORGANIZACAO"] = np.where(taxa_org_estado > 0, base["TAXA_ORG"] / taxa_org_estado, np.nan)

    saida = []
    for _, r in base.sort_values("ELEITORES_2026", ascending=False).iterrows():
        hist_idx = float(r["INDICE_HISTORICO"]) if pd.notna(r["INDICE_HISTORICO"]) else None
        org_idx = float(r["INDICE_ORGANIZACAO"]) if pd.notna(r["INDICE_ORGANIZACAO"]) else None
        classe, motivo = classificar(hist_idx, org_idx, int(r["APOIADORES"]))
        apoiadores_exibicao = int(r["APOIADORES"]) if int(r["APOIADORES"]) >= MIN_CELL else f"<{MIN_CELL}"
        votos_2022 = int(r["VOTOS_2022"]) if bool(r["TEM_REGISTRO_2022"]) and pd.notna(r["VOTOS_2022"]) else None
        saida.append({
            "municipio": str(r["NM_MUNICIPIO"]),
            "eleitores_2026": int(r["ELEITORES_2026"]),
            "votos_2022": votos_2022,
            "apoiadores_cadastrados": apoiadores_exibicao,
            "indice_historico": round(hist_idx, 2) if hist_idx is not None else None,
            "indice_organizacao": round(float(r["INDICE_ORGANIZACAO"]), 2) if int(r["APOIADORES"]) >= MIN_CELL and pd.notna(r["INDICE_ORGANIZACAO"]) else None,
            "classificacao": classe,
            "motivo": motivo,
        })
    return saida


def montar_bairros(
    ele_bairro: pd.DataFrame,
    ele_mun: pd.DataFrame,
    hist_bairro: pd.DataFrame,
    apoiadores_bairro: pd.DataFrame,
    apoiadores_mun: pd.DataFrame,
) -> tuple[list[dict], list[dict]]:
    base = ele_bairro.merge(hist_bairro, on=["MUN_KEY", "BAIRRO_KEY"], how="left")
    base = base.merge(apoiadores_bairro, on=["MUN_KEY", "BAIRRO_KEY"], how="left")
    base["APOIADORES"] = base["APOIADORES"].fillna(0).astype(int)
    base = base.merge(
        apoiadores_mun.rename(columns={"APOIADORES": "APOIADORES_MUN"}),
        on="MUN_KEY",
        how="left"
    )
    base["APOIADORES_MUN"] = base["APOIADORES_MUN"].fillna(0)
    base = base.merge(
        ele_mun[["MUN_KEY", "ELEITORES_2026"]].rename(columns={"ELEITORES_2026": "ELEITORES_MUN"}),
        on="MUN_KEY",
        how="left"
    )
    base["TAXA_ORG_BAIRRO"] = np.where(base["ELEITORES_2026"] > 0, base["APOIADORES"] / base["ELEITORES_2026"], np.nan)
    base["TAXA_ORG_MUN"] = np.where(base["ELEITORES_MUN"] > 0, base["APOIADORES_MUN"] / base["ELEITORES_MUN"], np.nan)
    base["INDICE_ORGANIZACAO"] = np.where(base["TAXA_ORG_MUN"] > 0, base["TAXA_ORG_BAIRRO"] / base["TAXA_ORG_MUN"], np.nan)

    territorios = []
    for _, r in base.iterrows():
        hidx = float(r["INDICE_HISTORICO"]) if pd.notna(r["INDICE_HISTORICO"]) else None
        oidx = float(r["INDICE_ORGANIZACAO"]) if pd.notna(r["INDICE_ORGANIZACAO"]) else None
        n = int(r["APOIADORES"])
        classe, motivo = classificar(hidx, oidx, n)
        territorios.append({
            "municipio": str(r["NM_MUNICIPIO"]),
            "bairro": str(r["NM_BAIRRO"]) if pd.notna(r["NM_BAIRRO"]) and str(r["NM_BAIRRO"]).strip() else str(r["BAIRRO_KEY"]).title(),
            "eleitores_2026": int(r["ELEITORES_2026"]),
            "secoes_2026": int(r["SECOES_2026"]),
            "apoiadores_cadastrados": n if n >= MIN_CELL else f"<{MIN_CELL}",
            "indice_historico": round(hidx, 2) if hidx is not None else None,
            "indice_organizacao": round(oidx, 2) if n >= MIN_CELL and oidx is not None else None,
            "votos_historicos_mapeados": int(r["VOTOS_HISTORICOS"]) if pd.notna(r["VOTOS_HISTORICOS"]) else 0,
            "eleicoes_com_voto_mapeado": int(r["ELEICOES_COM_VOTO"]) if pd.notna(r["ELEICOES_COM_VOTO"]) else 0,
            "classificacao": classe,
            "motivo": motivo,
        })

    # Cadastros cujo bairro não bateu exatamente com a nomenclatura TSE.
    oficiais = {
        m: sorted(set(g["BAIRRO_KEY"]))
        for m, g in ele_bairro.groupby("MUN_KEY")
    }
    chaves_oficiais = set(zip(ele_bairro["MUN_KEY"], ele_bairro["BAIRRO_KEY"]))
    nao_casados = apoiadores_bairro[
        ~apoiadores_bairro.apply(lambda r: (r["MUN_KEY"], r["BAIRRO_KEY"]) in chaves_oficiais, axis=1)
    ].copy()

    revisao = []
    for _, r in nao_casados.sort_values("APOIADORES", ascending=False).iterrows():
        candidatos = oficiais.get(r["MUN_KEY"], [])
        sugestoes = difflib.get_close_matches(r["BAIRRO_KEY"], candidatos, n=3, cutoff=0.65)
        n = int(r["APOIADORES"])
        revisao.append({
            "municipio": r["MUN_KEY"].title(),
            "bairro_declarado": r["BAIRRO_KEY"].title() if n >= MIN_CELL else f"Suprimido (<{MIN_CELL})",
            "apoiadores": n if n >= MIN_CELL else f"<{MIN_CELL}",
            "sugestoes_tse": [s.title() for s in sugestoes] if n >= MIN_CELL else [],
        })

    territorios.sort(
        key=lambda x: (
            x["classificacao"] not in {"RECUPERAR ORGANIZAÇÃO", "SINAL DE EXPANSÃO", "CONSOLIDAR"},
            -x["eleitores_2026"]
        )
    )
    return territorios, revisao


def resumo_classes(items: list[dict]) -> dict:
    c = Counter(x["classificacao"] for x in items)
    return dict(sorted(c.items()))


def main():
    hist, ele = carregar_bases()
    apoiadores, meta_ap = carregar_apoiadores_privados()

    ele_b = eleitorado_por_bairro(ele)
    ele_m = eleitorado_por_municipio(ele)
    ap_b, ap_m = agregar_apoiadores(apoiadores)

    hist_map, cobertura = historico_mapeado_para_2026(hist, ele)
    hist_b = calcular_historico_bairro(hist_map, ele_b, ele_m)

    municipios = montar_municipios(hist, ele_m, ap_m)
    bairros, revisao = montar_bairros(ele_b, ele_m, hist_b, ap_b, ap_m)

    total_sem_mun = int((apoiadores["MUN_KEY"] == "MUNICIPIO NAO INFORMADO").sum())
    total_com_mun = len(apoiadores) - total_sem_mun

    payload = {
        "meta": {
            "gerado_em": datetime.now(ACRE_TZ).isoformat(timespec="seconds"),
            "versao_motor": "1.0",
            "privacidade": (
                f"Sem PII. Contagens menores que {MIN_CELL} são suprimidas. "
                "A base de apoiadores mede organização cadastrada, não intenção de voto."
            ),
            "fontes": [
                str(HISTORICO_PATH),
                str(ELEITORADO_2026_PATH),
                f"Google Sheets / {meta_ap['aba']}",
            ],
            "colunas_apoiadores": {
                "municipio": meta_ap["coluna_municipio"],
                "bairro": meta_ap["coluna_bairro"],
            },
        },
        "qualidade": {
            "apoiadores_lidos": len(apoiadores),
            "apoiadores_com_municipio": total_com_mun,
            "apoiadores_sem_municipio": total_sem_mun,
            "cobertura_historico_para_secoes_2026": cobertura,
            "bairros_declarados_para_revisao": len(revisao),
        },
        "matriz_municipal": {
            "resumo": resumo_classes(municipios),
            "territorios": municipios,
        },
        "matriz_bairros": {
            "resumo": resumo_classes(bairros),
            "territorios": bairros,
            "revisao_nomes_bairro": revisao[:50],
        },
        "regras": {
            "historico_alto": "Índice histórico >= 1,00 (acima da referência territorial).",
            "organizacao_alta": "Índice de organização >= 1,00 e pelo menos o mínimo de cadastros.",
            "celula_minima": MIN_CELL,
            "rio_branco": "Índice histórico usa a mediana relativa de 2020, 2022 e 2024 quando a seção histórica pôde ser ligada ao território 2026.",
            "demais_municipios": "Histórico territorial usa 2022; ausência de registro em dados.csv não é convertida em zero. 2020/2024 não são tratados como zero fora de Rio Branco.",
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "saida": str(OUTPUT_PATH),
        "apoiadores": len(apoiadores),
        "municipios": len(municipios),
        "bairros": len(bairros),
        "revisoes_bairro": len(revisao),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
