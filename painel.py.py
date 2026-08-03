import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import zipfile
import os
import json
import re
import unicodedata
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="Painel Executivo | Análise Territorial", page_icon="🎯", layout="wide")


# ==========================================
# PADRÃO RESPONSIVO PARA GRÁFICOS E LEGENDAS
# ==========================================
def exibir_grafico_altair(grafico):
    """Exibe gráficos com legendas completas, abaixo da área de plotagem."""
    grafico_responsivo = grafico.configure_legend(
        orient="bottom",
        direction="horizontal",
        columns=2,
        labelLimit=0,
        titleLimit=0,
        columnPadding=24,
        rowPadding=8,
        offset=12,
        padding=8
    )
    st.altair_chart(grafico_responsivo, use_container_width=True)

# ==========================================
# SISTEMA DE LOGIN E SEGURANÇA
# ==========================================
def registrar_log(usuario):
    """Registra o acesso silenciosamente no Google Sheets."""
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

        # ID exato da sua planilha
        planilha_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"

        # Abre a aba
        aba_logs = cliente.open_by_key(planilha_id).worksheet("Logs_Acesso")

        # Insere a nova linha com as informações
        aba_logs.append_row([usuario, data_formatada, hora_formatada])

    except Exception as e:
        # Se der erro, ele não trava o app, apenas avisa nos bastidores
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
# INJEÇÃO DE CSS
# ==========================================
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0A1C2E !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div.stMarkdown { color: #FFFFFF !important; }
    div[data-baseweb="select"] * { color: #262730 !important; }
</style>
""", unsafe_allow_html=True)

# Insere a logo da campanha
col_logo1, col_logo2, col_logo3 = st.columns([3, 2, 3])
with col_logo2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.markdown("<h3 style='text-align: center;'>🎯 Painel Eleitoral</h3>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# CARREGAMENTO DOS DADOS E INTEGRAÇÃO DE ZONAS
# ==========================================
@st.cache_data
def carregar_dados():
    df = pd.read_csv("dados.csv")
    centros_acre = {
        'RIO BRANCO': (-9.9749, -67.8243), 'SENA MADUREIRA': (-9.3356, -68.6558),
        'TARAUACA': (-8.1578, -70.8675), 'XAPURI': (-10.6514, -68.5078),
        'PORTO ACRE': (-9.5847, -67.5342), 'SENADOR GUIOMARD': (-10.1503, -67.7408),
        'PLACIDO DE CASTRO': (-10.2742, -67.1908), 'RODRIGUES ALVES': (-7.7428, -72.6506),
        'SANTA ROSA DO PURUS': (-9.4353, -70.4903), 'CRUZEIRO DO SUL': (-7.6311, -72.6756),
        'FEIJO': (-8.1642, -70.3556)
    }
    col_mun = None
    for col in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']:
        if col in df.columns:
            col_mun = col
            break

    if 'lat' not in df.columns or 'lon' not in df.columns or df['lat'].isnull().all():
        np.random.seed(42)
        escolas_unicas = df['NM_LOCAL_VOTACAO'].unique()
        escola_coords = {}
        for esc in escolas_unicas:
            sub = df[df['NM_LOCAL_VOTACAO'] == esc]
            mun = str(sub[col_mun].iloc[0]).strip().upper() if col_mun and not sub.empty else 'RIO BRANCO'
            center_lat, center_lon = centros_acre.get(mun, (-9.9749, -67.8243))
            escola_coords[esc] = (center_lat + np.random.normal(0, 0.03), center_lon + np.random.normal(0, 0.03))
        df['lat'] = df['NM_LOCAL_VOTACAO'].map(lambda x: escola_coords[x][0])
        df['lon'] = df['NM_LOCAL_VOTACAO'].map(lambda x: escola_coords[x][1])
    else:
        df['lat'] = df['lat'].fillna(-9.9749)
        df['lon'] = df['lon'].fillna(-67.8243)
    return df

def aplicar_zonas(df_principal):
    # Lista oficial cruzada com bases do TRE-AC e dados de localização
    escolas_rurais = [
        'ESCOLA ESTADUAL RURAL JORGE KALUME', 'ESCOLA RURAL BEIJA-FLOR', 
        'INSTITUTO FEDERAL DO ACRE (IFAC) - TRANSACREANA', 'ESCOLA RURAL CAPITÃO EDGARD CERQUEIRA FILHO', 
        'ESCOLA RURAL PROF. CLAUDIO AUGUSTO F. DE SALES', 'ESCOLA RURAL RUY AZEVEDO', 
        'IDAF - VILA ACRE', 'ESCOLA RURAL SÃO PEDRO I', 'ESCOLA RURAL ERCÍLIA FEITOSA GOMES', 
        'ESCOLA EST. DALVA DE SOUZA DAS NEVES (TRANSACREANA)', 'ESCOLA VALERIA BISPO SABALA - KM 26', 
        'ESCOLA ESTADUAL PADRE JÓSIMO - COMUNIDADE SÃO JOÃO DO GUARANI', 'ESCOLA RURAL NOVA VIDA', 
        'ESCOLA ESTADUAL RURAL MANUEL DE BARROS', 'ESCOLA ESTADUAL RURAL FLAVIA BARROS PIMENTEL', 
        'ESCOLA ESTADUAL RURAL BOM DESTINO', 'ESCOLA RURAL ALTO ALEGRE I', 
        'ESCOLA CASTELO BRANCO - KM 20', 'ESCOLA VALDOMIRO FERREIRA BARROSO - KM 19', 
        'ESCOLA FRANCISCO GERMANO DA SILVA - KM 68', 'IFAC - POLO PORTO ACRE', 
        'ESCOLA LAGO - KM 05 MAIS 28 DE RAMAL (SERINGAL PORONGABA)', 
        'PRÉDIO DA SEATER - BOCA DO RAMAL AREIA BRANCA', 'ESCOLA RURAL MARIA DO CARMO RAMOS', 
        'ESCOLA LUIZ GONZAGA DA ROCHA - KM 09 VILA PROGRESSO', 
        'UNIDADE DE SAÚDE SEBASTIÃO PRADO (TRANSACREANA)', 'ESCOLA RURAL ALTO ALEGRE II',
        'ESCOLA ESTADUAL PROFESSORA TEREZINHA MIGUÉIS', 'ESCOLA MÁRIO LOBÃO', 'CENTRO DE SAUDE DE PORTO ACRE'
    ]

    # O sistema marca como RURAL se estiver na lista, e URBANA todo o restante
    df_principal['TIPO_ZONA'] = np.where(df_principal['NM_LOCAL_VOTACAO'].isin(escolas_rurais), 'RURAL', 'URBANA')
    return df_principal


# ==========================================
# BASES TSE USADAS SOMENTE NA ROTA 6
# ==========================================
ARQUIVOS_LOCAIS_TSE = {
    2020: "tse_locais_acre_2020.csv.xlsx",
    2022: "tse_locais_acre_2022.csv.xlsx",
    2024: "tse_locais_acre_2024.csv.xlsx",
}

# Preencha somente após conferência documental ou territorial.
# Copie o ID exibido na tabela "Locais pendentes de revisão" da Rota 6.
AJUSTES_MANUAIS_ZONA_RURAL = {
    # "2024|1392|1|1848": {
    #     "CLASSIFICACAO_RURAL": "RURAL",
    #     "OBSERVACAO": "Confirmado pela coordenação em DD/MM/AAAA",
    # },
}


def normalizar_coordenada_tse(valor, minimo_absoluto, maximo_absoluto):
    """Recupera coordenadas que chegaram ao XLSX sem separador decimal."""
    if pd.isna(valor):
        return np.nan
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return np.nan

    if numero in (-1, 0, 1):
        return np.nan

    sinal = -1 if numero < 0 else 1
    numero = abs(numero)
    for potencia in range(10):
        candidato = numero / (10 ** potencia)
        if minimo_absoluto <= candidato <= maximo_absoluto:
            return sinal * candidato
    return np.nan


@st.cache_data
def carregar_locais_tse_rota_rural():
    """Carrega as planilhas TSE sem afetar a inicialização das demais rotas."""
    bases = []
    avisos = []

    for ano, arquivo in ARQUIVOS_LOCAIS_TSE.items():
        if not os.path.exists(arquivo):
            avisos.append(f"Arquivo ausente: {arquivo}")
            continue

        try:
            df_tse = pd.read_excel(arquivo, engine="openpyxl")
        except Exception as erro:
            avisos.append(f"Não foi possível ler {arquivo}: {erro}")
            continue

        colunas_obrigatorias = {
            'AA_ELEICAO', 'NR_TURNO', 'CD_MUNICIPIO', 'NM_MUNICIPIO',
            'NR_ZONA', 'NR_SECAO', 'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO',
            'NM_BAIRRO', 'DS_ENDERECO', 'QT_ELEITOR_SECAO',
            'NR_LATITUDE', 'NR_LONGITUDE'
        }
        faltantes = colunas_obrigatorias.difference(df_tse.columns)
        if faltantes:
            avisos.append(
                f"{arquivo} sem as colunas: {', '.join(sorted(faltantes))}"
            )
            continue

        df_tse['NR_TURNO'] = pd.to_numeric(df_tse['NR_TURNO'], errors='coerce')
        df_tse = df_tse[df_tse['NR_TURNO'] == 1].copy()
        df_tse = df_tse.rename(columns={'AA_ELEICAO': 'ANO_ELEICAO'})

        for coluna in [
            'ANO_ELEICAO', 'CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO',
            'NR_LOCAL_VOTACAO', 'QT_ELEITOR_SECAO'
        ]:
            df_tse[coluna] = pd.to_numeric(
                df_tse[coluna], errors='coerce'
            ).astype('Int64')

        df_tse['lat'] = df_tse['NR_LATITUDE'].apply(
            lambda x: normalizar_coordenada_tse(x, 7, 12)
        )
        df_tse['lon'] = df_tse['NR_LONGITUDE'].apply(
            lambda x: normalizar_coordenada_tse(x, 65, 75)
        )
        df_tse['ID_LOCAL_ANO'] = (
            df_tse['ANO_ELEICAO'].astype(str) + '|' +
            df_tse['CD_MUNICIPIO'].astype(str) + '|' +
            df_tse['NR_ZONA'].astype(str) + '|' +
            df_tse['NR_LOCAL_VOTACAO'].astype(str)
        )
        df_tse['ID_LOCAL_HISTORICO'] = (
            df_tse['CD_MUNICIPIO'].astype(str) + '|' +
            df_tse['NR_ZONA'].astype(str) + '|' +
            df_tse['NR_LOCAL_VOTACAO'].astype(str)
        )
        bairro = df_tse['NM_BAIRRO'].fillna('').astype(str).str.upper()
        df_tse['RURAL_DECLARADO_TSE'] = bairro.str.contains(
            r'\bRURAL\b', regex=True
        )
        bases.append(df_tse)

    if not bases:
        raise RuntimeError(
            "Nenhuma planilha válida de locais do TSE foi carregada. "
            + " | ".join(avisos)
        )

    locais = pd.concat(bases, ignore_index=True)
    locais_rurais_historicos = set(
        locais.loc[locais['RURAL_DECLARADO_TSE'], 'ID_LOCAL_HISTORICO']
    )
    locais['RURAL_HISTORICO_TSE'] = locais['ID_LOCAL_HISTORICO'].isin(
        locais_rurais_historicos
    )

    texto_indicio = (
        locais['NM_LOCAL_VOTACAO'].fillna('').astype(str).str.upper() + ' ' +
        locais['NM_BAIRRO'].fillna('').astype(str).str.upper() + ' ' +
        locais['DS_ENDERECO'].fillna('').astype(str).str.upper()
    )
    texto_indicio = (
        texto_indicio.str.normalize('NFKD')
        .str.encode('ascii', errors='ignore')
        .str.decode('ascii')
        .str.replace(r'[^A-Z0-9]+', ' ', regex=True)
    )
    locais['INDICIO_RURAL'] = texto_indicio.str.contains(
        r'\bRURAL\b|RAMAL|SERINGAL|COLONIA|COMUNIDADE|'
        r'ASSENTAMENTO|ALDEIA|RESERVA|RODOVIA|\bBR\s*\d|\bAC\s*\d|\bKM\s*\d',
        regex=True
    )
    locais['CLASSIFICACAO_RURAL'] = np.select(
        [
            locais['RURAL_DECLARADO_TSE'],
            locais['RURAL_HISTORICO_TSE'],
            locais['INDICIO_RURAL'],
        ],
        ['RURAL', 'REVISAR', 'REVISAR'],
        default='URBANA'
    )
    locais['FONTE_CLASSIFICACAO_RURAL'] = np.select(
        [
            locais['RURAL_DECLARADO_TSE'],
            locais['RURAL_HISTORICO_TSE'],
            locais['INDICIO_RURAL'],
        ],
        [
            'Bairro identificado como rural no TSE',
            'O mesmo número de local foi rural em outra eleição',
            'Indício rural no nome, bairro ou endereço',
        ],
        default='Sem indício rural na planilha TSE'
    )
    locais['CONFIANCA_CLASSIFICACAO'] = np.select(
        [
            locais['RURAL_DECLARADO_TSE'],
            locais['RURAL_HISTORICO_TSE'],
            locais['INDICIO_RURAL'],
        ],
        ['ALTA', 'MÉDIA', 'BAIXA'],
        default='MÉDIA'
    )
    locais['OBSERVACAO_CLASSIFICACAO'] = ''

    for id_local, ajuste in AJUSTES_MANUAIS_ZONA_RURAL.items():
        mascara = locais['ID_LOCAL_ANO'] == id_local
        if mascara.any():
            locais.loc[mascara, 'CLASSIFICACAO_RURAL'] = ajuste.get(
                'CLASSIFICACAO_RURAL', 'REVISAR'
            )
            locais.loc[mascara, 'FONTE_CLASSIFICACAO_RURAL'] = (
                'Revisão manual documentada'
            )
            locais.loc[mascara, 'CONFIANCA_CLASSIFICACAO'] = 'ALTA'
            locais.loc[mascara, 'OBSERVACAO_CLASSIFICACAO'] = ajuste.get(
                'OBSERVACAO', ''
            )

    locais.attrs['avisos'] = avisos
    return locais


@st.cache_data
def carregar_validos_oficiais_por_local():
    """Reconstrói os votos válidos do cargo com as bases já usadas pelo app."""
    if not os.path.exists("base_concorrencia_ac.zip"):
        return pd.DataFrame()

    try:
        with zipfile.ZipFile("base_concorrencia_ac.zip", 'r') as arquivo_zip:
            nome_csv = arquivo_zip.namelist()[0]
            with arquivo_zip.open(nome_csv) as arquivo_csv:
                concorrencia = pd.read_csv(arquivo_csv)

        cargos_samir = {
            2020: 'Vereador',
            2022: 'Deputado Federal',
            2024: 'Vereador',
        }
        partes = []
        for ano, cargo in cargos_samir.items():
            parte = concorrencia[
                (concorrencia['ANO_ELEICAO'] == ano) &
                (concorrencia['DS_CARGO'] == cargo)
            ].copy()
            # Nas eleições municipais, a candidatura foi somente em Rio Branco.
            if ano in (2020, 2024):
                parte = parte[parte['NM_MUNICIPIO'] == 'RIO BRANCO']
            partes.append(parte)

        concorrencia = pd.concat(partes, ignore_index=True)
        locais_tse = carregar_locais_tse_rota_rural()
        mapa_secoes = locais_tse[[
            'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO',
            'NM_LOCAL_VOTACAO'
        ]].drop_duplicates()

        concorrencia = pd.merge(
            concorrencia,
            mapa_secoes,
            on=['ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
            how='inner'
        )
        return concorrencia.groupby(
            [
                'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA',
                'NM_LOCAL_VOTACAO'
            ],
            as_index=False,
            dropna=False
        ).agg(QT_VOTOS_VALIDOS_CARGO=('QT_VOTOS', 'sum'))
    except Exception:
        # Mantém o restante do painel disponível se alguma base auxiliar faltar.
        return pd.DataFrame()


# ==========================================
# BASES DO CENÁRIO ELEITORAL 2026
# ==========================================
ARQUIVOS_CENARIO_2026 = {
    'eleitorado': 'eleitorado_2026_ac.csv',
    'perfil': 'perfil_eleitorado_2026_ac.csv',
    'perfil_secao': 'perfil_secao_resumo_2026_ac.csv',
    'demografia_secao': 'perfil_secao_demografico_2026_ac.csv',
    'municipios': 'resumo_municipal_2026_ac.csv',
    'metadados': 'metadados_2026.json',
}


def normalizar_chave_texto(valor):
    """Padroniza nomes apenas para cruzamento técnico entre bases."""
    texto = '' if pd.isna(valor) else str(valor)
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ascii', errors='ignore').decode('ascii')
    texto = re.sub(r'[^A-Za-z0-9]+', ' ', texto.upper())
    return re.sub(r'\s+', ' ', texto).strip()


@st.cache_data
def carregar_bases_cenario_2026():
    """Carrega somente as bases tratadas de 2026 quando a rota 7 for aberta."""
    ausentes = [
        arquivo for arquivo in ARQUIVOS_CENARIO_2026.values()
        if not os.path.exists(arquivo)
    ]
    if ausentes:
        raise FileNotFoundError(
            'Arquivos de 2026 ausentes: ' + ', '.join(ausentes)
        )

    eleitorado = pd.read_csv(
        ARQUIVOS_CENARIO_2026['eleitorado'],
        dtype={'CD_MUNICIPIO': 'string'}
    )
    perfil = pd.read_csv(
        ARQUIVOS_CENARIO_2026['perfil'],
        dtype={'CD_MUNICIPIO': 'string'}
    )
    perfil_secao = pd.read_csv(
        ARQUIVOS_CENARIO_2026['perfil_secao'],
        dtype={'CD_MUNICIPIO': 'string'}
    )
    demografia_secao = pd.read_csv(
        ARQUIVOS_CENARIO_2026['demografia_secao'],
        dtype={'CD_MUNICIPIO': 'string'}
    )
    municipios = pd.read_csv(
        ARQUIVOS_CENARIO_2026['municipios'],
        dtype={'CD_MUNICIPIO': 'string'}
    )
    with open(
        ARQUIVOS_CENARIO_2026['metadados'], 'r', encoding='utf-8'
    ) as arquivo_metadados:
        metadados = json.load(arquivo_metadados)

    return eleitorado, perfil, perfil_secao, demografia_secao, municipios, metadados


def construir_matriz_oportunidades_2026(eleitorado_2026, historico):
    """Cruza o eleitorado atual com 2022, mantendo as eleições separadas.

    Os votos de 2022 são uma referência territorial, e não uma previsão para
    2026. O cruzamento usa município normalizado, zona e seção.
    """
    if eleitorado_2026.empty:
        return pd.DataFrame(), 0.0

    base_2026 = eleitorado_2026.copy()
    base_2026['CHAVE_MUNICIPIO'] = base_2026['NM_MUNICIPIO'].apply(
        normalizar_chave_texto
    )
    for coluna in ['NR_ZONA', 'NR_SECAO']:
        base_2026[coluna] = pd.to_numeric(
            base_2026[coluna], errors='coerce'
        ).astype('Int64')

    col_municipio_historico = next(
        (
            coluna for coluna in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']
            if coluna in historico.columns
        ),
        None
    )
    colunas_historicas = {
        'ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO', 'QT_VOTOS_SAMIR'
    }
    if (
        col_municipio_historico is None
        or not colunas_historicas.issubset(historico.columns)
    ):
        return pd.DataFrame(), 0.0

    votos_2022 = historico[
        pd.to_numeric(historico['ANO_ELEICAO'], errors='coerce') == 2022
    ].copy()
    if votos_2022.empty:
        return pd.DataFrame(), 0.0

    votos_2022['CHAVE_MUNICIPIO'] = votos_2022[
        col_municipio_historico
    ].apply(normalizar_chave_texto)
    for coluna in ['NR_ZONA', 'NR_SECAO', 'QT_VOTOS_SAMIR']:
        votos_2022[coluna] = pd.to_numeric(votos_2022[coluna], errors='coerce')
    votos_2022 = votos_2022.groupby(
        ['CHAVE_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
        as_index=False,
        dropna=False
    ).agg(VOTOS_REFERENCIA_2022=('QT_VOTOS_SAMIR', 'sum'))
    votos_2022['SECAO_COM_REFERENCIA_2022'] = True

    secoes = pd.merge(
        base_2026,
        votos_2022,
        on=['CHAVE_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
        how='left',
        validate='one_to_one'
    )
    secoes['SECAO_COM_REFERENCIA_2022'] = secoes[
        'SECAO_COM_REFERENCIA_2022'
    ].fillna(False).astype(bool)
    secoes['VOTOS_REFERENCIA_2022'] = secoes[
        'VOTOS_REFERENCIA_2022'
    ].fillna(0)

    matriz = secoes.groupby(
        [
            'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA',
            'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO', 'NM_BAIRRO',
            'DS_ENDERECO', 'LATITUDE', 'LONGITUDE', 'TERRITORIO_2026',
            'ID_LOCAL_2026'
        ],
        as_index=False,
        dropna=False
    ).agg(
        ELEITORES_2026=('QT_ELEITOR_SECAO', 'sum'),
        VOTOS_REFERENCIA_2022=('VOTOS_REFERENCIA_2022', 'sum'),
        SECOES_2026=('NR_SECAO', 'nunique'),
        SECOES_COM_REFERENCIA_2022=('SECAO_COM_REFERENCIA_2022', 'sum'),
        DS_SITU_LOCAL_VOTACAO=(
            'DS_SITU_LOCAL_VOTACAO',
            lambda serie: (
                serie.dropna().iloc[0]
                if serie.dropna().nunique() <= 1
                else 'MISTA'
            )
        )
    )
    matriz['PENETRACAO_REFERENCIA_PCT'] = np.where(
        matriz['ELEITORES_2026'] > 0,
        matriz['VOTOS_REFERENCIA_2022'] / matriz['ELEITORES_2026'] * 100,
        0
    )
    matriz['COBERTURA_SECOES_PCT'] = np.where(
        matriz['SECOES_2026'] > 0,
        matriz['SECOES_COM_REFERENCIA_2022'] / matriz['SECOES_2026'] * 100,
        0
    )
    cobertura = (
        secoes['SECAO_COM_REFERENCIA_2022'].mean() * 100
        if len(secoes) else 0.0
    )
    return matriz, float(cobertura)


def consolidar_eleitorado_2026_por_local(eleitorado_2026):
    """Consolida seções em um registro por local sem duplicar eleitores."""
    if eleitorado_2026.empty:
        return pd.DataFrame()
    return eleitorado_2026.groupby(
        [
            'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA',
            'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO', 'NM_BAIRRO',
            'DS_ENDERECO', 'LATITUDE', 'LONGITUDE', 'TERRITORIO_2026',
            'ID_LOCAL_2026'
        ],
        as_index=False,
        dropna=False
    ).agg(
        ELEITORES_2026=('QT_ELEITOR_SECAO', 'sum'),
        SECOES_2026=('NR_SECAO', 'nunique'),
        DS_SITU_LOCAL_VOTACAO=(
            'DS_SITU_LOCAL_VOTACAO',
            lambda serie: (
                serie.dropna().iloc[0]
                if serie.dropna().nunique() <= 1
                else 'MISTA'
            )
        )
    )


def inteiro_pt(valor):
    return f"{int(round(float(valor))):,}".replace(',', '.')


def percentual_pt(valor, casas=2):
    return f"{float(valor):.{casas}f}%".replace('.', ',')

try:
    dados = carregar_dados()
    dados = aplicar_zonas(dados) # Aplica a classificação urbana/rural com precisão
except:
    st.error("Erro ao carregar o arquivo 'dados.csv'.")
    st.stop()

# VERSAO_VALIDOS_CORRIGIDOS_2026_08_03
@st.cache_data
def consolidar_votos_por_local(df):
    """Consolida as seções sem repetir o total de válidos do local.

    Em dados.csv, QT_VOTOS_VALIDOS_SECAO contém o total do local de votação e
    aparece repetido nas linhas das seções em que o candidato teve votos.
    Portanto, os votos do candidato devem ser somados, enquanto o total de
    válidos deve ser considerado uma única vez por local, município, zona e ano.
    """
    if df.empty:
        return df.copy()

    base = df.copy()

    # Padroniza o nome do local pela chave oficial da seção. Isso evita separar
    # o mesmo local por pequenas diferenças de grafia entre os arquivos.
    if 'NR_SECAO' in base.columns:
        try:
            mapa_oficial = carregar_locais_tse_rota_rural()[[
                'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO',
                'NM_LOCAL_VOTACAO'
            ]].drop_duplicates().rename(columns={
                'NM_LOCAL_VOTACAO': 'NM_LOCAL_VOTACAO_TSE'
            })
            base = pd.merge(
                base,
                mapa_oficial,
                on=['ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
                how='left'
            )
            base['NM_LOCAL_VOTACAO'] = base[
                'NM_LOCAL_VOTACAO_TSE'
            ].fillna(base['NM_LOCAL_VOTACAO'])
            base = base.drop(columns=['NM_LOCAL_VOTACAO_TSE'])
        except Exception:
            pass

    chaves = [
        'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NM_LOCAL_VOTACAO'
    ]
    colunas_ausentes = [coluna for coluna in chaves if coluna not in base.columns]
    if colunas_ausentes:
        return base

    agregacoes = {'QT_VOTOS_SAMIR': 'sum'}
    if 'QT_VOTOS_VALIDOS_SECAO' in base.columns:
        agregacoes['QT_VOTOS_VALIDOS_SECAO'] = 'max'
    if 'lat' in base.columns:
        agregacoes['lat'] = 'median'
    if 'lon' in base.columns:
        agregacoes['lon'] = 'median'
    if 'TIPO_ZONA' in base.columns:
        agregacoes['TIPO_ZONA'] = 'first'

    consolidado = base.groupby(
        chaves, as_index=False, dropna=False
    ).agg(agregacoes)

    # Prioriza o denominador reconstruído para o mesmo cargo da candidatura.
    # O max() acima permanece como contingência caso as bases auxiliares faltem.
    validos_oficiais = carregar_validos_oficiais_por_local()
    if not validos_oficiais.empty:
        consolidado = pd.merge(
            consolidado, validos_oficiais, on=chaves, how='left'
        )
        if 'QT_VOTOS_VALIDOS_SECAO' in consolidado.columns:
            consolidado['QT_VOTOS_VALIDOS_SECAO'] = consolidado[
                'QT_VOTOS_VALIDOS_CARGO'
            ].fillna(consolidado['QT_VOTOS_VALIDOS_SECAO'])
        else:
            consolidado['QT_VOTOS_VALIDOS_SECAO'] = consolidado[
                'QT_VOTOS_VALIDOS_CARGO'
            ]
        consolidado = consolidado.drop(
            columns=['QT_VOTOS_VALIDOS_CARGO']
        )
    return consolidado

@st.cache_data
def carregar_demografia(df_votos):
    try:
        df_demo = pd.DataFrame()
        if os.path.exists("base_demografica_ac.zip"):
            with zipfile.ZipFile("base_demografica_ac.zip", 'r') as z:
                nome_arquivo = z.namelist()[0]
                with z.open(nome_arquivo) as f:
                    df_demo = pd.read_csv(f)
        else:
             return pd.DataFrame() 

        if not df_votos.empty and not df_demo.empty and 'NR_ZONA' in df_votos.columns and 'NR_SECAO' in df_votos.columns and 'NM_LOCAL_VOTACAO' in df_votos.columns:
            mapa_escolas = df_votos[['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO', 'NM_LOCAL_VOTACAO']].drop_duplicates()
            df_demo = pd.merge(df_demo, mapa_escolas, on=['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO'], how='inner')
            votos_escola = consolidar_votos_por_local(df_votos)
            votos_escola['MARKET_SHARE'] = np.where(votos_escola['QT_VOTOS_VALIDOS_SECAO'] > 0, votos_escola['QT_VOTOS_SAMIR'] / votos_escola['QT_VOTOS_VALIDOS_SECAO'], 0)
            chaves_demo = [
                coluna for coluna in [
                    'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA',
                    'NM_LOCAL_VOTACAO'
                ] if coluna in df_demo.columns and coluna in votos_escola.columns
            ]
            df_demo = pd.merge(
                df_demo,
                votos_escola[chaves_demo + ['QT_VOTOS_SAMIR', 'MARKET_SHARE']],
                on=chaves_demo,
                how='left'
            )
            df_demo['VOTOS_ESTIMADOS_SAMIR'] = df_demo['QT_ELEITORES_PERFIL'] * df_demo['MARKET_SHARE']
            fator_correcao = df_demo.groupby(['ANO_ELEICAO', 'NM_LOCAL_VOTACAO'])['VOTOS_ESTIMADOS_SAMIR'].transform('sum')
            fator_correcao = np.where(fator_correcao > 0, df_demo['QT_VOTOS_SAMIR'] / fator_correcao, 0)
            df_demo['VOTOS_ESTIMADOS_SAMIR'] = df_demo['VOTOS_ESTIMADOS_SAMIR'] * fator_correcao
        return df_demo
    except:
        return pd.DataFrame()

@st.cache_data
def carregar_adormecidos(df_votos):
    try:
        if os.path.exists("base_adormecidos_ac.csv"):
            df_ador = pd.read_csv("base_adormecidos_ac.csv")
            if not df_votos.empty and 'NR_ZONA' in df_votos.columns and 'NR_SECAO' in df_votos.columns and 'NM_LOCAL_VOTACAO' in df_votos.columns:
                mapa_escolas = df_votos[['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO', 'NM_LOCAL_VOTACAO']].drop_duplicates()
                df_ador = pd.merge(df_ador, mapa_escolas, on=['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO'], how='inner')
            return df_ador
        return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data
def carregar_concorrencia(df_votos):
    try:
        df_conc = pd.DataFrame()
        if os.path.exists("base_concorrencia_ac.zip"):
            with zipfile.ZipFile("base_concorrencia_ac.zip", 'r') as z:
                nome_arquivo = z.namelist()[0]
                with z.open(nome_arquivo) as f:
                    df_conc = pd.read_csv(f)
        else:
             return pd.DataFrame() 

        if not df_votos.empty and not df_conc.empty and 'NR_ZONA' in df_votos.columns and 'NR_SECAO' in df_votos.columns and 'NM_LOCAL_VOTACAO' in df_votos.columns:
            mapa_escolas = df_votos[['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO', 'NM_LOCAL_VOTACAO']].drop_duplicates()
            df_conc = pd.merge(df_conc, mapa_escolas, on=['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO'], how='inner')
        return df_conc
    except:
        return pd.DataFrame()

dados_demo = carregar_demografia(dados)
dados_adormecidos = carregar_adormecidos(dados)
dados_concorrencia = carregar_concorrencia(dados)

# ==========================================
# 3. BARRA LATERAL (MENUS E FILTROS)
# ==========================================
try:
    st.sidebar.image("IMG_3571.PNG", use_container_width=True)
except:
    pass 

st.sidebar.header("🧭 Navegação do Sistema")
menu_selecionado = st.sidebar.radio(
    "Selecione o Painel Desejado:",
    [
        "📊 1. Desempenho Eleitoral por Território",
        "👥 2. Composição do Eleitorado",
        "🗺️ 3. Participação e Não Comparecimento",
        "📋 4. Panorama da Concorrência",
        "🔗 5. Correlação territorial",
        "🚜 6. Análise Territorial da Zona Rural",
        "🗳️ 7. Cenário Eleitoral 2026"
    ]
)
st.sidebar.markdown("---")

rota_cenario_2026 = menu_selecionado == "🗳️ 7. Cenário Eleitoral 2026"

if rota_cenario_2026:
    st.sidebar.header("🎛️ Filtros do Cenário 2026")
    try:
        (
            eleitorado_2026,
            perfil_2026,
            perfil_secao_2026,
            demografia_secao_2026,
            resumo_municipal_2026,
            metadados_2026,
        ) = carregar_bases_cenario_2026()
        erro_bases_2026 = None
    except Exception as erro:
        eleitorado_2026 = pd.DataFrame()
        perfil_2026 = pd.DataFrame()
        perfil_secao_2026 = pd.DataFrame()
        demografia_secao_2026 = pd.DataFrame()
        resumo_municipal_2026 = pd.DataFrame()
        metadados_2026 = {}
        erro_bases_2026 = str(erro)

    municipios_2026_disponiveis = (
        sorted(eleitorado_2026['NM_MUNICIPIO'].dropna().unique())
        if not eleitorado_2026.empty else []
    )
    municipios_2026_selecionados = st.sidebar.multiselect(
        "Município(s):",
        municipios_2026_disponiveis,
        default=municipios_2026_disponiveis
    )
    territorio_2026_selecionado = st.sidebar.selectbox(
        "Território:",
        [
            "Todos os territórios",
            "RURAL IDENTIFICADA",
            "URBANA OU NÃO IDENTIFICADA COMO RURAL",
            "REVISAR CLASSIFICAÇÃO",
        ]
    )
    situacao_2026_selecionada = st.sidebar.selectbox(
        "Situação do local:",
        ["Todos os locais", "ATIVO", "BLOQUEADO"]
    )
    st.sidebar.caption(
        "Base 2026 separada da série histórica. Os filtros desta rota não "
        "alteram as análises de 2020, 2022 e 2024."
    )
else:
    st.sidebar.header("🎛️ Filtros de Análise")
    anos_disponiveis = sorted(dados['ANO_ELEICAO'].unique(), reverse=True)
    opcoes_ano = ['Todos os Anos (Série Histórica)'] + [str(a) for a in anos_disponiveis]
    ano_selecionado = st.sidebar.selectbox("Selecione o Período / Ano:", opcoes_ano)

    col_municipio = None
    texto_local = "em Todo o Estado"
    for col in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']:
        if col in dados.columns:
            col_municipio = col
            break

    if col_municipio:
        municipios_disponiveis = sorted(dados[col_municipio].dropna().unique())
        municipios_selecionados = st.sidebar.multiselect("Filtrar por Município(s):", municipios_disponiveis, default=municipios_disponiveis)
        dados = dados[dados[col_municipio].isin(municipios_selecionados)]
        if not municipios_selecionados or len(municipios_selecionados) == len(municipios_disponiveis):
            texto_local = "em Todo o Estado"
        elif len(municipios_selecionados) == 1:
            texto_local = f"em {municipios_selecionados[0].title()}"
        elif len(municipios_selecionados) == 2:
            texto_local = f"em {municipios_selecionados[0].title()} e {municipios_selecionados[1].title()}"
        else:
            texto_local = "nos Municípios Selecionados"

    st.sidebar.markdown("---")
    st.sidebar.header("🚜 Filtro de Localidade")
    zonas_disponiveis = ['Todas as Zonas', 'URBANA', 'RURAL']
    zona_selecionada = st.sidebar.selectbox("Selecione o Tipo de Zona:", zonas_disponiveis)

    if zona_selecionada != 'Todas as Zonas':
        dados = dados[dados['TIPO_ZONA'] == zona_selecionada]

    st.sidebar.caption("Versão 03/08/2026 • válidos consolidados por local")

    st.sidebar.markdown("---")
    mostrar_todas = st.sidebar.checkbox("👁️ Exibir TODOS os locais", value=False)
    limite_slider = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5, disabled=mostrar_todas)
    limite_ranking = 999999 if mostrar_todas else limite_slider

    label_periodo = "Série Histórica Acumulada" if ano_selecionado == 'Todos os Anos (Série Histórica)' else f"Ano de {ano_selecionado}"

# ==========================================
# ROTA 1: DESEMPENHO ELEITORAL POR TERRITÓRIO
# ==========================================
if menu_selecionado == "📊 1. Desempenho Eleitoral por Território":
    st.title(f"📊 Desempenho Eleitoral por Território - {label_periodo}")

    st.info("""
    **Como interpretar este módulo**

    Os gráficos descrevem a distribuição histórica dos votos por local de votação.
    Comparações entre anos devem considerar possíveis mudanças de cargo, eleitorado
    e contexto da eleição.
    """)

    if ano_selecionado == 'Todos os Anos (Série Histórica)':
        dados_filtrados_secoes = dados.copy()
    else:
        dados_filtrados_secoes = dados[
            dados['ANO_ELEICAO'] == int(ano_selecionado)
        ].copy()

    dados_filtrados = consolidar_votos_por_local(dados_filtrados_secoes)

    st.caption(
        "Critério de cálculo: votos do candidato são somados entre as seções; "
        "votos válidos são contados uma única vez por local de votação, ano, "
        "município e zona."
    )

    total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
    total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

    col1, col2 = st.columns(2)
    col1.metric(label=f"Total de Votos ({label_periodo})", value=f"{total_votos:,}".replace(",", "."))
    col2.metric(label="Locais de Votação Mapeados", value=total_escolas)

    st.markdown("---")

    st.subheader(f"📍 Mapa de Distribuição Geográfica ({label_periodo} {texto_local})")
    group_cols = ['NM_LOCAL_VOTACAO', 'lat', 'lon']
    if col_municipio:
        group_cols.append(col_municipio)

    dados_mapa = dados_filtrados.groupby(group_cols, as_index=False)['QT_VOTOS_SAMIR'].sum()
    dados_mapa = dados_mapa.dropna(subset=['lat', 'lon'])

    if not dados_mapa.empty:
        st.map(dados_mapa, latitude='lat', longitude='lon')
    else:
        st.info("Nenhum dado geográfico disponível para os filtros selecionados.")

    st.markdown("---")

    texto_top = "Todos os Locais" if mostrar_todas else f"Top {limite_ranking}"
    st.subheader(f"📊 Votos e Participação nos Válidos ({texto_top} - {label_periodo})")

    agg_dict = {'QT_VOTOS_SAMIR': 'sum'}
    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        agg_dict['QT_VOTOS_VALIDOS_SECAO'] = 'sum'

    top_escolas = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg(agg_dict).reset_index()

    if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
        top_escolas['MARKET_SHARE'] = (top_escolas['QT_VOTOS_SAMIR'] / top_escolas['QT_VOTOS_VALIDOS_SECAO']) * 100
        top_escolas['MARKET_SHARE'] = top_escolas['MARKET_SHARE'].fillna(0).round(1)
    else:
        top_escolas['MARKET_SHARE'] = 0.0

    top_escolas = top_escolas.sort_values(by='QT_VOTOS_SAMIR', ascending=False).head(limite_ranking)
    altura_grafico = max(500, len(top_escolas) * 35)

    grafico_barras = alt.Chart(top_escolas).mark_bar(color="#1A73E8").encode(
        x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Obtidos', axis=alt.Axis(tickMinStep=1, format='d')),
        y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title=None, axis=alt.Axis(labelLimit=1000, labelOverlap=False)),
        tooltip=['NM_LOCAL_VOTACAO:N', 'QT_VOTOS_SAMIR:Q', alt.Tooltip('MARKET_SHARE:Q', title='Participação nos válidos (%)', format='.1f')]
    ).properties(height=altura_grafico)
    exibir_grafico_altair(grafico_barras)

    if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
        top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Participação nos Válidos (%)']
    else:
        top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Participação nos Válidos (%)']
    st.dataframe(top_escolas, use_container_width=True)

    st.markdown("---")

    st.subheader("📈 Matriz de Evolução Histórica (Comparativo entre Eleições)")
    if len(anos_disponiveis) > 1:
        tabela_comparativa = dados.pivot_table(index='NM_LOCAL_VOTACAO', columns='ANO_ELEICAO', values='QT_VOTOS_SAMIR', aggfunc='sum').fillna(0)
        ano_recente = anos_disponiveis[0]
        if ano_recente in tabela_comparativa.columns:
            tabela_comparativa = tabela_comparativa.sort_values(by=ano_recente, ascending=False).head(limite_ranking)
        st.dataframe(tabela_comparativa, use_container_width=True)
    else:
        st.info("ℹ️ A base de dados atual possui apenas um ano eleitoral registrado.")

    st.markdown("---")

    st.subheader("🎯 Distribuição entre Votos do Candidato e Demais Votos Válidos")
    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        agenda_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        agenda_df['VOTOS_EM_DISPUTA'] = agenda_df['QT_VOTOS_VALIDOS_SECAO'] - agenda_df['QT_VOTOS_SAMIR']
        limite_reduto = agenda_df['QT_VOTOS_SAMIR'].quantile(0.75)
        agenda_df['ESTRATEGIA'] = np.where(agenda_df['QT_VOTOS_SAMIR'] > limite_reduto, 'Alta votação histórica', 'Demais locais')
        agenda_df = agenda_df.sort_values(by='VOTOS_EM_DISPUTA', ascending=False).head(limite_ranking)

        scatter = alt.Chart(agenda_df).mark_circle(size=350).encode(
            x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Históricos do Candidato'),
            y=alt.Y('VOTOS_EM_DISPUTA:Q', title='Demais Votos Válidos'),
            color=alt.Color('ESTRATEGIA:N', title='Faixa de desempenho', scale=alt.Scale(domain=['Alta votação histórica', 'Demais locais'], range=['#25D366', '#A7B0BE'])),
            tooltip=['NM_LOCAL_VOTACAO', 'VOTOS_EM_DISPUTA', 'QT_VOTOS_SAMIR']
        ).properties(height=450)
        exibir_grafico_altair(scatter)
    else:
        st.warning("A coluna 'QT_VOTOS_VALIDOS_SECAO' não está presente.")

    st.markdown("---")

    st.subheader("🧩 Matriz Descritiva dos Locais de Votação")

    st.markdown("""
    > **Como ler:** o eixo horizontal mostra o total de votos válidos e o eixo
    > vertical mostra os votos históricos do candidato. As linhas pontilhadas usam
    > as médias da seleção e dividem os locais em quatro grupos descritivos.
    """)

    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        matriz_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        matriz_df = matriz_df.sort_values(by='QT_VOTOS_VALIDOS_SECAO', ascending=False).head(limite_ranking)
        media_tamanho = matriz_df['QT_VOTOS_VALIDOS_SECAO'].mean()
        media_votos = matriz_df['QT_VOTOS_SAMIR'].mean()

        def classificar_quadrante(row):
            escola_grande = row['QT_VOTOS_VALIDOS_SECAO'] >= media_tamanho
            samir_forte = row['QT_VOTOS_SAMIR'] >= media_votos
            if escola_grande and samir_forte: return "Alta votação em local de grande volume"
            elif escola_grande and not samir_forte: return "Baixa penetração histórica"
            elif not escola_grande and samir_forte: return "Alta votação em local de menor volume"
            else: return "Monitoramento"

        matriz_df['CLASSIFICACAO'] = matriz_df.apply(classificar_quadrante, axis=1)

        scatter_matriz = alt.Chart(matriz_df).mark_circle(size=400).encode(
            x=alt.X('QT_VOTOS_VALIDOS_SECAO:Q', title='Votos Válidos'),
            y=alt.Y('QT_VOTOS_SAMIR:Q', title='Votos Históricos do Candidato'),
            color=alt.Color(
                'CLASSIFICACAO:N',
                title='Classificação descritiva',
                scale=alt.Scale(
                    domain=[
                        "Alta votação em local de grande volume",
                        "Baixa penetração histórica",
                        "Alta votação em local de menor volume",
                        "Monitoramento"
                    ],
                    range=['#1A73E8', '#25D366', '#FFC107', '#A7B0BE']
                )
            ),
            tooltip=['NM_LOCAL_VOTACAO', 'CLASSIFICACAO', alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', format=','), alt.Tooltip('QT_VOTOS_SAMIR:Q', format=',')]
        ).properties(height=500)

        regra_x = alt.Chart(pd.DataFrame({'x': [media_tamanho]})).mark_rule(strokeDash=[5, 5], color='gray').encode(x='x:Q')
        regra_y = alt.Chart(pd.DataFrame({'y': [media_votos]})).mark_rule(strokeDash=[5, 5], color='gray').encode(y='y:Q')
        exibir_grafico_altair(scatter_matriz + regra_x + regra_y)

    st.markdown("---")

    st.subheader("📈 Concentração dos Votos Históricos por Local")
    if not dados_filtrados.empty:
        pareto_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().reset_index().sort_values(by='QT_VOTOS_SAMIR', ascending=False)
        pareto_df['Votos Acumulados'] = pareto_df['QT_VOTOS_SAMIR'].cumsum()
        pareto_df['% Acumulado'] = (pareto_df['Votos Acumulados'] / pareto_df['QT_VOTOS_SAMIR'].sum()) * 100
        pareto_df['Posição no Ranking'] = range(1, len(pareto_df) + 1)

        curva = alt.Chart(pareto_df).mark_line(color='#E83E8C', strokeWidth=4, point=alt.OverlayMarkDef(color='#E83E8C', size=150)).encode(
            x=alt.X('Posição no Ranking:Q', title='Quantidade de Locais'),
            y=alt.Y('% Acumulado:Q', title='% Acumulada', scale=alt.Scale(domain=[0, 100])),
            tooltip=['NM_LOCAL_VOTACAO:N', alt.Tooltip('% Acumulado:Q', format='.1f')]
        ).properties(height=400)

        area = curva.mark_area(color='#E83E8C', opacity=0.2)
        linha_80 = alt.Chart(pd.DataFrame({'y': [80]})).mark_rule(strokeDash=[5, 5], color='red', strokeWidth=2).encode(y='y:Q')
        exibir_grafico_altair(area + curva + linha_80)

    st.markdown("---")

    st.subheader("🏁 Meta proporcional de referência")

    st.info("""
    Este cenário distribui uma meta global proporcionalmente ao peso histórico de
    cada local nos votos válidos. É uma referência matemática; não representa
    previsão nem garantia de resultado futuro.
    """)

    meta_global = st.number_input("Digite a Meta Global de Votos:", min_value=1, value=11000, step=500)

    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        metas_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({
            'QT_VOTOS_VALIDOS_SECAO': 'sum',
            'QT_VOTOS_SAMIR': 'sum'
        }).reset_index()

        total_validos_estado = metas_df['QT_VOTOS_VALIDOS_SECAO'].sum()

        if total_validos_estado > 0:
            metas_df['Peso_Calc'] = metas_df['QT_VOTOS_VALIDOS_SECAO'] / total_validos_estado
            metas_df['Meta proporcional de referência'] = (meta_global * metas_df['Peso_Calc']).astype(int)

            metas_df['Diferença para o Cenário'] = metas_df['Meta proporcional de referência'] - metas_df['QT_VOTOS_SAMIR']
            metas_df['Diferença para o Cenário'] = metas_df['Diferença para o Cenário'].apply(lambda x: max(0, x))

            metas_df['Peso do Local'] = (metas_df['Peso_Calc'] * 100).round(2).astype(str) + '%'

            metas_df = metas_df.sort_values(by='Diferença para o Cenário', ascending=False).head(limite_ranking)

            tabela_final_metas = metas_df[['NM_LOCAL_VOTACAO', 'Peso do Local', 'Meta proporcional de referência', 'QT_VOTOS_SAMIR', 'Diferença para o Cenário']]
            tabela_final_metas.columns = ['Local de Votação', 'Peso na Eleição', 'Meta proporcional de referência', 'Votos Históricos', 'Diferença para o Cenário']

            st.markdown(f"#### 📋 Distribuição Matemática de Metas ({texto_top})")
            st.dataframe(tabela_final_metas, use_container_width=True)
    else:
        st.warning("A coluna de Votos Válidos não está disponível para calcular a proporção da meta.")

# ==========================================
# ROTA 2: COMPOSIÇÃO DO ELEITORADO
# ==========================================
elif menu_selecionado == "👥 2. Composição do Eleitorado":
    st.title(f"👥 Composição Estimada do Eleitorado - {label_periodo}")

    st.info("""
    Este módulo combina a composição agregada do eleitorado do TSE com a
    participação histórica do candidato em cada local. Os resultados são estimativas
    proporcionais: não identificam eleitores individuais nem comprovam o perfil de
    quem votou em determinada candidatura.
    """)

    if dados_demo.empty:
        st.error("⚠️ A base 'base_demografica_ac.zip' não foi encontrada. Faça o upload do arquivo ZIP diretamente pelo site do GitHub.")
    else:
        df_demo_macro = dados_demo.copy()
        if ano_selecionado != 'Todos os Anos (Série Histórica)':
            df_demo_macro = df_demo_macro[df_demo_macro['ANO_ELEICAO'] == int(ano_selecionado)]
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_x' in df_demo_macro.columns:
                df_demo_macro = df_demo_macro[df_demo_macro['NM_MUNICIPIO_x'].isin(municipios_selecionados) | df_demo_macro['NM_MUNICIPIO_y'].isin(municipios_selecionados)]
            elif 'NM_MUNICIPIO' in df_demo_macro.columns:
                 df_demo_macro = df_demo_macro[df_demo_macro['NM_MUNICIPIO'].isin(municipios_selecionados)]

        df_demo_filtrado = df_demo_macro.copy()

        escolas_tse = ["Visão Macro (Todas as Selecionadas)"] + sorted(df_demo_filtrado['NM_LOCAL_VOTACAO'].dropna().unique().tolist())
        escola_alvo = st.selectbox("Aprofundar a análise em um Local de Votação:", escolas_tse)

        if escola_alvo != "Visão Macro (Todas as Selecionadas)":
            df_demo_filtrado = df_demo_filtrado[df_demo_filtrado['NM_LOCAL_VOTACAO'] == escola_alvo]
            st.markdown(f"**Analisando a Base em:** {escola_alvo}")
        else:
            st.markdown(f"**Analisando a Base:** {texto_local}")

        total_votos_estimados = df_demo_filtrado['VOTOS_ESTIMADOS_SAMIR'].sum()
        st.metric("Votos Estimados na Seleção", f"{int(total_votos_estimados):,}".replace(',', '.'))
        st.markdown("---")

        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.subheader("Distribuição por Gênero")
            df_genero = df_demo_filtrado.groupby('DS_GENERO', as_index=False)['VOTOS_ESTIMADOS_SAMIR'].sum()
            df_genero['VOTOS_ESTIMADOS_SAMIR'] = df_genero['VOTOS_ESTIMADOS_SAMIR'].astype(int)
            df_genero['Percentual'] = (df_genero['VOTOS_ESTIMADOS_SAMIR'] / total_votos_estimados) * 100
            grafico_genero = alt.Chart(df_genero).mark_arc(innerRadius=65).encode(
                theta=alt.Theta(field="VOTOS_ESTIMADOS_SAMIR", type="quantitative"),
                color=alt.Color(field="DS_GENERO", type="nominal", scale=alt.Scale(domain=['FEMININO', 'MASCULINO', 'NÃO INFORMADO'], range=['#E83E8C', '#1A73E8', '#808080'])),
                tooltip=['DS_GENERO:N', 'VOTOS_ESTIMADOS_SAMIR:Q', 'Percentual:Q']
            ).properties(height=350)
            exibir_grafico_altair(grafico_genero)

        with col_graf2:
            st.subheader("Faixa Etária do Eleitorado")
            df_idade = df_demo_filtrado.groupby('DS_FAIXA_ETARIA', as_index=False)['VOTOS_ESTIMADOS_SAMIR'].sum()
            df_idade['VOTOS_ESTIMADOS_SAMIR'] = df_idade['VOTOS_ESTIMADOS_SAMIR'].astype(int)
            altura_idade = max(350, len(df_idade) * 28)
            grafico_idade = alt.Chart(df_idade).mark_bar(color="#0A1C2E").encode(
                x=alt.X('VOTOS_ESTIMADOS_SAMIR:Q', title='Qtd. Votos (Estimado)', axis=alt.Axis(format='d')),
                y=alt.Y('DS_FAIXA_ETARIA:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                tooltip=['DS_FAIXA_ETARIA:N', alt.Tooltip('VOTOS_ESTIMADOS_SAMIR:Q', format=',')]
            ).properties(height=altura_idade)
            exibir_grafico_altair(grafico_idade)

        st.markdown("---")
        st.subheader("Grau de Instrução (Nível de Escolaridade)")
        df_escola = df_demo_filtrado.groupby('DS_GRAU_ESCOLARIDADE', as_index=False)['VOTOS_ESTIMADOS_SAMIR'].sum()
        df_escola['VOTOS_ESTIMADOS_SAMIR'] = df_escola['VOTOS_ESTIMADOS_SAMIR'].astype(int)
        altura_escola = max(350, len(df_escola) * 28)

        grafico_escola = alt.Chart(df_escola).mark_bar(color="#1A73E8").encode(
            x=alt.X('VOTOS_ESTIMADOS_SAMIR:Q', title='Quantidade de Votos (Estimado)', axis=alt.Axis(format='d')),
            y=alt.Y('DS_GRAU_ESCOLARIDADE:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
            tooltip=['DS_GRAU_ESCOLARIDADE:N', alt.Tooltip('VOTOS_ESTIMADOS_SAMIR:Q', format=',')]
        ).properties(height=altura_escola)
        exibir_grafico_altair(grafico_escola)

        st.markdown("---")

        # --- FUNÇÃO: DISTRIBUIÇÃO ESTIMADA POR PERFIL ---
        st.subheader("📍 Hipótese a validar por perfil demográfico")

        st.info("""
        A comparação abaixo parte dos dois perfis com maior estimativa proporcional
        na seleção. Ela descreve a presença desses perfis nos locais de votação, mas
        não permite concluir intenção de voto individual nem estimar conversão futura.
        """)

        avatar_df = df_demo_macro.groupby(['DS_GENERO', 'DS_FAIXA_ETARIA'])['VOTOS_ESTIMADOS_SAMIR'].sum().reset_index()
        if not avatar_df.empty:
            avatar_df = avatar_df.sort_values(by='VOTOS_ESTIMADOS_SAMIR', ascending=False)

            def renderizar_radar_avatar(posicao_label, top_avatar_row, cor_barra):
                avatar_genero = top_avatar_row['DS_GENERO']
                avatar_idade = top_avatar_row['DS_FAIXA_ETARIA']

                st.success(f"**{posicao_label} Perfil estimado de maior volume:** **{avatar_genero}**, na faixa etária de **{avatar_idade}**.")

                df_alvo = df_demo_macro[(df_demo_macro['DS_GENERO'] == avatar_genero) & (df_demo_macro['DS_FAIXA_ETARIA'] == avatar_idade)].copy()
                df_alvo['VOTOS_NAO_CONQUISTADOS'] = df_alvo['QT_ELEITORES_PERFIL'] - df_alvo['VOTOS_ESTIMADOS_SAMIR']
                df_alvo['VOTOS_NAO_CONQUISTADOS'] = df_alvo['VOTOS_NAO_CONQUISTADOS'].apply(lambda x: max(0, x))

                radar_df = df_alvo.groupby('NM_LOCAL_VOTACAO').agg({
                    'QT_ELEITORES_PERFIL': 'sum', 
                    'VOTOS_ESTIMADOS_SAMIR': 'sum', 
                    'VOTOS_NAO_CONQUISTADOS': 'sum'
                }).reset_index()

                radar_df = radar_df.sort_values(by='VOTOS_NAO_CONQUISTADOS', ascending=False).head(limite_ranking)

                tabela_radar = radar_df.copy()
                tabela_radar['QT_ELEITORES_PERFIL'] = tabela_radar['QT_ELEITORES_PERFIL'].round(0).astype(int)
                tabela_radar['VOTOS_ESTIMADOS_SAMIR'] = tabela_radar['VOTOS_ESTIMADOS_SAMIR'].round(0).astype(int)
                tabela_radar['VOTOS_NAO_CONQUISTADOS'] = tabela_radar['VOTOS_NAO_CONQUISTADOS'].round(0).astype(int)

                tabela_radar.columns = ['Local de Votação', f'Total de {avatar_genero.title()}s ({avatar_idade})', 'Votos Estimados', 'Diferença entre Perfil e Estimativa']
                st.dataframe(tabela_radar, use_container_width=True)

                grafico_radar = alt.Chart(radar_df).mark_bar(color=cor_barra).encode(
                    x=alt.X('VOTOS_NAO_CONQUISTADOS:Q', title='Diferença entre Perfil e Estimativa', axis=alt.Axis(format='d')),
                    y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title=None, axis=alt.Axis(labelLimit=1000)),
                    tooltip=[
                        alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local de Votação'),
                        alt.Tooltip('VOTOS_NAO_CONQUISTADOS:Q', title='Diferença estimada', format=','),
                        alt.Tooltip('QT_ELEITORES_PERFIL:Q', title='Total deste Perfil no Local', format=',')
                    ]
                ).properties(height=max(400, len(radar_df) * 35))
                exibir_grafico_altair(grafico_radar)

            # Renderiza o 1º Avatar
            if len(avatar_df) >= 1:
                renderizar_radar_avatar("1º", avatar_df.iloc[0], "#FF8C00") # Laranja

            # Renderiza o 2º Avatar
            if len(avatar_df) >= 2:
                st.markdown("---")
                renderizar_radar_avatar("2º", avatar_df.iloc[1], "#1A73E8") # Azul Corporativo
        else:
            st.warning("Não há dados demográficos suficientes para esta análise na seleção atual.")


# ==========================================
# ROTA 3: PARTICIPAÇÃO E NÃO COMPARECIMENTO
# ==========================================
elif menu_selecionado == "🗺️ 3. Participação e Não Comparecimento":
    st.title(f"🗺️ Participação, abstenções, brancos e nulos - {label_periodo}")

    st.info("""
    Este módulo descreve abstenções, votos brancos e votos nulos por local de
    votação. Esses dados não revelam a motivação individual e não devem ser
    interpretados como votos automaticamente disponíveis para qualquer candidatura.
    """)

    if dados_adormecidos.empty:
        st.error("⚠️ A base 'base_adormecidos_ac.csv' não foi encontrada. Faça o upload do arquivo para o GitHub.")
    else:
        df_ador_filtrado = dados_adormecidos.copy()
        if ano_selecionado != 'Todos os Anos (Série Histórica)':
            df_ador_filtrado = df_ador_filtrado[df_ador_filtrado['ANO_ELEICAO'] == int(ano_selecionado)]
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_x' in df_ador_filtrado.columns:
                 df_ador_filtrado = df_ador_filtrado[df_ador_filtrado['NM_MUNICIPIO_x'].isin(municipios_selecionados) | df_ador_filtrado['NM_MUNICIPIO_y'].isin(municipios_selecionados)]
            elif 'NM_MUNICIPIO' in df_ador_filtrado.columns:
                 df_ador_filtrado = df_ador_filtrado[df_ador_filtrado['NM_MUNICIPIO'].isin(municipios_selecionados)]

        ador_escola = df_ador_filtrado.groupby(['NM_LOCAL_VOTACAO'], as_index=False).agg({
            'QT_APTOS': 'sum', 'VOTOS_ADORMECIDOS': 'sum', 'QT_ABSTENCOES': 'sum',
            'QT_VOTOS_BRANCOS': 'sum', 'QT_VOTOS_NULOS': 'sum'
        })

        coords = dados[['NM_LOCAL_VOTACAO', 'lat', 'lon']].drop_duplicates(subset=['NM_LOCAL_VOTACAO'])
        ador_escola = pd.merge(ador_escola, coords, on='NM_LOCAL_VOTACAO', how='left')

        total_adormecidos = ador_escola['VOTOS_ADORMECIDOS'].sum()
        total_aptos = ador_escola['QT_APTOS'].sum()
        taxa_adormecidos = (total_adormecidos / total_aptos) * 100 if total_aptos > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Abstenções, brancos e nulos", f"{int(total_adormecidos):,}".replace(',', '.'))
        col2.metric("Percentual sobre Eleitores Aptos", f"{taxa_adormecidos:.1f}%")
        col3.metric("Abstenções", f"{int(ador_escola['QT_ABSTENCOES'].sum()):,}".replace(',', '.'))

        st.markdown("---")

        st.subheader("📍 Dispersão Geográfica das Abstenções")
        mapa_ador = ador_escola.dropna(subset=['lat', 'lon'])
        if not mapa_ador.empty:
            st.map(mapa_ador, latitude='lat', longitude='lon')
        else:
            st.info("Dados de localização não disponíveis para este filtro.")

        st.markdown("---")

        st.subheader("📊 Locais com maior volume de abstenções, brancos e nulos")
        ador_top = ador_escola.sort_values(by='VOTOS_ADORMECIDOS', ascending=False).head(limite_ranking)

        altura_ador = max(500, len(ador_top) * 35)

        grafico_ador = alt.Chart(ador_top).mark_bar(color="#E83E8C").encode(
            x=alt.X('VOTOS_ADORMECIDOS:Q', title='Abstenções, brancos e nulos', axis=alt.Axis(format='d')),
            y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
            tooltip=[
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
                alt.Tooltip('VOTOS_ADORMECIDOS:Q', title='Total', format=','),
                alt.Tooltip('QT_ABSTENCOES:Q', title='Abstenções', format=','),
                alt.Tooltip('QT_VOTOS_BRANCOS:Q', title='Brancos', format=','),
                alt.Tooltip('QT_VOTOS_NULOS:Q', title='Nulos', format=','),
                alt.Tooltip('QT_APTOS:Q', title='Total de Aptos', format=',')
            ]
        ).properties(height=altura_ador)
        exibir_grafico_altair(grafico_ador)

        st.markdown("#### 📋 Detalhamento da Participação")
        tabela_ador = ador_top[['NM_LOCAL_VOTACAO', 'VOTOS_ADORMECIDOS', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_VOTOS_NULOS', 'QT_APTOS']]
        tabela_ador.columns = ['Local de Votação', 'Abstenções + brancos + nulos', 'Abstenções', 'Brancos', 'Nulos', 'Eleitores Aptos']
        st.dataframe(tabela_ador, use_container_width=True)


# ==========================================
# ROTA 4: PANORAMA DA CONCORRÊNCIA
# ==========================================
elif menu_selecionado == "📋 4. Panorama da Concorrência":
    st.title(f"📋 Panorama da Concorrência - {label_periodo}")

    st.info("""
    Este módulo mostra a distribuição dos votos entre as demais candidaturas no
    local e cargo selecionados. Os percentuais são descritivos e ajudam a observar
    concentração ou fragmentação da votação naquele recorte.
    """)

    if dados_concorrencia.empty:
        st.error("⚠️ A base 'base_concorrencia_ac.zip' não foi encontrada. Faça o upload do arquivo ZIP para o GitHub.")
    else:
        df_conc_filtrado = dados_concorrencia.copy()
        if ano_selecionado != 'Todos os Anos (Série Histórica)':
            df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['ANO_ELEICAO'] == int(ano_selecionado)]
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_x' in df_conc_filtrado.columns:
                 df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['NM_MUNICIPIO_x'].isin(municipios_selecionados) | df_conc_filtrado['NM_MUNICIPIO_y'].isin(municipios_selecionados)]
            elif 'NM_MUNICIPIO' in df_conc_filtrado.columns:
                 df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['NM_MUNICIPIO'].isin(municipios_selecionados)]

        escolas_conc = sorted(df_conc_filtrado['NM_LOCAL_VOTACAO'].dropna().unique().tolist())
        escola_alvo = st.selectbox("Selecione o Local de Votação:", escolas_conc)

        df_alvo = df_conc_filtrado[df_conc_filtrado['NM_LOCAL_VOTACAO'] == escola_alvo]

        cargos_disponiveis = df_alvo['DS_CARGO'].dropna().unique().tolist()
        cargo_selecionado = st.selectbox("Selecione o Cargo Disputado:", cargos_disponiveis)
        df_alvo = df_alvo[df_alvo['DS_CARGO'] == cargo_selecionado]

        adversarios = df_alvo.groupby('NM_VOTAVEL', as_index=False)['QT_VOTOS'].sum()
        adversarios = adversarios[~adversarios['NM_VOTAVEL'].str.contains("SAMIR", case=False, na=False)]
        adversarios = adversarios.sort_values(by='QT_VOTOS', ascending=False)

        total_votos_escola = adversarios['QT_VOTOS'].sum()

        if total_votos_escola > 0:
            adversarios['Share (%)'] = (adversarios['QT_VOTOS'] / total_votos_escola) * 100
            top_1 = adversarios.iloc[0]

            st.markdown(f"#### 📊 Distribuição em: **{escola_alvo}**")

            col1, col2 = st.columns(2)
            col1.metric("Candidatura Mais Votada", top_1['NM_VOTAVEL'])
            col2.metric("Participação", f"{top_1['Share (%)']:.1f}%")

            st.markdown("---")

            adversarios_grafico = adversarios.head(20) 
            altura_adv = max(500, len(adversarios_grafico) * 35)

            grafico_adv = alt.Chart(adversarios_grafico).mark_bar(color="#FFC107").encode(
                x=alt.X('QT_VOTOS:Q', title='Votos da Candidatura', axis=alt.Axis(format='d')),
                y=alt.Y('NM_VOTAVEL:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                tooltip=[
                    alt.Tooltip('NM_VOTAVEL:N', title='Candidato'),
                    alt.Tooltip('QT_VOTOS:Q', title='Votos', format=','),
                alt.Tooltip('Share (%):Q', title='Participação (%)', format='.1f')
                ]
            ).properties(height=altura_adv)
            exibir_grafico_altair(grafico_adv)

            st.markdown("#### 📋 Concorrentes no local")
            tabela_adv = adversarios[['NM_VOTAVEL', 'QT_VOTOS', 'Share (%)']]
            tabela_adv.columns = ['Candidatura', 'Votos no Local', 'Participação (%)']
            tabela_adv['Participação (%)'] = tabela_adv['Participação (%)'].round(2).astype(str) + '%'
            st.dataframe(tabela_adv.head(50), use_container_width=True)
        else:
            st.warning("Não há dados de concorrência suficientes para este local/cargo nos filtros selecionados.")


# ==========================================
# ROTA 5: CORRELAÇÃO TERRITORIAL
# ==========================================
elif menu_selecionado == "🔗 5. Correlação territorial":
    st.title(f"🔗 Correlação territorial entre candidaturas - {label_periodo}")

    st.info("""
    O coeficiente de Pearson mede se os votos de candidaturas variam de forma
    semelhante entre seções eleitorais. Correlação não prova transferência de
    votos, aliança, preferência conjunta nem causalidade.
    """)

    if dados_concorrencia.empty or ano_selecionado == 'Todos os Anos (Série Histórica)':
        st.warning("⚠️ Selecione um **Ano Específico** (por exemplo, 2022 ou 2024). A mistura de eleições e cargos diferentes distorce a correlação.")
    else:
        df_conc_filtrado = dados_concorrencia[dados_concorrencia['ANO_ELEICAO'] == int(ano_selecionado)].copy()
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_x' in df_conc_filtrado.columns:
                 df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['NM_MUNICIPIO_x'].isin(municipios_selecionados) | df_conc_filtrado['NM_MUNICIPIO_y'].isin(municipios_selecionados)]
            elif 'NM_MUNICIPIO' in df_conc_filtrado.columns:
                 df_conc_filtrado = df_conc_filtrado[df_conc_filtrado['NM_MUNICIPIO'].isin(municipios_selecionados)]

        cargos_disponiveis = df_conc_filtrado['DS_CARGO'].dropna().unique().tolist()
        cargo_alvo = st.selectbox("🎯 Selecione o Cargo para cruzar com os votos do Samir:", cargos_disponiveis)

        votos_samir_secao = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].groupby('NR_SECAO', as_index=False)['QT_VOTOS_SAMIR'].sum()
        df_alvo = df_conc_filtrado[df_conc_filtrado['DS_CARGO'] == cargo_alvo]

        if df_alvo.empty:
            st.info("Nenhum dado encontrado para o cargo selecionado.")
        else:
            pivot_alvo = df_alvo.pivot_table(index='NR_SECAO', columns='NM_VOTAVEL', values='QT_VOTOS', aggfunc='sum').fillna(0)
            base_correlacao = pd.merge(votos_samir_secao, pivot_alvo, on='NR_SECAO', how='inner')

            if len(base_correlacao) > 5: 
                matriz_corr = base_correlacao.drop(columns=['NR_SECAO']).corr()
                corr_samir = matriz_corr['QT_VOTOS_SAMIR'].drop('QT_VOTOS_SAMIR').reset_index()
                corr_samir.columns = ['Candidatura', 'Correlação de Pearson (r)']

                corr_samir = corr_samir[corr_samir['Correlação de Pearson (r)'] > 0.1]
                corr_samir = corr_samir[~corr_samir['Candidatura'].str.contains("SAMIR", case=False, na=False)]
                corr_samir = corr_samir.sort_values(by='Correlação de Pearson (r)', ascending=False).head(limite_ranking)

                if corr_samir.empty:
                    st.warning("Não foi detectada nenhuma correlação matemática positiva forte com os candidatos deste cargo.")
                else:
                    st.markdown(f"#### 📊 Correlações Observadas (Cargo: {cargo_alvo})")

                    top_1_corr = corr_samir.iloc[0]
                    st.success(f"**Maior correlação observada:** **{top_1_corr['Candidatura']}** (r = {top_1_corr['Correlação de Pearson (r)']:.2f}). Este resultado descreve associação linear entre seções; não permite concluir causalidade ou transferência de votos.")

                    altura_corr = max(500, len(corr_samir) * 35)

                    grafico_corr = alt.Chart(corr_samir).mark_bar(color="#25D366").encode(
                        x=alt.X('Correlação de Pearson (r):Q', title='Correlação (r)', scale=alt.Scale(domain=[0, 1])),
                        y=alt.Y('Candidatura:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                        tooltip=[
                            alt.Tooltip('Candidatura:N', title='Candidatura'),
                            alt.Tooltip('Correlação de Pearson (r):Q', title='Correlação de Pearson', format='.2f')
                        ]
                    ).properties(height=altura_corr)
                    exibir_grafico_altair(grafico_corr)

                    corr_samir['Correlação de Pearson (r)'] = corr_samir['Correlação de Pearson (r)'].round(3)
                    st.dataframe(corr_samir, use_container_width=True)
            else:
                st.warning("Não há volume de urnas suficientes nos filtros selecionados para garantir significância estatística no cálculo de Pearson.")

# ==========================================
# ROTA 6: ANÁLISE TERRITORIAL DA ZONA RURAL
# ==========================================
elif menu_selecionado == "🚜 6. Análise Territorial da Zona Rural":
    st.title("🚜 Análise Territorial da Zona Rural")

    st.info("""
    Esta análise cruza os votos históricos do candidato com todas as seções e
    locais de votação informados nas planilhas do TSE. Um local é confirmado como
    rural quando o bairro do ano selecionado está identificado como rural. Evidências
    históricas ou indícios no nome e endereço ficam separados em **REVISAR**.
    """)

    # As planilhas novas são carregadas somente nesta rota. Se houver problema nelas,
    # as outras cinco análises do painel continuam funcionando normalmente.
    try:
        locais_tse_rural = carregar_locais_tse_rota_rural()
    except Exception as erro_rural:
        st.error(
            "Não foi possível abrir a análise rural. As outras áreas do painel não "
            f"são afetadas. Detalhe: {erro_rural}"
        )
        st.info(
            "Confirme se `openpyxl` está no requirements.txt e se as três planilhas "
            "XLSX abrem normalmente."
        )
        st.stop()

    avisos_tse = locais_tse_rural.attrs.get('avisos', [])
    if avisos_tse:
        st.warning(
            "Alguns anos não foram carregados: " + " | ".join(avisos_tse)
        )

    anos_tse = sorted(
        [int(a) for a in locais_tse_rural['ANO_ELEICAO'].dropna().unique()]
    )
    serie_historica_rural = (
        ano_selecionado == 'Todos os Anos (Série Histórica)'
    )
    anos_rurais_selecionados = (
        anos_tse if serie_historica_rural else [int(ano_selecionado)]
    )
    titulo_periodo_rural = (
        "Série Histórica — 2020, 2022 e 2024"
        if serie_historica_rural else f"Ano de {anos_rurais_selecionados[0]}"
    )
    if serie_historica_rural:
        st.caption(
            "Todos os quadros numéricos abaixo incluem 2020, 2022 e 2024. "
            "Cada linha informa o ano para evitar a mistura silenciosa de eleições."
        )

    incluir_revisao = st.checkbox(
        "Incluir locais pendentes de revisão no mapa, resumo e ranking",
        value=False,
        help=(
            "Os indicadores do cabeçalho permanecem restritos aos locais rurais "
            "confirmados."
        )
    )

    locais_periodo = locais_tse_rural[
        locais_tse_rural['ANO_ELEICAO'].isin(anos_rurais_selecionados)
    ].copy()
    if col_municipio and municipios_selecionados:
        locais_periodo = locais_periodo[
            locais_periodo['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]

    # O número do local é a chave oficial. Nomes diferentes podem aparecer para o
    # mesmo local em seções distintas e não devem duplicar eleitorado ou votos.
    chaves_local = [
        'ANO_ELEICAO', 'ID_LOCAL_ANO', 'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA',
        'NR_LOCAL_VOTACAO', 'CLASSIFICACAO_RURAL',
        'FONTE_CLASSIFICACAO_RURAL', 'CONFIANCA_CLASSIFICACAO',
        'OBSERVACAO_CLASSIFICACAO'
    ]
    locais_resumo = locais_periodo.groupby(
        chaves_local, as_index=False, dropna=False
    ).agg(
        NM_LOCAL_VOTACAO=('NM_LOCAL_VOTACAO', 'first'),
        NM_BAIRRO=('NM_BAIRRO', 'first'),
        DS_ENDERECO=('DS_ENDERECO', 'first'),
        QT_SECOES=('NR_SECAO', 'nunique'),
        QT_ELEITORES=('QT_ELEITOR_SECAO', 'sum'),
        lat=('lat', 'median'),
        lon=('lon', 'median')
    )

    rurais_confirmados = locais_resumo[
        locais_resumo['CLASSIFICACAO_RURAL'] == 'RURAL'
    ].copy()
    locais_revisar = locais_resumo[
        locais_resumo['CLASSIFICACAO_RURAL'] == 'REVISAR'
    ].copy()
    classificacoes_exibidas = (
        ['RURAL', 'REVISAR'] if incluir_revisao else ['RURAL']
    )
    locais_analise = locais_resumo[
        locais_resumo['CLASSIFICACAO_RURAL'].isin(classificacoes_exibidas)
    ].copy()

    # Recupera a base original completa, sem depender da classificação manual de 30
    # escolas e sem alterar os DataFrames utilizados pelas outras rotas.
    votos_completos = carregar_dados()
    if col_municipio and municipios_selecionados:
        votos_completos = votos_completos[
            votos_completos[col_municipio].isin(municipios_selecionados)
        ]
    votos_periodo = votos_completos[
        votos_completos['ANO_ELEICAO'].isin(anos_rurais_selecionados)
    ].copy()

    # Explicita a cobertura da base do candidato. A planilha de locais do TSE é
    # estadual, mas o dados.csv pode não conter votação do candidato em todos os
    # municípios em todos os anos.
    cobertura_tse = locais_periodo.groupby(
        'ANO_ELEICAO'
    )['NM_MUNICIPIO'].nunique()
    cobertura_votos = votos_periodo.groupby(
        'ANO_ELEICAO'
    )['NM_MUNICIPIO'].nunique()
    textos_cobertura = []
    cobertura_incompleta = False
    for ano_cobertura in anos_rurais_selecionados:
        municipios_tse = int(cobertura_tse.get(ano_cobertura, 0))
        municipios_votos = int(cobertura_votos.get(ano_cobertura, 0))
        textos_cobertura.append(
            f"{ano_cobertura}: {municipios_votos} de {municipios_tse} municípios"
        )
        cobertura_incompleta = (
            cobertura_incompleta or municipios_votos < municipios_tse
        )
    st.caption(
        "Cobertura da base de votos do candidato — " +
        "; ".join(textos_cobertura) + "."
    )
    if cobertura_incompleta:
        st.warning(
            "A base de locais do TSE cobre todo o estado, mas o arquivo dados.csv "
            "não contém registros do candidato em todos os municípios e anos. "
            "Nesses casos, o valor zero significa ausência de registro na base "
            "atual e não comprova votação igual a zero."
        )

    mapa_secao = locais_periodo[[
        'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'ID_LOCAL_ANO'
    ]].drop_duplicates()
    votos_periodo = pd.merge(
        votos_periodo,
        mapa_secao,
        on=['ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
        how='inner'
    )
    votos_por_local = votos_periodo.groupby(
        'ID_LOCAL_ANO', as_index=False
    ).agg(
        QT_VOTOS_SAMIR=('QT_VOTOS_SAMIR', 'sum'),
        QT_VOTOS_VALIDOS_SECAO=('QT_VOTOS_VALIDOS_SECAO', 'max')
    )

    base_rural = pd.merge(
        locais_analise, votos_por_local, on='ID_LOCAL_ANO', how='left'
    )

    # Substitui o denominador repetido de dados.csv pelos votos válidos do cargo,
    # reconstruídos a partir da base de concorrência e do mapa oficial de seções.
    validos_rurais = carregar_validos_oficiais_por_local()
    if not validos_rurais.empty:
        validos_rurais = validos_rurais[
            validos_rurais['ANO_ELEICAO'].isin(anos_rurais_selecionados)
        ]
        if municipios_selecionados:
            validos_rurais = validos_rurais[
                validos_rurais['NM_MUNICIPIO'].isin(municipios_selecionados)
            ]
        base_rural = pd.merge(
            base_rural,
            validos_rurais,
            on=[
                'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA',
                'NM_LOCAL_VOTACAO'
            ],
            how='left'
        )
        base_rural['QT_VOTOS_VALIDOS_SECAO'] = base_rural[
            'QT_VOTOS_VALIDOS_CARGO'
        ].fillna(base_rural['QT_VOTOS_VALIDOS_SECAO'])
        base_rural = base_rural.drop(columns=['QT_VOTOS_VALIDOS_CARGO'])

    base_rural['QT_VOTOS_SAMIR'] = base_rural['QT_VOTOS_SAMIR'].fillna(0)
    base_rural['QT_VOTOS_VALIDOS_SECAO'] = base_rural[
        'QT_VOTOS_VALIDOS_SECAO'
    ].fillna(0)
    base_rural['PARTICIPACAO_VALIDOS'] = np.where(
        base_rural['QT_VOTOS_VALIDOS_SECAO'] > 0,
        base_rural['QT_VOTOS_SAMIR'] /
        base_rural['QT_VOTOS_VALIDOS_SECAO'] * 100,
        0
    )
    base_rural['DEMAIS_VOTOS_VALIDOS'] = (
        base_rural['QT_VOTOS_VALIDOS_SECAO'] -
        base_rural['QT_VOTOS_SAMIR']
    ).clip(lower=0)

    base_confirmada = base_rural[
        base_rural['CLASSIFICACAO_RURAL'] == 'RURAL'
    ]
    total_votos_samir = base_confirmada['QT_VOTOS_SAMIR'].sum()
    total_validos_rural = base_confirmada['QT_VOTOS_VALIDOS_SECAO'].sum()
    demais_validos_rural = max(total_validos_rural - total_votos_samir, 0)
    participacao_rural = (
        total_votos_samir / total_validos_rural * 100
        if total_validos_rural > 0 else 0
    )
    total_eleitorado_selecao = locais_resumo['QT_ELEITORES'].sum()
    eleitorado_rural = rurais_confirmados['QT_ELEITORES'].sum()
    pct_eleitorado_rural = (
        eleitorado_rural / total_eleitorado_selecao * 100
        if total_eleitorado_selecao > 0 else 0
    )

    m1, m2, m3, m4 = st.columns(4)
    rotulo_locais = (
        "Registros de Local/Ano" if serie_historica_rural else "Locais Examinados"
    )
    rotulo_eleitores = (
        "Eleitores Rurais (Soma Histórica)"
        if serie_historica_rural else "Eleitores Rurais"
    )
    m1.metric(rotulo_locais, f"{len(locais_resumo):,}".replace(',', '.'))
    m2.metric("Rurais Confirmados", f"{len(rurais_confirmados):,}".replace(',', '.'))
    m3.metric("Seções Rurais", f"{int(rurais_confirmados['QT_SECOES'].sum()):,}".replace(',', '.'))
    m4.metric(rotulo_eleitores, f"{int(eleitorado_rural):,}".replace(',', '.'))

    m5, m6, m7, m8 = st.columns(4)
    sufixo_historico = " (Soma Histórica)" if serie_historica_rural else ""
    m5.metric("Votos do Candidato" + sufixo_historico, f"{int(total_votos_samir):,}".replace(',', '.'))
    m6.metric("Votos Válidos Rurais" + sufixo_historico, f"{int(total_validos_rural):,}".replace(',', '.'))
    m7.metric("Demais Votos Válidos" + sufixo_historico, f"{int(demais_validos_rural):,}".replace(',', '.'))
    m8.metric("Participação nos Válidos", f"{participacao_rural:.2f}%")
    st.caption(
        f"Período exibido: {titulo_periodo_rural}. Os locais rurais representam "
        f"{pct_eleitorado_rural:.1f}% do eleitorado da seleção atual. 'Demais "
        "votos válidos' é uma medida histórica e não significa que esses votos "
        "estejam automaticamente disponíveis."
    )

    if incluir_revisao:
        st.warning(
            "Mapa, resumo municipal e ranking incluem pendências. Os indicadores "
            "do cabeçalho continuam usando somente rurais confirmados."
        )

    st.markdown("---")
    st.subheader("📍 Mapa dos Locais Rurais")
    if serie_historica_rural:
        ano_mapa = st.selectbox(
            "Ano exibido no mapa:",
            sorted(anos_rurais_selecionados, reverse=True)
        )
        mapa_rural = base_rural[
            base_rural['ANO_ELEICAO'] == ano_mapa
        ].dropna(subset=['lat', 'lon'])
        st.caption(
            "O mapa exibe um ano por vez para evitar sobreposição de locais em "
            "eleições diferentes. As tabelas seguem mostrando todos os anos."
        )
    else:
        mapa_rural = base_rural.dropna(subset=['lat', 'lon'])
    if not mapa_rural.empty:
        st.map(mapa_rural, latitude='lat', longitude='lon')
    else:
        st.info("Não há coordenadas válidas para os filtros selecionados.")

    st.markdown("---")
    st.subheader(f"📊 Resumo Rural por Município — {titulo_periodo_rural}")
    chaves_municipio = (
        ['ANO_ELEICAO', 'NM_MUNICIPIO']
        if serie_historica_rural else ['NM_MUNICIPIO']
    )
    resumo_municipal = base_rural.groupby(
        chaves_municipio, as_index=False
    ).agg(
        LOCAIS=('ID_LOCAL_ANO', 'nunique'),
        SECOES=('QT_SECOES', 'sum'),
        ELEITORES=('QT_ELEITORES', 'sum'),
        VOTOS_SAMIR=('QT_VOTOS_SAMIR', 'sum'),
        VOTOS_VALIDOS=('QT_VOTOS_VALIDOS_SECAO', 'sum')
    )
    resumo_municipal['PARTICIPACAO_VALIDOS_PCT'] = np.where(
        resumo_municipal['VOTOS_VALIDOS'] > 0,
        resumo_municipal['VOTOS_SAMIR'] /
        resumo_municipal['VOTOS_VALIDOS'] * 100,
        0
    )
    eleitorado_total_municipio = locais_resumo.groupby(
        chaves_municipio, as_index=False
    )['QT_ELEITORES'].sum().rename(
        columns={'QT_ELEITORES': 'ELEITORADO_TOTAL_MUNICIPIO'}
    )
    resumo_municipal = pd.merge(
        resumo_municipal,
        eleitorado_total_municipio,
        on=chaves_municipio,
        how='left'
    )
    resumo_municipal['ELEITORADO_RURAL_PCT'] = np.where(
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] > 0,
        resumo_municipal['ELEITORES'] /
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] * 100,
        0
    )
    resumo_municipal = resumo_municipal.sort_values(
        ['ANO_ELEICAO', 'ELEITORES'] if serie_historica_rural else 'ELEITORES',
        ascending=[True, False] if serie_historica_rural else False
    ).rename(columns={
        'ANO_ELEICAO': 'Ano',
        'NM_MUNICIPIO': 'Município',
        'LOCAIS': 'Locais',
        'SECOES': 'Seções',
        'ELEITORES': 'Eleitores Rurais',
        'VOTOS_SAMIR': 'Votos do Candidato',
        'VOTOS_VALIDOS': 'Votos Válidos',
        'PARTICIPACAO_VALIDOS_PCT': 'Participação nos Válidos (%)',
        'ELEITORADO_RURAL_PCT': 'Eleitorado Rural no Município (%)'
    })
    resumo_municipal['Participação nos Válidos (%)'] = resumo_municipal[
        'Participação nos Válidos (%)'
    ].round(2)
    resumo_municipal['Eleitorado Rural no Município (%)'] = resumo_municipal[
        'Eleitorado Rural no Município (%)'
    ].round(1)
    colunas_resumo = (
        ['Ano'] if serie_historica_rural else []
    ) + [
            'Município', 'Locais', 'Seções', 'Eleitores Rurais',
            'Eleitorado Rural no Município (%)', 'Votos do Candidato',
            'Votos Válidos', 'Participação nos Válidos (%)'
        ]
    st.dataframe(
        resumo_municipal[colunas_resumo],
        use_container_width=True
    )

    st.markdown("---")
    titulo_ranking = (
        "📋 Ranking Histórico por Local/Ano"
        if serie_historica_rural else "📋 Desempenho por Local Rural"
    )
    st.subheader(titulo_ranking)
    criterio_rural = st.selectbox(
        "Ordenar os locais por:",
        [
            'Votos do Candidato', 'Participação nos Válidos',
            'Eleitorado', 'Demais Votos Válidos'
        ]
    )
    colunas_criterio = {
        'Votos do Candidato': 'QT_VOTOS_SAMIR',
        'Participação nos Válidos': 'PARTICIPACAO_VALIDOS',
        'Eleitorado': 'QT_ELEITORES',
        'Demais Votos Válidos': 'DEMAIS_VOTOS_VALIDOS'
    }
    coluna_ranking = colunas_criterio[criterio_rural]
    ranking_rural = base_rural.sort_values(
        coluna_ranking, ascending=False
    ).head(limite_ranking)

    if not ranking_rural.empty:
        ranking_rural = ranking_rural.copy()
        ranking_rural['LOCAL_EXIBICAO'] = np.where(
            serie_historica_rural,
            ranking_rural['ANO_ELEICAO'].astype(str) + ' — ' +
            ranking_rural['NM_LOCAL_VOTACAO'],
            ranking_rural['NM_LOCAL_VOTACAO']
        )
        grafico_rural = alt.Chart(ranking_rural).mark_bar(
            color="#28A745"
        ).encode(
            x=alt.X(f'{coluna_ranking}:Q', title=criterio_rural),
            y=alt.Y('LOCAL_EXIBICAO:N', title=None, sort='-x'),
            tooltip=[
                alt.Tooltip('ANO_ELEICAO:O', title='Ano'),
                alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
                alt.Tooltip('QT_ELEITORES:Q', title='Eleitores', format=','),
                alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos', format=','),
                alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', title='Válidos', format=','),
                alt.Tooltip('PARTICIPACAO_VALIDOS:Q', title='Participação (%)', format='.2f'),
                alt.Tooltip('CLASSIFICACAO_RURAL:N', title='Classificação')
            ]
        ).properties(height=max(450, len(ranking_rural) * 34))
        exibir_grafico_altair(grafico_rural)

        colunas_ranking = (
            ['ANO_ELEICAO'] if serie_historica_rural else []
        ) + [
            'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
            'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'QT_SECOES', 'QT_ELEITORES',
            'QT_VOTOS_SAMIR', 'QT_VOTOS_VALIDOS_SECAO',
            'PARTICIPACAO_VALIDOS', 'CLASSIFICACAO_RURAL',
            'CONFIANCA_CLASSIFICACAO'
        ]
        tabela_ranking = ranking_rural[colunas_ranking].copy()
        titulos_ranking = (
            ['Ano'] if serie_historica_rural else []
        ) + [
            'Município', 'Zona', 'Nº Local', 'Local de Votação', 'Bairro',
            'Seções', 'Eleitores', 'Votos do Candidato', 'Votos Válidos',
            'Participação nos Válidos (%)', 'Classificação', 'Confiança'
        ]
        tabela_ranking.columns = titulos_ranking
        tabela_ranking['Participação nos Válidos (%)'] = tabela_ranking[
            'Participação nos Válidos (%)'
        ].round(2)
        st.dataframe(tabela_ranking, use_container_width=True)
    else:
        st.info("Nenhum local rural encontrado para os filtros selecionados.")

    st.markdown("---")
    st.subheader("📈 Evolução Histórica Rural")
    locais_hist = locais_tse_rural[
        locais_tse_rural['ANO_ELEICAO'].isin(anos_rurais_selecionados)
    ].copy()
    if col_municipio and municipios_selecionados:
        locais_hist = locais_hist[
            locais_hist['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]

    votos_hist = base_rural[
        base_rural['CLASSIFICACAO_RURAL'] == 'RURAL'
    ].groupby('ANO_ELEICAO', as_index=False).agg(
        VOTOS_SAMIR=('QT_VOTOS_SAMIR', 'sum'),
        VOTOS_VALIDOS=('QT_VOTOS_VALIDOS_SECAO', 'sum')
    )
    votos_hist['PARTICIPACAO_VALIDOS_PCT'] = np.where(
        votos_hist['VOTOS_VALIDOS'] > 0,
        votos_hist['VOTOS_SAMIR'] / votos_hist['VOTOS_VALIDOS'] * 100,
        0
    )

    universo_hist = locais_hist[
        locais_hist['CLASSIFICACAO_RURAL'] == 'RURAL'
    ].groupby(
        ['ANO_ELEICAO', 'ID_LOCAL_ANO'], as_index=False
    ).agg(
        SECOES=('NR_SECAO', 'nunique'),
        ELEITORES=('QT_ELEITOR_SECAO', 'sum')
    ).groupby('ANO_ELEICAO', as_index=False).agg(
        LOCAIS=('ID_LOCAL_ANO', 'nunique'),
        SECOES=('SECOES', 'sum'),
        ELEITORES=('ELEITORES', 'sum')
    )
    evolucao_rural = pd.merge(
        universo_hist, votos_hist, on='ANO_ELEICAO', how='left'
    ).fillna(0)

    if evolucao_rural['ANO_ELEICAO'].nunique() > 1:
        grafico_evolucao_rural = alt.Chart(evolucao_rural).mark_line(
            point=alt.OverlayMarkDef(size=100),
            strokeWidth=4,
            color="#28A745"
        ).encode(
            x=alt.X('ANO_ELEICAO:O', title='Ano da Eleição'),
            y=alt.Y(
                'PARTICIPACAO_VALIDOS_PCT:Q',
                title='Participação nos Válidos Rurais (%)'
            ),
            tooltip=[
                alt.Tooltip('ANO_ELEICAO:O', title='Ano'),
                alt.Tooltip('LOCAIS:Q', title='Locais', format=','),
                alt.Tooltip('SECOES:Q', title='Seções', format=','),
                alt.Tooltip('ELEITORES:Q', title='Eleitores', format=','),
                alt.Tooltip('VOTOS_SAMIR:Q', title='Votos', format=','),
                alt.Tooltip(
                    'PARTICIPACAO_VALIDOS_PCT:Q',
                    title='Participação (%)',
                    format='.2f'
                )
            ]
        ).properties(height=420)
        exibir_grafico_altair(grafico_evolucao_rural)
    st.caption(
        "A comparação é descritiva. Mudanças de cargo, seções, eleitorado e contexto "
        "eleitoral podem afetar os resultados entre anos."
    )
    evolucao_rural['PARTICIPACAO_VALIDOS_PCT'] = evolucao_rural[
        'PARTICIPACAO_VALIDOS_PCT'
    ].round(2)
    st.dataframe(evolucao_rural, use_container_width=True)

    st.markdown("---")
    st.subheader("🔎 Controle de Qualidade da Classificação")
    q1, q2, q3 = st.columns(3)
    q1.metric(
        "Rurais com Confiança Alta",
        int((rurais_confirmados['CONFIANCA_CLASSIFICACAO'] == 'ALTA').sum())
    )
    q2.metric(
        "Registros Pendentes de Revisão" if serie_historica_rural else "Locais Pendentes de Revisão",
        len(locais_revisar)
    )
    q3.metric(
        "Registros sem Coordenada" if serie_historica_rural else "Locais sem Coordenada",
        int(locais_resumo[['lat', 'lon']].isna().any(axis=1).sum())
    )

    if not locais_revisar.empty:
        colunas_revisao = (
            ['ANO_ELEICAO'] if serie_historica_rural else []
        ) + [
            'ID_LOCAL_ANO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
            'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'DS_ENDERECO', 'QT_ELEITORES',
            'FONTE_CLASSIFICACAO_RURAL', 'CONFIANCA_CLASSIFICACAO'
        ]
        tabela_revisao = locais_revisar[colunas_revisao].copy()
        tabela_revisao.columns = (
            ['Ano'] if serie_historica_rural else []
        ) + [
            'ID Local/Ano', 'Município', 'Zona', 'Nº Local',
            'Local de Votação', 'Bairro', 'Endereço', 'Eleitores',
            'Motivo', 'Confiança'
        ]
        st.dataframe(tabela_revisao, use_container_width=True)
        periodo_arquivo = (
            "serie_historica" if serie_historica_rural
            else str(anos_rurais_selecionados[0])
        )
        st.download_button(
            "Baixar lista de locais pendentes",
            data=tabela_revisao.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"locais_rurais_revisar_{periodo_arquivo}.csv",
            mime="text/csv"
        )


# ==========================================
# ROTA 7: CENÁRIO ELEITORAL 2026
# ==========================================
elif menu_selecionado == "🗳️ 7. Cenário Eleitoral 2026":
    st.title("🗳️ Cenário Eleitoral 2026")
    st.info(
        "Este módulo apresenta o eleitorado atual e referências territoriais. "
        "Eleitorado não é voto disponível, e a votação de 2022 não é uma "
        "previsão: ela é usada somente como referência histórica comparável."
    )

    if erro_bases_2026:
        st.error(
            "Não foi possível abrir as bases independentes de 2026. "
            f"Detalhe: {erro_bases_2026}"
        )
        st.warning(
            "As abas históricas continuam preservadas. Envie os arquivos de "
            "2026 para a mesma pasta do painel e recarregue a aplicação."
        )
        st.stop()

    if not municipios_2026_selecionados:
        st.warning("Selecione pelo menos um município no filtro lateral.")
        st.stop()

    base_municipios_2026 = eleitorado_2026[
        eleitorado_2026['NM_MUNICIPIO'].isin(
            municipios_2026_selecionados
        )
    ].copy()

    if situacao_2026_selecionada != "Todos os locais":
        base_municipios_2026 = base_municipios_2026[
            base_municipios_2026['DS_SITU_LOCAL_VOTACAO']
            == situacao_2026_selecionada
        ].copy()

    base_exibida_2026 = base_municipios_2026.copy()
    if territorio_2026_selecionado != "Todos os territórios":
        base_exibida_2026 = base_exibida_2026[
            base_exibida_2026['TERRITORIO_2026']
            == territorio_2026_selecionado
        ].copy()

    total_eleitores_2026 = base_exibida_2026['QT_ELEITOR_SECAO'].sum()
    total_locais_2026 = base_exibida_2026['ID_LOCAL_2026'].nunique()
    total_secoes_2026 = base_exibida_2026['ID_SECAO_2026'].nunique()
    total_rural_2026 = base_exibida_2026.loc[
        base_exibida_2026['RURAL_IDENTIFICADA'], 'QT_ELEITOR_SECAO'
    ].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Eleitorado no Filtro", inteiro_pt(total_eleitores_2026))
    k2.metric("Locais de Votação", inteiro_pt(total_locais_2026))
    k3.metric("Seções Eleitorais", inteiro_pt(total_secoes_2026))
    k4.metric("Eleitorado Rural Identificado", inteiro_pt(total_rural_2026))

    datas_geracao = metadados_2026.get('generation_dates', {})
    data_locais = ', '.join(datas_geracao.get('locations', [])) or 'não informada'
    data_perfil = ', '.join(datas_geracao.get('profile', [])) or 'não informada'
    st.caption(
        f"Locais e seções: extração de {data_locais}. "
        f"Perfil do eleitorado: extração de {data_perfil}. "
        "As diferenças entre datas são mantidas visíveis na metodologia."
    )

    aba_visao, aba_rural, aba_oportunidades, aba_perfil, aba_metodologia = st.tabs(
        [
            "Visão Geral",
            "Zona Rural",
            "Matriz de Oportunidades",
            "Perfil do Eleitorado",
            "Metodologia e Qualidade",
        ]
    )

    with aba_visao:
        st.subheader("Distribuição Territorial do Eleitorado")
        locais_exibidos_2026 = consolidar_eleitorado_2026_por_local(
            base_exibida_2026
        )

        if locais_exibidos_2026.empty:
            st.warning("Não há registros para a combinação de filtros selecionada.")
        else:
            mapa_2026 = locais_exibidos_2026[[
                'LATITUDE', 'LONGITUDE', 'ELEITORES_2026'
            ]].dropna().rename(
                columns={'LATITUDE': 'lat', 'LONGITUDE': 'lon'}
            )
            mapa_2026['TAMANHO_MAPA'] = np.clip(
                mapa_2026['ELEITORES_2026'] / 35, 8, 85
            )
            try:
                st.map(
                    mapa_2026,
                    latitude='lat',
                    longitude='lon',
                    size='TAMANHO_MAPA'
                )
            except Exception:
                st.map(mapa_2026, latitude='lat', longitude='lon')
            st.caption(
                "Os pontos utilizam as coordenadas publicadas pelo TSE; o tamanho "
                "representa o eleitorado alocado no local."
            )

            distribuicao_municipal = base_exibida_2026.groupby(
                ['NM_MUNICIPIO', 'TERRITORIO_2026'],
                as_index=False
            ).agg(ELEITORES=('QT_ELEITOR_SECAO', 'sum'))
            nomes_territorio = {
                'RURAL IDENTIFICADA': 'Rural identificada',
                'REVISAR CLASSIFICAÇÃO': 'Revisar classificação',
                'URBANA OU NÃO IDENTIFICADA COMO RURAL': 'Demais territórios',
            }
            distribuicao_municipal['TERRITORIO'] = distribuicao_municipal[
                'TERRITORIO_2026'
            ].map(nomes_territorio).fillna(
                distribuicao_municipal['TERRITORIO_2026']
            )
            ordem_municipios = (
                distribuicao_municipal.groupby('NM_MUNICIPIO')['ELEITORES']
                .sum().sort_values(ascending=False).index.tolist()
            )
            grafico_municipios_2026 = alt.Chart(
                distribuicao_municipal
            ).mark_bar().encode(
                x=alt.X('ELEITORES:Q', title='Eleitorado 2026'),
                y=alt.Y(
                    'NM_MUNICIPIO:N',
                    title=None,
                    sort=ordem_municipios
                ),
                color=alt.Color(
                    'TERRITORIO:N',
                    title='Território',
                    scale=alt.Scale(
                        domain=[
                            'Rural identificada',
                            'Revisar classificação',
                            'Demais territórios'
                        ],
                        range=['#28A745', '#F0AD4E', '#2878D0']
                    )
                ),
                tooltip=[
                    alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
                    alt.Tooltip('TERRITORIO:N', title='Território'),
                    alt.Tooltip('ELEITORES:Q', title='Eleitores', format=',')
                ]
            ).properties(
                height=max(360, len(ordem_municipios) * 27)
            )
            exibir_grafico_altair(grafico_municipios_2026)

            resumo_dinamico = base_exibida_2026.groupby(
                'NM_MUNICIPIO', as_index=False
            ).agg(
                ELEITORES=('QT_ELEITOR_SECAO', 'sum'),
                LOCAIS=('ID_LOCAL_2026', 'nunique'),
                SECOES=('ID_SECAO_2026', 'nunique')
            )
            rural_dinamico = base_exibida_2026[
                base_exibida_2026['RURAL_IDENTIFICADA']
            ].groupby('NM_MUNICIPIO', as_index=False).agg(
                ELEITORES_RURAIS=('QT_ELEITOR_SECAO', 'sum')
            )
            resumo_dinamico = resumo_dinamico.merge(
                rural_dinamico, on='NM_MUNICIPIO', how='left'
            ).fillna({'ELEITORES_RURAIS': 0})
            resumo_dinamico['PARTICIPACAO_NO_FILTRO_PCT'] = np.where(
                resumo_dinamico['ELEITORES'] > 0,
                resumo_dinamico['ELEITORES_RURAIS']
                / resumo_dinamico['ELEITORES'] * 100,
                0
            )
            resumo_dinamico = resumo_dinamico.sort_values(
                'ELEITORES', ascending=False
            ).rename(columns={
                'NM_MUNICIPIO': 'Município',
                'ELEITORES': 'Eleitorado no Filtro',
                'LOCAIS': 'Locais',
                'SECOES': 'Seções',
                'ELEITORES_RURAIS': 'Eleitorado Rural Identificado',
                'PARTICIPACAO_NO_FILTRO_PCT': 'Rural no Filtro (%)'
            })
            resumo_dinamico['Rural no Filtro (%)'] = resumo_dinamico[
                'Rural no Filtro (%)'
            ].round(2)
            st.dataframe(resumo_dinamico, use_container_width=True)

    with aba_rural:
        st.subheader("Análise Territorial da Zona Rural — 2026")
        st.caption(
            "Esta aba considera como rural somente o que possui o termo RURAL "
            "no bairro ou no nome do local publicado pelo TSE. Indícios não "
            "confirmados aparecem separadamente e não entram no total. O filtro "
            "de território não altera esta aba; município e situação do local "
            "continuam sendo respeitados."
        )
        base_rural_2026 = base_municipios_2026[
            base_municipios_2026['RURAL_IDENTIFICADA']
        ].copy()
        locais_rurais_2026 = consolidar_eleitorado_2026_por_local(
            base_rural_2026
        )
        eleitorado_contexto = base_municipios_2026['QT_ELEITOR_SECAO'].sum()
        eleitorado_rural_contexto = base_rural_2026['QT_ELEITOR_SECAO'].sum()
        participacao_rural_contexto = (
            eleitorado_rural_contexto / eleitorado_contexto * 100
            if eleitorado_contexto else 0
        )

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Eleitorado Rural Identificado", inteiro_pt(eleitorado_rural_contexto))
        r2.metric("Locais Rurais", inteiro_pt(base_rural_2026['ID_LOCAL_2026'].nunique()))
        r3.metric("Seções Rurais", inteiro_pt(base_rural_2026['ID_SECAO_2026'].nunique()))
        r4.metric("Participação no Eleitorado", percentual_pt(participacao_rural_contexto))

        todos_municipios = (
            len(municipios_2026_selecionados)
            == len(municipios_2026_disponiveis)
        )
        if todos_municipios and situacao_2026_selecionada == "Todos os locais":
            totais_validados = metadados_2026.get('validated_totals', {})
            rural_oficial = totais_validados.get('official_tre_rural', 0)
            diferenca_rural = totais_validados.get(
                'difference_rural_identified_vs_official', 0
            )
            st.info(
                f"Referência do TRE-AC: {inteiro_pt(rural_oficial)} eleitores "
                f"rurais. Reconstrução nos campos do arquivo: "
                f"{inteiro_pt(eleitorado_rural_contexto)}. Diferença: "
                f"{inteiro_pt(abs(diferenca_rural))} "
                f"({'acima' if diferenca_rural > 0 else 'abaixo'} da referência), "
                "compatível com os diferentes momentos de extração."
            )

        if not base_rural_2026.empty:
            rural_municipal_2026 = base_municipios_2026.groupby(
                'NM_MUNICIPIO', as_index=False
            ).agg(ELEITORES_MUNICIPIO=('QT_ELEITOR_SECAO', 'sum'))
            rural_confirmado_municipal = base_rural_2026.groupby(
                'NM_MUNICIPIO', as_index=False
            ).agg(
                ELEITORES_RURAIS=('QT_ELEITOR_SECAO', 'sum'),
                LOCAIS_RURAIS=('ID_LOCAL_2026', 'nunique'),
                SECOES_RURAIS=('ID_SECAO_2026', 'nunique')
            )
            rural_municipal_2026 = rural_municipal_2026.merge(
                rural_confirmado_municipal,
                on='NM_MUNICIPIO',
                how='left'
            ).fillna(0)
            rural_municipal_2026['PARTICIPACAO_RURAL_PCT'] = np.where(
                rural_municipal_2026['ELEITORES_MUNICIPIO'] > 0,
                rural_municipal_2026['ELEITORES_RURAIS']
                / rural_municipal_2026['ELEITORES_MUNICIPIO'] * 100,
                0
            )
            rural_municipal_2026 = rural_municipal_2026.sort_values(
                'ELEITORES_RURAIS', ascending=False
            )

            grafico_rural_2026 = alt.Chart(
                rural_municipal_2026
            ).mark_bar(color='#28A745').encode(
                x=alt.X('ELEITORES_RURAIS:Q', title='Eleitorado rural identificado'),
                y=alt.Y(
                    'NM_MUNICIPIO:N', title=None,
                    sort=rural_municipal_2026['NM_MUNICIPIO'].tolist()
                ),
                tooltip=[
                    alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
                    alt.Tooltip('ELEITORES_RURAIS:Q', title='Eleitores rurais', format=','),
                    alt.Tooltip('LOCAIS_RURAIS:Q', title='Locais', format=','),
                    alt.Tooltip('SECOES_RURAIS:Q', title='Seções', format=','),
                    alt.Tooltip(
                        'PARTICIPACAO_RURAL_PCT:Q',
                        title='Rural no município (%)',
                        format='.2f'
                    )
                ]
            ).properties(
                height=max(360, len(rural_municipal_2026) * 27)
            )
            exibir_grafico_altair(grafico_rural_2026)

            tabela_rural_2026 = rural_municipal_2026.rename(columns={
                'NM_MUNICIPIO': 'Município',
                'ELEITORES_MUNICIPIO': 'Eleitorado Municipal',
                'ELEITORES_RURAIS': 'Eleitorado Rural Identificado',
                'LOCAIS_RURAIS': 'Locais Rurais',
                'SECOES_RURAIS': 'Seções Rurais',
                'PARTICIPACAO_RURAL_PCT': 'Participação Rural (%)'
            })
            tabela_rural_2026['Participação Rural (%)'] = tabela_rural_2026[
                'Participação Rural (%)'
            ].round(2)
            st.dataframe(tabela_rural_2026, use_container_width=True)

            st.subheader("Mapa dos Locais Rurais Identificados")
            mapa_rural_2026 = locais_rurais_2026[[
                'LATITUDE', 'LONGITUDE', 'ELEITORES_2026'
            ]].dropna().rename(
                columns={'LATITUDE': 'lat', 'LONGITUDE': 'lon'}
            )
            mapa_rural_2026['TAMANHO_MAPA'] = np.clip(
                mapa_rural_2026['ELEITORES_2026'] / 20, 9, 90
            )
            try:
                st.map(
                    mapa_rural_2026,
                    latitude='lat',
                    longitude='lon',
                    size='TAMANHO_MAPA'
                )
            except Exception:
                st.map(mapa_rural_2026, latitude='lat', longitude='lon')
        else:
            st.warning("Nenhum local rural identificado para os filtros selecionados.")

        st.markdown("---")
        st.subheader("Locais com Indícios que Exigem Revisão")
        st.caption(
            "Esses registros não são somados ao eleitorado rural confirmado. "
            "A lista serve para conferência territorial pela equipe."
        )
        revisar_2026 = base_municipios_2026[
            base_municipios_2026['TERRITORIO_2026'] == 'REVISAR CLASSIFICAÇÃO'
        ].copy()
        locais_revisar_2026 = consolidar_eleitorado_2026_por_local(revisar_2026)
        if locais_revisar_2026.empty:
            st.success("Não há locais pendentes nos filtros selecionados.")
        else:
            tabela_revisar_2026 = locais_revisar_2026[[
                'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
                'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'DS_ENDERECO',
                'ELEITORES_2026', 'SECOES_2026'
            ]].sort_values('ELEITORES_2026', ascending=False).rename(columns={
                'NM_MUNICIPIO': 'Município',
                'NR_ZONA': 'Zona',
                'NR_LOCAL_VOTACAO': 'Nº Local',
                'NM_LOCAL_VOTACAO': 'Local de Votação',
                'NM_BAIRRO': 'Bairro',
                'DS_ENDERECO': 'Endereço',
                'ELEITORES_2026': 'Eleitores',
                'SECOES_2026': 'Seções'
            })
            st.dataframe(tabela_revisar_2026, use_container_width=True)
            st.download_button(
                "Baixar lista para revisão territorial",
                data=tabela_revisar_2026.to_csv(index=False).encode('utf-8-sig'),
                file_name='locais_revisar_classificacao_2026.csv',
                mime='text/csv'
            )

    with aba_oportunidades:
        st.subheader("Matriz Territorial de Oportunidades")
        st.caption(
            "A matriz cruza o eleitorado de 2026 com os votos de 2022 por "
            "município, zona e seção. Samir concorreu a deputado federal em "
            "2022; portanto, o resultado é referência territorial, não projeção "
            "para o cargo de deputado estadual."
        )
        matriz_2026, cobertura_historica_2026 = construir_matriz_oportunidades_2026(
            base_exibida_2026,
            dados
        )
        if matriz_2026.empty:
            st.warning(
                "Não foi possível construir o cruzamento com 2022. Verifique se "
                "dados.csv contém município, zona, seção e votos do candidato."
            )
        else:
            o1, o2, o3 = st.columns(3)
            o1.metric("Cobertura das Seções de 2022", percentual_pt(cobertura_historica_2026))
            o2.metric("Locais Comparados", inteiro_pt(len(matriz_2026)))
            o3.metric(
                "Votos de Referência Mapeados",
                inteiro_pt(matriz_2026['VOTOS_REFERENCIA_2022'].sum())
            )

            comparaveis = matriz_2026[
                matriz_2026['COBERTURA_SECOES_PCT'] > 0
            ].copy()
            if comparaveis.empty:
                st.warning("Nenhuma seção de 2026 encontrou referência correspondente em 2022.")
            else:
                mediana_eleitores = comparaveis['ELEITORES_2026'].median()
                mediana_penetracao = comparaveis[
                    'PENETRACAO_REFERENCIA_PCT'
                ].median()
                condicoes = [
                    (
                        comparaveis['ELEITORES_2026'] >= mediana_eleitores
                    ) & (
                        comparaveis['PENETRACAO_REFERENCIA_PCT'] < mediana_penetracao
                    ),
                    (
                        comparaveis['ELEITORES_2026'] >= mediana_eleitores
                    ) & (
                        comparaveis['PENETRACAO_REFERENCIA_PCT'] >= mediana_penetracao
                    ),
                    (
                        comparaveis['ELEITORES_2026'] < mediana_eleitores
                    ) & (
                        comparaveis['PENETRACAO_REFERENCIA_PCT'] < mediana_penetracao
                    ),
                ]
                classificacoes = [
                    'Alta escala / baixa penetração histórica',
                    'Alta escala / presença histórica acima da mediana',
                    'Menor escala / baixa penetração histórica',
                ]
                comparaveis['LEITURA_TERRITORIAL'] = np.select(
                    condicoes,
                    classificacoes,
                    default='Menor escala / presença histórica acima da mediana'
                )

                grafico_oportunidades = alt.Chart(
                    comparaveis
                ).mark_circle(size=115, opacity=0.75).encode(
                    x=alt.X(
                        'ELEITORES_2026:Q',
                        title='Eleitorado 2026 no local'
                    ),
                    y=alt.Y(
                        'PENETRACAO_REFERENCIA_PCT:Q',
                        title='Penetração histórica de referência (%)'
                    ),
                    color=alt.Color(
                        'LEITURA_TERRITORIAL:N',
                        title='Leitura territorial'
                    ),
                    tooltip=[
                        alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
                        alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
                        alt.Tooltip('TERRITORIO_2026:N', title='Território'),
                        alt.Tooltip('ELEITORES_2026:Q', title='Eleitores', format=','),
                        alt.Tooltip(
                            'VOTOS_REFERENCIA_2022:Q',
                            title='Votos de referência 2022',
                            format=','
                        ),
                        alt.Tooltip(
                            'PENETRACAO_REFERENCIA_PCT:Q',
                            title='Penetração (%)',
                            format='.2f'
                        ),
                        alt.Tooltip(
                            'COBERTURA_SECOES_PCT:Q',
                            title='Cobertura das seções (%)',
                            format='.1f'
                        )
                    ]
                ).properties(height=520).interactive()
                exibir_grafico_altair(grafico_oportunidades)
                st.caption(
                    f"Limites descritivos do filtro atual: mediana de "
                    f"{inteiro_pt(mediana_eleitores)} eleitores por local e "
                    f"{percentual_pt(mediana_penetracao)} de penetração histórica. "
                    "Esses limites organizam a leitura; não definem prioridade "
                    "automática nem resultado garantido."
                )

                ordem_leitura = {
                    'Alta escala / baixa penetração histórica': 1,
                    'Alta escala / presença histórica acima da mediana': 2,
                    'Menor escala / baixa penetração histórica': 3,
                    'Menor escala / presença histórica acima da mediana': 4,
                }
                comparaveis['ORDEM_LEITURA'] = comparaveis[
                    'LEITURA_TERRITORIAL'
                ].map(ordem_leitura)
                tabela_oportunidades = comparaveis.sort_values(
                    ['ORDEM_LEITURA', 'ELEITORES_2026'],
                    ascending=[True, False]
                )[[
                    'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
                    'NM_LOCAL_VOTACAO', 'TERRITORIO_2026', 'ELEITORES_2026',
                    'SECOES_2026', 'VOTOS_REFERENCIA_2022',
                    'PENETRACAO_REFERENCIA_PCT', 'COBERTURA_SECOES_PCT',
                    'LEITURA_TERRITORIAL'
                ]].rename(columns={
                    'NM_MUNICIPIO': 'Município',
                    'NR_ZONA': 'Zona',
                    'NR_LOCAL_VOTACAO': 'Nº Local',
                    'NM_LOCAL_VOTACAO': 'Local de Votação',
                    'TERRITORIO_2026': 'Território',
                    'ELEITORES_2026': 'Eleitorado 2026',
                    'SECOES_2026': 'Seções 2026',
                    'VOTOS_REFERENCIA_2022': 'Votos de Referência 2022',
                    'PENETRACAO_REFERENCIA_PCT': 'Penetração Histórica (%)',
                    'COBERTURA_SECOES_PCT': 'Cobertura das Seções (%)',
                    'LEITURA_TERRITORIAL': 'Leitura Territorial'
                })
                tabela_oportunidades['Penetração Histórica (%)'] = (
                    tabela_oportunidades['Penetração Histórica (%)'].round(2)
                )
                tabela_oportunidades['Cobertura das Seções (%)'] = (
                    tabela_oportunidades['Cobertura das Seções (%)'].round(1)
                )
                st.dataframe(tabela_oportunidades, use_container_width=True)
                st.download_button(
                    "Baixar matriz territorial 2026",
                    data=tabela_oportunidades.to_csv(index=False).encode('utf-8-sig'),
                    file_name='matriz_territorial_2026.csv',
                    mime='text/csv'
                )

    with aba_perfil:
        st.subheader("Perfil Agregado do Eleitorado")
        st.caption(
            "Os dados são agregados por seção e servem para planejamento de "
            "comunicação pública, acessibilidade e logística. Não identificam "
            "pessoas e não devem ser usados para perfilamento individual."
        )
        chaves_selecionadas_2026 = base_exibida_2026[[
            'CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'NR_LOCAL_VOTACAO'
        ]].drop_duplicates()
        demografia_filtrada_2026 = pd.merge(
            demografia_secao_2026,
            chaves_selecionadas_2026,
            on=['CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'NR_LOCAL_VOTACAO'],
            how='inner',
            validate='many_to_one'
        )

        if demografia_filtrada_2026.empty:
            st.warning("Não há perfil demográfico para os filtros selecionados.")
        else:
            perfil_genero_2026 = demografia_filtrada_2026[
                demografia_filtrada_2026['DIMENSAO'] == 'GÊNERO'
            ].copy()
            total_perfil_2026 = perfil_genero_2026['QT_ELEITORES'].sum()
            total_biometria_2026 = perfil_genero_2026[
                'QT_ELEITORES_BIOMETRIA'
            ].sum()
            total_deficiencia_2026 = perfil_genero_2026[
                'QT_ELEITORES_DEFICIENCIA'
            ].sum()
            biometria_pct_2026 = (
                total_biometria_2026 / total_perfil_2026 * 100
                if total_perfil_2026 else 0
            )

            p1, p2, p3 = st.columns(3)
            p1.metric("Eleitorado com Perfil", inteiro_pt(total_perfil_2026))
            p2.metric("Biometria Cadastrada", percentual_pt(biometria_pct_2026))
            p3.metric("Pessoas com Deficiência", inteiro_pt(total_deficiencia_2026))

            genero_agrupado_2026 = perfil_genero_2026.groupby(
                'CATEGORIA', as_index=False
            ).agg(ELEITORES=('QT_ELEITORES', 'sum')).sort_values(
                'ELEITORES', ascending=False
            )
            grafico_genero_2026 = alt.Chart(
                genero_agrupado_2026
            ).mark_bar().encode(
                x=alt.X('ELEITORES:Q', title='Eleitores'),
                y=alt.Y('CATEGORIA:N', title=None, sort='-x'),
                color=alt.Color('CATEGORIA:N', title='Gênero'),
                tooltip=[
                    alt.Tooltip('CATEGORIA:N', title='Gênero'),
                    alt.Tooltip('ELEITORES:Q', title='Eleitores', format=',')
                ]
            ).properties(height=180)
            exibir_grafico_altair(grafico_genero_2026)

            faixa_agrupada_2026 = demografia_filtrada_2026[
                demografia_filtrada_2026['DIMENSAO'] == 'FAIXA ETÁRIA'
            ].groupby('CATEGORIA', as_index=False).agg(
                ELEITORES=('QT_ELEITORES', 'sum')
            )
            ordem_faixa_2026 = [
                '16 anos', '17 anos', '18 anos', '19 anos', '20 anos',
                '21 a 24 anos', '25 a 29 anos', '30 a 34 anos',
                '35 a 39 anos', '40 a 44 anos', '45 a 49 anos',
                '50 a 54 anos', '55 a 59 anos', '60 a 64 anos',
                '65 a 69 anos', '70 a 74 anos', '75 a 79 anos',
                '80 a 84 anos', '85 a 89 anos', '90 a 94 anos',
                '95 a 99 anos', '100 anos ou mais', 'Inválida'
            ]
            grafico_faixa_2026 = alt.Chart(
                faixa_agrupada_2026
            ).mark_bar(color='#2878D0').encode(
                x=alt.X('ELEITORES:Q', title='Eleitores'),
                y=alt.Y(
                    'CATEGORIA:N',
                    title=None,
                    sort=ordem_faixa_2026
                ),
                tooltip=[
                    alt.Tooltip('CATEGORIA:N', title='Faixa etária'),
                    alt.Tooltip('ELEITORES:Q', title='Eleitores', format=',')
                ]
            ).properties(height=560)
            st.subheader("Faixa Etária")
            exibir_grafico_altair(grafico_faixa_2026)

            escolaridade_agrupada_2026 = demografia_filtrada_2026[
                demografia_filtrada_2026['DIMENSAO'] == 'ESCOLARIDADE'
            ].groupby('CATEGORIA', as_index=False).agg(
                ELEITORES=('QT_ELEITORES', 'sum')
            ).sort_values('ELEITORES', ascending=False)
            grafico_escolaridade_2026 = alt.Chart(
                escolaridade_agrupada_2026
            ).mark_bar(color='#6F42C1').encode(
                x=alt.X('ELEITORES:Q', title='Eleitores'),
                y=alt.Y('CATEGORIA:N', title=None, sort='-x'),
                tooltip=[
                    alt.Tooltip('CATEGORIA:N', title='Escolaridade'),
                    alt.Tooltip('ELEITORES:Q', title='Eleitores', format=',')
                ]
            ).properties(height=330)
            st.subheader("Escolaridade")
            exibir_grafico_altair(grafico_escolaridade_2026)

    with aba_metodologia:
        st.subheader("Metodologia, Fontes e Limitações")
        totais_validados = metadados_2026.get('validated_totals', {})
        tabela_conciliacao = pd.DataFrame([
            {
                'Indicador': 'Eleitorado total',
                'Arquivo analisado': totais_validados.get('electorate_snapshot', 0),
                'Referência TRE-AC': totais_validados.get('official_tre_electorate', 0),
                'Diferença': totais_validados.get('difference_snapshot_vs_official', 0),
            },
            {
                'Indicador': 'Eleitorado rural',
                'Arquivo analisado': totais_validados.get('rural_identified_snapshot', 0),
                'Referência TRE-AC': totais_validados.get('official_tre_rural', 0),
                'Diferença': totais_validados.get('difference_rural_identified_vs_official', 0),
            },
        ])
        st.dataframe(tabela_conciliacao, use_container_width=True, hide_index=True)
        st.caption(
            "As diferenças não são corrigidas artificialmente. Elas decorrem de "
            "datas de extração e critérios de disponibilização distintos e "
            "permanecem documentadas para auditoria."
        )

        st.markdown("**Critérios utilizados**")
        st.markdown(
            "- Cada seção aparece uma única vez na base territorial de 2026.\n"
            "- O eleitorado do local é a soma das seções desse local.\n"
            "- Rural identificada: termo `RURAL` no bairro ou no nome do local do TSE.\n"
            "- Registros apenas indiciários ficam em revisão e não entram no total rural.\n"
            "- O cruzamento histórico utiliza município, zona e seção.\n"
            "- 2022 é referência estadual; 2020 e 2024 não são extrapolados para o estado."
        )
        st.code(
            "Penetração histórica de referência (%) = "
            "Votos de Samir em 2022 / Eleitorado da seção ou local em 2026 × 100",
            language=None
        )
        st.warning(
            "Mudanças de cargo, seção, local de votação, comparecimento e contexto "
            "eleitoral impedem tratar essa razão como previsão de votos."
        )

        cobertura_2026 = metadados_2026.get('coverage', {})
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Municípios", inteiro_pt(cobertura_2026.get('municipalities', 0)))
        q2.metric("Locais", inteiro_pt(cobertura_2026.get('locations', 0)))
        q3.metric("Seções", inteiro_pt(cobertura_2026.get('sections', 0)))
        q4.metric(
            "Coordenadas Válidas",
            percentual_pt(cobertura_2026.get('valid_coordinates_pct', 0))
        )

        fonte_tse = metadados_2026.get('source', {}).get('tse_dataset', '')
        fonte_tre = metadados_2026.get('source', {}).get('tre_reference', '')
        st.markdown(
            f"**Fontes oficiais:** [Portal de Dados Abertos do TSE]({fonte_tse}) "
            f"e [referência pública do TRE-AC]({fonte_tre})."
        )
        st.download_button(
            "Baixar registro metodológico",
            data=json.dumps(
                metadados_2026, ensure_ascii=False, indent=2
            ).encode('utf-8'),
            file_name='metadados_cenario_2026.json',
            mime='application/json'
        )
