#!/usr/bin/env python3
"""
Central Samir 2026 — Runtime Snapshot v1

Gera, em uma única execução:
1) radar_runtime.json
   - métricas atuais do Radar_Politico;
   - últimas ocorrências públicas relevantes;
2) perfil_territorial_2026.json
   - perfil demográfico agregado por município;
   - leitura territorial de Rio Branco por zona eleitoral;
   - histórico de Samir comparado ao perfil atual de 2026.

IMPORTANTE
----------
- Não usa a base privada de apoiadores para perfil demográfico.
- Não exporta PII.
- Não chama escolaridade de renda.
- O TSE não fornece renda domiciliar nem vulnerabilidade socioeconômica.
  Esta versão usa escolaridade, idade e ruralidade como PERFIL ELEITORAL
  agregado. Renda/vulnerabilidade exigirão fonte geográfica externa (IBGE)
  numa etapa posterior.
"""
from __future__ import annotations

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

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
RADAR_WORKSHEET = os.getenv("RADAR_WORKSHEET", "Radar_Politico").strip()

PERFIL_PATH = Path(os.getenv("PERFIL_PATH", "perfil_eleitorado_2026_ac.csv"))
RESUMO_MUNICIPAL_PATH = Path(os.getenv("RESUMO_MUNICIPAL_PATH", "resumo_municipal_2026_ac.csv"))
ELEITORADO_PATH = Path(os.getenv("ELEITORADO_2026_PATH", "eleitorado_2026_ac.csv"))
HISTORICO_PATH = Path(os.getenv("HISTORICO_PATH", "dados.csv"))

RADAR_OUT = Path(os.getenv("RADAR_OUTPUT", "radar_runtime.json"))
PERFIL_OUT = Path(os.getenv("PERFIL_OUTPUT", "perfil_territorial_2026.json"))

ACRE_TZ = timezone(timedelta(hours=-5))
AGORA = datetime.now(ACRE_TZ)


def norm(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def truthy(v: Any) -> bool:
    return norm(v) in {"SIM", "TRUE", "VERDADEIRO", "1", "YES", "S"}


def service_account_from_env() -> dict[str, Any]:
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("Defina GCP_SERVICE_ACCOUNT_JSON.")
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


def google_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    return gspread.authorize(creds)


def parse_datetime(v: Any) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]
    for f in formats:
        try:
            dt = datetime.strptime(s, f)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ACRE_TZ)
            return dt.astimezone(ACRE_TZ)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ACRE_TZ)
        return dt.astimezone(ACRE_TZ)
    except Exception:
        return None


# ============================================================
# RADAR
# ============================================================

