#!/usr/bin/env python3
"""
Google Trends — Samir Bestene | coletor conservador via navegador

SEM API OFICIAL
---------------
- Abre a página pública Google Trends com Playwright.
- Usa o botão de download CSV disponibilizado na própria interface.
- Não tenta contornar CAPTCHA, bloqueio, autenticação ou proteção anti-bot.
- Faz somente duas consultas por execução:
    1) Brasil, últimos 90 dias;
    2) Acre, últimos 90 dias.
- Persiste o resultado mais recente em uma aba privada `Trends_Runtime`
  do Google Sheets.
- Também gera `trends_runtime.json` como Artifact para validação.

O índice do Google Trends é relativo (0–100) dentro do período/recorte;
não representa quantidade absoluta de pesquisas.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import statistics
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

TERM = os.getenv("TRENDS_TERM", "Samir Bestene").strip()
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
TRENDS_SHEET = os.getenv("TRENDS_WORKSHEET", "Trends_Runtime").strip()
OUTPUT = Path(os.getenv("TRENDS_OUTPUT", "trends_runtime.json"))
DIAG_DIR = Path(os.getenv("TRENDS_DIAG_DIR", "trends_diag"))
ACRE_TZ = timezone(timedelta(hours=-5))

SCOPES = [
    {"id": "BR", "label": "Brasil", "geo": "BR"},
    {"id": "BR-AC", "label": "Acre", "geo": "BR-AC"},
]

HEADERS = [
    "ATUALIZADO_EM", "ESCOPO_ID", "ESCOPO", "GEO", "TERMO", "PERIODO",
    "STATUS", "MENSAGEM", "INDICE_ATUAL", "MEDIA_7D", "MEDIA_30D",
    "VAR_7D_PCT", "VAR_30D_PCT", "PICO_30D", "DATA_PICO_30D",
    "PONTOS_JSON"
]


def norm(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().upper()


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
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    return gspread.authorize(creds)


def trends_url(geo: str, date_code: str = "today%203-m") -> str:
    return (
        "https://trends.google.com/trends/explore"
        f"?date={date_code}&geo={quote(geo)}&q={quote(TERM)}&hl=pt-BR"
    )


def maybe_accept_consent(page):
    patterns = [
        re.compile(r"Aceitar tudo", re.I),
        re.compile(r"Accept all", re.I),
        re.compile(r"Concordo", re.I),
        re.compile(r"I agree", re.I),
    ]
    for pat in patterns:
        try:
            btn = page.get_by_role("button", name=pat).first
            if btn.is_visible(timeout=1200):
                btn.click(timeout=2500)
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass



def maybe_use_classic_explore(page):
    patterns = [
        re.compile(r"Remain on Classic Explore", re.I),
        re.compile(r"Permanecer no Explore clássico", re.I),
        re.compile(r"Continuar no Explore clássico", re.I),
        re.compile(r"Explore clássico", re.I),
    ]
    for pat in patterns:
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=pat).first
                if loc.is_visible(timeout=1200):
                    loc.click(timeout=3500)
                    page.wait_for_timeout(2500)
                    return True
            except Exception:
                pass
    return False


def save_diagnostic(page, scope_id: str, label: str):
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{scope_id}_{label}")
    try:
        page.screenshot(path=str(DIAG_DIR / f"{safe}.png"), full_page=True)
    except Exception:
        pass
    try:
        body = page.locator("body").inner_text(timeout=2500)
        (DIAG_DIR / f"{safe}.txt").write_text(body[:30000], encoding="utf-8")
    except Exception:
        pass


def detect_block(page) -> str | None:
    try:
        body = norm(page.locator("body").inner_text(timeout=2500))
    except Exception:
        return None
    signals = [
        "UNUSUAL TRAFFIC",
        "TRAFEGO INCOMUM",
        "REC CAPTCHA",
        "RECAPTCHA",
        "OUR SYSTEMS HAVE DETECTED",
    ]
    return next((s for s in signals if s in body), None)


def find_interest_widget(page):
    title_pat = re.compile(r"Interesse ao longo do tempo|Interest over time", re.I)
    candidates = [
        "div.widget-template",
        "trends-widget",
        "div.widget",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).filter(has_text=title_pat).first
            if loc.count() and loc.is_visible(timeout=1800):
                return loc
        except Exception:
            pass

    try:
        title = page.get_by_text(title_pat).first
        if title.is_visible(timeout=1800):
            return title.locator("xpath=ancestor::*[contains(@class,'widget')][1]")
    except Exception:
        pass
    return None


def find_download_control(widget):
    # Não depende de um único seletor; inspeciona controles da área do gráfico.
    controls = widget.locator("button, a")
    try:
        count = min(controls.count(), 40)
    except Exception:
        count = 0

    keywords = ("download", "baixar", "transferir", "csv", "file_download")
    for i in range(count):
        c = controls.nth(i)
        try:
            if not c.is_visible(timeout=500):
                continue
            parts = [
                c.get_attribute("aria-label") or "",
                c.get_attribute("title") or "",
                c.get_attribute("data-tooltip") or "",
                c.inner_text(timeout=500) or "",
            ]
            hay = " ".join(parts).lower()
            if any(k in hay for k in keywords):
                return c
        except Exception:
            continue

    # Fallback para classes conhecidas da interface, sem contornar proteção.
    for sel in [
        ".widget-actions-item.export",
        "[data-action='download']",
        "[aria-label*='Download']",
        "[aria-label*='Baixar']",
        "[title*='Download']",
        "[title*='Baixar']",
    ]:
        try:
            c = widget.locator(sel).first
            if c.count() and c.is_visible(timeout=800):
                return c
        except Exception:
            pass
    return None



def parse_series_from_rendered_page(page) -> list[dict]:
    """
    Fallback seguro: lê a série já renderizada na própria página.
    Não chama endpoints internos e não contorna proteção.
    """
    try:
        text = page.locator("body").inner_text(timeout=4000)
    except Exception:
        return []

    m = re.search(
        r"Interesse ao longo do[\s\u00a0]+tempo.*?x[\s\t]+y1\s*(.*?)(?:Interesse(?:s)? por|Assuntos relacionados|Pesquisas relacionadas|$)",
        text,
        re.I | re.S,
    )
    if not m:
        return []

    points = []
    for raw in m.group(1).splitlines():
        line = raw.replace("\u202a", "").replace("\u202c", "").replace("\u00a0", " ").strip()
        mm = re.match(
            r"(.+?\b(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.\s+de\s+\d{4})\s+(\d+(?:[.,]\d+)?)$",
            line,
            re.I,
        )
        if mm:
            points.append({
                "data": mm.group(1).strip(),
                "indice": round(float(mm.group(2).replace(",", ".")), 2),
            })
    return points


def download_csv(page, geo: str, scope_id: str) -> tuple[bytes | None, str | None, str, list[dict]]:
    attempts = [
        ("90d", "today%203-m"),
        ("12m", "today%2012-m"),
    ]

    last_error = None
    for label, date_code in attempts:
        page.goto(trends_url(geo, date_code), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4500)
        maybe_accept_consent(page)
        maybe_use_classic_explore(page)
        page.wait_for_timeout(4500)

        # Após escolher Classic Explore, recarrega a URL completa para garantir
        # que termo, período e geografia foram realmente aplicados.
        if "explore" not in page.url.lower() or TERM.lower().replace(" ", "") not in page.url.lower().replace("%20", "").replace("+", "").replace(" ", ""):
            try:
                page.goto(trends_url(geo, date_code), wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
            except Exception:
                pass

        blocked = detect_block(page)
        if blocked:
            save_diagnostic(page, scope_id, f"{label}_bloqueado")
            return None, "AUTOMAÇÃO BLOQUEADA PELO GOOGLE; nenhuma tentativa de contorno foi feita.", label, []

        widget = find_interest_widget(page)
        if widget is None:
            rendered_points = parse_series_from_rendered_page(page)
            if rendered_points:
                return None, None, label, rendered_points
            save_diagnostic(page, scope_id, f"{label}_sem_grafico")
            last_error = (
                f"Gráfico de interesse não encontrado no recorte {label}; "
                "pode haver volume insuficiente ou mudança na interface."
            )
            continue

        control = find_download_control(widget)
        if control is None:
            save_diagnostic(page, scope_id, f"{label}_sem_download")
            last_error = f"Botão de exportação CSV não encontrado no recorte {label}."
            continue

        try:
            with page.expect_download(timeout=18000) as info:
                control.click(timeout=7000)
            download = info.value
            path = download.path()
            if not path:
                last_error = f"Download {label} não disponibilizou arquivo local."
                continue
            return Path(path).read_bytes(), None, label, []
        except PlaywrightTimeoutError:
            save_diagnostic(page, scope_id, f"{label}_timeout")
            last_error = f"O Trends não iniciou o download CSV no recorte {label}."
        except Exception as e:
            save_diagnostic(page, scope_id, f"{label}_erro")
            last_error = f"Falha ao exportar CSV em {label}: {type(e).__name__}"

    return None, last_error or "Coleta indisponível.", "12m", []

def parse_value(v: str) -> float | None:
    s = str(v or "").strip()
    if not s:
        return None
    if s.startswith("<"):
        # O Trends pode exibir <1. Para estatística de tendência,
        # usamos 0,5 como aproximação explícita.
        return 0.5
    s = s.replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_trends_csv(blob: bytes) -> list[dict]:
    text = blob.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []

    date_labels = {"DIA", "SEMANA", "MES", "MÊS", "HORA", "DAY", "WEEK", "MONTH", "HOUR"}
    header_i = None
    for i, row in enumerate(rows):
        if row and norm(row[0]) in date_labels and len(row) >= 2:
            header_i = i
            break
    if header_i is None:
        return []

    header = rows[header_i]
    partial_idx = next((i for i, h in enumerate(header) if "PARTIAL" in norm(h)), None)

    series_idx = None
    for i in range(1, len(header)):
        if i == partial_idx:
            continue
        if TERM.lower() in str(header[i]).lower():
            series_idx = i
            break
    if series_idx is None:
        series_idx = 1 if len(header) > 1 else None
    if series_idx is None:
        return []

    points = []
    for row in rows[header_i + 1:]:
        if len(row) <= series_idx:
            continue
        if partial_idx is not None and len(row) > partial_idx and norm(row[partial_idx]) in {"TRUE", "VERDADEIRO", "SIM"}:
            continue
        val = parse_value(row[series_idx])
        if val is None:
            continue
        points.append({"data": str(row[0]).strip(), "indice": round(val, 2)})
    return points


def avg(values: list[float]) -> float | None:
    return round(statistics.mean(values), 1) if values else None


def pct_change(current: list[float], previous: list[float]) -> float | None:
    if not current or not previous:
        return None
    a = statistics.mean(current)
    b = statistics.mean(previous)
    if b == 0:
        return None
    return round((a / b - 1) * 100, 1)


def summarize(points: list[dict], recorte: str) -> dict:
    vals = [float(x["indice"]) for x in points]
    if not vals:
        return {}

    if recorte == "12m":
        short_n, long_n = 4, 12
        short_label, long_label = "4 semanas", "12 semanas"
    else:
        short_n, long_n = 7, 30
        short_label, long_label = "7 dias", "30 dias"

    recent_for_peak = points[-long_n:]
    peak = max(recent_for_peak, key=lambda x: x["indice"]) if recent_for_peak else max(points, key=lambda x: x["indice"])

    short_now = vals[-short_n:]
    short_prev = vals[-2 * short_n:-short_n]
    long_now = vals[-long_n:]
    long_prev = vals[-2 * long_n:-long_n]

    return {
        "indice_atual": round(vals[-1], 1),
        "media_curta": avg(short_now),
        "media_longa": avg(long_now),
        "variacao_curta_pct": pct_change(short_now, short_prev),
        "variacao_longa_pct": pct_change(long_now, long_prev),
        "rotulo_curta": short_label,
        "rotulo_longa": long_label,
        "pico_recente": round(float(peak["indice"]), 1),
        "data_pico_recente": peak["data"],
    }


def collect_scope(browser, scope: dict) -> dict:
    page = browser.new_page(
        locale="pt-BR",
        timezone_id="America/Rio_Branco",
        viewport={"width": 1440, "height": 1100},
    )
    try:
        blob, error, recorte, rendered_points = download_csv(page, scope["geo"], scope["id"])
        if error:
            return {
                "escopo_id": scope["id"],
                "escopo": scope["label"],
                "geo": scope["geo"],
                "status": "INDISPONIVEL",
                "mensagem": error,
                "recorte_usado": recorte,
                "pontos": [],
            }

        points = rendered_points if rendered_points else parse_trends_csv(blob)
        if not points:
            return {
                "escopo_id": scope["id"],
                "escopo": scope["label"],
                "geo": scope["geo"],
                "status": "SEM_DADOS",
                "mensagem": "O CSV foi obtido, mas não continha série temporal utilizável. Isso pode ocorrer por volume insuficiente.",
                "recorte_usado": recorte,
                "pontos": [],
            }

        nonzero = sum(1 for p in points if float(p.get("indice", 0)) > 0)
        sparse = nonzero <= 2
        return {
            "escopo_id": scope["id"],
            "escopo": scope["label"],
            "geo": scope["geo"],
            "status": "OK_SPARSO" if sparse else "OK",
            "mensagem": (
                "Série obtida, mas com volume muito baixo; interpretar apenas como sinal relativo."
                if sparse else
                "Coleta concluída pela interface pública do Google Trends."
            ),
            "recorte_usado": recorte,
            **summarize(points, recorte),
            "pontos": points[-90:],
        }
    finally:
        page.close()


def write_sheet(scopes: list[dict], updated_at: str):
    gc = google_client()
    book = gc.open_by_key(SHEET_ID)
    try:
        ws = book.worksheet(TRENDS_SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=TRENDS_SHEET, rows=20, cols=len(HEADERS))

    rows = [HEADERS]
    for x in scopes:
        rows.append([
            updated_at,
            x.get("escopo_id", ""),
            x.get("escopo", ""),
            x.get("geo", ""),
            TERM,
            "últimos 90 dias",
            x.get("status", ""),
            x.get("mensagem", ""),
            x.get("indice_atual", ""),
            x.get("media_7d", ""),
            x.get("media_30d", ""),
            x.get("var_7d_pct", ""),
            x.get("var_30d_pct", ""),
            x.get("pico_30d", ""),
            x.get("data_pico_30d", ""),
            json.dumps(x.get("pontos", []), ensure_ascii=False, separators=(",", ":")),
        ])
    ws.clear()
    ws.update(range_name=f"A1:P{len(rows)}", values=rows, value_input_option="RAW")


def main():
    updated_at = datetime.now(ACRE_TZ).isoformat(timespec="seconds")
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for scope in SCOPES:
                results.append(collect_scope(browser, scope))
        finally:
            browser.close()

    payload = {
        "meta": {
            "gerado_em": updated_at,
            "termo": TERM,
            "periodo": "últimos 90 dias",
            "metodo": "Automação conservadora da exportação CSV da interface pública do Google Trends.",
            "fonte": "Google Trends",
            "nota": "Índice relativo de 0 a 100; não representa volume absoluto de buscas.",
        },
        "escopos": results,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persiste inclusive estados de indisponibilidade, para a Central nunca
    # fingir que uma coleta antiga acabou de acontecer.
    write_sheet(results, updated_at)

    print(json.dumps({
        "ok": True,
        "saida": str(OUTPUT),
        "resultados": {x["escopo_id"]: x["status"] for x in results},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
