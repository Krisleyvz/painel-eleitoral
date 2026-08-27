#!/usr/bin/env python3
"""Adaptador TSE para o Radar Social SAMIR.

Usa o DivulgaCandContas como fonte principal de candidaturas e links sociais,
contornando bloqueios 403 do CDN bruto do TSE em runners do GitHub Actions.
"""
from __future__ import annotations

import os
import time
from typing import Any

import radar_social_v1 as radar

DIVULGACAND_BASE = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
ANO = 2026
UF = "AC"
CARGO_DEP_ESTADUAL = 7


def headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://divulgacandcontas.tse.jus.br",
        "Referer": "https://divulgacandcontas.tse.jus.br/divulga/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
    }


def election_id() -> str:
    data = radar.http_get(
        f"{DIVULGACAND_BASE}/eleicao/ordinarias",
        headers=headers(),
        timeout=35,
        retries=2,
    ).json()
    for item in data if isinstance(data, list) else []:
        if int(item.get("ano") or 0) == ANO and item.get("id"):
            return str(item["id"])
    raise RuntimeError(f"DivulgaCand: eleição {ANO} não localizada.")


def party(c: dict[str, Any]) -> str:
    p = c.get("partido")
    if isinstance(p, dict) and p.get("sigla"):
        return str(p["sigla"]).strip()
    for key in ("siglaPartido", "sg_PARTIDO", "sgPartido"):
        if c.get(key):
            return str(c[key]).strip()
    return ""


def candidate_id(c: dict[str, Any]) -> str:
    for key in ("id", "sqCandidato", "sq_CANDIDATO", "SQ_CANDIDATO"):
        if c.get(key):
            return str(c[key]).strip()
    return ""


def sites(c: dict[str, Any]) -> list[str]:
    value = c.get("sites")
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def detail(eid: str, cid: str) -> dict[str, Any]:
    if not cid:
        return {}
    url = f"{DIVULGACAND_BASE}/candidatura/buscar/{ANO}/{UF}/{eid}/candidato/{cid}"
    value = radar.http_get(url, headers=headers(), timeout=35, retries=1).json()
    return value if isinstance(value, dict) else {}


def candidate_registry() -> list[list[Any]]:
    eid = election_id()
    url = f"{DIVULGACAND_BASE}/candidatura/listar/{ANO}/{UF}/{eid}/{CARGO_DEP_ESTADUAL}/candidatos"
    payload = radar.http_get(url, headers=headers(), timeout=50, retries=2).json()

    if isinstance(payload, dict):
        raw_candidates = payload.get("candidatos") or []
    elif isinstance(payload, list):
        raw_candidates = payload
    else:
        raw_candidates = []

    if not raw_candidates:
        raise RuntimeError("DivulgaCand: nenhum deputado estadual do Acre retornado.")

    stamp = radar.iso_now()
    out: list[list[Any]] = []

    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue

        cid = candidate_id(raw)
        nome = str(
            raw.get("nomeUrna")
            or raw.get("nm_URNA")
            or raw.get("nomeCompleto")
            or ""
        ).strip()
        numero = str(
            raw.get("numero")
            or raw.get("nr_CANDIDATO")
            or raw.get("nrCandidato")
            or ""
        ).strip()
        sigla = party(raw)
        federacao = str(
            raw.get("nomeColigacao")
            or raw.get("composicaoColigacao")
            or ""
        ).strip()
        situacao = str(
            raw.get("descricaoSituacao")
            or raw.get("descricaoSituacaoCandidato")
            or ""
        ).strip()

        n_nome = radar.norm(nome)
        is_samir = ("SAMIR" in n_nome and "BESTENE" in n_nome) or numero == "11106"
        same_fed = (
            "UNIAO PROGRESSISTA" in radar.norm(federacao)
            or radar.norm(sigla) in {"PP", "UNIAO", "UNIAO BRASIL"}
        )

        urls = sites(raw)

        # A lista oficial é enxuta; aprofundamos somente Samir + União Progressista.
        if (is_samir or same_fed) and not urls and cid:
            try:
                d = detail(eid, cid)
                urls = sites(d)
                if not federacao:
                    federacao = str(
                        d.get("nomeColigacao")
                        or d.get("composicaoColigacao")
                        or ""
                    ).strip()
                if not situacao:
                    situacao = str(
                        d.get("descricaoSituacao")
                        or d.get("descricaoSituacaoCandidato")
                        or ""
                    ).strip()
                time.sleep(0.12)
            except Exception as exc:
                print(f"[social][tse] ficha {cid} indisponível: {exc}")

        urls = list(dict.fromkeys(u for u in urls if u))

        if not urls:
            out.append([
                stamp, cid, numero, nome, sigla, federacao, situacao,
                "", "", "", is_samir, same_fed, True,
            ])
        else:
            for social_url in urls:
                rede, username = radar.extract_social(social_url)
                out.append([
                    stamp, cid, numero, nome, sigla, federacao, situacao,
                    rede, social_url, username, is_samir, same_fed, True,
                ])

    if not out:
        raise RuntimeError("DivulgaCand: cadastro processado sem linhas válidas.")
    return out


# Substitui apenas a origem do cadastro; todo o restante continua no motor v1.
radar.candidate_registry = candidate_registry

_original_update_profiles = radar.update_profiles


def update_profiles_strict(ws):
    result = _original_update_profiles(ws)
    forced = os.getenv("SOCIAL_FORCE_ALL", "").strip().lower() in {
        "1", "true", "sim", "yes"
    }
    if forced and not result.get("ok"):
        raise RuntimeError(f"Validação TSE falhou: {result.get('error', '')}")
    return result


radar.update_profiles = update_profiles_strict

if __name__ == "__main__":
    radar.main()