def gerar_radar():
    if not SHEET_ID:
        raise RuntimeError("Defina GOOGLE_SHEET_ID.")
    ws = google_client().open_by_key(SHEET_ID).worksheet(RADAR_WORKSHEET)
    rows = ws.get_all_records(default_blank="")

    itens = []
    for r in rows:
        dt = parse_datetime(r.get("COLETADO_EM")) or parse_datetime(r.get("PUBLICADO_EM"))
        if not dt:
            continue
        itens.append((dt, r))

    itens.sort(key=lambda x: x[0], reverse=True)
    limite_24h = AGORA - timedelta(hours=24)
    limite_7d = AGORA - timedelta(days=7)
    ult24 = [(dt, r) for dt, r in itens if dt >= limite_24h]
    ult7 = [(dt, r) for dt, r in itens if dt >= limite_7d]

    def nivel_importante(r):
        return norm(r.get("NIVEL_ATENCAO")) in {"IMPORTANTE", "CRITICO", "CRÍTICO", "ALTO"}

    metricas = {
        "ocorrencias_24h": len(ult24),
        "ocorrencias_7d": len(ult7),
        "alertas_24h": sum(1 for _, r in ult24 if nivel_importante(r)),
        "samir_direto_24h": sum(1 for _, r in ult24 if truthy(r.get("SAMIR_DIRETO"))),
        "pesquisas_24h": sum(1 for _, r in ult24 if truthy(r.get("PESQUISA_ELEITORAL"))),
        "total_base": len(itens),
    }

    # Últimos itens: somente conteúdo público já processado pelo Radar.
    recentes = []
    for dt, r in itens[:20]:
        recentes.append({
            "coletado_em": dt.isoformat(timespec="seconds"),
            "publicado_em": str(r.get("PUBLICADO_EM", "")).strip(),
            "fonte": str(r.get("FONTE", "")).strip(),
            "tipo_fonte": str(r.get("TIPO_FONTE", "")).strip(),
            "titulo": str(r.get("TITULO", "")).strip(),
            "url": str(r.get("URL", "")).strip(),
            "ator_principal": str(r.get("ATOR_PRINCIPAL", "")).strip(),
            "tema": str(r.get("TEMA", "")).strip(),
            "tom": str(r.get("TOM_COBERTURA", "")).strip(),
            "nivel": str(r.get("NIVEL_ATENCAO", "")).strip() or "ROTINA",
            "resumo": str(r.get("RESUMO", "")).strip(),
            "por_que_importa": str(r.get("POR_QUE_IMPORTA", "")).strip(),
            "samir_direto": truthy(r.get("SAMIR_DIRETO")),
            "pesquisa_eleitoral": truthy(r.get("PESQUISA_ELEITORAL")),
        })

    payload = {
        "meta": {
            "gerado_em": AGORA.isoformat(timespec="seconds"),
            "fonte": f"Google Sheets / {RADAR_WORKSHEET}",
            "janela_principal_horas": 24,
        },
        "metricas": metricas,
        "itens": recentes,
    }
    RADAR_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


# ============================================================
# PERFIL TERRITORIAL
# ============================================================

LOW_EDU = {
    "ANALFABETO",
    "LE E ESCREVE",
    "ENSINO FUNDAMENTAL INCOMPLETO",
}
MID_EDU = {
    "ENSINO FUNDAMENTAL COMPLETO",
    "ENSINO MEDIO INCOMPLETO",
    "ENSINO MEDIO COMPLETO",
}
HIGH_EDU = {
    "SUPERIOR INCOMPLETO",
    "SUPERIOR COMPLETO",
}


def idade_bucket(faixa: Any) -> str:
    s = norm(faixa)
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if "MENOR" in s:
        return "ATE_29"
    if not nums:
        return "NAO_INFORMADO"
    idade_ref = min(nums)
    if idade_ref <= 29:
        return "ATE_29"
    if idade_ref <= 59:
        return "30_59"
    return "60_MAIS"


def safe_pct(num, den):
    return round((float(num) / float(den) * 100), 1) if den else 0.0


def perfil_agregado(df: pd.DataFrame) -> dict:
    total = float(df["QT_ELEITORES"].sum())
    if total <= 0:
        return {
            "eleitores": 0,
            "escolaridade_baixa_pct": 0,
            "escolaridade_media_pct": 0,
            "superior_pct": 0,
            "ate_29_pct": 0,
            "30_59_pct": 0,
            "60_mais_pct": 0,
        }

    escolar = Counter()
    idade = Counter()

    for _, r in df.iterrows():
        q = float(r["QT_ELEITORES"])
        esc = norm(r.get("DS_GRAU_ESCOLARIDADE"))
        if esc in LOW_EDU:
            escolar["BAIXA"] += q
        elif esc in MID_EDU:
            escolar["MEDIA"] += q
        elif esc in HIGH_EDU:
            escolar["SUPERIOR"] += q
        else:
            escolar["OUTROS"] += q

        idade[idade_bucket(r.get("DS_FAIXA_ETARIA"))] += q

    return {
        "eleitores": int(total),
        "escolaridade_baixa_pct": safe_pct(escolar["BAIXA"], total),
        "escolaridade_media_pct": safe_pct(escolar["MEDIA"], total),
        "superior_pct": safe_pct(escolar["SUPERIOR"], total),
        "ate_29_pct": safe_pct(idade["ATE_29"], total),
        "30_59_pct": safe_pct(idade["30_59"], total),
        "60_mais_pct": safe_pct(idade["60_MAIS"], total),
    }


