#!/usr/bin/env python3
"""
Radar Social SAMIR v1
---------------------
Camada ADITIVA ao Radar Político existente.

Objetivos:
1) Atualizar automaticamente o cadastro de candidatos e redes sociais a partir do TSE 2026;
2) Coletar métricas do Instagram do próprio Samir por API oficial da Meta;
3) Coletar métricas públicas comparáveis de contas profissionais concorrentes via Business Discovery;
4) Coletar comentários nas publicações do próprio Samir, sem armazenar nome/ID do comentarista;
5) Classificar comentários anonimizados com Gemini em sentimento/tema;
6) Calcular um Termômetro Digital COMPARÁVEL entre candidatos, sem tratá-lo como pesquisa eleitoral;
7) Persistir tudo em abas NOVAS do Google Sheets, sem alterar Radar_Politico.

Privacidade:
- Não armazena nome, username ou ID do autor de comentário.
- O ID de comentário é transformado em hash local apenas para deduplicação.
- Não usa a base privada de apoiadores.
- Não tenta inferir atributos pessoais/sensíveis.

Variáveis de ambiente:
  GCP_SERVICE_ACCOUNT_JSON
  GOOGLE_SHEET_ID
  GEMINI_API_KEY                   opcional
  GEMINI_MODEL                     padrão gemini-3.7-flash
  META_GRAPH_VERSION               padrão v26.0
  META_IG_USER_ID                  ID da conta profissional do Instagram de Samir
  META_PAGE_ACCESS_TOKEN           token da Página/Meta com acesso ao Instagram
  SOCIAL_SAMIR_USERNAME            opcional; usado para identificar Samir no TSE/Instagram
  SOCIAL_FORCE_ALL                 1/true para forçar todas as camadas
  THREADS_ACCESS_TOKEN             opcional
  THREADS_API_HOST                 padrão https://graph.threads.net/v1.0
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import statistics
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import gspread
import requests
from google.oauth2.service_account import Credentials

ACRE_TZ = timezone(timedelta(hours=-5))
AGORA = datetime.now(ACRE_TZ)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip()
META_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0").strip()
META_IG_USER_ID = os.getenv("META_IG_USER_ID", "").strip()
META_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
SAMIR_USERNAME_ENV = os.getenv("SOCIAL_SAMIR_USERNAME", "").strip().lstrip("@")
THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
THREADS_HOST = os.getenv("THREADS_API_HOST", "https://graph.threads.net/v1.0").strip().rstrip("/")

TSE_CAND_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip"
TSE_SOCIAL_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_2026.zip"

WS_PERFIS = os.getenv("SOCIAL_PROFILES_WORKSHEET", "Social_Perfis")
WS_METRICAS = os.getenv("SOCIAL_METRICS_WORKSHEET", "Social_Metricas")
WS_EVENTOS = os.getenv("SOCIAL_EVENTS_WORKSHEET", "Social_Eventos")
WS_TERMOMETRO = os.getenv("SOCIAL_THERMOMETER_WORKSHEET", "Social_Termometro")
WS_STATUS = os.getenv("SOCIAL_STATUS_WORKSHEET", "Social_Status")

PROFILE_HEADERS = [
    "ATUALIZADO_EM", "SQ_CANDIDATO", "NR_CANDIDATO", "NOME_URNA",
    "PARTIDO", "FEDERACAO", "SITUACAO", "REDE", "URL", "USERNAME",
    "E_SAMIR", "MESMA_FEDERACAO", "ATIVO"
]

METRIC_HEADERS = [
    "COLETADO_EM", "CANDIDATO", "USERNAME", "PARTIDO", "FONTE",
    "FOLLOWERS", "MEDIA_COUNT", "POSTS_7D", "POSTS_30D",
    "AVG_LIKES_RECENTES", "AVG_COMMENTS_RECENTES",
    "ENGAGEMENT_RATE_PCT", "DISCUSSION_RATE_PER_1K",
    "MOMENTUM_PCT", "ULTIMO_POST_EM", "STATUS"
]

EVENT_HEADERS = [
    "ID", "COLETADO_EM", "PUBLICADO_EM", "FONTE", "TIPO",
    "CANDIDATO", "USERNAME", "MEDIA_ID", "PERMALINK",
    "TEXTO", "SENTIMENTO", "TEMA", "NIVEL_ATENCAO", "STATUS"
]

THERM_HEADERS = [
    "CALCULADO_EM", "POSICAO", "CANDIDATO", "USERNAME", "PARTIDO",
    "TERMOMETRO_0_100", "PRESENCA", "ENGAJAMENTO", "DISCUSSAO",
    "MOMENTO", "ESCALA", "OBSERVACAO"
]

STATUS_HEADERS = [
    "ATUALIZADO_EM", "COMPONENTE", "STATUS", "MENSAGEM"
]


def norm(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def iso_now() -> str:
    return datetime.now(ACRE_TZ).isoformat(timespec="seconds")


def parse_dt(v: Any) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ACRE_TZ)
    except Exception:
        return None


def truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def due(minutes: int) -> bool:
    if truthy_env("SOCIAL_FORCE_ALL"):
        return True
    if minutes <= 15:
        return True
    return (datetime.now(timezone.utc).minute % minutes) < 15


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
        raise RuntimeError("Credencial Google inválida.")
    pk = obj.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        obj["private_key"] = pk.replace("\\n", "\n")
    return obj


def google_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    return gspread.authorize(creds)


def ensure_ws(book, name: str, headers: list[str], rows: int = 3000):
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=rows, cols=max(20, len(headers)))
    current = ws.row_values(1)
    if current[:len(headers)] != headers:
        ws.update(range_name=f"A1:{chr(64+len(headers))}1", values=[headers], value_input_option="RAW")
    return ws


def http_get(url: str, *, params: dict[str, Any] | None = None,
             headers: dict[str, str] | None = None, timeout: int = 35,
             retries: int = 2) -> requests.Response:
    h = {
        "User-Agent": "RadarSocialSamir/1.0",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    }
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(2 + 3 * attempt)
                continue
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            if attempt >= retries:
                raise
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(str(last))


def get_csv_rows_from_tse_zip(url: str, uf: str = "AC") -> list[dict[str, str]]:
    blob = http_get(url, timeout=70, retries=2).content
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv")]
        # Prefere o arquivo específico da UF quando houver.
        preferred = [n for n in members if re.search(rf"[_-]{uf}\.csv$", n, re.I)]
        selected = preferred or members
        for name in selected:
            raw = z.read(name)
            text = raw.decode("latin-1", errors="replace")
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            for row in reader:
                sg = norm(row.get("SG_UF"))
                if sg and sg != uf:
                    continue
                rows.append({str(k): str(v or "") for k, v in row.items()})
    return rows


def first(row: dict[str, str], *names: str) -> str:
    m = {norm(k): v for k, v in row.items()}
    for name in names:
        if norm(name) in m:
            return str(m[norm(name)] or "").strip()
    return ""


def extract_social(url: str) -> tuple[str, str]:
    u = str(url or "").strip()
    if not u:
        return "", ""
    low = u.lower()
    network = "OUTRA"
    if "instagram.com" in low:
        network = "INSTAGRAM"
    elif "threads.net" in low:
        network = "THREADS"
    elif "facebook.com" in low or "fb.com" in low:
        network = "FACEBOOK"
    elif "youtube.com" in low or "youtu.be" in low:
        network = "YOUTUBE"
    elif "tiktok.com" in low:
        network = "TIKTOK"
    elif "x.com" in low or "twitter.com" in low:
        network = "X"

    username = ""
    try:
        p = urlparse(u if "://" in u else "https://" + u)
        parts = [x for x in p.path.split("/") if x]
        if parts:
            candidate = parts[0].lstrip("@")
            if network == "YOUTUBE" and candidate.startswith("@"):
                candidate = candidate[1:]
            if candidate not in {"p", "reel", "reels", "watch", "channel", "user"}:
                username = candidate
    except Exception:
        pass
    return network, username


def candidate_registry() -> list[list[Any]]:
    cand_rows = get_csv_rows_from_tse_zip(TSE_CAND_URL, "AC")
    social_rows = get_csv_rows_from_tse_zip(TSE_SOCIAL_URL, "AC")

    social_by_sq: dict[str, list[str]] = {}
    for r in social_rows:
        sq = first(r, "SQ_CANDIDATO")
        url = first(r, "DS_URL", "DS_REDE_SOCIAL")
        if sq and url:
            social_by_sq.setdefault(sq, []).append(url)

    candidates = []
    for r in cand_rows:
        cargo = norm(first(r, "DS_CARGO"))
        if "DEPUTADO ESTADUAL" not in cargo:
            continue
        sq = first(r, "SQ_CANDIDATO")
        nome = first(r, "NM_URNA_CANDIDATO", "NM_CANDIDATO")
        nr = first(r, "NR_CANDIDATO")
        party = first(r, "SG_PARTIDO")
        fed = first(r, "NM_FEDERACAO", "SG_FEDERACAO", "DS_COMPOSICAO_FEDERACAO")
        situacao = first(r, "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND")
        n_nome = norm(nome)
        is_samir = ("SAMIR" in n_nome and "BESTENE" in n_nome) or nr == "11106"
        same_fed = (
            "UNIAO PROGRESSISTA" in norm(fed)
            or norm(party) in {"PP", "UNIAO", "UNIAO BRASIL"}
        )
        candidates.append({
            "sq": sq, "nr": nr, "nome": nome, "party": party, "fed": fed,
            "situacao": situacao, "is_samir": is_samir, "same_fed": same_fed,
        })

    out: list[list[Any]] = []
    stamp = iso_now()
    for c in candidates:
        urls = social_by_sq.get(c["sq"], [])
        if not urls:
            out.append([
                stamp, c["sq"], c["nr"], c["nome"], c["party"], c["fed"],
                c["situacao"], "", "", "", c["is_samir"], c["same_fed"], True
            ])
            continue
        for url in urls:
            network, username = extract_social(url)
            out.append([
                stamp, c["sq"], c["nr"], c["nome"], c["party"], c["fed"],
                c["situacao"], network, url, username,
                c["is_samir"], c["same_fed"], True
            ])
    return out


def update_profiles(ws) -> dict[str, Any]:
    try:
        rows = candidate_registry()
        ws.clear()
        ws.update(range_name=f"A1:M{len(rows)+1}",
                  values=[PROFILE_HEADERS] + rows, value_input_option="RAW")
        return {"ok": True, "rows": len(rows)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


def profile_records(ws) -> list[dict[str, Any]]:
    return ws.get_all_records(default_blank="")


def samir_username_from_profiles(profiles: list[dict[str, Any]]) -> str:
    if SAMIR_USERNAME_ENV:
        return SAMIR_USERNAME_ENV
    for r in profiles:
        if norm(r.get("REDE")) == "INSTAGRAM" and str(r.get("E_SAMIR")).strip().lower() in {"true", "1", "sim"}:
            u = str(r.get("USERNAME", "")).strip().lstrip("@")
            if u:
                return u
    return ""


def instagram_username_candidates(profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen = set()
    out = []
    for r in profiles:
        if norm(r.get("REDE")) != "INSTAGRAM":
            continue
        username = str(r.get("USERNAME", "")).strip().lstrip("@")
        if not username:
            continue
        key = username.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "candidate": str(r.get("NOME_URNA", "")).strip(),
            "username": username,
            "party": str(r.get("PARTIDO", "")).strip(),
            "same_fed": str(r.get("MESMA_FEDERACAO", "")).strip().lower() in {"true", "1", "sim"},
            "is_samir": str(r.get("E_SAMIR", "")).strip().lower() in {"true", "1", "sim"},
        })
    return out


def meta_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not META_TOKEN:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN ausente.")
    url = f"https://graph.facebook.com/{META_VERSION}/{path.lstrip('/')}"
    p = dict(params or {})
    p["access_token"] = META_TOKEN
    return http_get(url, params=p, timeout=40, retries=1).json()


def own_instagram_snapshot(samir_username: str) -> tuple[list[Any] | None, list[dict[str, Any]]]:
    if not META_IG_USER_ID or not META_TOKEN:
        return None, []

    user = meta_get(META_IG_USER_ID, {
        "fields": "id,username,followers_count,media_count"
    })
    username = str(user.get("username") or samir_username or "").strip()
    followers = int(user.get("followers_count") or 0)
    media_count = int(user.get("media_count") or 0)

    media_resp = meta_get(f"{META_IG_USER_ID}/media", {
        "fields": "id,caption,media_type,permalink,timestamp,comments_count,like_count",
        "limit": 30,
    })
    media = media_resp.get("data", []) if isinstance(media_resp, dict) else []
    metric_row = build_metric_row(
        candidate="Samir Bestene",
        username=username,
        party="PP",
        source="INSTAGRAM_OWN",
        followers=followers,
        media_count=media_count,
        media=media,
        status="OK",
    )
    return metric_row, media


def business_discovery(username: str) -> dict[str, Any]:
    fields = (
        f"business_discovery.username({username})"
        "{username,followers_count,media_count,"
        "media.limit(20){id,caption,media_type,permalink,timestamp,comments_count,like_count}}"
    )
    data = meta_get(META_IG_USER_ID, {"fields": fields})
    return data.get("business_discovery", {}) if isinstance(data, dict) else {}


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def media_stats(media: list[dict[str, Any]], followers: int) -> dict[str, Any]:
    now = datetime.now(ACRE_TZ)
    valid = []
    for m in media:
        dt = parse_dt(m.get("timestamp"))
        if dt:
            valid.append((dt, m))
    valid.sort(key=lambda x: x[0], reverse=True)
    recent = [m for _, m in valid[:12]]
    posts_7d = sum(1 for dt, _ in valid if dt >= now - timedelta(days=7))
    posts_30d = sum(1 for dt, _ in valid if dt >= now - timedelta(days=30))
    likes = [float(m.get("like_count") or 0) for m in recent]
    comments = [float(m.get("comments_count") or 0) for m in recent]
    interactions = [l + c for l, c in zip(likes, comments)]
    avg_likes = mean(likes)
    avg_comments = mean(comments)
    er = ((mean(interactions) / followers) * 100) if followers else 0.0
    discussion = ((avg_comments / followers) * 1000) if followers else 0.0

    top3 = [float(m.get("like_count") or 0) + float(m.get("comments_count") or 0)
            for _, m in valid[:3]]
    prev3 = [float(m.get("like_count") or 0) + float(m.get("comments_count") or 0)
             for _, m in valid[3:6]]
    m_recent = mean(top3)
    m_prev = mean(prev3)
    momentum = ((m_recent / m_prev) - 1) * 100 if m_prev > 0 else (100.0 if m_recent > 0 else 0.0)

    last_dt = valid[0][0].isoformat(timespec="seconds") if valid else ""
    return {
        "posts_7d": posts_7d,
        "posts_30d": posts_30d,
        "avg_likes": round(avg_likes, 2),
        "avg_comments": round(avg_comments, 2),
        "engagement_rate": round(er, 4),
        "discussion_rate": round(discussion, 4),
        "momentum": round(max(-100.0, min(momentum, 500.0)), 2),
        "last_post": last_dt,
    }


def build_metric_row(*, candidate: str, username: str, party: str, source: str,
                     followers: int, media_count: int, media: list[dict[str, Any]],
                     status: str) -> list[Any]:
    s = media_stats(media, followers)
    return [
        iso_now(), candidate, username, party, source,
        followers, media_count, s["posts_7d"], s["posts_30d"],
        s["avg_likes"], s["avg_comments"], s["engagement_rate"],
        s["discussion_rate"], s["momentum"], s["last_post"], status
    ]


def collect_competitor_metrics(profiles: list[dict[str, Any]]) -> tuple[list[list[Any]], list[str]]:
    rows = []
    errors = []
    if not META_IG_USER_ID or not META_TOKEN:
        return rows, ["Meta não configurada."]
    candidates = instagram_username_candidates(profiles)
    samir_user = samir_username_from_profiles(profiles).lower()

    # Prioriza a mesma federação; depois demais candidatos registrados.
    candidates.sort(key=lambda x: (not x["same_fed"], x["candidate"]))
    for item in candidates:
        username = item["username"]
        if item["is_samir"] or username.lower() == samir_user:
            continue
        try:
            d = business_discovery(username)
            if not d:
                errors.append(f"{username}: conta não disponível em Business Discovery.")
                continue
            media = d.get("media", {}).get("data", []) if isinstance(d.get("media"), dict) else []
            rows.append(build_metric_row(
                candidate=item["candidate"],
                username=str(d.get("username") or username),
                party=item["party"],
                source="INSTAGRAM_BUSINESS_DISCOVERY",
                followers=int(d.get("followers_count") or 0),
                media_count=int(d.get("media_count") or 0),
                media=media,
                status="OK",
            ))
            time.sleep(0.25)
        except Exception as exc:
            errors.append(f"{username}: {str(exc)[:180]}")
    return rows, errors


def hash_public_id(prefix: str, raw_id: Any) -> str:
    h = hashlib.sha256(f"{prefix}|{raw_id}".encode("utf-8")).hexdigest()
    return h[:24]


def existing_event_ids(ws) -> set[str]:
    values = ws.col_values(1)
    return {x.strip() for x in values[1:] if x.strip()}


def collect_samir_comments(media: list[dict[str, Any]], ws_events) -> list[list[Any]]:
    existing = existing_event_ids(ws_events)
    out = []
    for m in media[:15]:
        mid = str(m.get("id") or "")
        if not mid:
            continue
        try:
            comments = meta_get(f"{mid}/comments", {
                "fields": "id,text,timestamp",
                "limit": 100,
            }).get("data", [])
        except Exception:
            continue
        for c in comments:
            cid = str(c.get("id") or "")
            if not cid:
                continue
            eid = hash_public_id("IG_COMMENT", cid)
            if eid in existing:
                continue
            text = re.sub(r"\s+", " ", str(c.get("text") or "")).strip()[:2500]
            if not text:
                continue
            out.append([
                eid, iso_now(), str(c.get("timestamp") or ""),
                "INSTAGRAM", "COMENTARIO_SAMIR", "Samir Bestene",
                "", mid, str(m.get("permalink") or ""),
                text, "", "", "", "NOVO"
            ])
            existing.add(eid)
    return out


def classify_new_comments(rows: list[list[Any]]) -> list[list[Any]]:
    if not rows or not GEMINI_KEY:
        return rows

    items = [{"id": r[0], "texto": r[9]} for r in rows[:120]]
    prompt = f"""
