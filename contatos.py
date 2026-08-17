import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import numpy as np
import urllib.parse
import re
import unicodedata
import hashlib
import html
import folium
from folium.plugins import Fullscreen, LocateControl
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


def serie_municipios_mapa(dataframe, coluna_municipio):
    """Padroniza o município e considera cadastros vazios como Rio Branco."""
    if not coluna_municipio or coluna_municipio not in dataframe.columns:
        return pd.Series('Rio Branco', index=dataframe.index, dtype='object')

    municipios = (
        dataframe[coluna_municipio]
        .fillna('')
        .astype(str)
        .str.strip()
    )
    sem_municipio = municipios.str.lower().isin(['', 'nan', 'none'])
    return municipios.mask(sem_municipio, 'Rio Branco')


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
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
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
            ponto['motivo_falha'] = str(registro.get('FONTE', ''))
            nao_localizados.append(ponto)

    return localizados, nao_localizados, pendentes


# Referências territoriais usadas somente quando não existe coordenada real.
_MUNICIPIOS_REFERENCIA = {
    'Acrelândia': (-9.8258, -66.8972),
    'Assis Brasil': (-10.9297, -69.5738),
    'Brasiléia': (-11.0164, -68.7482),
    'Bujari': (-9.8153, -67.9550),
    'Capixaba': (-10.5660, -67.6860),
    'Cruzeiro do Sul': (-7.6276, -72.6756),
    'Epitaciolândia': (-11.0288, -68.7440),
    'Feijó': (-8.1645, -70.3536),
    'Jordão': (-9.4309, -71.8974),
    'Mâncio Lima': (-7.6142, -72.8954),
    'Manoel Urbano': (-8.8389, -69.2599),
    'Marechal Thaumaturgo': (-8.9536, -72.7903),
    'Plácido de Castro': (-10.3353, -67.1889),
    'Porto Acre': (-9.5883, -67.5439),
    'Porto Walter': (-8.2686, -72.7430),
    'Rio Branco': (-9.9749, -67.8243),
    'Rodrigues Alves': (-7.7386, -72.6479),
    'Santa Rosa do Purus': (-9.4465, -70.4903),
    'Sena Madureira': (-9.0635, -68.6727),
    'Senador Guiomard': (-10.1497, -67.7374),
    'Tarauacá': (-8.1569, -70.7722),
    'Xapuri': (-10.6516, -68.4969),
}
REFERENCIAS_MUNICIPIOS_MAPA = {
    normalizar_texto_mapa(nome): coordenadas
    for nome, coordenadas in _MUNICIPIOS_REFERENCIA.items()
}

_BAIRROS_REFERENCIA = {
    'Centro': (-9.9749, -67.8243),
    'Doca Furtado': (-9.9650, -67.8100),
    'Floresta': (-9.9820, -67.8400),
    'Parque dos Sabiás': (-9.9550, -67.8000),
    'Vila Acre': (-10.0100, -67.7800),
    'Universitário': (-9.9500, -67.8600),
    'Estação Experimental': (-9.9580, -67.8250),
    'Calafate': (-9.9600, -67.8700),
    'Baixada': (-9.9800, -67.8000),
    'São Francisco': (-9.9600, -67.8500),
    'Tancredo Neves': (-9.9400, -67.8400),
}
REFERENCIAS_BAIRROS_MAPA = {
    normalizar_texto_mapa(nome): coordenadas
    for nome, coordenadas in _BAIRROS_REFERENCIA.items()
}
ALIASES_BAIRROS_MAPA = {
    'baixada da cadeia velha': 'baixada',
    'cadeia velha': 'baixada',
    'parque dos sabias': 'parque dos sabias',
}


def referencia_territorial_mapa(ponto):
    bairro_original = str(ponto.get('bairro', '')).strip()
    municipio_original = str(
        ponto.get('municipio', 'Rio Branco')
    ).strip() or 'Rio Branco'
    bairro = normalizar_texto_mapa(bairro_original)
    municipio = normalizar_texto_mapa(municipio_original)
    bairro = ALIASES_BAIRROS_MAPA.get(bairro, bairro)

    if bairro in REFERENCIAS_BAIRROS_MAPA:
        latitude, longitude = REFERENCIAS_BAIRROS_MAPA[bairro]
        return (
            latitude, longitude, 0.0045,
            f'Bairro {bairro_original or bairro.title()}'
        )

    if municipio in REFERENCIAS_MUNICIPIOS_MAPA:
        latitude, longitude = REFERENCIAS_MUNICIPIOS_MAPA[municipio]
        raio = 0.008 if municipio == 'rio branco' else 0.012
        return (
            latitude, longitude, raio,
            f'Município {municipio_original}'
        )

    return -9.9749, -67.8243, 0.015, 'Referência geral de Rio Branco'


