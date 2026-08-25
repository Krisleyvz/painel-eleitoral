#!/usr/bin/env python3
"""Radar Político — coleta pública + triagem com Gemini + Google Sheets.

Projetado para rodar no GitHub Actions a cada 5 minutos e, opcionalmente,
ser chamado manualmente pelo painel Streamlit.

Privacidade: o módulo envia ao Gemini apenas conteúdo público coletado na web.
Ele não lê bases internas de apoiadores, logística, materiais ou estratégia.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Iterable
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import gspread
import requests
from google.oauth2.service_account import Credentials

ACRE_TZ_OFFSET = "-05:00"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE")
RADAR_WORKSHEET = os.getenv("RADAR_WORKSHEET", "Radar_Politico")
CONFIG_PATH = os.getenv("RADAR_CONFIG", "config_radar.json")

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
TSE_PESQELE_ZIP = "https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/pesquisa_eleitoral_2026.zip"
TSE_DATASET_URL = "https://dadosabertos.tse.jus.br/dataset/pesquisas-eleitorais-2026"
TSE_RESOURCE_ID = "769a663e-12c5-489e-a9c8-04633c2d57a3"
TSE_RESOURCE_API = "https://dadosabertos.tse.jus.br/api/3/action/resource_show?id={resource_id}"

RSS_LOCAIS_PADRAO = {
    "ac24horas": "https://ac24horas.com/feed/",
    "ContilNet Notícias": "https://contilnetnoticias.com.br/feed/",
    "A Gazeta do Acre": "https://agazetadoacre.com/feed/",
    "Notícias da Hora": "https://noticiasdahora.com.br/feed/",
    "Portal Acre": "https://portalacre.com.br/feed/",
    "Acre Agora": "https://acreagora.com/feed/",
    "O Alto Acre": "https://oaltoacre.com/feed/",
    "Diário do Acre": "https://diariodoacre.com.br/feed/",
    "Na Hora da Notícia": "https://nahoradanoticia.com.br/feed/",
    "PáginaNET": "https://paginanet.com.br/feed/",
    "O Palaciano": "https://opalaciano.com.br/feed/",
    "NauasNews": "https://www.nauasnews.com.br/feed/",
}

# Segunda rota de captura para portais WordPress. Se um RSS atrasar ou omitir
# uma matéria, a busca pública do próprio portal pode encontrá-la.
WP_PORTAIS_SAMIR = {
    "ContilNet Notícias": "https://contilnetnoticias.com.br",
    "Notícias da Hora": "https://noticiasdahora.com.br",
    "Portal Acre": "https://portalacre.com.br",
    "Acre Agora": "https://acreagora.com",
    "O Alto Acre": "https://oaltoacre.com",
    "Diário do Acre": "https://diariodoacre.com.br",
    "Na Hora da Notícia": "https://nahoradanoticia.com.br",
    "PáginaNET": "https://paginanet.com.br",
    "O Palaciano": "https://opalaciano.com.br",
}

HEADERS = [
    "ID", "COLETADO_EM", "PUBLICADO_EM", "FONTE", "TIPO_FONTE", "TITULO",
    "URL", "ATOR_PRINCIPAL", "TEMA", "TIPO_OCORRENCIA", "TOM_COBERTURA",
    "NIVEL_ATENCAO", "RESUMO", "POR_QUE_IMPORTA", "FATO_ALEGACAO",
    "PESQUISA_ELEITORAL", "SAMIR_DIRETO", "STATUS", "CONTEUDO_BRUTO"
]

DEFAULT_CONFIG = {
    "queries": [
        '"Samir Bestene"',
        '"Samir Bestene" Acre',
        '"Samir Bestene" eleição 2026',
        'eleição Acre 2026 deputado estadual',
        'pesquisa eleitoral Acre 2026',
        'PesqEle Acre 2026',
        'política Acre eleições 2026',
        'Assembleia Legislativa Acre eleições 2026',
    ],
    "local_domains": [
        "ac24horas.com",
        "contilnetnoticias.com.br",
        "agazetadoacre.com",
        "noticiasdahora.com.br",
        "acreagora.com",
        "portalacre.com.br",
        "oaltoacre.com",
        "diariodoacre.com.br",
        "nahoradanoticia.com.br",
        "paginanet.com.br",
        "opalaciano.com.br",
        "nauasnews.com.br",
    ],
    "adversaries": [],
    "topics": [
        "saúde", "segurança", "emprego", "educação", "infraestrutura",
        "zona rural", "funcionalismo", "transporte", "custo de vida",
        "aliança", "apoio", "pesquisa eleitoral", "rejeição", "aprovação"
    ],
    "max_news_per_run": 80,
    "max_ai_items_per_run": 30,
    "news_window_hours": 72,
    "google_news_when": "3d",
    "google_news_every_minutes": 30,
    "samir_watch_every_minutes": 10,
    "wp_samir_every_minutes": 15,
    "samir_watch_window_hours": 168,
    "wp_samir_portais": WP_PORTAIS_SAMIR,
    "gdelt_every_minutes": 60,
    "tse_every_minutes": 60,
    "rss_local_feeds": RSS_LOCAIS_PADRAO,
}


@dataclass
class Item:
    id: str
    coletado_em: str
    publicado_em: str
    fonte: str
    tipo_fonte: str
    titulo: str
    url: str
    conteudo_bruto: str


def agora_iso() -> str:
    # Registra em UTC; o painel converte para horário local quando necessário.
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalizar_texto(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def make_id(tipo: str, url: str, titulo: str) -> str:
    base = f"{tipo}|{url}|{titulo}".encode("utf-8", errors="ignore")
    return hashlib.sha256(base).hexdigest()[:24]


def carregar_config(path: str = CONFIG_PATH) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                cfg[k] = v
        except Exception as exc:
            print(f"[radar] config ignorada ({exc})")
    # Acrescenta adversários como consultas sem substituir as buscas-base.
    for nome in cfg.get("adversaries", []):
        consulta = f'"{nome}" Acre eleição 2026'
        if consulta not in cfg["queries"]:
            cfg["queries"].append(consulta)
    return cfg


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 25,
    retries: int = 2,
    extra_headers: dict[str, str] | None = None,
) -> requests.Response:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "application/rss+xml;q=0.9,application/json;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    if extra_headers:
        headers.update(extra_headers)

    ultimo_erro: Exception | None = None
    for tentativa in range(max(1, retries + 1)):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code in {429, 500, 502, 503, 504} and tentativa < retries:
                espera = 2 + tentativa * 3
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r
        except Exception as exc:
            ultimo_erro = exc
            if tentativa >= retries:
                raise
            time.sleep(2 + tentativa * 3)
    raise RuntimeError(f"Falha ao acessar {url}: {ultimo_erro}")


def parse_pubdate(texto: str) -> str:
    if not texto:
        return ""
    try:
        return parsedate_to_datetime(texto).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return normalizar_texto(texto)


def timestamp_publicacao(valor: str) -> float:
    """Converte datas ISO em timestamp; datas inválidas ficam no fim da fila."""
    if not valor:
        return 0.0
    try:
        normalizado = valor.replace("Z", "+00:00")
        return datetime.fromisoformat(normalizado).timestamp()
    except Exception:
        return 0.0


def dentro_da_janela(valor: str, horas: int) -> bool:
    """Mantém notícias recentes; datas não interpretáveis são preservadas."""
    if not valor:
        return True
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(hours=horas)
    except Exception:
        return True


def limpar_html(texto: str) -> str:
    texto = normalizar_texto(texto)
    texto = re.sub(r"<script.*?</script>", " ", texto, flags=re.I | re.S)
    texto = re.sub(r"<style.*?</style>", " ", texto, flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = (
        texto.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
    )
    return normalizar_texto(texto)


def rodada_due(intervalo_minutos: int) -> bool:
    """Executa fontes mais pesadas apenas em uma das rodadas do intervalo."""
    if os.getenv("RADAR_FORCE_ALL", "").strip().lower() in {"1", "true", "sim", "yes"}:
        return True
    if intervalo_minutos <= 5:
        return True
    minuto = datetime.now(timezone.utc).minute
    return (minuto % intervalo_minutos) < 5


def menciona_samir(texto: str) -> bool:
    """Detecção determinística de menção ao principal nome monitorado."""
    base = normalizar_texto(texto).lower()
    if not base:
        return False

    # Casos inequívocos
    if "samir bestene" in base or "samir figueiredo bestene" in base:
        return True

    # Alguns veículos usam apenas o primeiro nome no título/corpo.
    # Só aceitamos "Samir" isolado se houver contexto político acreano suficiente.
    if re.search(r"\bsamir\b", base):
        contexto = [
            "vereador", "candidato", "deputado estadual", "progressistas",
            "pp", "comitê", "comite", "campanha", "rio branco", "acre",
            "bestene"
        ]
        if any(t in base for t in contexto):
            return True
    return False


def item_politicamente_relevante(texto: str, cfg: dict[str, Any]) -> bool:
    base = normalizar_texto(texto).lower()
    if not base:
        return False
    if menciona_samir(base):
        return True

    termos_diretos = [
        "samir bestene", "samir",
        "eleição", "eleicoes", "eleições", "eleitoral",
        "candidato", "candidata", "candidatura", "campanha",
        "deputado", "deputada", "senador", "senadora",
        "governador", "governadora", "prefeito", "prefeita",
        "vereador", "vereadora", "aleac", "assembleia legislativa",
        "tse", "tre-ac", "tre acre", "pesquisa eleitoral",
        "partido", "federação", "federacao", "aliança", "alianca",
        "convenção", "convencao", "apoio político", "apoio politico",
        "mandato", "chapa", "pré-candidato", "pre-candidato",
    ]
    termos_diretos.extend(
        normalizar_texto(nome).lower()
        for nome in cfg.get("adversaries", [])
        if normalizar_texto(nome)
    )
    return any(t in base for t in termos_diretos)


def coletar_rss_locais(cfg: dict[str, Any]) -> list[Item]:
    """Camada primária: RSS direto de veículos locais, consultado a cada rodada."""
    itens: list[Item] = []
    vistos: set[str] = set()
    janela_horas = int(cfg.get("news_window_hours", 72))
    feeds = cfg.get("rss_local_feeds") or RSS_LOCAIS_PADRAO

    if isinstance(feeds, list):
        feeds = {url: url for url in feeds}

    for nome_fonte, url_feed in dict(feeds).items():
        try:
            xml = http_get(str(url_feed), timeout=20, retries=1).text
            root = ET.fromstring(xml)

            nodes = root.findall(".//item")
            # Fallback Atom
            if not nodes:
                nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for node in nodes[:40]:
                def achar(tag_rss: str, tag_atom: str | None = None) -> str:
                    valor = node.findtext(tag_rss)
                    if valor:
                        return valor
                    if tag_atom:
                        return node.findtext(f"{{http://www.w3.org/2005/Atom}}{tag_atom}") or ""
                    return ""

                titulo = normalizar_texto(achar("title", "title"))
                descricao = limpar_html(
                    achar("description", "summary")
                    or achar("{http://purl.org/rss/1.0/modules/content/}encoded")
                )
                publicado = parse_pubdate(
                    normalizar_texto(
                        achar("pubDate", "updated")
                        or achar("{http://purl.org/dc/elements/1.1/}date")
                    )
                )

                link = normalizar_texto(achar("link"))
                if not link:
                    atom_link = node.find("{http://www.w3.org/2005/Atom}link")
                    if atom_link is not None:
                        link = normalizar_texto(atom_link.attrib.get("href"))

                if not titulo or not link:
                    continue
                if not dentro_da_janela(publicado, janela_horas):
                    continue
                if not item_politicamente_relevante(f"{titulo} {descricao}", cfg):
                    continue

                iid = make_id("RSS_LOCAL", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid,
                    coletado_em=agora_iso(),
                    publicado_em=publicado,
                    fonte=normalizar_texto(nome_fonte),
                    tipo_fonte="RSS_LOCAL",
                    titulo=titulo,
                    url=link,
                    conteudo_bruto=descricao[:6000],
                ))
        except Exception as exc:
            print(f"[rss-local] {nome_fonte}: {exc}")
    return itens


def coletar_google_news(cfg: dict[str, Any]) -> list[Item]:
    """Fallback amplo. Não é a camada primária porque pode bloquear IPs de nuvem."""
    itens: list[Item] = []
    consultas_base = [
        '"Samir Bestene"',
        '"Samir Bestene" Acre',
        'eleição Acre 2026',
        'pesquisa eleitoral Acre 2026',
        'política Acre 2026',
    ]
    for nome in cfg.get("adversaries", [])[:5]:
        consultas_base.append(f'"{nome}" Acre')

    vistos: set[str] = set()
    janela_horas = int(cfg.get("news_window_hours", 72))
    operador_when = str(cfg.get("google_news_when", "3d")).strip()

    for consulta in consultas_base[:8]:
        try:
            consulta_efetiva = consulta
            if operador_when and "when:" not in consulta_efetiva.lower():
                consulta_efetiva = f"{consulta_efetiva} when:{operador_when}"
            url = GOOGLE_NEWS_RSS.format(q=quote_plus(consulta_efetiva))
            xml = http_get(url, timeout=20, retries=0).text
            root = ET.fromstring(xml)
            for node in root.findall(".//item"):
                titulo = normalizar_texto(node.findtext("title"))
                link = normalizar_texto(node.findtext("link"))
                fonte = normalizar_texto(node.findtext("source")) or "Google Notícias"
                descricao = limpar_html(node.findtext("description") or "")
                publicado = parse_pubdate(normalizar_texto(node.findtext("pubDate")))
                if not titulo or not link:
                    continue
                if not dentro_da_janela(publicado, janela_horas):
                    continue
                iid = make_id("GOOGLE_NEWS", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid, coletado_em=agora_iso(), publicado_em=publicado,
                    fonte=fonte, tipo_fonte="GOOGLE_NEWS", titulo=titulo,
                    url=link, conteudo_bruto=f"Consulta: {consulta_efetiva}. {descricao}"[:6000]
                ))
            time.sleep(0.7)
        except Exception as exc:
            print(f"[google-news] {consulta!r}: {exc}")
    return itens


def coletar_google_news_samir(cfg: dict[str, Any]) -> list[Item]:
    """
    Vigia redundante do nome Samir. Roda mais frequentemente que o Google News
    geral e usa janela de 7 dias para recuperar matérias que tenham surgido
    entre execuções ou atrasado na indexação.
    """
    itens: list[Item] = []
    vistos: set[str] = set()
    janela_horas = int(cfg.get("samir_watch_window_hours", 168))

    consultas = [
        '"Samir Bestene"',
        '"Samir Figueiredo Bestene"',
        '"Samir Bestene" Acre',
        '"Samir Bestene" campanha',
        '"Samir Bestene" comitê',
        '"Samir Bestene" deputado estadual',
        '"Samir" "deputado estadual" Acre',
    ]

    for consulta in consultas:
        try:
            consulta_efetiva = f"{consulta} when:7d"
            url = GOOGLE_NEWS_RSS.format(q=quote_plus(consulta_efetiva))
            xml = http_get(url, timeout=20, retries=1).text
            root = ET.fromstring(xml)

            for node in root.findall(".//item"):
                titulo = normalizar_texto(node.findtext("title"))
                link = normalizar_texto(node.findtext("link"))
                fonte = normalizar_texto(node.findtext("source")) or "Google Notícias"
                descricao = limpar_html(node.findtext("description") or "")
                publicado = parse_pubdate(normalizar_texto(node.findtext("pubDate")))

                if not titulo or not link:
                    continue
                if not dentro_da_janela(publicado, janela_horas):
                    continue
                if not menciona_samir(f"{titulo} {descricao}"):
                    continue

                iid = make_id("GOOGLE_NEWS_SAMIR", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid,
                    coletado_em=agora_iso(),
                    publicado_em=publicado,
                    fonte=fonte,
                    tipo_fonte="GOOGLE_NEWS_SAMIR",
                    titulo=titulo,
                    url=link,
                    conteudo_bruto=f"Vigia Samir. Consulta: {consulta_efetiva}. {descricao}"[:6000],
                ))
            time.sleep(0.4)
        except Exception as exc:
            print(f"[google-news-samir] {consulta!r}: {exc}")

    return itens


def coletar_wp_samir(cfg: dict[str, Any]) -> list[Item]:
    """
    Fallback público para WordPress: consulta o mecanismo REST do próprio portal.
    Não é obrigatório para o radar funcionar; qualquer portal que bloqueie o
    endpoint simplesmente é ignorado naquela rodada.
    """
    itens: list[Item] = []
    vistos: set[str] = set()
    portais = cfg.get("wp_samir_portais") or WP_PORTAIS_SAMIR
    janela_horas = int(cfg.get("samir_watch_window_hours", 168))
    after = (datetime.now(timezone.utc) - timedelta(hours=janela_horas)).isoformat(timespec="seconds").replace("+00:00", "Z")

    for nome_fonte, base_url in dict(portais).items():
        endpoint = str(base_url).rstrip("/") + "/wp-json/wp/v2/posts"
        try:
            params = {
                "search": "Samir Bestene",
                "after": after,
                "per_page": 20,
                "orderby": "date",
                "order": "desc",
                "_fields": "date_gmt,date,link,title,excerpt",
            }
            dados = http_get(
                endpoint,
                params=params,
                timeout=18,
                retries=0,
                extra_headers={"Accept": "application/json"},
            ).json()

            if not isinstance(dados, list):
                continue

            for post in dados:
                titulo_obj = post.get("title") or {}
                exc_obj = post.get("excerpt") or {}
                titulo = limpar_html(titulo_obj.get("rendered") if isinstance(titulo_obj, dict) else titulo_obj)
                descricao = limpar_html(exc_obj.get("rendered") if isinstance(exc_obj, dict) else exc_obj)
                link = normalizar_texto(post.get("link"))
                publicado_raw = normalizar_texto(post.get("date_gmt") or post.get("date"))
                publicado = publicado_raw
                if publicado and publicado.endswith("Z") is False and "+" not in publicado[-6:]:
                    publicado = publicado + "+00:00"

                if not titulo or not link:
                    continue
                if not menciona_samir(f"{titulo} {descricao}"):
                    continue
                if not dentro_da_janela(publicado, janela_horas):
                    continue

                iid = make_id("WP_SAMIR", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid,
                    coletado_em=agora_iso(),
                    publicado_em=publicado,
                    fonte=normalizar_texto(nome_fonte),
                    tipo_fonte="WP_SAMIR",
                    titulo=titulo,
                    url=link,
                    conteudo_bruto=f"Busca pública do portal. {descricao}"[:6000],
                ))
        except Exception as exc:
            print(f"[wp-samir] {nome_fonte}: {exc}")

    return itens


def coletar_gdelt(cfg: dict[str, Any]) -> list[Item]:
    """Rede secundária, consultada com baixa frequência para evitar 429."""
    itens: list[Item] = []
    vistos: set[str] = set()
    consultas = ['"Samir Bestene"', 'Acre election 2026']
    for nome in cfg.get("adversaries", [])[:3]:
        consultas.append(f'"{nome}" Acre')

    for consulta in consultas:
        try:
            params = {
                "query": consulta,
                "mode": "artlist",
                "maxrecords": 25,
                "format": "json",
                "sort": "datedesc",
                "timespan": "24h",
            }
            data = http_get(GDELT_DOC_API, params=params, timeout=25, retries=0).json()
            for art in data.get("articles", []) or []:
                titulo = normalizar_texto(art.get("title"))
                link = normalizar_texto(art.get("url"))
                fonte = normalizar_texto(art.get("domain")) or "GDELT"
                publicado = normalizar_texto(art.get("seendate"))
                if not titulo or not link:
                    continue
                iid = make_id("GDELT", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid, coletado_em=agora_iso(), publicado_em=publicado,
                    fonte=fonte, tipo_fonte="GDELT", titulo=titulo, url=link,
                    conteudo_bruto=(
                        f"Consulta GDELT: {consulta}. "
                        f"Idioma: {art.get('language','')}. "
                        f"País-fonte: {art.get('sourcecountry','')}."
                    )[:6000]
                ))
            time.sleep(2.0)
        except Exception as exc:
            print(f"[gdelt] {consulta!r}: {exc}")
    return itens


def escolher_coluna(colunas: Iterable[str], exatas: list[str], contem: list[str]) -> str | None:
    cols = list(colunas)
    mapa = {c.upper(): c for c in cols}
    for e in exatas:
        if e.upper() in mapa:
            return mapa[e.upper()]
    for c in cols:
        up = c.upper()
        if any(p.upper() in up for p in contem):
            return c
    return None


def decodificar_csv(raw: bytes) -> tuple[str, str]:
    for enc in ("latin-1", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", errors="replace"), "latin-1"


def coletar_tse_pesqele() -> list[Item]:
    """Baixa o ZIP oficial e registra pesquisas cuja UF/abrangência contenha AC.

    A estrutura do CSV pode mudar. Por isso a leitura usa detecção dinâmica de colunas.
    """
    itens: list[Item] = []
    try:
        url_recurso = TSE_PESQELE_ZIP
        try:
            meta = http_get(
                TSE_RESOURCE_API.format(resource_id=TSE_RESOURCE_ID),
                timeout=25,
                retries=1,
                extra_headers={"Referer": TSE_DATASET_URL},
            ).json()
            if meta.get("success") and isinstance(meta.get("result"), dict):
                url_recurso = normalizar_texto(meta["result"].get("url")) or url_recurso
        except Exception as exc:
            print(f"[tse-pesqele] metadados CKAN indisponíveis: {exc}")

        raw_zip = http_get(
            url_recurso,
            timeout=60,
            retries=1,
            extra_headers={
                "Referer": TSE_DATASET_URL,
                "Accept": "application/zip,application/octet-stream,*/*;q=0.8",
            },
        ).content
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
            # O arquivo principal costuma conter "pesquisa" e não "contrat"/"pagant".
            principais = [n for n in csvs if "contrat" not in n.lower() and "pagant" not in n.lower()]
            nomes = principais or csvs[:1]
            for nome in nomes[:1]:
                texto, _ = decodificar_csv(z.read(nome))
                # TSE historicamente usa ; em vários arquivos; autodetecta delimitador.
                amostra = texto[:10000]
                try:
                    dialect = csv.Sniffer().sniff(amostra, delimiters=";,|")
                    delim = dialect.delimiter
                except Exception:
                    delim = ";"
                reader = csv.DictReader(io.StringIO(texto), delimiter=delim)
                if not reader.fieldnames:
                    continue
                cols = reader.fieldnames
                uf_col = escolher_coluna(cols, ["SG_UF", "UF"], ["SG_UF", "UF"])
                nr_col = escolher_coluna(cols, ["NR_PESQUISA", "SQ_PESQUISA"], ["PESQUISA"])
                dt_col = escolher_coluna(cols, ["DT_REGISTRO", "DT_CADASTRO"], ["DT_REG", "DATA_REG", "CADASTRO"])
                inst_col = escolher_coluna(cols, [], ["INSTITUTO", "EMPRESA", "RAZAO_SOCIAL"])
                cargo_col = escolher_coluna(cols, ["DS_CARGO"], ["CARGO"])
                mun_col = escolher_coluna(cols, ["NM_MUNICIPIO"], ["MUNICIP"])
                for row in reader:
                    vals = {k: normalizar_texto(v) for k, v in row.items()}
                    universo = " | ".join(vals.values()).upper()
                    uf_val = vals.get(uf_col, "").upper() if uf_col else ""
                    # Aceita UF explícita AC; como contingência, procura ACRE no registro.
                    if uf_val and uf_val != "AC":
                        continue
                    if not uf_val and "ACRE" not in universo and "|AC|" not in universo.replace(" ", ""):
                        continue
                    numero = vals.get(nr_col, "") if nr_col else ""
                    instituto = vals.get(inst_col, "") if inst_col else ""
                    cargo = vals.get(cargo_col, "") if cargo_col else ""
                    municipio = vals.get(mun_col, "") if mun_col else ""
                    data_reg = vals.get(dt_col, "") if dt_col else ""
                    titulo = "Pesquisa eleitoral registrada no TSE"
                    partes = [p for p in [numero, instituto, cargo, municipio] if p]
                    if partes:
                        titulo += " — " + " | ".join(partes[:4])
                    # O número de registro, quando disponível, estabiliza a deduplicação.
                    url = TSE_DATASET_URL + (f"#pesquisa-{quote_plus(numero)}" if numero else "")
                    iid = make_id("TSE_PESQELE", numero or url, titulo)
                    conteudo = json.dumps(vals, ensure_ascii=False)[:12000]
                    itens.append(Item(
                        id=iid, coletado_em=agora_iso(), publicado_em=data_reg,
                        fonte="TSE / PesqEle", tipo_fonte="TSE_PESQELE",
                        titulo=titulo, url=url, conteudo_bruto=conteudo
                    ))
    except Exception as exc:
        print(f"[tse-pesqele] {exc}")
    return itens


def credenciais_sheets(service_account: dict[str, Any] | None = None) -> Credentials:
    if service_account is None:
        raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
        if not raw:
            raise RuntimeError("Defina GCP_SERVICE_ACCOUNT_JSON no ambiente/Secrets.")

        # O Secret pode conter:
        # 1) o JSON completo da conta de serviço; ou
        # 2) o bloco TOML [gcp_service_account] usado pelo Streamlit.
        try:
            service_account = json.loads(raw)
        except json.JSONDecodeError:
            try:
                import tomllib
                toml_data = tomllib.loads(raw)
                service_account = toml_data.get("gcp_service_account", toml_data)
            except Exception as erro_toml:
                raise RuntimeError(
                    "GCP_SERVICE_ACCOUNT_JSON não é um JSON nem um bloco TOML válido "
                    "de [gcp_service_account]."
                ) from erro_toml

        if not isinstance(service_account, dict):
            raise RuntimeError(
                "GCP_SERVICE_ACCOUNT_JSON precisa conter a conta de serviço completa, "
                "e não apenas número de projeto, ID ou outro valor isolado."
            )
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    return Credentials.from_service_account_info(service_account, scopes=scopes)


def abrir_aba_radar(service_account: dict[str, Any] | None = None, sheet_id: str | None = None):
    gc = gspread.authorize(credenciais_sheets(service_account))
    sh = gc.open_by_key(sheet_id or DEFAULT_SHEET_ID)
    try:
        ws = sh.worksheet(RADAR_WORKSHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=RADAR_WORKSHEET, rows=5000, cols=len(HEADERS) + 2)
    valores = ws.get_all_values()
    if not valores:
        ws.append_row(HEADERS, value_input_option="RAW")
    elif valores[0] != HEADERS:
        # Se a aba não possui registros de dados (apenas uma primeira linha
        # vazia, parcial ou um cabeçalho de teste), ela pode ser inicializada
        # com segurança. Se houver linhas de dados, preserva tudo e interrompe.
        if len(valores) <= 1:
            ws.clear()
            ws.append_row(HEADERS, value_input_option="RAW")
        else:
            cabecalho_atual = " | ".join(str(v) for v in valores[0][:8])
            raise RuntimeError(
                f"A aba {RADAR_WORKSHEET} possui dados e um cabeçalho incompatível. "
                f"Início do cabeçalho atual: {cabecalho_atual}"
            )
    return ws


def ids_existentes(ws) -> set[str]:
    try:
        col = ws.col_values(1)
        return set(col[1:]) if len(col) > 1 else set()
    except Exception:
        return set()


def extrair_json_resposta(texto: str) -> Any:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
    try:
        return json.loads(texto)
    except Exception:
        m = re.search(r"(\[.*\]|\{.*\})", texto, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def classificar_com_gemini(itens: list[Item], api_key: str | None = None, model: str = DEFAULT_MODEL) -> dict[str, dict[str, Any]]:
    if not itens:
        return {}
    api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[gemini] chave ausente; gravando itens sem análise de IA")
        return {}

    payload_itens = [
        {
            "id": i.id,
            "fonte": i.fonte,
            "tipo_fonte": i.tipo_fonte,
            "titulo": i.titulo,
            "publicado_em": i.publicado_em,
            "url": i.url,
            "conteudo_publico": i.conteudo_bruto[:5000],
        }
        for i in itens
    ]
    prompt = f"""