Classifique comentários PUBLICAMENTE VISÍVEIS em publicações de um candidato político.
Os autores foram removidos e não devem ser inferidos.
Não tente identificar idade, sexo, raça, religião, renda, orientação política individual
ou qualquer outro atributo pessoal.

Para cada item devolva JSON com:
id, sentimento, tema, nivel_atencao

sentimento: FAVORAVEL | NEUTRO | CRITICO | INDETERMINADO
nivel_atencao: CRITICO | IMPORTANTE | ACOMPANHAR | ROTINA

CRITICO somente para ameaça, possível crise reputacional com gravidade, acusação séria,
risco de segurança ou conteúdo que claramente exija avaliação humana rápida.
Tema: expressão curta em português.

ITENS:
{json.dumps(items, ensure_ascii=False)}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    resp = requests.post(
        url,
        headers={"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = parsed.get("items", [parsed])
    by_id = {str(x.get("id")): x for x in parsed if isinstance(x, dict) and x.get("id")}
    for r in rows:
        a = by_id.get(r[0])
        if not a:
            continue
        r[10] = str(a.get("sentimento") or "INDETERMINADO")
        r[11] = str(a.get("tema") or "")
        r[12] = str(a.get("nivel_atencao") or "ROTINA")
        r[13] = "ANALISADO"
    return rows


def latest_metrics(ws) -> list[dict[str, Any]]:
    rows = ws.get_all_records(default_blank="")
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        user = str(r.get("USERNAME", "")).strip().lower()
        if not user:
            continue
        dt = parse_dt(r.get("COLETADO_EM")) or datetime.min.replace(tzinfo=ACRE_TZ)
        prev = latest.get(user)
        prev_dt = parse_dt(prev.get("COLETADO_EM")) if prev else None
        if prev is None or prev_dt is None or dt > prev_dt:
            latest[user] = r
    return list(latest.values())


def minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return [50.0 for _ in values]
    return [100.0 * (v - lo) / (hi - lo) for v in values]


def calculate_thermometer(ws_metrics, ws_therm) -> list[list[Any]]:
    rows = latest_metrics(ws_metrics)
    clean = []
    for r in rows:
        try:
            clean.append({
                "candidate": str(r.get("CANDIDATO") or ""),
                "username": str(r.get("USERNAME") or ""),
                "party": str(r.get("PARTIDO") or ""),
                "followers": float(r.get("FOLLOWERS") or 0),
                "posts7": float(r.get("POSTS_7D") or 0),
                "er": float(r.get("ENGAGEMENT_RATE_PCT") or 0),
                "discussion": float(r.get("DISCUSSION_RATE_PER_1K") or 0),
                "momentum": float(r.get("MOMENTUM_PCT") or 0),
            })
        except Exception:
            pass
    if not clean:
        return []

    presence = minmax([x["posts7"] for x in clean])
    engagement = minmax([math.log1p(max(0, x["er"])) for x in clean])
    discussion = minmax([math.log1p(max(0, x["discussion"])) for x in clean])
    moment = minmax([max(-100, min(500, x["momentum"])) for x in clean])
    scale = minmax([math.log1p(max(0, x["followers"])) for x in clean])

    scored = []
    for i, x in enumerate(clean):
        score = (
            0.25 * presence[i]
            + 0.30 * engagement[i]
            + 0.20 * discussion[i]
            + 0.15 * moment[i]
            + 0.10 * scale[i]
        )
        scored.append({
            **x,
            "score": round(score, 1),
            "presence": round(presence[i], 1),
            "engagement": round(engagement[i], 1),
            "discussion_s": round(discussion[i], 1),
            "moment_s": round(moment[i], 1),
            "scale_s": round(scale[i], 1),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    out = []
    stamp = iso_now()
    for pos, x in enumerate(scored, start=1):
        out.append([
            stamp, pos, x["candidate"], x["username"], x["party"],
            x["score"], x["presence"], x["engagement"], x["discussion_s"],
            x["moment_s"], x["scale_s"],
            "Índice digital comparativo; não é pesquisa eleitoral nem intenção de voto."
        ])
    ws_therm.clear()
    ws_therm.update(range_name=f"A1:L{len(out)+1}",
                    values=[THERM_HEADERS] + out, value_input_option="RAW")
    return out


def collect_threads(profiles: list[dict[str, Any]], ws_events) -> tuple[int, list[str]]:
    if not THREADS_TOKEN:
        return 0, ["Threads não configurado."]
    existing = existing_event_ids(ws_events)
    terms = ["Samir Bestene"]
    # Acrescenta até 10 nomes da mesma federação para manter custo/rate limit previsível.
    for r in profiles:
        if str(r.get("MESMA_FEDERACAO", "")).strip().lower() not in {"true", "1", "sim"}:
            continue
        name = str(r.get("NOME_URNA", "")).strip()
        if name and "SAMIR" not in norm(name):
            terms.append(name)
        if len(terms) >= 11:
            break

    appended = []
    errors = []
    for term in terms:
        try:
            resp = http_get(
                f"{THREADS_HOST}/keyword_search",
                params={
                    "q": term,
                    "search_type": "RECENT",
                    "fields": "id,permalink,username,text,timestamp",
                    "limit": 30,
                    "access_token": THREADS_TOKEN,
                },
                timeout=35,
                retries=1,
            ).json()
            for item in resp.get("data", []):
                rid = str(item.get("id") or "")
                if not rid:
                    continue
                eid = hash_public_id("THREADS", rid)
                if eid in existing:
                    continue
                text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()[:2500]
                if not text:
                    continue
                appended.append([
                    eid, iso_now(), str(item.get("timestamp") or ""),
                    "THREADS", "MENCAO_PUBLICA", term, "",
                    "", str(item.get("permalink") or ""), text,
                    "", "", "", "NOVO"
                ])
                existing.add(eid)
        except Exception as exc:
            errors.append(f"{term}: {str(exc)[:160]}")
    if appended:
        classify_new_comments(appended)
        ws_events.append_rows(appended, value_input_option="RAW")
    return len(appended), errors


def write_status(ws, component: str, status: str, message: str):
    ws.append_row([iso_now(), component, status, message[:1000]], value_input_option="RAW")


def main():
    if not SHEET_ID:
        raise RuntimeError("Defina GOOGLE_SHEET_ID.")

    gc = google_client()
    book = gc.open_by_key(SHEET_ID)
    ws_profiles = ensure_ws(book, WS_PERFIS, PROFILE_HEADERS)
    ws_metrics = ensure_ws(book, WS_METRICAS, METRIC_HEADERS, rows=8000)
    ws_events = ensure_ws(book, WS_EVENTOS, EVENT_HEADERS, rows=12000)
    ws_therm = ensure_ws(book, WS_TERMOMETRO, THERM_HEADERS)
    ws_status = ensure_ws(book, WS_STATUS, STATUS_HEADERS)

    summary = {
        "profiles": None,
        "own_instagram": "SKIP",
        "competitors": 0,
        "comments": 0,
        "threads": 0,
        "thermometer": 0,
    }

    # TSE: 1x/hora; o conjunto oficial informa atualização 4x ao dia.
    if due(60):
        r = update_profiles(ws_profiles)
        summary["profiles"] = r
        write_status(
            ws_status, "TSE_REDES",
            "OK" if r.get("ok") else "ERRO",
            f"Perfis atualizados: {r.get('rows', 0)}" if r.get("ok") else r.get("error", "")
        )

    profiles = profile_records(ws_profiles)
    samir_username = samir_username_from_profiles(profiles)

    # Instagram do próprio Samir a cada execução.
    own_metric = None
    own_media = []
    if META_IG_USER_ID and META_TOKEN:
        try:
            own_metric, own_media = own_instagram_snapshot(samir_username)
            if own_metric:
                ws_metrics.append_row(own_metric, value_input_option="RAW")
                summary["own_instagram"] = "OK"
            new_comments = collect_samir_comments(own_media, ws_events)
            if new_comments:
                classify_new_comments(new_comments)
                ws_events.append_rows(new_comments, value_input_option="RAW")
            summary["comments"] = len(new_comments)
            write_status(ws_status, "INSTAGRAM_SAMIR", "OK",
                         f"Métrica própria coletada; {len(new_comments)} comentário(s) novo(s).")
        except Exception as exc:
            summary["own_instagram"] = "ERRO"
            write_status(ws_status, "INSTAGRAM_SAMIR", "ERRO", str(exc))
    else:
        write_status(ws_status, "INSTAGRAM_SAMIR", "AGUARDANDO_CONFIG",
                     "Defina META_IG_USER_ID e META_PAGE_ACCESS_TOKEN.")

    # Concorrentes: 1x/hora para reduzir chamadas.
    if due(60) and profiles and META_IG_USER_ID and META_TOKEN:
        rows, errors = collect_competitor_metrics(profiles)
        if rows:
            ws_metrics.append_rows(rows, value_input_option="RAW")
        summary["competitors"] = len(rows)
        write_status(ws_status, "INSTAGRAM_CONCORRENTES",
                     "OK" if rows else "PARCIAL",
                     f"{len(rows)} conta(s) profissional(is) coletada(s); {len(errors)} indisponível(is).")

    # Threads: 1x/hora e somente se houver token.
    if due(60) and profiles:
        n, errors = collect_threads(profiles, ws_events)
        summary["threads"] = n
        if THREADS_TOKEN:
            write_status(ws_status, "THREADS", "OK" if not errors else "PARCIAL",
                         f"{n} menção(ões) nova(s); {len(errors)} erro(s).")

    therm = calculate_thermometer(ws_metrics, ws_therm)
    summary["thermometer"] = len(therm)

    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