def deslocamento_estavel_mapa(chave, latitude, longitude, raio):
    resumo = hashlib.sha256(
        f'aproximado|{chave}'.encode('utf-8')
    ).digest()
    maximo = float((1 << 64) - 1)
    fracao_angulo = int.from_bytes(resumo[:8], 'big') / maximo
    fracao_raio = int.from_bytes(resumo[8:16], 'big') / maximo
    angulo = 2 * np.pi * fracao_angulo
    distancia = raio * (0.20 + 0.80 * np.sqrt(fracao_raio))
    ajuste_longitude = max(abs(np.cos(np.radians(latitude))), 0.20)
    return (
        latitude + distancia * np.cos(angulo),
        longitude + distancia * np.sin(angulo) / ajuste_longitude
    )


def construir_pontos_hibridos_mapa(pontos, cache):
    localizados, nao_localizados, pendentes = aplicar_cache_aos_pontos(
        pontos, cache
    )

    for ponto in localizados:
        ponto['tipo_localizacao'] = 'coordenada'
        if not ponto.get('precisao'):
            ponto['precisao'] = 'COORDENADA DISPONÍVEL'

    aproximados = nao_localizados + pendentes
    for ponto in aproximados:
        latitude, longitude, raio, referencia = referencia_territorial_mapa(
            ponto
        )
        latitude, longitude = deslocamento_estavel_mapa(
            ponto['chave'], latitude, longitude, raio
        )
        ponto['latitude'] = latitude
        ponto['longitude'] = longitude
        ponto['tipo_localizacao'] = 'aproximada'
        ponto['precisao'] = 'APROXIMADA'
        ponto['fonte'] = f'Referência territorial: {referencia}'

    return localizados + aproximados, len(localizados), len(aproximados)


def total_apoiadores_nos_pontos(pontos):
    return sum(len(ponto.get('apoiadores', [])) for ponto in pontos)


