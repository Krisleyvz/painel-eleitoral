import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import numpy as np
import urllib.parse
import urllib.request
import urllib.error
import json
import re
import unicodedata
import hashlib
import html
import time
import folium
from folium.plugins import MarkerCluster, Fullscreen, LocateControl
from streamlit_folium import st_folium
import pytz
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="App de Rua | Gestão", page_icon="📱", layout="centered")

# ==========================================
# SISTEMA DE LOGIN E SEGURANÇA
# ==========================================
def registrar_log(usuario):
    """Registra o acesso silenciosamente na mesma aba do Google Sheets."""
    fuso_acre = pytz.timezone('America/Rio_Branco')
    agora = datetime.now(fuso_acre)
    data_formatada = agora.strftime("%d/%m/%Y")
    hora_formatada = agora.strftime("%H:%M:%S")
    
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credenciais = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=scopes
        )
        cliente = gspread.authorize(credenciais)
        
        # ID da sua planilha principal (a mesma do outro painel)
        planilha_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
        
        # Abre a aba de logs
        aba_logs = cliente.open_by_key(planilha_id).worksheet("Logs_Acesso")
        
        # Insere a nova linha indicando que o login foi no App de Rua
        aba_logs.append_row([f"{usuario} (App de Rua)", data_formatada, hora_formatada])
        
    except Exception as e:
        print(f"❌ Falha ao registrar log no Sheets: {e}")

def verificar_senha():
    """Retorna True se o usuário inserir as credenciais corretas."""
    def senha_inserida():
        usuario = st.session_state["usuario_input"].strip()
        senha = st.session_state["senha_input"].strip()
        
        if usuario in st.secrets["senhas"] and senha == st.secrets["senhas"][usuario]:
            st.session_state["autenticado"] = True
            st.session_state["usuario_logado"] = usuario
            del st.session_state["senha_input"] 
            registrar_log(usuario)
        else:
            st.session_state["autenticado"] = False

    if "autenticado" not in st.session_state:
        st.markdown("<br><br><h2 style='text-align: center; color: #FFFFFF;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Usuário", key="usuario_input")
            st.text_input("Senha", type="password", key="senha_input")
            st.button("Entrar no Sistema", on_click=senha_inserida, use_container_width=True)
        return False
    
    elif not st.session_state["autenticado"]:
        st.markdown("<br><br><h2 style='text-align: center; color: #FFFFFF;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Usuário", key="usuario_input")
            st.text_input("Senha", type="password", key="senha_input")
            st.button("Entrar no Sistema", on_click=senha_inserida, use_container_width=True)
            st.error("😕 Usuário ou senha incorretos. Tente novamente.")
        return False
    
    return True