Você é o analista de triagem de um radar político estadual do Acre durante a eleição de 2026.
Analise SOMENTE o conteúdo público abaixo. Não invente fatos e não trate alegação como fato.
Samir Bestene é o principal nome monitorado.

Para cada item, devolva um objeto JSON com exatamente estes campos:
id, ator_principal, tema, tipo_ocorrencia, tom_cobertura, nivel_atencao,
resumo, por_que_importa, fato_alegacao, pesquisa_eleitoral, samir_direto.

Regras:
- nivel_atencao: CRITICO, IMPORTANTE, ACOMPANHAR ou INFORMATIVO.
- tom_cobertura: FAVORAVEL, NEUTRO_INFORMATIVO, CRITICO ou INDETERMINADO.
- fato_alegacao: FATO_REPORTADO, ALEGACAO, OPINIAO, RUMOR_NAO_CONFIRMADO ou INDETERMINADO.
- pesquisa_eleitoral e samir_direto: booleanos.
- samir_direto = true sempre que Samir Bestene for citado nominalmente no título
  OU no conteúdo do item, mesmo que ele não seja o ator principal da matéria.
- CRITICO é reservado a situação que possa exigir resposta da coordenação em poucas horas: crise reputacional relevante, ataque com propagação concreta, decisão judicial/eleitoral de alto impacto, pesquisa confiável com mudança material, fato grave diretamente ligado a Samir ou rearranjo político excepcional. Uma agenda, declaração, apoio comum, convenção rotineira ou matéria favorável NÃO é CRITICO; nesses casos use IMPORTANTE ou ACOMPANHAR.
- Pesquisa registrada no TSE é um registro oficial de existência, não valida resultado nem metodologia.
- Resumo em até 320 caracteres e por_que_importa em até 320 caracteres.
- Se o item for pouco relevante ao Acre/eleição, use INFORMATIVO.
- Responda SOMENTE com um array JSON válido, na mesma ordem dos itens.