def popup_ponto_mapa(ponto):
    localizacao_aproximada = (
        ponto.get('tipo_localizacao') == 'aproximada'
    )
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
    if localizacao_aproximada:
        linhas.append(
            "<div style='background:#FFF3CD;color:#664D03;padding:6px;"
            "border-radius:4px;font-size:12px;margin-top:7px;'>"
            "≈ Ponto aproximado para leitura territorial. Não corresponde "
            "necessariamente ao imóvel informado.</div>"
        )
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
    zoom_link = 15 if localizacao_aproximada else 18
    texto_link = (
        'Ver área aproximada'
        if localizacao_aproximada
        else 'Abrir localização'
    )
    linhas.append(
        f"<a href='https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map={zoom_link}/{latitude}/{longitude}' "
        "target='_blank' style='display:inline-block;background:#1A73E8;"
        "color:white;padding:5px 8px;border-radius:4px;text-decoration:none;"
        f"margin-top:8px;'>🧭 {texto_link}</a></div>"
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
        tiles='CartoDB positron',
        control_scale=True
    )
    folium.TileLayer(
        'OpenStreetMap', name='Mapa detalhado', control=True
    ).add_to(mapa)
    Fullscreen(
        position='topright', title='Tela cheia',
        title_cancel='Sair da tela cheia'
    ).add_to(mapa)
    LocateControl(
        position='topleft', strings={'title': 'Mostrar minha localização'}
    ).add_to(mapa)
    camada_apoiadores = folium.FeatureGroup(
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
        localizacao_aproximada = (
            ponto.get('tipo_localizacao') == 'aproximada'
        )
        nome_tooltip = (
            ponto['apoiadores'][0]['nome'] if quantidade == 1
            else f'{quantidade} apoiadores neste ponto'
        )
        if localizacao_aproximada:
            nome_tooltip = f'≈ {nome_tooltip} · aproximação territorial'
        folium.CircleMarker(
            location=localizacao,
            radius=6.5 if quantidade > 1 else 5.5,
            color='#D9E2EC' if localizacao_aproximada else 'white',
            weight=1 if localizacao_aproximada else 2,
            dash_array='3,3' if localizacao_aproximada else None,
            fill=True,
            fill_color=cores.get(ponto['categoria'], '#007BFF'),
            fill_opacity=0.72 if localizacao_aproximada else 0.95,
            tooltip=nome_tooltip,
            popup=folium.Popup(popup_ponto_mapa(ponto), max_width=340)
        ).add_to(camada_apoiadores)

    if len(limites) > 1:
        mapa.fit_bounds(limites, padding=(35, 35))
    folium.LayerControl(collapsed=True).add_to(mapa)
    return mapa


# ==========================================
# CABEÇAL GLOBAL: LOGO + MAPA COMPARTILHADO ENTRE AS ABAS
# ==========================================
df_mapa_completo = pd.DataFrame()
col_classificacao_mapa = None
municipios_mapa = []
categorias_disponiveis = []
bairros_disp = ["Todos"]
cache_mapa = pd.DataFrame(columns=CABECALHO_CACHE_MAPA)
pontos_mapa_completo = []
pontos_mapa_filtrado = []
pontos_hibridos_global = []
enderecos_com_coordenada_global = 0
enderecos_aproximados_global = 0

if not df.empty and 'Bairro' in df.columns:
    df_mapa_completo = df.copy()
    df_mapa_completo['_MUNICIPIO_MAPA'] = serie_municipios_mapa(
        df_mapa_completo, col_mun
    )
    col_classificacao_mapa = localizar_coluna_mapa(
        df_mapa_completo,
        ['Classificação Interna', 'Classificacao Interna']
    )
    df_mapa_completo['_CATEGORIA_MAPA'] = df_mapa_completo.apply(
        lambda linha: categoria_mapa(
            texto_linha_mapa(linha, col_classificacao_mapa)
        ),
        axis=1
    )

    municipios_mapa = sorted({
        str(municipio).strip()
        for municipio in df_mapa_completo['_MUNICIPIO_MAPA']
        if str(municipio).strip()
    })

    opcoes_municipio = ['Todos'] + municipios_mapa
    municipio_anterior = st.session_state.get(
        'municipio_filtro_compartilhado',
        st.session_state.get('municipio_mapa_gratuito', 'Todos')
    )
    if municipio_anterior not in opcoes_municipio:
        municipio_anterior = 'Todos'
    st.session_state['municipio_filtro_compartilhado'] = municipio_anterior
    municipio_mapa_ativo = st.session_state[
        'municipio_filtro_compartilhado'
    ]

    df_referencia_bairros = df_mapa_completo
    if municipio_mapa_ativo != 'Todos':
        df_referencia_bairros = df_referencia_bairros[
            df_referencia_bairros['_MUNICIPIO_MAPA']
            == municipio_mapa_ativo
        ]
    bairros_disp = ["Todos"] + sorted({
        str(bairro).strip()
        for bairro in df_referencia_bairros['Bairro'].dropna()
        if str(bairro).strip() and str(bairro).strip().lower() != 'nan'
    })

    categorias_disponiveis = [
        categoria
        for categoria in ['Liderança', 'Parceria', 'Manutenção', 'Padrão']
        if categoria in df_mapa_completo['_CATEGORIA_MAPA'].unique()
    ]

    if (
        'bairro_filtro_compartilhado' not in st.session_state
        or st.session_state['bairro_filtro_compartilhado'] not in bairros_disp
    ):
        st.session_state['bairro_filtro_compartilhado'] = 'Todos'

    if 'categorias_mapa_gratuito' not in st.session_state:
        st.session_state['categorias_mapa_gratuito'] = categorias_disponiveis.copy()
    else:
        categorias_salvas = st.session_state['categorias_mapa_gratuito']
        categorias_validas = [
            categoria for categoria in categorias_salvas
            if categoria in categorias_disponiveis
        ]
        if categorias_salvas and not categorias_validas:
            categorias_validas = categorias_disponiveis.copy()
        st.session_state['categorias_mapa_gratuito'] = categorias_validas

    bairro_mapa_ativo = st.session_state['bairro_filtro_compartilhado']
    categorias_mapa_ativas = st.session_state['categorias_mapa_gratuito']

    df_mapa_filtrado = df_mapa_completo.copy()
    if bairro_mapa_ativo != 'Todos':
        df_mapa_filtrado = df_mapa_filtrado[
            df_mapa_filtrado['Bairro'].fillna('').astype(str).str.strip()
            == bairro_mapa_ativo
        ]
    if municipio_mapa_ativo != 'Todos':
        df_mapa_filtrado = df_mapa_filtrado[
            df_mapa_filtrado['_MUNICIPIO_MAPA'] == municipio_mapa_ativo
        ]
    df_mapa_filtrado = df_mapa_filtrado[
        df_mapa_filtrado['_CATEGORIA_MAPA'].isin(categorias_mapa_ativas)
    ]

    cache_mapa = carregar_cache_mapa()
    pontos_mapa_completo = preparar_pontos_mapa(df_mapa_completo, col_mun)
    pontos_mapa_filtrado = preparar_pontos_mapa(df_mapa_filtrado, col_mun)
    (
        pontos_hibridos_global,
        enderecos_com_coordenada_global,
        enderecos_aproximados_global
    ) = construir_pontos_hibridos_mapa(
        pontos_mapa_filtrado, cache_mapa
    )
else:
    bairro_mapa_ativo = 'Todos'
    municipio_mapa_ativo = 'Todos'
    categorias_mapa_ativas = []
    df_mapa_filtrado = pd.DataFrame()

col_logo, col_mapa_global = st.columns([1, 3], gap='medium')
with col_logo:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except Exception:
        st.title("📱 Gestão de Contatos")

    if not df.empty and 'Bairro' in df.columns:
        rotulo_municipio = (
            'Todos os municípios'
            if municipio_mapa_ativo == 'Todos'
            else municipio_mapa_ativo
        )
        rotulo_bairro = (
            'Todos os bairros'
            if bairro_mapa_ativo == 'Todos'
            else bairro_mapa_ativo
        )
        st.markdown(f"**Município no mapa:** {rotulo_municipio}")
        st.markdown(f"**Bairro no mapa:** {rotulo_bairro}")
        st.metric(
            "Apoiadores no recorte",
            len(df_mapa_filtrado)
        )
        st.markdown(
            "<span style='color:#DC3545;font-size:17px;'>●</span> Liderança<br>"
            "<span style='color:#6F42C1;font-size:17px;'>●</span> Parceria<br>"
            "<span style='color:#28A745;font-size:17px;'>●</span> Manutenção<br>"
            "<span style='color:#007BFF;font-size:17px;'>●</span> Padrão<br>"
            "<hr style='margin:8px 0;border-color:#334e68;'>"
            "<span style='font-size:13px;'>Ponto contínuo: coordenada "
            "disponível<br>Ponto tracejado: aproximação territorial</span>",
            unsafe_allow_html=True
        )

with col_mapa_global:
    st.subheader("🗺️ Mapa de Apoiadores")
    if not df.empty and 'Bairro' in df.columns:
        filtro_municipio, filtro_bairro, filtro_classificacao = st.columns(3)
        with filtro_municipio:
            st.selectbox(
                "Município:",
                ['Todos'] + municipios_mapa,
                key='municipio_filtro_compartilhado',
                format_func=lambda valor: (
                    'Todos os municípios'
                    if valor == 'Todos'
                    else valor
                )
            )
        with filtro_bairro:
            st.selectbox(
                "Bairro:",
                bairros_disp,
                key='bairro_filtro_compartilhado',
                format_func=lambda valor: (
                    'Todos os bairros'
                    if valor == 'Todos'
                    else valor
                )
            )
        with filtro_classificacao:
            st.multiselect(
                "Classificação:",
                categorias_disponiveis,
                key='categorias_mapa_gratuito'
            )

        mapa_global = criar_mapa_gratuito(pontos_hibridos_global)
        assinatura_filtro = hashlib.md5(
            (
                f"{bairro_mapa_ativo}|{municipio_mapa_ativo}|"
                f"{'|'.join(categorias_mapa_ativas)}"
            ).encode('utf-8')
        ).hexdigest()[:10]
        st_folium(
            mapa_global,
            use_container_width=True,
            height=420,
            returned_objects=[],
            key=f'mapa_apoiadores_global_{assinatura_filtro}'
        )
        st.caption(
            f"{total_apoiadores_nos_pontos(pontos_hibridos_global)} "
            f"apoiador(es) em {len(pontos_hibridos_global)} ponto(s) · "
            f"{enderecos_com_coordenada_global} com coordenada · "
            f"{enderecos_aproximados_global} aproximado(s) · "
            "os filtros acima atualizam o mapa e a aba Território."
        )
    else:
        st.info("A planilha ainda não possui endereços disponíveis para o mapa.")

st.markdown("---")

aba1, aba2, aba3, aba5, aba6 = st.tabs(["🎂 Aniver.", "📍 Território", "📞 Contatos", "🏆 Lid.", "🤝 Reuniões"])

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
                        texto_aniver = urllib.parse.quote(f"Olá {nome.split()[0]}! Feliz aniversário! 🎉 Pode nos enviar uma foto sua? O vereador Samir Bestene gostaria de fazer uma homenagem especial para você.")
                        st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Mandar Parabéns</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")

# --- ABA 2: BAIRROS ---
with aba2:
    st.subheader("📍 Apoiadores no Recorte Territorial")
    if not df.empty and 'Bairro' in df.columns:
        st.caption(
            "Esta relação acompanha os filtros de município, bairro e "
            "classificação posicionados acima do mapa."
        )

        filtrados = df_mapa_filtrado.copy()
        
        st.markdown(f"**Total encontrado:** {len(filtrados)} pessoa(s)")
        
        for idx, row in filtrados.iterrows():
            nome, bairro = str(row.get('Nome Completo', 'Sem Nome')), str(row.get('Bairro', ''))
            cidade = str(row.get('_MUNICIPIO_MAPA', 'Rio Branco')).strip()
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
