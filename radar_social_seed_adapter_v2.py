#!/usr/bin/env python3
"""
Radar Social SAMIR — adaptador de perfis locais v2.

Motivo:
Os runners hospedados do GitHub Actions estão recebendo HTTP 403 das rotas
públicas do TSE (CDN e DivulgaCand). Para que o monitoramento social não dependa
desse gargalo, os perfis prioritários ficam versionados em
social_perfis_seed_2026.json.

O TSE continua sendo referência de atualização cadastral, mas NÃO é dependência
de runtime do workflow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import radar_social_v1 as radar

SEED_PATH = Path("social_perfis_seed_2026.json")
FEDERACAO = "FEDERAÇÃO UNIÃO PROGRESSISTA (UNIÃO / PP)"


def candidate_registry_seed() -> list[list[Any]]:
    if not SEED_PATH.exists():
        raise RuntimeError(f"Cadastro local ausente: {SEED_PATH}")

    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    perfis = data.get("perfis") or []
    if not perfis:
        raise RuntimeError("Cadastro local de perfis está vazio.")

    stamp = radar.iso_now()
    rows: list[list[Any]] = []

    for p in perfis:
        nr = str(p.get("nr") or "").strip()
        nome = str(p.get("nome") or "").strip()
        partido = str(p.get("partido") or "").strip()
        username = str(p.get("instagram") or "").strip().lstrip("@")
        e_samir = bool(p.get("e_samir"))
        prioridade = str(p.get("prioridade") or "MONITORADO").strip()

        if not nome or not username:
            continue

        rows.append([
            stamp,
            f"SEED-{nr}",
            nr,
            nome,
            partido,
            FEDERACAO,
            f"MONITORAMENTO_{prioridade}",
            "INSTAGRAM",
            f"https://www.instagram.com/{username}/",
            username,
            e_samir,
            True,
            True,
        ])

    if not any(bool(r[10]) for r in rows):
        raise RuntimeError("Cadastro local não contém Samir.")
    if len(rows) < 5:
        raise RuntimeError("Cadastro local contém poucos perfis para o termômetro.")

    return rows


# Substitui somente a origem cadastral.
radar.candidate_registry = candidate_registry_seed

if __name__ == "__main__":
    radar.main()