ITENS:
{json.dumps(payload_itens, ensure_ascii=False)}
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=body, timeout=90)
    r.raise_for_status()
    data = r.json()
    texto = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = extrair_json_resposta(texto)
    if isinstance(parsed, dict):
        parsed = parsed.get("items", [parsed])
    saida = {}
    for obj in parsed or []:
        if isinstance(obj, dict) and obj.get("id"):
            saida[str(obj["id"])] = obj
    return saida


def linha_sheet(item: Item, analise: dict[str, Any] | None = None) -> list[Any]:
    a = analise or {}
    return [
        item.id,
        item.coletado_em,
        item.publicado_em,
        item.fonte,
        item.tipo_fonte,
        item.titulo,
        item.url,
        normalizar_texto(a.get("ator_principal")),
        normalizar_texto(a.get("tema")),
        normalizar_texto(a.get("tipo_ocorrencia")),
        normalizar_texto(a.get("tom_cobertura")) or "INDETERMINADO",
        normalizar_texto(a.get("nivel_atencao")) or "INFORMATIVO",
        normalizar_texto(a.get("resumo")) or item.titulo[:320],
        normalizar_texto(a.get("por_que_importa")),
        normalizar_texto(a.get("fato_alegacao")) or "INDETERMINADO",
        bool(a.get("pesquisa_eleitoral", item.tipo_fonte == "TSE_PESQELE")),
        bool(a.get("samir_direto")) or menciona_samir(f"{item.titulo} {item.conteudo_bruto}"),
        "NOVO",
        item.conteudo_bruto[:12000],
    ]