if not verificar_senha():
    st.stop()

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E CARTÕES LIMPOS
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0A1C2E !important; }
    h1, h2, h3, p, label, div.stMarkdown, .stMetricValue { color: #FFFFFF !important; }
    .contato-card {
        background-color: #152b45;
        padding: 12px 15px;
        border-radius: 8px;
        border-left: 4px solid #1A73E8;
        margin-bottom: 12px;
    }
    .card-aniversario-hoje {
        border-left: 5px solid #25D366 !important; 
        background-color: #1a3a30;
    }
    .apoiador-lider {
        background-color: #0e2439;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        border-left: 3px solid #25D366;
    }
    input, select {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
    [data-testid="stExpander"] {
        background-color: #152b45 !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] p {
        font-weight: bold !important;
        font-size: 16px !important;
    }
    .btn-disabled {
        display: block; text-align: center; background-color: #334e68; color: #8899a6; 
        padding: 6px; border-radius: 4px; font-size: 14px; font-weight: bold; cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função para tratar telefones
def tratar_telefone(tel_raw):
    tel_str = str(tel_raw).strip()
    if tel_str.lower() == 'nan' or tel_str == '':
        return "", "Sem telefone"
    tel_limpo = tel_str.split('.')[0]
    tel_num = ''.join(filter(str.isdigit, tel_limpo))
    if len(tel_num) < 8: 
        return "", tel_str
    return tel_num, tel_limpo

# Carregar os dados
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("📱 Gestão de Contatos")

st.markdown("---")

try:
    df = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha. Detalhe: {e}")
    df = pd.DataFrame()

total_cadastros = len(df) if not df.empty else 0

# Identifica a coluna do Município dinamicamente para usar no app todo
col_mun = None
if not df.empty:
    for col in df.columns:
        if "Município" in str(col) or "Municipio" in str(col):
            col_mun = col
            break

# Função para formatar o cartão padrão limpo
def card_html(nome, tel_exibicao, cidade, bairro, extra=""):
    cidade_str = cidade if cidade and cidade.lower() != 'nan' else 'Rio Branco'
    return f"""
    <div class="contato-card">
        <b>👤 {nome}</b> {extra}<br>
        📞 {tel_exibicao} &nbsp;|&nbsp; 📍 {cidade_str} - {bairro}
    </div>
    """

# ==========================================
# MAPA GRATUITO: OPENSTREETMAP + CACHE NO SHEETS
# ==========================================
PLANILHA_ID_MAPA = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
ABA_CACHE_MAPA = "Mapa_Coordenadas"
CABECALHO_CACHE_MAPA = [
    'CHAVE_ENDERECO', 'ENDERECO_CONSULTADO', 'LATITUDE', 'LONGITUDE',
    'FONTE', 'PRECISAO', 'ENDERECO_RETORNADO', 'DATA_CONSULTA'
]
LIMITE_GEOCODIFICACAO_POR_CLIQUE = 10


def normalizar_texto_mapa(valor):
    texto = unicodedata.normalize('NFKD', str(valor))
    texto = texto.encode('ascii', errors='ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


def localizar_coluna_mapa(dataframe, opcoes):
    mapa_colunas = {
        normalizar_texto_mapa(coluna): coluna for coluna in dataframe.columns
    }
    for opcao in opcoes:
        normalizada = normalizar_texto_mapa(opcao)
        if normalizada in mapa_colunas:
            return mapa_colunas[normalizada]
    for nome_normalizado, nome_original in mapa_colunas.items():
        if any(
            normalizar_texto_mapa(opcao) in nome_normalizado
            for opcao in opcoes
        ):
            return nome_original
    return None


def texto_linha_mapa(row, coluna, padrao=""):
    if not coluna:
        return padrao
    valor = row.get(coluna, padrao)
    if pd.isna(valor):
        return padrao
    texto = str(valor).strip()
    return padrao if texto.lower() in ('', 'nan', 'none') else texto


def categoria_mapa(classificacao):
    texto = normalizar_texto_mapa(classificacao)
    if 'lider' in texto:
        return 'Liderança'
    if 'parceria' in texto or 'estrategic' in texto:
        return 'Parceria'
    if 'manutencao' in texto:
        return 'Manutenção'
    return 'Padrão'


def coordenada_numerica(valor):
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None


def coordenada_valida_acre(latitude, longitude):
    return (
        latitude is not None and longitude is not None and
        -12.0 <= latitude <= -6.5 and -74.5 <= longitude <= -66.0
    )


def coordenadas_da_linha(row, col_lat, col_lon, col_coordenadas):
    latitude = coordenada_numerica(row.get(col_lat)) if col_lat else None
    longitude = coordenada_numerica(row.get(col_lon)) if col_lon else None

    if not coordenada_valida_acre(latitude, longitude) and col_coordenadas:
        valor = texto_linha_mapa(row, col_coordenadas)
        numeros = re.findall(r'-?\d{1,3}(?:[\.,]\d+)', valor)
        if len(numeros) >= 2:
            latitude = coordenada_numerica(numeros[0])
            longitude = coordenada_numerica(numeros[1])

    if coordenada_valida_acre(latitude, longitude):
        return latitude, longitude
    return None, None


def montar_endereco_mapa(
    row, col_endereco, col_rua, col_bairro, col_cep, coluna_municipio
):
    municipio = texto_linha_mapa(row, coluna_municipio, 'Rio Branco')
    bairro = texto_linha_mapa(row, col_bairro)
    cep = re.sub(r'\D', '', texto_linha_mapa(row, col_cep))
    endereco_completo = texto_linha_mapa(row, col_endereco)

    if endereco_completo:
        partes = [endereco_completo]
        texto_normalizado = normalizar_texto_mapa(endereco_completo)
        if normalizar_texto_mapa(municipio) not in texto_normalizado:
            partes.append(municipio)
        if cep and cep not in re.sub(r'\D', '', endereco_completo):
            partes.append(cep)
        partes.extend(['Acre', 'Brasil'])
    else:
        rua = texto_linha_mapa(row, col_rua)
        partes = [rua, bairro, municipio, 'Acre', cep, 'Brasil']

    endereco = ', '.join(parte for parte in partes if parte).strip(' ,')
    return endereco, cep


def preparar_pontos_mapa(dataframe, coluna_municipio):
    if dataframe.empty:
        return []

    col_endereco = localizar_coluna_mapa(
        dataframe, ['Endereço Completo', 'Endereco Completo']
    )
    col_rua = localizar_coluna_mapa(
        dataframe, ['Rua e Número', 'Rua e Numero', 'Logradouro']
    )
    col_bairro = localizar_coluna_mapa(dataframe, ['Bairro'])
    col_cep = localizar_coluna_mapa(dataframe, ['CEP'])
    col_classificacao = localizar_coluna_mapa(
        dataframe, ['Classificação Interna', 'Classificacao Interna']
    )
    col_lat = localizar_coluna_mapa(dataframe, ['Latitude', 'Lat'])
    col_lon = localizar_coluna_mapa(
        dataframe, ['Longitude', 'Lng', 'Lon']
    )
    col_coordenadas = localizar_coluna_mapa(
        dataframe, ['Coordenadas', 'Localização', 'Localizacao', 'LatLong']
    )

    prioridades = {'Padrão': 1, 'Manutenção': 2, 'Parceria': 3, 'Liderança': 4}
    pontos = {}

    for _, row in dataframe.iterrows():
        endereco, cep = montar_endereco_mapa(
            row, col_endereco, col_rua, col_bairro, col_cep,
            coluna_municipio
        )
        if not endereco:
            continue

        endereco_normalizado = normalizar_texto_mapa(endereco)
        chave = hashlib.sha256(
            endereco_normalizado.encode('utf-8')
        ).hexdigest()[:24]
        classificacao = texto_linha_mapa(row, col_classificacao)
        categoria = categoria_mapa(classificacao)
        telefone_numero, telefone_exibicao = tratar_telefone(
            row.get('Telefone', '')
        )
        latitude, longitude = coordenadas_da_linha(
            row, col_lat, col_lon, col_coordenadas
        )
        apoiador = {
            'nome': texto_linha_mapa(row, 'Nome Completo', 'Sem nome'),
            'telefone': telefone_exibicao,
            'telefone_numero': telefone_numero,
            'classificacao': classificacao or categoria,
        }

        if chave not in pontos:
            pontos[chave] = {
                'chave': chave,
                'endereco': endereco,
                'cep': cep,
                'bairro': texto_linha_mapa(row, col_bairro),
                'municipio': texto_linha_mapa(
                    row, coluna_municipio, 'Rio Branco'
                ),
                'categoria': categoria,
                'latitude': latitude,
                'longitude': longitude,
                'fonte': 'Coordenada informada' if latitude is not None else '',
                'precisao': 'ALTA' if latitude is not None else '',
                'apoiadores': [apoiador],
            }
        else:
            ponto = pontos[chave]
            ponto['apoiadores'].append(apoiador)
            if prioridades[categoria] > prioridades[ponto['categoria']]:
                ponto['categoria'] = categoria
            if ponto['latitude'] is None and latitude is not None:
                ponto['latitude'] = latitude
                ponto['longitude'] = longitude
                ponto['fonte'] = 'Coordenada informada'
                ponto['precisao'] = 'ALTA'

    return list(pontos.values())


def autorizar_google_sheets_mapa():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credenciais = Credentials.from_service_account_info(
        st.secrets['gcp_service_account'], scopes=scopes
    )
    return gspread.authorize(credenciais)


@st.cache_data(ttl=60, show_spinner=False)
def carregar_cache_mapa():
    try:
        cliente = autorizar_google_sheets_mapa()
        aba = cliente.open_by_key(PLANILHA_ID_MAPA).worksheet(ABA_CACHE_MAPA)
        registros = aba.get_all_records()
        if not registros:
            return pd.DataFrame(columns=CABECALHO_CACHE_MAPA)
        cache = pd.DataFrame(registros)
        for coluna in CABECALHO_CACHE_MAPA:
            if coluna not in cache.columns:
                cache[coluna] = ''
        return cache[CABECALHO_CACHE_MAPA]
    except Exception:
        return pd.DataFrame(columns=CABECALHO_CACHE_MAPA)


def salvar_cache_mapa(registros):
    if not registros:
        return 0, None
    try:
        cliente = autorizar_google_sheets_mapa()
        planilha = cliente.open_by_key(PLANILHA_ID_MAPA)
        try:
            aba = planilha.worksheet(ABA_CACHE_MAPA)
        except Exception:
            aba = planilha.add_worksheet(
                title=ABA_CACHE_MAPA, rows=3000,
                cols=len(CABECALHO_CACHE_MAPA)
            )

        primeira_linha = aba.row_values(1)
        if not primeira_linha:
            aba.append_row(CABECALHO_CACHE_MAPA, value_input_option='RAW')

        chaves_existentes = set(aba.col_values(1)[1:])
        linhas = []
        for registro in registros:
            if registro['CHAVE_ENDERECO'] in chaves_existentes:
                continue
            linhas.append([
                registro.get(coluna, '') for coluna in CABECALHO_CACHE_MAPA
            ])
            chaves_existentes.add(registro['CHAVE_ENDERECO'])

        if linhas:
            aba.append_rows(linhas, value_input_option='RAW')
        carregar_cache_mapa.clear()
        return len(linhas), None
    except Exception as erro:
        return 0, str(erro)


def consultar_json_mapa(url, headers=None, timeout=12):
    requisicao = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode('utf-8'))


def geocodificar_nominatim(endereco):
    parametros = urllib.parse.urlencode({
        'q': endereco,
        'format': 'jsonv2',
        'addressdetails': 1,
        'limit': 1,
        'countrycodes': 'br',
        'viewbox': '-74.0,-7.0,-66.5,-11.2',
        'bounded': 1,
        'accept-language': 'pt-BR',
    })
    url = 'https://nominatim.openstreetmap.org/search?' + parametros
    headers = {
        'User-Agent': (
            'AppDeRuaGestao/1.0 '
            '(https://github.com/Krisleyvz/painel-eleitoral)'
        ),
        'Referer': 'https://github.com/Krisleyvz/painel-eleitoral',
        'Accept': 'application/json',
    }
    try:
        resultados = consultar_json_mapa(url, headers=headers)
        if not resultados:
            return None
        resultado = resultados[0]
        latitude = coordenada_numerica(resultado.get('lat'))
        longitude = coordenada_numerica(resultado.get('lon'))
        if not coordenada_valida_acre(latitude, longitude):
            return None

        tipo = normalizar_texto_mapa(
            resultado.get('addresstype') or resultado.get('type') or ''
        )
        if tipo in {'house', 'building', 'amenity', 'shop', 'office'}:
            precisao = 'ALTA'
        elif tipo in {'road', 'residential', 'street', 'postcode'}:
            precisao = 'MÉDIA'
        else:
            precisao = 'BAIXA'
        return {
            'latitude': latitude,
            'longitude': longitude,
            'fonte': 'OpenStreetMap/Nominatim',
            'precisao': precisao,
            'endereco_retornado': resultado.get('display_name', ''),
        }
    except Exception:
        return None


def geocodificar_brasilapi(cep):
    cep_limpo = re.sub(r'\D', '', str(cep))
    if len(cep_limpo) != 8:
        return None
    try:
        resultado = consultar_json_mapa(
            f'https://brasilapi.com.br/api/cep/v2/{cep_limpo}'
        )
        coordenadas = resultado.get('location', {}).get('coordinates', {})
        latitude = coordenada_numerica(coordenadas.get('latitude'))
        longitude = coordenada_numerica(coordenadas.get('longitude'))
        if not coordenada_valida_acre(latitude, longitude):
            return None
        endereco_retornado = ', '.join(
            str(valor) for valor in [
                resultado.get('street'), resultado.get('neighborhood'),
                resultado.get('city'), resultado.get('state'),
                resultado.get('cep')
            ] if valor
        )
        return {
            'latitude': latitude,
            'longitude': longitude,
            'fonte': 'BrasilAPI/CEP',
            'precisao': 'MÉDIA',
            'endereco_retornado': endereco_retornado,
        }
    except Exception:
        return None


def geocodificar_ponto_gratuito(ponto):
    resultado = geocodificar_nominatim(ponto['endereco'])
    if resultado is None:
        resultado = geocodificar_brasilapi(ponto.get('cep', ''))

    fuso_acre = pytz.timezone('America/Rio_Branco')
    agora = datetime.now(fuso_acre).strftime('%d/%m/%Y %H:%M:%S')
    if resultado is None:
        return {
            'CHAVE_ENDERECO': ponto['chave'],
            'ENDERECO_CONSULTADO': ponto['endereco'],
            'LATITUDE': '',
            'LONGITUDE': '',
            'FONTE': 'Não localizado',
            'PRECISAO': 'NÃO LOCALIZADO',
            'ENDERECO_RETORNADO': '',
            'DATA_CONSULTA': agora,
        }

    return {
        'CHAVE_ENDERECO': ponto['chave'],
        'ENDERECO_CONSULTADO': ponto['endereco'],
        'LATITUDE': resultado['latitude'],
        'LONGITUDE': resultado['longitude'],
        'FONTE': resultado['fonte'],
        'PRECISAO': resultado['precisao'],
        'ENDERECO_RETORNADO': resultado['endereco_retornado'],
        'DATA_CONSULTA': agora,
    }


def aplicar_cache_aos_pontos(pontos, cache):
    if cache.empty:
        localizados = [
            ponto for ponto in pontos
            if coordenada_valida_acre(
                ponto['latitude'], ponto['longitude']
            )
        ]
        pendentes = [
            ponto for ponto in pontos
            if not coordenada_valida_acre(
                ponto['latitude'], ponto['longitude']
            )
        ]
        return localizados, [], pendentes

    cache_por_chave = {
        str(row['CHAVE_ENDERECO']).strip(): row
        for _, row in cache.iterrows()
    }
    localizados = []
    nao_localizados = []
    pendentes = []

    for ponto in pontos:
        if coordenada_valida_acre(ponto['latitude'], ponto['longitude']):
            localizados.append(ponto)
            continue

        registro = cache_por_chave.get(ponto['chave'])
        if registro is None:
            pendentes.append(ponto)
            continue

        latitude = coordenada_numerica(registro.get('LATITUDE'))
        longitude = coordenada_numerica(registro.get('LONGITUDE'))
        if coordenada_valida_acre(latitude, longitude):
            ponto['latitude'] = latitude
            ponto['longitude'] = longitude
            ponto['fonte'] = str(registro.get('FONTE', ''))
            ponto['precisao'] = str(registro.get('PRECISAO', ''))
            ponto['endereco_retornado'] = str(
                registro.get('ENDERECO_RETORNADO', '')
            )
            localizados.append(ponto)
        else:
            nao_localizados.append(ponto)

    return localizados, nao_localizados, pendentes


def popup_ponto_mapa(ponto):
    titulo = (
        html.escape(ponto['apoiadores'][0]['nome'])
        if len(ponto['apoiadores']) == 1
        else f"{len(ponto['apoiadores'])} apoiadores neste endereço"
    )
    linhas = [
        "<div style='min-width:230px;max-width:310px;font-family:Arial;'>",
        f"<strong style='font-size:15px;color:#0A1C2E;'>{titulo}</strong>",
        f"<div style='font-size:12px;color:#555;margin:5px 0 8px;'>📍 {html.escape(ponto['endereco'])}</div>",
        f"<div style='font-size:12px;color:#555;'>Precisão: {html.escape(ponto.get('precisao', ''))} · {html.escape(ponto.get('fonte', ''))}</div>",
    ]
    for apoiador in ponto['apoiadores'][:12]:
        nome = html.escape(apoiador['nome'])
        classificacao = html.escape(apoiador['classificacao'])
        telefone = html.escape(apoiador['telefone'])
        linhas.append(
            "<div style='border-top:1px solid #ddd;padding-top:6px;"
            f"margin-top:6px;'><b>{nome}</b><br>"
            f"<span style='font-size:12px;color:#666;'>{classificacao} · "
            f"{telefone}</span>"
        )
        if apoiador['telefone_numero']:
            mensagem = urllib.parse.quote(
                f"Olá {apoiador['nome'].split()[0]}, tudo bem?"
            )
            linhas.append(
                f"<br><a href='https://api.whatsapp.com/send?phone=55{apoiador['telefone_numero']}&text={mensagem}' "
                "target='_blank' style='display:inline-block;background:#25D366;"
                "color:white;padding:4px 7px;border-radius:4px;"
                "text-decoration:none;margin-top:4px;'>💬 WhatsApp</a>"
            )
        linhas.append('</div>')

    latitude = ponto['latitude']
    longitude = ponto['longitude']
    linhas.append(
        f"<a href='https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=18/{latitude}/{longitude}' "
        "target='_blank' style='display:inline-block;background:#1A73E8;"
        "color:white;padding:5px 8px;border-radius:4px;text-decoration:none;"
        "margin-top:8px;'>🧭 Abrir localização</a></div>"
    )
    return ''.join(linhas)


def criar_mapa_gratuito(pontos):
    if pontos:
        centro_lat = float(np.mean([p['latitude'] for p in pontos]))
        centro_lon = float(np.mean([p['longitude'] for p in pontos]))
        zoom_inicial = 12 if len({p['municipio'] for p in pontos}) == 1 else 7
    else:
        centro_lat, centro_lon, zoom_inicial = -9.9749, -67.8243, 7

    mapa = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=zoom_inicial,
        tiles='OpenStreetMap',
        control_scale=True
    )
    folium.TileLayer(
        'CartoDB positron', name='Mapa claro', control=True
    ).add_to(mapa)
    Fullscreen(
        position='topright', title='Tela cheia',
        title_cancel='Sair da tela cheia'
    ).add_to(mapa)
    LocateControl(
        position='topleft', strings={'title': 'Mostrar minha localização'}
    ).add_to(mapa)
    agrupador = MarkerCluster(
        name='Apoiadores', control=True, show=True
    ).add_to(mapa)

    cores = {
        'Liderança': '#DC3545', 'Parceria': '#6F42C1',
        'Manutenção': '#28A745', 'Padrão': '#007BFF'
    }
    limites = []
    for ponto in pontos:
        localizacao = [ponto['latitude'], ponto['longitude']]
        limites.append(localizacao)
        quantidade = len(ponto['apoiadores'])
        folium.CircleMarker(
            location=localizacao,
            radius=9 if quantidade > 1 else 7,
            color='white',
            weight=2,
            fill=True,
            fill_color=cores.get(ponto['categoria'], '#007BFF'),
            fill_opacity=0.95,
            tooltip=(
                ponto['apoiadores'][0]['nome'] if quantidade == 1
                else f'{quantidade} apoiadores neste endereço'
            ),
            popup=folium.Popup(popup_ponto_mapa(ponto), max_width=340)
        ).add_to(agrupador)

    if len(limites) > 1:
        mapa.fit_bounds(limites, padding=(35, 35))
    folium.LayerControl(collapsed=True).add_to(mapa)
    return mapa

aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(["🎂 Aniver.", "📍 Bairros", "📞 Contatos", "🗺️ Mapa", "🏆 Lid.", "🤝 Reuniões"])

# --- ABA 1: ANIVERSARIANTES ---
with aba1:
    st.subheader("🎂 Aniversariantes")
    if not df.empty and 'Data de Nascimento' in df.columns:
        df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
        if not df_aniver.empty:
            fuso_acre = timezone(timedelta(hours=-5))
            hoje = datetime.now(fuso_acre)
            hoje_data = datetime(hoje.year, hoje.month, hoje.day)
            
            def calc_dias_para_aniv(data_str):
                try:
                    partes = str(data_str).strip().split('/')
                    dia, mes = int(partes[0]), int(partes[1])
                    if mes == 2 and dia == 29: dia = 28
                    aniv = datetime(hoje.year, mes, dia)
                    if aniv < hoje_data: aniv = datetime(hoje.year + 1, mes, dia)
                    return (aniv - hoje_data).days
                except: return 99999 
            
            df_aniver['DiasFaltando'] = df_aniver['Data de Nascimento'].apply(calc_dias_para_aniv)
            df_aniver = df_aniver.sort_values(by='DiasFaltando')
            
            for idx, row in df_aniver.iterrows():
                if row['DiasFaltando'] == 99999: continue
                
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                bairro = str(row.get('Bairro', ''))
                cidade = str(row.get(col_mun, 'Rio Branco')).strip()
                nascimento = str(row.get('Data de Nascimento', ''))
                dias = row['DiasFaltando']
                tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
                
                texto_dias = "🔥 **É HOJE!**" if dias == 0 else f"Faltam {dias} dias"
                extra_html = f"<span style='float: right; color: #4da6ff; font-size: 14px;'>{nascimento} ({texto_dias})</span>"
                
                if dias == 0:
                    st.markdown(card_html(nome, tel_exibicao, cidade, bairro, extra_html).replace('contato-card', 'contato-card card-aniversario-hoje').replace('👤', '🎂'), unsafe_allow_html=True)
                else:
                    st.markdown(card_html(nome, tel_exibicao, cidade, bairro, extra_html).replace('👤', '🎂'), unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    if tel_num:
                        texto_aniver = urllib.parse.quote(f"Olá {nome.split()[0]}! Em nome do Vereador Samir Bestene e de toda a nossa equipe, desejo um feliz aniversário! Que sua vida seja repleta de alegrias, muita saúde e sucesso. 🎉 Gostaríamos muito de preparar uma homenagem para você nas redes sociais do Samir. Você tem alguma objeção? Se estiver tudo bem, nos mande aqui uma foto sua que você mais gosta para montarmos a arte! É uma honra ter você caminhando ao nosso lado. A luta continua 🚀")
                        st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Mandar Parabéns</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")

# --- ABA 2: BAIRROS ---
with aba2:
    st.subheader("📍 Filtro por Bairro")
    if not df.empty and 'Bairro' in df.columns:
        bairros_disp = ["Todos"] + sorted([str(b).strip() for b in df['Bairro'].dropna().unique() if str(b).strip() != ''])
        bairro_sel = st.selectbox("Selecione o Bairro:", bairros_disp)
        filtrados = df if bairro_sel == "Todos" else df[df['Bairro'].astype(str).str.strip() == bairro_sel]
        
        st.markdown(f"**Total encontrado:** {len(filtrados)} pessoa(s)")
        
        for idx, row in filtrados.iterrows():
            nome, bairro = str(row.get('Nome Completo', 'Sem Nome')), str(row.get('Bairro', ''))
            cidade = str(row.get(col_mun, 'Rio Branco')).strip()
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num: st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={urllib.parse.quote(f'Olá {nome.split()[0]}, tudo bem?')}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            st.markdown("")

# --- ABA 3: CONTATOS ---
with aba3:
    st.subheader("📞 Pesquisa de Contatos")
    busca = st.text_input("🔍 Digite o nome para buscar:", placeholder="Ex: Maria...")
    if not df.empty and 'Nome Completo' in df.columns:
        df_contatos = df[df['Nome Completo'].str.contains(busca, case=False, na=False)] if busca else df
        st.markdown(f"**Exibindo {len(df_contatos)} contato(s)**")
        
        for idx, row in df_contatos.iterrows():
            nome, bairro = str(row.get('Nome Completo', 'Sem Nome')), str(row.get('Bairro', ''))
            cidade = str(row.get(col_mun, 'Rio Branco')).strip()
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num: st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={urllib.parse.quote(f'Olá {nome.split()[0]}, tudo bem?')}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            st.markdown("")

# --- ABA 4: MAPA ---
with aba4:
    st.subheader("🗺️ Mapa de Apoiadores")
    st.markdown(
        "Mapa gratuito com OpenStreetMap. Os endereços são localizados uma única "
        "vez e as coordenadas ficam guardadas em uma aba separada da planilha."
    )
    st.markdown("""
    <div style='background-color: #152b45; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px; text-align: center;'>
        <b>Legenda Tática:</b><br>
        <span style="color:#DC3545; font-size: 18px;">●</span> Liderança &nbsp;|&nbsp; <span style="color:#6F42C1; font-size: 18px;">●</span> Parceria<br>
        <span style="color:#28A745; font-size: 18px;">●</span> Manutenção &nbsp;|&nbsp; <span style="color:#007BFF; font-size: 18px;">●</span> Padrão
    </div>
    """, unsafe_allow_html=True)

    if not df.empty and 'Bairro' in df.columns:
        df_mapa = df.copy()
        col_classificacao_mapa = localizar_coluna_mapa(
            df_mapa, ['Classificação Interna', 'Classificacao Interna']
        )
        df_mapa['_CATEGORIA_MAPA'] = df_mapa.apply(
            lambda linha: categoria_mapa(
                texto_linha_mapa(linha, col_classificacao_mapa)
            ), axis=1
        )

        filtro_municipio, filtro_categoria = st.columns(2)
        with filtro_municipio:
            if col_mun:
                municipios_mapa = sorted(
                    municipio for municipio in
                    df_mapa[col_mun].fillna('Rio Branco').astype(str)
                    .str.strip().unique()
                    if municipio and municipio.lower() != 'nan'
                )
                municipio_mapa = st.selectbox(
                    "Município no mapa:", ['Todos'] + municipios_mapa,
                    key='municipio_mapa_gratuito'
                )
            else:
                municipio_mapa = 'Todos'
        with filtro_categoria:
            categorias_disponiveis = [
                categoria for categoria in
                ['Liderança', 'Parceria', 'Manutenção', 'Padrão']
                if categoria in df_mapa['_CATEGORIA_MAPA'].unique()
            ]
            categorias_mapa = st.multiselect(
                "Classificação no mapa:", categorias_disponiveis,
                default=categorias_disponiveis,
                key='categorias_mapa_gratuito'
            )

        if col_mun and municipio_mapa != 'Todos':
            df_mapa = df_mapa[
                df_mapa[col_mun].fillna('Rio Branco').astype(str).str.strip()
                == municipio_mapa
            ]
        df_mapa = df_mapa[
            df_mapa['_CATEGORIA_MAPA'].isin(categorias_mapa)
        ]

        pontos = preparar_pontos_mapa(df_mapa, col_mun)
        cache_mapa = carregar_cache_mapa()
        pontos_localizados, pontos_nao_localizados, pontos_pendentes = (
            aplicar_cache_aos_pontos(pontos, cache_mapa)
        )

        total_precisos = sum(
            normalizar_texto_mapa(ponto.get('precisao', '')) == 'alta'
            for ponto in pontos_localizados
        )
        metrica1, metrica2, metrica3 = st.columns(3)
        metrica1.metric("Localizados", len(pontos_localizados))
        metrica2.metric("Precisão alta", total_precisos)
        metrica3.metric(
            "Pendentes",
            len(pontos_pendentes) + len(pontos_nao_localizados)
        )
        st.caption(
            f"{len(df_mapa)} cadastro(s) em {len(pontos)} endereço(s) único(s). "
            "Pessoas do mesmo endereço aparecem no mesmo ponto."
        )

        if pontos_pendentes:
            st.info(
                "Há endereços novos ainda sem coordenadas. O botão abaixo "
                f"processa no máximo {LIMITE_GEOCODIFICACAO_POR_CLIQUE} por vez, "
                "respeitando o limite do serviço gratuito."
            )
            if st.button(
                f"📍 Localizar próximos {min(LIMITE_GEOCODIFICACAO_POR_CLIQUE, len(pontos_pendentes))} endereços",
                use_container_width=True,
                key='geocodificar_lote_gratuito'
            ):
                lote = pontos_pendentes[:LIMITE_GEOCODIFICACAO_POR_CLIQUE]
                barra = st.progress(0)
                mensagem_progresso = st.empty()
                novos_registros = []
                for posicao, ponto in enumerate(lote, start=1):
                    mensagem_progresso.write(
                        f"Localizando {posicao} de {len(lote)}: "
                        f"{ponto['endereco']}"
                    )
                    novos_registros.append(
                        geocodificar_ponto_gratuito(ponto)
                    )
                    barra.progress(posicao / len(lote))
                    # Política pública do Nominatim: no máximo 1 consulta/segundo.
                    time.sleep(1.05)

                gravados, erro_cache = salvar_cache_mapa(novos_registros)
                if erro_cache:
                    st.error(
                        "As coordenadas foram consultadas, mas não puderam ser "
                        f"gravadas na aba {ABA_CACHE_MAPA}. Detalhe: {erro_cache}"
                    )
                else:
                    st.success(
                        f"{gravados} endereço(s) processado(s). Atualizando o mapa…"
                    )
                    st.rerun()

        if pontos_nao_localizados:
            with st.expander(
                f"⚠️ {len(pontos_nao_localizados)} endereço(s) precisam de revisão"
            ):
                st.markdown(
                    "Revise rua, número, CEP e município no formulário. Para uma "
                    "correção exata, informe Latitude e Longitude na aba "
                    f"**{ABA_CACHE_MAPA}** criada automaticamente."
                )
                st.dataframe(
                    pd.DataFrame({
                        'Endereço não localizado': [
                            ponto['endereco'] for ponto in pontos_nao_localizados
                        ]
                    }),
                    use_container_width=True,
                    hide_index=True
                )

        mapa = criar_mapa_gratuito(pontos_localizados)
        st_folium(
            mapa, use_container_width=True, height=560,
            returned_objects=[], key='mapa_apoiadores_gratuito'
        )
        st.caption(
            "© OpenStreetMap contributors · Geocodificação gratuita e armazenada "
            "em cache. Nenhuma API paga do Google Maps é utilizada."
        )
    else:
        st.info("A planilha ainda não possui endereços disponíveis para o mapa.")

# --- ABA 5: RANKING DE LIDERANÇAS ---
with aba5:
    st.subheader("🏆 Ranking de Lideranças")
    col_indicacao = next((col for col in df.columns if "Através de quem" in str(col)), None)
    if not df.empty and col_indicacao:
        df_lideres = df.dropna(subset=[col_indicacao]).copy()
        df_lideres = df_lideres[df_lideres[col_indicacao].astype(str).str.strip() != ""]
        df_lideres[col_indicacao] = df_lideres[col_indicacao].astype(str).str.strip().str.title()
        
        if not df_lideres.empty:
            ranking = df_lideres.groupby(col_indicacao).size().reset_index(name='Qtd').sort_values(by='Qtd', ascending=False).reset_index(drop=True)
            top1 = ranking.iloc[0]
            st.metric(label="🥇 Liderança Destaque", value=top1[col_indicacao], delta=f"{top1['Qtd']} indicações ({(top1['Qtd'] / total_cadastros) * 100:.1f}% da base)")
            st.markdown("---")
            
            for idx, row in ranking.iterrows():
                lider, qtd = row[col_indicacao], row['Qtd']
                with st.expander(f"#{idx + 1} | {lider} - {qtd} pessoa(s) ({(qtd / total_cadastros) * 100:.1f}%)"):
                    for _, apoiado in df_lideres[df_lideres[col_indicacao] == lider].iterrows():
                        nome_ap = str(apoiado.get('Nome Completo', 'Sem Nome'))
                        bairro_ap = str(apoiado.get('Bairro', ''))
                        cidade_ap = str(apoiado.get(col_mun, 'Rio Branco')).strip()
                        if cidade_ap.lower() == 'nan' or cidade_ap == '': cidade_ap = 'Rio Branco'
                        
                        tel_num_ap, tel_exibicao_ap = tratar_telefone(apoiado.get('Telefone', ''))
                        tel_html = f"📞 <a href='https://api.whatsapp.com/send?phone=55{tel_num_ap}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{tel_exibicao_ap}</a>" if tel_num_ap else "📞 <span style='color: #8899a6;'>Sem Número</span>"
                        
                        st.markdown(f"<div class='apoiador-lider'><b>{nome_ap}</b><br><span style='font-size: 14px; color: #a9b9cc;'>📍 {cidade_ap} - {bairro_ap} | {tel_html}</span></div>", unsafe_allow_html=True)
        else: st.info("Ainda não há dados suficientes de indicações preenchidos.")
    else: st.warning("A coluna de indicação não foi encontrada.")

# --- ABA 6: REUNIÕES E AJUNTAMENTOS ---
with aba6:
    st.subheader("🤝 Agendar Reuniões")
    col_participacao = next((col for col in df.columns if "participar" in str(col).lower()), None)
            
    if not df.empty and col_participacao:
        df_reunioes = df[df[col_participacao].astype(str).str.contains("reunião|reuniao", case=False, na=False)].copy()
        if not df_reunioes.empty:
            df_reunioes = df_reunioes.sort_values(by='Nome Completo')
            st.markdown(f"**Total de interessados:** {len(df_reunioes)}")
            
            for idx, row in df_reunioes.iterrows():
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                bairro = str(row.get('Bairro', ''))
                cidade = str(row.get(col_mun, 'Rio Branco')).strip()
                if cidade.lower() == 'nan' or cidade == '': cidade = 'Rio Branco'
                tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
                
                st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    if tel_num:
                        texto_reuniao = urllib.parse.quote(f"Olá {nome.split()[0]}, tudo bem? Aqui é da equipe do Samir Bestene. Vimos no seu cadastro que você tem interesse em organizar uma reunião aí na sua rua/bairro! Ficamos muito animados com esse apoio. Vamos fazer acontecer? Qual seria o melhor dia da semana e horário para você reunir alguns amigos e vizinhos para um bate-papo com o Samir? Estamos à disposição para agendar. A luta continua 🚀")
                        st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_reuniao}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Agendar Reunião</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")
        else: st.info("Nenhum apoiador sinalizou interesse em organizar reunião até o momento.")
