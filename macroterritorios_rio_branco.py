#!/usr/bin/env python3
"""
Macroterritórios de Rio Branco — Central Samir 2026

Objetivo:
Criar uma camada territorial mais segura do que comparar diretamente
"bairro de residência" (Forms) com "bairro do local de votação" (TSE).

Método:
- Agrupa bairros eleitorais de Rio Branco em macroterritórios geográficos
  usando coordenadas dos locais de votação de 2026.
- Mantém ZONA RURAL separada.
- Liga 2020/2022/2024 às seções atuais por município + zona + seção.
- Liga apoiadores aos macroterritórios SOMENTE quando o bairro residencial
  consegue ser associado com segurança ao nome territorial eleitoral.
- Não usa nomes, telefones ou endereços pessoais.
- Mede e publica a cobertura do casamento de bairros; não esconde incerteza.

ATENÇÃO:
A base de apoiadores mede organização residencial cadastrada, não intenção de voto.
Mesmo nos macroterritórios, a comparação é uma aproximação territorial agregada.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gspread
import numpy as np
import pandas as pd
from google.oauth2.service_account import Credentials

HISTORICO_PATH = Path(os.getenv("HISTORICO_PATH", "dados.csv"))
ELEITORADO_PATH = Path(os.getenv("ELEITORADO_2026_PATH", "eleitorado_2026_ac.csv"))
OUTPUT_PATH = Path(os.getenv("MACRO_OUTPUT", "macroterritorios_rio_branco.json"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
WORKSHEET_ENV = os.getenv("SUPPORTER_WORKSHEET", "").strip()
MIN_CELL = int(os.getenv("SUPPORTER_MIN_CELL", "10"))
K_URBANO = int(os.getenv("MACRO_K_URBANO", "6"))
ACRE_TZ = timezone(timedelta(hours=-5))
RNG = np.random.default_rng(42)


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
        raise RuntimeError("Credencial inválida.")
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
    raise RuntimeError(f"Aba de apoiadores não encontrada. Abas: {[w.title for w in book.worksheets()]}")


def carregar_apoiadores_rb() -> tuple[pd.DataFrame, dict]:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    gc = gspread.authorize(creds)
    ws = escolher_aba(gc.open_by_key(SHEET_ID))
    rows = ws.get_all_records(default_blank="")
    if not rows:
        raise RuntimeError("Aba de apoiadores vazia.")
    headers = list(rows[0].keys())
    col_mun = (
        achar_coluna(headers, ["Município", "Municipio", "Cidade"])
        or achar_coluna(headers, [], contem=["MUNICIP"])
        or achar_coluna(headers, [], contem=["CIDADE"])
    )
    col_bairro = achar_coluna(headers, ["Bairro"]) or achar_coluna(headers, [], contem=["BAIRRO"])
    if not col_mun or not col_bairro:
        raise RuntimeError(f"Colunas territoriais não encontradas: município={col_mun}, bairro={col_bairro}")

    items = []
    for r in rows:
        if norm(r.get(col_mun, "")) != "RIO BRANCO":
            continue
        b = norm(r.get(col_bairro, ""))
        if not b:
            b = "BAIRRO NAO INFORMADO"
        items.append({"BAIRRO_DECLARADO": b})

    return pd.DataFrame(items), {
        "aba": ws.title,
        "coluna_municipio": col_mun,
        "coluna_bairro": col_bairro,
        "total_rio_branco": len(items),
    }


def carregar_bases():
    if not HISTORICO_PATH.exists():
        raise FileNotFoundError(HISTORICO_PATH)
    if not ELEITORADO_PATH.exists():
        raise FileNotFoundError(ELEITORADO_PATH)

    hist = pd.read_csv(HISTORICO_PATH, encoding="utf-8-sig")
    ele = pd.read_csv(ELEITORADO_PATH, dtype={"CD_MUNICIPIO": "string"})

    req_ele = {
        "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NM_BAIRRO",
        "QT_ELEITOR_SECAO", "LATITUDE", "LONGITUDE"
    }
    req_hist = {
        "ANO_ELEICAO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "QT_VOTOS_SAMIR"
    }
    faltam_e = req_ele - set(ele.columns)
    faltam_h = req_hist - set(hist.columns)
    if faltam_e:
        raise RuntimeError(f"eleitorado_2026_ac.csv sem colunas: {sorted(faltam_e)}")
    if faltam_h:
        raise RuntimeError(f"dados.csv sem colunas: {sorted(faltam_h)}")

    ele = ele[ele["NM_MUNICIPIO"].map(norm).eq("RIO BRANCO")].copy()
    hist = hist[hist["NM_MUNICIPIO"].map(norm).eq("RIO BRANCO")].copy()

    for df in [ele, hist]:
        df["NR_ZONA"] = pd.to_numeric(df["NR_ZONA"], errors="coerce").astype("Int64")
        df["NR_SECAO"] = pd.to_numeric(df["NR_SECAO"], errors="coerce").astype("Int64")

    ele["QT_ELEITOR_SECAO"] = pd.to_numeric(ele["QT_ELEITOR_SECAO"], errors="coerce").fillna(0)
    ele["LATITUDE"] = pd.to_numeric(ele["LATITUDE"], errors="coerce")
    ele["LONGITUDE"] = pd.to_numeric(ele["LONGITUDE"], errors="coerce")
    ele["BAIRRO_KEY"] = ele["NM_BAIRRO"].fillna("").map(norm)
    ele.loc[ele["BAIRRO_KEY"].eq(""), "BAIRRO_KEY"] = "BAIRRO NAO INFORMADO"

    hist["QT_VOTOS_SAMIR"] = pd.to_numeric(hist["QT_VOTOS_SAMIR"], errors="coerce").fillna(0)
    return hist, ele


def centroides_bairro(ele: pd.DataFrame) -> pd.DataFrame:
    # Coordenadas ponderadas pelo eleitorado da seção.
    e = ele.dropna(subset=["LATITUDE", "LONGITUDE"]).copy()
    if e.empty:
        raise RuntimeError("Não há coordenadas válidas no eleitorado 2026.")

    def agg(g):
        w = g["QT_ELEITOR_SECAO"].to_numpy(float)
        if w.sum() <= 0:
            w = np.ones(len(g))
        return pd.Series({
            "ELEITORES_2026": float(g["QT_ELEITOR_SECAO"].sum()),
            "LAT": float(np.average(g["LATITUDE"], weights=w)),
            "LON": float(np.average(g["LONGITUDE"], weights=w)),
            "SECOES": int(g["NR_SECAO"].nunique()),
            "NM_BAIRRO": str(g["NM_BAIRRO"].dropna().iloc[0]) if g["NM_BAIRRO"].notna().any() else g.name,
        })

    return e.groupby("BAIRRO_KEY").apply(agg, include_groups=False).reset_index()


def weighted_kmeans(points: np.ndarray, weights: np.ndarray, k: int, max_iter: int = 100):
    n = len(points)
    k = max(1, min(k, n))

    # k-means++ ponderado e determinístico.
    first = int(np.argmax(weights))
    centers = [points[first]]
    for _ in range(1, k):
        d2 = np.min(
            np.stack([np.sum((points - c) ** 2, axis=1) for c in centers], axis=1),
            axis=1
        )
        score = d2 * np.maximum(weights, 1.0)
        idx = int(np.argmax(score))
        centers.append(points[idx])
    centers = np.array(centers, dtype=float)

    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        dist = np.stack([np.sum((points - c) ** 2, axis=1) for c in centers], axis=1)
        new_labels = np.argmin(dist, axis=1)
        if np.array_equal(new_labels, labels) and _ > 0:
            break
        labels = new_labels
        for j in range(k):
            mask = labels == j
            if not mask.any():
                continue
            w = weights[mask]
            centers[j] = np.average(points[mask], axis=0, weights=w)
    return labels, centers


def construir_macros(ele: pd.DataFrame):
    b = centroides_bairro(ele)
    rural_mask = b["BAIRRO_KEY"].str.contains("ZONA RURAL", na=False)

    urbanos = b[~rural_mask].copy()
    rurais = b[rural_mask].copy()

    # Ajusta longitude à latitude de Rio Branco para distância aproximada.
    lat0 = math.radians(float(urbanos["LAT"].median()))
    pts = np.column_stack([
        urbanos["LON"].to_numpy(float) * math.cos(lat0),
        urbanos["LAT"].to_numpy(float)
    ])
    weights = urbanos["ELEITORES_2026"].to_numpy(float)
    labels, centers = weighted_kmeans(pts, weights, K_URBANO)
    urbanos["CLUSTER"] = labels

    # Ordena clusters pelo centro geográfico (norte->sul, oeste->leste) só para IDs estáveis.
    cluster_info = []
    for c in sorted(urbanos["CLUSTER"].unique()):
        g = urbanos[urbanos["CLUSTER"].eq(c)]
        cluster_info.append((c, float(g["LAT"].mean()), float(g["LON"].mean())))
    ordenados = sorted(cluster_info, key=lambda x: (-x[1], x[2]))
    remap = {old: i + 1 for i, (old, _, _) in enumerate(ordenados)}
    urbanos["MACRO_ID"] = urbanos["CLUSTER"].map(lambda x: f"RB-{remap[x]:02d}")

    macros = []
    bairro_para_macro = {}

    for macro_id, g in urbanos.groupby("MACRO_ID"):
        top = g.sort_values("ELEITORES_2026", ascending=False).head(3)["NM_BAIRRO"].astype(str).tolist()
        nome = " / ".join(top)
        macros.append({
            "macro_id": macro_id,
            "nome": f"Macroterritório {macro_id.split('-')[1]} — {nome}",
            "tipo": "URBANO",
            "eleitores_2026": int(g["ELEITORES_2026"].sum()),
            "bairros": sorted(g["BAIRRO_KEY"].tolist()),
            "bairros_referencia": top,
            "lat": round(float(np.average(g["LAT"], weights=g["ELEITORES_2026"])), 6),
            "lon": round(float(np.average(g["LON"], weights=g["ELEITORES_2026"])), 6),
        })
        for x in g["BAIRRO_KEY"]:
            bairro_para_macro[x] = macro_id

    if not rurais.empty:
        macro_id = "RB-RURAL"
        macros.append({
            "macro_id": macro_id,
            "nome": "Macroterritório Rural",
            "tipo": "RURAL",
            "eleitores_2026": int(rurais["ELEITORES_2026"].sum()),
            "bairros": sorted(rurais["BAIRRO_KEY"].tolist()),
            "bairros_referencia": rurais.sort_values("ELEITORES_2026", ascending=False).head(3)["NM_BAIRRO"].astype(str).tolist(),
            "lat": round(float(np.average(rurais["LAT"], weights=rurais["ELEITORES_2026"])), 6),
            "lon": round(float(np.average(rurais["LON"], weights=rurais["ELEITORES_2026"])), 6),
        })
        for x in rurais["BAIRRO_KEY"]:
            bairro_para_macro[x] = macro_id

    return macros, bairro_para_macro, b


def historico_por_macro(hist, ele, bairro_para_macro):
    sec = ele[["NR_ZONA", "NR_SECAO", "BAIRRO_KEY"]].drop_duplicates(["NR_ZONA", "NR_SECAO"])
    sec["MACRO_ID"] = sec["BAIRRO_KEY"].map(bairro_para_macro)
    h = hist[hist["ANO_ELEICAO"].isin([2020, 2022, 2024])].merge(
        sec[["NR_ZONA", "NR_SECAO", "MACRO_ID"]],
        on=["NR_ZONA", "NR_SECAO"],
        how="left",
        indicator=True,
        validate="many_to_one",
    )

    cobertura = []
    for ano, g in h.groupby("ANO_ELEICAO"):
        vt = float(g["QT_VOTOS_SAMIR"].sum())
        vm = float(g.loc[g["_merge"].eq("both") & g["MACRO_ID"].notna(), "QT_VOTOS_SAMIR"].sum())
        cobertura.append({
            "ano": int(ano),
            "votos_historicos": int(vt),
            "votos_mapeados": int(vm),
            "cobertura_pct": round((vm / vt * 100) if vt else 0, 1),
        })

    hm = (
        h[h["MACRO_ID"].notna()]
        .groupby(["ANO_ELEICAO", "MACRO_ID"], as_index=False)
        .agg(VOTOS=("QT_VOTOS_SAMIR", "sum"))
    )
    return hm, cobertura


ALIASES_SEGUROS = {
    "UNIVERSITARIO": "CONJUNTO UNIVERSITARIO",
    "CONJ UNIVERSITARIO": "CONJUNTO UNIVERSITARIO",
}


def casar_bairro_forms(nome: str, oficiais: list[str]) -> tuple[str | None, str]:
    n = ALIASES_SEGUROS.get(nome, nome)
    if n in oficiais:
        return n, "EXATO_OU_ALIAS"

    # Fuzzy muito conservador. Só aceita se a melhor opção for realmente forte
    # e claramente melhor que a segunda.
    scores = sorted(
        [(difflib.SequenceMatcher(None, n, o).ratio(), o) for o in oficiais],
        reverse=True
    )
    if not scores:
        return None, "SEM_MATCH"
    best_score, best = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0
    if best_score >= 0.94 and (best_score - second) >= 0.05:
        return best, "FUZZY_SEGURO"
    return None, "SEM_MATCH"


def apoiadores_por_macro(apoiadores, bairro_para_macro):
    oficiais = sorted(bairro_para_macro.keys())
    cont_macro = Counter()
    cont_nao = Counter()
    modos = Counter()

    for b in apoiadores["BAIRRO_DECLARADO"]:
        casado, modo = casar_bairro_forms(b, oficiais)
        modos[modo] += 1
        if casado is None:
            cont_nao[b] += 1
            continue
        macro = bairro_para_macro.get(casado)
        if macro:
            cont_macro[macro] += 1
        else:
            cont_nao[b] += 1

    return cont_macro, cont_nao, modos


def classificar(hist_idx, org_idx, n):
    if hist_idx is None or org_idx is None or n < MIN_CELL:
        return "SINAL INSUFICIENTE"
    if hist_idx >= 1 and org_idx >= 1:
        return "CONSOLIDAR"
    if hist_idx >= 1 and org_idx < 1:
        return "RECUPERAR ORGANIZAÇÃO"
    if hist_idx < 1 and org_idx >= 1:
        return "SINAL DE EXPANSÃO"
    return "DIAGNOSTICAR"


def main():
    hist, ele = carregar_bases()
    apoiadores, meta_ap = carregar_apoiadores_rb()
    macros, bairro_para_macro, bairros = construir_macros(ele)
    hist_macro, cobertura_hist = historico_por_macro(hist, ele, bairro_para_macro)
    ap_macro, nao_casados, modos = apoiadores_por_macro(apoiadores, bairro_para_macro)

    macro_df = pd.DataFrame(macros)
    total_eleitores = float(macro_df["eleitores_2026"].sum())
    total_apoiadores = len(apoiadores)
    casados = int(sum(ap_macro.values()))
    cobertura_ap = round((casados / total_apoiadores * 100) if total_apoiadores else 0, 1)

    # Índice histórico por ano relativo à média de Rio Branco.
    hist_indices = defaultdict(list)
    for ano, g in hist_macro.groupby("ANO_ELEICAO"):
        total_v = float(g["VOTOS"].sum())
        if total_v <= 0:
            continue
        for _, r in g.iterrows():
            ele_macro = float(macro_df.loc[macro_df["macro_id"].eq(r["MACRO_ID"]), "eleitores_2026"].iloc[0])
            taxa_macro = float(r["VOTOS"]) / ele_macro if ele_macro else np.nan
            taxa_cidade = total_v / total_eleitores if total_eleitores else np.nan
            idx = taxa_macro / taxa_cidade if taxa_cidade else np.nan
            if pd.notna(idx):
                hist_indices[r["MACRO_ID"]].append(float(idx))

    resultados = []
    for m in macros:
        mid = m["macro_id"]
        hist_idx = float(np.median(hist_indices[mid])) if hist_indices[mid] else None
        n_ap = int(ap_macro.get(mid, 0))

        # Organização atual: participação dos apoiadores casados comparada
        # à participação do macroterritório no eleitorado.
        org_idx = None
        if casados > 0 and m["eleitores_2026"] > 0:
            share_ap = n_ap / casados
            share_ele = m["eleitores_2026"] / total_eleitores
            org_idx = share_ap / share_ele if share_ele else None

        resultados.append({
            **m,
            "apoiadores_mapeados": n_ap if n_ap >= MIN_CELL else f"<{MIN_CELL}",
            "indice_historico": round(hist_idx, 2) if hist_idx is not None else None,
            "indice_organizacao": round(org_idx, 2) if org_idx is not None and n_ap >= MIN_CELL else None,
            "classificacao": classificar(hist_idx, org_idx, n_ap),
        })

    if cobertura_ap >= 80:
        confianca = "ALTA"
    elif cobertura_ap >= 60:
        confianca = "MÉDIA"
    else:
        confianca = "BAIXA"

    # Só expõe nomes de bairros não casados se houver pelo menos MIN_CELL pessoas.
    nao_casados_visiveis = [
        {"bairro_declarado": b.title(), "apoiadores": n}
        for b, n in nao_casados.most_common()
        if n >= MIN_CELL
    ]

    payload = {
        "meta": {
            "gerado_em": datetime.now(ACRE_TZ).isoformat(timespec="seconds"),
            "versao": "1.0",
            "metodo": "Macroterritórios geográficos determinísticos a partir das coordenadas dos locais de votação 2026; ZONA RURAL separada.",
            "privacidade": "Sem PII. Apenas contagens agregadas.",
        },
        "qualidade": {
            "apoiadores_rio_branco": total_apoiadores,
            "apoiadores_mapeados_com_seguranca": casados,
            "cobertura_apoiadores_pct": cobertura_ap,
            "confianca_cruzamento_residencial_eleitoral": confianca,
            "modos_casamento": dict(modos),
            "cobertura_historico": cobertura_hist,
            "alerta": (
                "O Forms informa bairro de residência; o TSE informa território do local de votação. "
                "Macroterritórios reduzem o erro de escala, mas não tornam os conceitos idênticos."
            ),
        },
        "resumo": dict(Counter(x["classificacao"] for x in resultados)),
        "macroterritorios": resultados,
        "bairros_residenciais_nao_mapeados_relevantes": nao_casados_visiveis,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "saida": str(OUTPUT_PATH),
        "macros": len(resultados),
        "apoiadores_rb": total_apoiadores,
        "apoiadores_mapeados": casados,
        "cobertura_pct": cobertura_ap,
        "confianca": confianca,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