def deduplicar_local(itens: list[Item]) -> list[Item]:
    por_id: dict[str, Item] = {}
    por_url: set[str] = set()
    for i in itens:
        if i.id in por_id:
            continue
        # Google News e GDELT podem apontar para a mesma URL final; quando coincidir, mantém o primeiro.
        if i.url and i.url in por_url and i.tipo_fonte != "TSE_PESQELE":
            continue
        por_id[i.id] = i
        if i.url:
            por_url.add(i.url)
    return list(por_id.values())


def executar_radar(
    *,
    service_account: dict[str, Any] | None = None,
    sheet_id: str | None = None,
    gemini_api_key: str | None = None,
    config_path: str = CONFIG_PATH,
) -> dict[str, Any]:
    inicio = time.time()
    cfg = carregar_config(config_path)
    ws = abrir_aba_radar(service_account=service_account, sheet_id=sheet_id)
    existentes = ids_existentes(ws)

    coletados: list[Item] = []

    # 1) Camada rápida e principal: feeds diretos dos portais acreanos em toda rodada.
    coletados.extend(coletar_rss_locais(cfg))

    # 2) Vigia específico de Samir: redundância para que uma matéria direta
    # não dependa de um único RSS ou da classificação de IA.
    if rodada_due(int(cfg.get("samir_watch_every_minutes", 10))):
        coletados.extend(coletar_google_news_samir(cfg))

    if rodada_due(int(cfg.get("wp_samir_every_minutes", 15))):
        coletados.extend(coletar_wp_samir(cfg))

    # 3) Redes de descoberta mais amplas, porém mais sujeitas a bloqueio/rate limit.
    if rodada_due(int(cfg.get("google_news_every_minutes", 30))):
        coletados.extend(coletar_google_news(cfg))

    if rodada_due(int(cfg.get("gdelt_every_minutes", 60))):
        coletados.extend(coletar_gdelt(cfg))

    # 4) PesqEle: fonte oficial, atualização diária. Uma consulta por hora é suficiente.
    if rodada_due(int(cfg.get("tse_every_minutes", 60))):
        coletados.extend(coletar_tse_pesqele())

    coletados = deduplicar_local(coletados)

    novos = [i for i in coletados if i.id not in existentes]
    # Prioridade máxima: qualquer menção direta a Samir. Depois vêm TSE e
    # demais itens, sempre do mais recente para o mais antigo.
    novos.sort(
        key=lambda i: (
            not menciona_samir(f"{i.titulo} {i.conteudo_bruto}"),
            i.tipo_fonte != "TSE_PESQELE",
            -timestamp_publicacao(i.publicado_em),
        )
    )
    max_news = int(cfg.get("max_news_per_run", 80))
    novos = novos[:max_news]

    max_ai = int(cfg.get("max_ai_items_per_run", 30))
    analisar = novos[:max_ai]

    analises: dict[str, dict[str, Any]] = {}
    # Batches pequenos reduzem a chance de uma falha descartar toda a rodada.
    for pos in range(0, len(analisar), 12):
        lote = analisar[pos:pos + 12]
        try:
            analises.update(classificar_com_gemini(lote, api_key=gemini_api_key))
        except Exception as exc:
            print(f"[gemini] lote falhou: {exc}")

    # Menções diretas a Samir nunca podem desaparecer porque a IA falhou.
    # Se a classificação automática estiver indisponível, gravamos uma análise
    # mínima e conservadora. Os demais itens continuam podendo ser tentados depois.
    processados: list[Item] = []
    analises_finais: dict[str, dict[str, Any]] = dict(analises)

    for item in analisar:
        if item.id in analises_finais:
            processados.append(item)
            continue

        if menciona_samir(f"{item.titulo} {item.conteudo_bruto}"):
            analises_finais[item.id] = {
                "ator_principal": "Samir Bestene",
                "tema": "Menção direta",
                "tipo_ocorrencia": "MENCAO_DIRETA",
                "tom_cobertura": "INDETERMINADO",
                "nivel_atencao": "ACOMPANHAR",
                "resumo": item.titulo[:320],
                "por_que_importa": "Menção direta a Samir detectada. A análise automática detalhada ficou pendente, mas o registro foi preservado.",
                "fato_alegacao": "FATO_REPORTADO",
                "pesquisa_eleitoral": False,
                "samir_direto": True,
            }
            processados.append(item)

    linhas = [linha_sheet(i, analises_finais[i.id]) for i in processados]
    if linhas:
        ws.append_rows(linhas, value_input_option="RAW")

    criticos = sum(1 for i in processados if analises_finais.get(i.id, {}).get("nivel_atencao") == "CRITICO")
    importantes = sum(1 for i in processados if analises_finais.get(i.id, {}).get("nivel_atencao") == "IMPORTANTE")
    samir_diretos = sum(1 for i in processados if menciona_samir(f"{i.titulo} {i.conteudo_bruto}"))
    resultado = {
        "ok": True,
        "coletados": len(coletados),
        "novos": len(novos),
        "analisados_ia": len(analisar),
        "gravados": len(processados),
        "pendentes_ia": len(analisar) - len(processados),
        "criticos": criticos,
        "importantes": importantes,
        "samir_direto_detectados": samir_diretos,
        "portais_rss_configurados": len(cfg.get("rss_local_feeds") or RSS_LOCAIS_PADRAO),
        "duracao_s": round(time.time() - inicio, 1),
        "modelo": DEFAULT_MODEL,
        "aba": RADAR_WORKSHEET,
    }
    print(json.dumps(resultado, ensure_ascii=False))
    return resultado


if __name__ == "__main__":
    executar_radar()
