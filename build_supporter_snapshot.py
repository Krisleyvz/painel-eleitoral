#!/usr/bin/env python3
"""
Gera um snapshot AGREGADO da base de apoiadores para a Central Samir 2026.

PRIVACIDADE
-----------
- Lê a planilha privada com conta de serviço.
- NÃO grava nomes, telefones, endereços completos, data de nascimento ou outros
  identificadores pessoais no JSON de saída.
- O arquivo final contém apenas contagens por município/bairro e indicadores
  operacionais agregados.

Variáveis de ambiente:
  GCP_SERVICE_ACCOUNT_JSON  -> JSON completo OU bloco TOML [gcp_service_account]
  GOOGLE_SHEET_ID           -> ID da planilha
  SUPPORTER_WORKSHEET        -> opcional; padrão tenta nomes conhecidos

Uso:
  python scripts/build_supporter_snapshot.py
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE")
WORKSHEET_ENV = os.getenv("SUPPORTER_WORKSHEET", "").strip()
OUTPUT = Path(os.getenv("SUPPORTER_SNAPSHOT_OUTPUT", "data/apoiadores_agregado.json"))
ACRE_TZ = timezone(timedelta(hours=-5))
MIN_CELL = int(os.getenv("SUPPORTER_MIN_CELL", "10"))


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


def parse_data(v: Any) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    formatos = [
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"
    ]
    for f in formatos:
        try:
            return datetime.strptime(s, f).replace(tzinfo=ACRE_TZ)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(ACRE_TZ)
    except Exception:
        return None


def escolher_aba(book):
    candidatos = [x for x in [
        WORKSHEET_ENV,
        "Samir Bestene - Apoiadores (Respostas)",
        "Samir Bestene – Apoiadores (Respostas)",
        "Form_Responses",
        "Form Responses",
    ] if x]
    norm_map = {norm(ws.title): ws for ws in book.worksheets()}
    for c in candidatos:
        if norm(c) in norm_map:
            return norm_map[norm(c)]
    raise RuntimeError(f"Nenhuma aba de apoiadores encontrada. Abas: {[w.title for w in book.worksheets()]}")


def main():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    gc = gspread.authorize(creds)
    book = gc.open_by_key(SHEET_ID)
    ws = escolher_aba(book)
    registros = ws.get_all_records(default_blank="")

    if not registros:
        raise RuntimeError("A aba de apoiadores está vazia.")

    headers = list(registros[0].keys())
    col_nome = achar_coluna(headers, ["Nome Completo", "Nome"])
    col_bairro = achar_coluna(headers, ["Bairro"])
    col_mun = (
        achar_coluna(headers, ["Município", "Municipio", "Cidade"])
        or achar_coluna(headers, [], contem=["MUNICIP"])
        or achar_coluna(headers, [], contem=["CIDADE"])
    )
    col_data = achar_coluna(headers, ["Carimbo de data/hora", "Timestamp", "Data do cadastro"], contem=["DATA"])
    col_indicacao = achar_coluna(headers, ["Através de quem chegou até nós?", "Através de quem", "Atraves de quem"], contem=["ATRAVES", "QUEM"])
    col_participacao = achar_coluna(headers, [], contem=["PARTICIP"])

    if not col_mun:
        raise RuntimeError(
            "Não foi possível identificar a coluna de município/cidade na planilha. "
            "A execução foi interrompida para evitar classificar todos os cadastros como Rio Branco."
        )

    agora = datetime.now(ACRE_TZ)
    limite7 = agora - timedelta(days=7)
    limite30 = agora - timedelta(days=30)

    total = 0
    com_municipio = 0
    sem_municipio = 0
    novos7 = 0
    novos30 = 0
    reunioes = 0
    por_bairro = Counter()
    por_mun = Counter()
    novos7_bairro = Counter()

    for row in registros:
        # Considera registro válido se pelo menos nome ou bairro estiver preenchido.
        if col_nome and not str(row.get(col_nome, "")).strip() and col_bairro and not str(row.get(col_bairro, "")).strip():
            continue
        total += 1

        bairro = str(row.get(col_bairro, "") if col_bairro else "").strip().title() or "Sem bairro informado"
        mun_raw = str(row.get(col_mun, "")).strip()
        if mun_raw:
            com_municipio += 1
        else:
            sem_municipio += 1
        mun = mun_raw.upper() if mun_raw else "MUNICÍPIO NÃO INFORMADO"
        por_bairro[(mun, bairro)] += 1
        por_mun[mun] += 1

        dt = parse_data(row.get(col_data)) if col_data else None
        if dt:
            if dt >= limite7:
                novos7 += 1
                novos7_bairro[(mun, bairro)] += 1
            if dt >= limite30:
                novos30 += 1

        if col_participacao:
            p = norm(row.get(col_participacao, ""))
            if "REUNIAO" in p or "REUNIOES" in p:
                reunioes += 1

    bairros = []
    suprimidos_total = 0
    suprimidos_novos7 = 0
    for (mun, bairro), qtd in por_bairro.most_common():
        # Proteção contra reidentificação: bairros com poucos cadastros
        # não são expostos individualmente.
        if qtd < MIN_CELL:
            suprimidos_total += qtd
            suprimidos_novos7 += novos7_bairro[(mun, bairro)]
            continue
        bairros.append({
            "municipio": mun,
            "bairro": bairro,
            "total": qtd,
            "novos_7d": novos7_bairro[(mun, bairro)],
        })

    if suprimidos_total:
        bairros.append({
            "municipio": "AGREGADO",
            "bairro": f"Outros bairros (menos de {MIN_CELL} cadastros cada)",
            "total": suprimidos_total,
            "novos_7d": suprimidos_novos7,
        })

    leituras = []
    if bairros:
        top = bairros[0]
        leituras.append({
            "titulo": f"Maior concentração cadastrada: {top['bairro']}",
            "status": "OBSERVAR",
            "texto": f"{top['total']} apoiador(es) cadastrados nesse bairro. Isso mede organização da campanha, não intenção de voto."
        })
    if novos7:
        leituras.append({
            "titulo": "Crescimento recente da base",
            "status": "ACOMPANHAR",
            "texto": f"{novos7} novo(s) cadastro(s) nos últimos 7 dias. A tendência territorial deve ser comparada semana a semana."
        })
    else:
        leituras.append({
            "titulo": "Sem crescimento recente identificado",
            "status": "VERIFICAR",
            "texto": "Nenhum cadastro com data reconhecida nos últimos 7 dias; confirme se a coluna de data foi localizada corretamente."
        })

    out = {
        "meta": {
            "gerado_em": agora.isoformat(timespec="seconds"),
            "aba_origem": ws.title,
            "privacidade": f"Somente agregados; sem PII; territórios com menos de {MIN_CELL} cadastros são suprimidos.",
            "colunas_detectadas": {
                "bairro": col_bairro or "",
                "municipio": col_mun or "",
                "data": col_data or "",
                "participacao": col_participacao or ""
            }
        },
        "resumo": {
            "total": total,
            "com_municipio": com_municipio,
            "sem_municipio": sem_municipio,
            "territorializados_pct": round(100 * com_municipio / total, 1) if total else 0.0,
            "novos_7d": novos7,
            "novos_30d": novos30,
            "bairros": len(por_bairro),
            "municipios": len(por_mun),
            "reunioes": reunioes,
            "celula_minima_privacidade": MIN_CELL,
        },
        "leituras": leituras,
        "bairros": bairros,
        "municipios": [
            {"municipio": m, "total": q}
            for m, q in por_mun.most_common()
        ]
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "aba": ws.title,
        "total": total,
        "bairros": len(por_bairro),
        "saida": str(OUTPUT)
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
