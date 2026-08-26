#!/usr/bin/env python3
"""
Social Runtime Snapshot v1
Gera social_runtime.json a partir das abas Social_* criadas por radar_social_v1.py.
Arquivo pronto para ser consumido pela Central SAMIR sem expor dados pessoais.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
OUTPUT = Path(os.getenv("SOCIAL_RUNTIME_OUTPUT", "social_runtime.json"))
ACRE_TZ = timezone(timedelta(hours=-5))
AGORA = datetime.now(ACRE_TZ)

WS_METRICAS = os.getenv("SOCIAL_METRICS_WORKSHEET", "Social_Metricas")
WS_EVENTOS = os.getenv("SOCIAL_EVENTS_WORKSHEET", "Social_Eventos")
WS_TERMOMETRO = os.getenv("SOCIAL_THERMOMETER_WORKSHEET", "Social_Termometro")
WS_STATUS = os.getenv("SOCIAL_STATUS_WORKSHEET", "Social_Status")


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


def client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    return gspread.authorize(creds)


def sheet_records(book, name):
    try:
        return book.worksheet(name).get_all_records(default_blank="")
    except Exception:
        return []


def parse_dt(v):
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ACRE_TZ)
        return dt.astimezone(ACRE_TZ)
    except Exception:
        return None


def main():
    if not SHEET_ID:
        raise RuntimeError("Defina GOOGLE_SHEET_ID.")
    book = client().open_by_key(SHEET_ID)

    metrics = sheet_records(book, WS_METRICAS)
    events = sheet_records(book, WS_EVENTOS)
    therm = sheet_records(book, WS_TERMOMETRO)
    status = sheet_records(book, WS_STATUS)

    cutoff_24h = AGORA - timedelta(hours=24)
    comments24 = [
        r for r in events
        if str(r.get("TIPO")) == "COMENTARIO_SAMIR"
        and (parse_dt(r.get("COLETADO_EM")) or datetime.min.replace(tzinfo=ACRE_TZ)) >= cutoff_24h
    ]
    mentions24 = [
        r for r in events
        if str(r.get("TIPO")) == "MENCAO_PUBLICA"
        and (parse_dt(r.get("COLETADO_EM")) or datetime.min.replace(tzinfo=ACRE_TZ)) >= cutoff_24h
    ]

    sentiments = Counter(str(r.get("SENTIMENTO") or "INDETERMINADO") for r in comments24)
    topics = Counter(str(r.get("TEMA") or "").strip() for r in comments24 if str(r.get("TEMA") or "").strip())

    # métricas mais recentes de Samir
    samir_metrics = []
    for r in metrics:
        if "SAMIR" in str(r.get("CANDIDATO", "")).upper():
            dt = parse_dt(r.get("COLETADO_EM"))
            if dt:
                samir_metrics.append((dt, r))
    samir_metrics.sort(key=lambda x: x[0], reverse=True)
    samir_latest = samir_metrics[0][1] if samir_metrics else {}

    ranking = []
    for r in therm[:30]:
        ranking.append({
            "posicao": r.get("POSICAO"),
            "candidato": r.get("CANDIDATO"),
            "username": r.get("USERNAME"),
            "partido": r.get("PARTIDO"),
            "termometro": r.get("TERMOMETRO_0_100"),
            "presenca": r.get("PRESENCA"),
            "engajamento": r.get("ENGAJAMENTO"),
            "discussao": r.get("DISCUSSAO"),
            "momento": r.get("MOMENTO"),
            "escala": r.get("ESCALA"),
        })

    recent_comments = []
    for r in sorted(comments24, key=lambda x: str(x.get("COLETADO_EM")), reverse=True)[:20]:
        recent_comments.append({
            "publicado_em": r.get("PUBLICADO_EM"),
            "permalink": r.get("PERMALINK"),
            "texto": r.get("TEXTO"),
            "sentimento": r.get("SENTIMENTO"),
            "tema": r.get("TEMA"),
            "nivel": r.get("NIVEL_ATENCAO"),
        })

    payload = {
        "meta": {
            "gerado_em": AGORA.isoformat(timespec="seconds"),
            "nota": "Termômetro digital comparativo; não é pesquisa eleitoral nem intenção de voto.",
            "privacidade": "Comentários sem nome, username ou ID do autor.",
        },
        "samir": {
            "instagram": {
                "followers": samir_latest.get("FOLLOWERS", 0),
                "posts_7d": samir_latest.get("POSTS_7D", 0),
                "posts_30d": samir_latest.get("POSTS_30D", 0),
                "engagement_rate_pct": samir_latest.get("ENGAGEMENT_RATE_PCT", 0),
                "discussion_rate_per_1k": samir_latest.get("DISCUSSION_RATE_PER_1K", 0),
                "momentum_pct": samir_latest.get("MOMENTUM_PCT", 0),
                "ultimo_post_em": samir_latest.get("ULTIMO_POST_EM", ""),
            },
            "voz_24h": {
                "comentarios": len(comments24),
                "sentimentos": dict(sentiments),
                "temas_principais": [
                    {"tema": k, "total": v} for k, v in topics.most_common(10)
                ],
                "comentarios_recentes": recent_comments,
            },
            "mencoes_threads_24h": len(mentions24),
        },
        "termometro": ranking,
        "status_coleta": status[-20:],
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(OUTPUT), "ranking": len(ranking)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