def gerar_perfil():
    for p in [PERFIL_PATH, RESUMO_MUNICIPAL_PATH, ELEITORADO_PATH, HISTORICO_PATH]:
        if not p.exists():
            raise FileNotFoundError(f"Arquivo ausente: {p}")

    perfil = pd.read_csv(PERFIL_PATH, dtype={"CD_MUNICIPIO": "string"})
    resumo = pd.read_csv(RESUMO_MUNICIPAL_PATH, dtype={"CD_MUNICIPIO": "string"})
    ele = pd.read_csv(ELEITORADO_PATH, dtype={"CD_MUNICIPIO": "string"})
    hist = pd.read_csv(HISTORICO_PATH, encoding="utf-8-sig")

    perfil["QT_ELEITORES"] = pd.to_numeric(perfil["QT_ELEITORES"], errors="coerce").fillna(0)
    resumo["ELEITORES_2026"] = pd.to_numeric(resumo["ELEITORES_2026"], errors="coerce").fillna(0)
    resumo["PARTICIPACAO_RURAL_PCT"] = pd.to_numeric(resumo["PARTICIPACAO_RURAL_PCT"], errors="coerce").fillna(0)
    ele["QT_ELEITOR_SECAO"] = pd.to_numeric(ele["QT_ELEITOR_SECAO"], errors="coerce").fillna(0)
    hist["QT_VOTOS_SAMIR"] = pd.to_numeric(hist["QT_VOTOS_SAMIR"], errors="coerce").fillna(0)

    perfil["MUN_KEY"] = perfil["NM_MUNICIPIO"].map(norm)
    resumo["MUN_KEY"] = resumo["NM_MUNICIPIO"].map(norm)
    ele["MUN_KEY"] = ele["NM_MUNICIPIO"].map(norm)
    hist["MUN_KEY"] = hist["NM_MUNICIPIO"].map(norm)

    # ---------- Municípios ----------
    mun_profiles = []
    h22 = hist[hist["ANO_ELEICAO"].eq(2022)].groupby("MUN_KEY", as_index=False).agg(
        VOTOS_2022=("QT_VOTOS_SAMIR", "sum")
    )

    base_m = resumo.merge(h22, on="MUN_KEY", how="left")
    base_m["VOTOS_2022"] = base_m["VOTOS_2022"].fillna(0)

    total_votos_estado = float(base_m["VOTOS_2022"].sum())
    total_ele_estado = float(base_m["ELEITORES_2026"].sum())
    taxa_estado = total_votos_estado / total_ele_estado if total_ele_estado else 0

    for _, r in base_m.iterrows():
        mk = r["MUN_KEY"]
        pf = perfil[perfil["MUN_KEY"].eq(mk)]
        p = perfil_agregado(pf)
        taxa = float(r["VOTOS_2022"]) / float(r["ELEITORES_2026"]) if r["ELEITORES_2026"] else 0
        idx = taxa / taxa_estado if taxa_estado else None
        mun_profiles.append({
            "municipio": str(r["NM_MUNICIPIO"]),
            "eleitores_2026": int(r["ELEITORES_2026"]),
            "participacao_rural_pct": round(float(r["PARTICIPACAO_RURAL_PCT"]), 1),
            "votos_samir_2022": int(r["VOTOS_2022"]),
            "indice_historico_2022": round(idx, 2) if idx is not None else None,
            **p,
        })

    # ---------- Rio Branco por zona ----------
    rb_key = "RIO BRANCO"
    perfil_rb = perfil[perfil["MUN_KEY"].eq(rb_key)].copy()
    ele_rb = ele[ele["MUN_KEY"].eq(rb_key)].copy()
    hist_rb = hist[hist["MUN_KEY"].eq(rb_key) & hist["ANO_ELEICAO"].isin([2020, 2022, 2024])].copy()

    zonas = []
    for zona in sorted(pd.to_numeric(perfil_rb["NR_ZONA"], errors="coerce").dropna().astype(int).unique()):
        pfz = perfil_rb[pd.to_numeric(perfil_rb["NR_ZONA"], errors="coerce").eq(zona)]
        p = perfil_agregado(pfz)

        ez = ele_rb[pd.to_numeric(ele_rb["NR_ZONA"], errors="coerce").eq(zona)]
        total_zone_ele = float(ez["QT_ELEITOR_SECAO"].sum())
        rural_zone_ele = float(
            ez[ez["NM_BAIRRO"].fillna("").map(norm).str.contains("ZONA RURAL", na=False)]["QT_ELEITOR_SECAO"].sum()
        )
        rural_pct = safe_pct(rural_zone_ele, total_zone_ele)

        indices = []
        anos = {}
        for ano in [2020, 2022, 2024]:
            ha = hist_rb[hist_rb["ANO_ELEICAO"].eq(ano)]
            vz = float(ha[pd.to_numeric(ha["NR_ZONA"], errors="coerce").eq(zona)]["QT_VOTOS_SAMIR"].sum())
            vt = float(ha["QT_VOTOS_SAMIR"].sum())
            et = float(ele_rb["QT_ELEITOR_SECAO"].sum())
            taxa_z = vz / total_zone_ele if total_zone_ele else 0
            taxa_rb = vt / et if et else 0
            idx = taxa_z / taxa_rb if taxa_rb else None
            if idx is not None:
                indices.append(idx)
            anos[str(ano)] = {
                "votos": int(vz),
                "indice_relativo": round(idx, 2) if idx is not None else None,
            }

        idx_hist = float(np.median(indices)) if indices else None
        zonas.append({
            "zona": int(zona),
            "eleitores_2026": int(total_zone_ele),
            "participacao_rural_pct": rural_pct,
            "indice_historico": round(idx_hist, 2) if idx_hist is not None else None,
            "historico_por_ano": anos,
            **p,
        })

    # Gera leituras descritivas — sem inferir renda ou intenção individual.
    leituras_rb = []
    if len(zonas) >= 2:
        z_sorted = sorted(zonas, key=lambda x: (x["indice_historico"] or 0), reverse=True)
        forte, fraca = z_sorted[0], z_sorted[-1]
        leituras_rb.append({
            "titulo": f"Zona {forte['zona']} apresenta maior força histórica relativa",
            "texto": (
                f"Índice histórico {forte['indice_historico']:.2f}. "
                f"No eleitorado atual, {forte['escolaridade_baixa_pct']:.1f}% estão nas faixas de escolaridade baixa "
                f"e {forte['superior_pct']:.1f}% possuem ensino superior incompleto ou completo."
            ),
            "tipo": "DESCRITIVO",
        })
        leituras_rb.append({
            "titulo": f"Zona {fraca['zona']} apresenta menor força histórica relativa",
            "texto": (
                f"Índice histórico {fraca['indice_historico']:.2f}. "
                f"A participação de eleitores em seções classificadas como rurais é {fraca['participacao_rural_pct']:.1f}%."
            ),
            "tipo": "DESCRITIVO",
        })

    payload = {
        "meta": {
            "gerado_em": AGORA.isoformat(timespec="seconds"),
            "fontes": [
                str(PERFIL_PATH),
                str(RESUMO_MUNICIPAL_PATH),
                str(ELEITORADO_PATH),
                str(HISTORICO_PATH),
            ],
            "escopo": "Perfil eleitoral agregado. Não contém renda domiciliar.",
            "limite": (
                "Escolaridade, idade e ruralidade descrevem o eleitorado agregado do território. "
                "Não devem ser convertidas em características de indivíduos nem tratadas como causalidade do voto."
            ),
        },
        "rio_branco": {
            "zonas": zonas,
            "leituras": leituras_rb,
        },
        "municipios": sorted(mun_profiles, key=lambda x: x["eleitores_2026"], reverse=True),
    }

    PERFIL_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main():
    radar = gerar_radar()
    perfil = gerar_perfil()
    print(json.dumps({
        "ok": True,
        "radar_output": str(RADAR_OUT),
        "perfil_output": str(PERFIL_OUT),
        "radar_total": radar["metricas"]["total_base"],
        "municipios_perfil": len(perfil["municipios"]),
        "zonas_rio_branco": len(perfil["rio_branco"]["zonas"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
