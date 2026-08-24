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
from datetime import datetime, timezone
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
    ],
    "adversaries": [],
    "topics": [
        "saúde", "segurança", "emprego", "educação", "infraestrutura",
        "zona rural", "funcionalismo", "transporte", "custo de vida",
        "aliança", "apoio", "pesquisa eleitoral", "rejeição", "aprovação"
    ],
    "max_news_per_run": 80,
    "max_ai_items_per_run": 30,
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


def http_get(url: str, *, params: dict[str, Any] | None = None, timeout: int = 25) -> requests.Response:
    headers = {
        "User-Agent": "RadarPoliticoSamir/1.0 (+monitoramento-publico-eleitoral)",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    }
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


def parse_pubdate(texto: str) -> str:
    if not texto:
        return ""
    try:
        return parsedate_to_datetime(texto).astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return normalizar_texto(texto)


def coletar_google_news(cfg: dict[str, Any]) -> list[Item]:
    itens: list[Item] = []
    consultas = list(cfg.get("queries", []))
    # Busca local por domínio melhora recall de veículos do Acre sem depender de RSS próprio.
    for dominio in cfg.get("local_domains", []):
        consultas.append(f'"Samir Bestene" site:{dominio}')
        consultas.append(f'eleição Acre 2026 site:{dominio}')
        consultas.append(f'pesquisa eleitoral Acre site:{dominio}')

    vistos: set[str] = set()
    for consulta in consultas:
        try:
            url = GOOGLE_NEWS_RSS.format(q=quote_plus(consulta))
            xml = http_get(url).text
            root = ET.fromstring(xml)
            for node in root.findall(".//item"):
                titulo = normalizar_texto(node.findtext("title"))
                link = normalizar_texto(node.findtext("link"))
                fonte = normalizar_texto(node.findtext("source")) or "Google Notícias"
                descricao = normalizar_texto(node.findtext("description"))
                publicado = parse_pubdate(normalizar_texto(node.findtext("pubDate")))
                if not titulo or not link:
                    continue
                iid = make_id("GOOGLE_NEWS", link, titulo)
                if iid in vistos:
                    continue
                vistos.add(iid)
                itens.append(Item(
                    id=iid, coletado_em=agora_iso(), publicado_em=publicado,
                    fonte=fonte, tipo_fonte="GOOGLE_NEWS", titulo=titulo,
                    url=link, conteudo_bruto=f"Consulta: {consulta}. {descricao}"[:6000]
                ))
        except Exception as exc:
            print(f"[google-news] {consulta!r}: {exc}")
    return itens


def coletar_gdelt(cfg: dict[str, Any]) -> list[Item]:
    itens: list[Item] = []
    vistos: set[str] = set()
    # Mantém consultas GDELT mais compactas para evitar ruído excessivo.
    consultas = [
        '"Samir Bestene"',
        'Acre election 2026',
        'Acre pesquisa eleitoral',
    ]
    for nome in cfg.get("adversaries", [])[:10]:
        consultas.append(f'"{nome}" Acre')

    for consulta in consultas:
        try:
            params = {
                "query": consulta,
                "mode": "artlist",
                "maxrecords": 75,
                "format": "json",
                "sort": "datedesc",
                "timespan": "24h",
            }
            data = http_get(GDELT_DOC_API, params=params).json()
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
                    conteudo_bruto=f"Consulta GDELT: {consulta}. Idioma: {art.get('language','')}. País-fonte: {art.get('sourcecountry','')}."[:6000]
                ))
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
        raw_zip = http_get(TSE_PESQELE_ZIP, timeout=60).content
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
        service_account = json.loads(raw)
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
        # Não sobrescreve uma aba existente com estrutura inesperada.
        raise RuntimeError(
            f"A aba {RADAR_WORKSHEET} já existe, mas o cabeçalho não corresponde ao Radar v1."
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
- CRITICO exige relação direta com Samir ou fato eleitoral de alto impacto e sinais concretos de relevância; seja conservador.
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
        "generationConfig": {"responseMimeType": "application/json"},
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
        bool(a.get("samir_direto", "SAMIR" in item.titulo.upper())),
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
    coletados.extend(coletar_google_news(cfg))
    coletados.extend(coletar_gdelt(cfg))
    coletados.extend(coletar_tse_pesqele())
    coletados = deduplicar_local(coletados)
    max_news = int(cfg.get("max_news_per_run", 80))
    coletados = coletados[:max_news]

    novos = [i for i in coletados if i.id not in existentes]
    # Prioriza TSE e menções diretas a Samir para a cota de IA.
    novos.sort(key=lambda i: (i.tipo_fonte != "TSE_PESQELE", "SAMIR" not in i.titulo.upper(), i.publicado_em or ""))
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

    linhas = [linha_sheet(i, analises.get(i.id)) for i in novos]
    if linhas:
        ws.append_rows(linhas, value_input_option="RAW")

    criticos = sum(1 for i in novos if analises.get(i.id, {}).get("nivel_atencao") == "CRITICO")
    importantes = sum(1 for i in novos if analises.get(i.id, {}).get("nivel_atencao") == "IMPORTANTE")
    resultado = {
        "ok": True,
        "coletados": len(coletados),
        "novos": len(novos),
        "analisados_ia": len(analisar),
        "criticos": criticos,
        "importantes": importantes,
        "duracao_s": round(time.time() - inicio, 1),
        "modelo": DEFAULT_MODEL,
        "aba": RADAR_WORKSHEET,
    }
    print(json.dumps(resultado, ensure_ascii=False))
    return resultado


if __name__ == "__main__":
    executar_radar()
