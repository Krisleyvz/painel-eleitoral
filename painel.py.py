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
from PIL import Image

# 1. Configuração da Página
st.set_page_config(page_title="Painel Executivo | Análise Territorial", page_icon="🎯", layout="wide")


# ==========================================
# PADRÃO RESPONSIVO PARA GRÁFICOS E LEGENDAS
# ==========================================
def exibir_acao_pratica(texto):
    """Traduz a leitura do dado em uma orientação operacional curta."""
    st.info(f"🎯 **Ação prática indicada:** {texto}")


def exibir_grafico_altair(grafico, acao_pratica=None):
    """Exibe gráficos sem cortar rótulos e, quando informado, orienta a ação."""
    grafico_responsivo = grafico.configure_axis(
        labelLimit=0
    ).configure_legend(
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
    if acao_pratica:
        exibir_acao_pratica(acao_pratica)


def exibir_metodologia_modulo(arquivos, metodo, limitacoes):
    """Apresenta fontes, método e limites no mesmo padrão visual da aba 7."""
    st.subheader("Fontes, Método e Limitações")
    st.markdown("**Arquivos analisados**")
    st.markdown("\n".join(f"- `{arquivo}`" for arquivo in arquivos))
    st.markdown("**Método de leitura**")
    st.write(metodo)
    st.warning(limitacoes)
    st.markdown(
        "**Fonte oficial:** [Portal de Dados Abertos do TSE]"
        "(https://dadosabertos.tse.jus.br/)."
    )

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
    [data-testid="stSidebar"] [role="radiogroup"] label p {
        white-space: nowrap !important;
        font-size: 0.92rem !important;
        line-height: 1.25rem !important;
    }
    .cc-hero {
        background: linear-gradient(115deg, #0A1C2E 0%, #123D63 100%);
        border-radius: 16px;
        padding: 24px 28px;
        margin: 4px 0 20px 0;
        color: #FFFFFF;
        box-shadow: 0 6px 20px rgba(10, 28, 46, 0.12);
    }
    .cc-hero h2 { margin: 0 0 8px 0; color: #FFFFFF; }
    .cc-hero p { margin: 0; color: #EAF2F8; font-size: 1.04rem; }
    .cc-kicker {
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
        color: #B8D7F0;
        margin-bottom: 6px;
    }
    .cc-card {
        border: 1px solid #DCE7F2;
        border-radius: 14px;
        padding: 16px 18px;
        min-height: 150px;
        background: #FFFFFF;
        box-shadow: 0 3px 12px rgba(10, 28, 46, 0.06);
    }
    .cc-card h4 { margin: 0 0 8px 0; color: #0A1C2E; }
    .cc-card .cc-numero { font-size: 1.65rem; font-weight: 800; color: #0A1C2E; }
    .cc-card p { margin: 6px 0 0 0; color: #425466; line-height: 1.35; }
    .cc-tag {
        display: inline-block;
        border-radius: 999px;
        padding: 4px 9px;
        background: #EAF3FB;
        color: #0B5EA8;
        font-size: 0.78rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

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
except Exception as erro_dados:
    st.error("Erro ao carregar o arquivo 'dados.csv'.")
    with st.expander("Detalhes técnicos para diagnóstico"):
        st.code(f"{type(erro_dados).__name__}: {erro_dados}")
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

CHAVES_SECAO = [
    'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'
]


def dataframe_vazio_com_erro(nome_base, erro):
    """Preserva o motivo técnico sem derrubar as demais áreas do painel."""
    vazio = pd.DataFrame()
    vazio.attrs['erro_carregamento'] = (
        f"{nome_base}: {type(erro).__name__}: {erro}"
    )
    return vazio


def exibir_detalhes_erro_base(base):
    """Exibe o erro real somente quando houve falha de leitura ou tratamento."""
    detalhe = base.attrs.get('erro_carregamento')
    if detalhe:
        with st.expander("Detalhes técnicos para diagnóstico"):
            st.code(detalhe)


def construir_mapa_secoes(df_votos):
    """Cria uma referência única de local e tipo de zona para cada seção.

    O município integra a chave para impedir cruzamentos acidentais entre
    seções homônimas. A validação bloqueia duplicações silenciosas caso uma
    seção passe a apontar para mais de um local na mesma eleição.
    """
    colunas_mapa = CHAVES_SECAO + ['NM_LOCAL_VOTACAO', 'TIPO_ZONA']
    faltantes = [coluna for coluna in colunas_mapa if coluna not in df_votos]
    if faltantes:
        raise KeyError(
            "Colunas ausentes no mapa de seções: " + ', '.join(faltantes)
        )

    mapa = df_votos[colunas_mapa].drop_duplicates().copy()
    chaves_duplicadas = mapa.duplicated(CHAVES_SECAO, keep=False)
    if chaves_duplicadas.any():
        quantidade = mapa.loc[chaves_duplicadas, CHAVES_SECAO].drop_duplicates().shape[0]
        raise ValueError(
            f"{quantidade} seção(ões) possuem mais de um local ou tipo de zona."
        )
    return mapa


def aplicar_filtros_base_auxiliar(
    base, ano_selecionado, municipios_selecionados, zona_selecionada
):
    """Replica os filtros globais nas bases auxiliares das rotas históricas."""
    filtrada = base.copy()

    if ano_selecionado != 'Todos os Anos (Série Histórica)':
        filtrada = filtrada[
            filtrada['ANO_ELEICAO'] == int(ano_selecionado)
        ]

    if municipios_selecionados is not None:
        colunas_municipio = [
            coluna for coluna in [
                'NM_MUNICIPIO', 'NM_MUNICIPIO_x', 'NM_MUNICIPIO_y'
            ] if coluna in filtrada.columns
        ]
        if colunas_municipio:
            mascara_municipio = pd.Series(
                False, index=filtrada.index, dtype=bool
            )
            for coluna in colunas_municipio:
                mascara_municipio |= filtrada[coluna].isin(
                    municipios_selecionados
                )
            filtrada = filtrada[mascara_municipio]

    if zona_selecionada != 'Todas as Zonas':
        if 'TIPO_ZONA' not in filtrada.columns:
            raise KeyError(
                "A base auxiliar não recebeu a coluna TIPO_ZONA."
            )
        filtrada = filtrada[
            filtrada['TIPO_ZONA'] == zona_selecionada
        ]

    return filtrada.copy()


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

        if not df_votos.empty and not df_demo.empty:
            mapa_escolas = construir_mapa_secoes(df_votos)
            df_demo = pd.merge(
                df_demo,
                mapa_escolas,
                on=CHAVES_SECAO,
                how='inner',
                validate='many_to_one'
            )
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
            chaves_correcao_perfil = [
                'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA',
                'NM_LOCAL_VOTACAO'
            ]
            fator_correcao = df_demo.groupby(
                chaves_correcao_perfil
            )['VOTOS_ESTIMADOS_SAMIR'].transform('sum')
            fator_correcao = np.where(fator_correcao > 0, df_demo['QT_VOTOS_SAMIR'] / fator_correcao, 0)
            df_demo['VOTOS_ESTIMADOS_SAMIR'] = df_demo['VOTOS_ESTIMADOS_SAMIR'] * fator_correcao
        return df_demo
    except Exception as erro:
        return dataframe_vazio_com_erro('base_demografica_ac.zip', erro)

@st.cache_data
def carregar_adormecidos(df_votos):
    try:
        if os.path.exists("base_adormecidos_ac.csv"):
            df_ador = pd.read_csv("base_adormecidos_ac.csv")
            if not df_votos.empty:
                mapa_escolas = construir_mapa_secoes(df_votos)
                df_ador = pd.merge(
                    df_ador,
                    mapa_escolas,
                    on=CHAVES_SECAO,
                    how='inner',
                    validate='one_to_one'
                )
            return df_ador
        return pd.DataFrame()
    except Exception as erro:
        return dataframe_vazio_com_erro('base_adormecidos_ac.csv', erro)

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

        if not df_votos.empty and not df_conc.empty:
            mapa_escolas = construir_mapa_secoes(df_votos)
            df_conc = pd.merge(
                df_conc,
                mapa_escolas,
                on=CHAVES_SECAO,
                how='inner',
                validate='many_to_one'
            )
        return df_conc
    except Exception as erro:
        return dataframe_vazio_com_erro('base_concorrencia_ac.zip', erro)

dados_demo = carregar_demografia(dados)
dados_adormecidos = carregar_adormecidos(dados)
dados_concorrencia = carregar_concorrencia(dados)


# ==========================================
# RADAR POLÍTICO — LEITURA DA BASE AUTOMÁTICA
# ==========================================
PLANILHA_RADAR_ID = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
ABA_RADAR_POLITICO = "Radar_Politico"


@st.cache_data(ttl=60)
def carregar_radar_politico():
    """Lê a aba gerada pelo coletor sem derrubar o restante do painel."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credenciais = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scopes
        )
        cliente = gspread.authorize(credenciais)
        aba = cliente.open_by_key(PLANILHA_RADAR_ID).worksheet(ABA_RADAR_POLITICO)
        registros = aba.get_all_records()
        if not registros:
            return pd.DataFrame()
        radar = pd.DataFrame(registros)
        for coluna in ['COLETADO_EM', 'PUBLICADO_EM']:
            if coluna in radar.columns:
                radar[coluna] = pd.to_datetime(radar[coluna], errors='coerce', utc=True)
        return radar
    except Exception as erro:
        vazio = pd.DataFrame()
        vazio.attrs['erro_carregamento'] = f"{type(erro).__name__}: {erro}"
        return vazio


def radar_bool(serie):
    """Converte booleanos vindos do Google Sheets para uma máscara confiável."""
    if serie is None:
        return pd.Series(dtype=bool)
    if getattr(serie, 'dtype', None) == bool:
        return serie.fillna(False)
    return serie.astype(str).str.strip().str.upper().isin(['TRUE', 'VERDADEIRO', '1', 'SIM', 'YES'])


def filtrar_radar_periodo(radar, periodo):
    if radar.empty or 'COLETADO_EM' not in radar.columns or periodo == 'Todo o histórico':
        return radar.copy()
    horas = {'Últimas 24 horas': 24, 'Últimos 7 dias': 24 * 7, 'Últimos 30 dias': 24 * 30}.get(periodo)
    if not horas:
        return radar.copy()
    agora_utc = pd.Timestamp.now(tz='UTC')
    limite = agora_utc - pd.Timedelta(hours=horas)
    return radar[radar['COLETADO_EM'].notna() & (radar['COLETADO_EM'] >= limite)].copy()



# ==========================================
# FINANCEIRO — DADOS PÚBLICOS DO TSE
# ==========================================
ARQUIVO_FINANCEIRO_RUNTIME = "financeiro_runtime.json"
FINANCEIRO_TSE_BASE = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
FINANCEIRO_TSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://divulgacandcontas.tse.jus.br/divulga/",
    "Origin": "https://divulgacandcontas.tse.jus.br",
}
FINANCEIRO_CAMPANHAS = {
    2026: {
        "ue": "AC",
        "cargo": 7,
        "cargo_nome": "Deputado Estadual",
        "numero": 11106,
        "partido": 11,
        "id_candidato": "10002544519",
        "eleicoes": [20322002026, 2062262026],
    },
    2024: {
        "ue": "1392",
        "cargo": 13,
        "cargo_nome": "Vereador",
        "numero": 11106,
        "partido": 11,
        "eleicoes": [2045202024],
    },
}

# Último snapshot público conhecido para 2026. É usado somente se a API do TSE
# não responder; a tela o marca como desatualizado e tenta novamente no refresh.
FINANCEIRO_FALLBACK_2026 = {
    "ano": 2026,
    "cargo": "Deputado Estadual",
    "numero": 11106,
    "partido": "PP",
    "cnpj": "68499897000183",
    "atualizado_tse_em": "2026-08-27T15:13:00-05:00",
    "status": "desatualizado",
    "resumo": {
        "total_recebido": 0.0,
        "despesas_contratadas": 0.0,
        "despesas_pagas": 0.0,
        "saldo_caixa_aproximado": 0.0,
        "limite_gastos": 1270629.01,
        "percentual_limite_contratado": 0.0,
    },
    "origens_recursos": [],
    "natureza_receitas": [],
    "doadores": [],
    "fornecedores": [],
    "categorias_despesa": [],
    "historico_entregas": [],
    "tem_extratos": False,
    "tem_notas_fiscais": False,
}

# Contingência histórica: 2024 já é uma prestação final. Estes totais foram
# conferidos no material de referência enviado para esta implementação e só são
# usados se a consulta pública do TSE estiver temporariamente indisponível.
FINANCEIRO_FALLBACK_2024 = {
    "ano": 2024,
    "cargo": "Vereador",
    "numero": 11106,
    "partido": "PP",
    "status": "historico_contingencia",
    "resumo": {
        "total_recebido": 156410.0,
        "despesas_contratadas": 127241.0,
        "despesas_pagas": 127241.0,
        "saldo_caixa_aproximado": 29169.0,
        "limite_gastos": 0.0,
        "percentual_limite_contratado": 0.0,
    },
    "origens_recursos": [
        {"origem": "Fundo Especial", "valor": 127500.0},
        {"origem": "Outros recursos", "valor": 28910.0},
    ],
    "natureza_receitas": [],
    "doadores": [
        {"nome": "PROGRESSISTAS - BRASIL - BR - NACIONAL", "documento": "", "valor": 127500.0},
        {"nome": "ELIAS FIRMINO DE FARIAS", "documento": "", "valor": 4500.0},
        {"nome": "NABIHA BESTENE KOURY", "documento": "", "valor": 3250.0},
        {"nome": "TAMARA ABDALLA ISPER", "documento": "", "valor": 3250.0},
        {"nome": "MARIA LUCIA DA COSTA AMORIM", "documento": "", "valor": 3000.0},
        {"nome": "NATHALIN KRISHNA ROCHA DE ASSUNCAO", "documento": "", "valor": 2250.0},
    ],
    "fornecedores": [
        {"nome": "J A COMUNICACAO VISUAL LTDA", "documento": "", "valor": 75000.0},
        {"nome": "MARIA KLAUDIA MENDES DA SILVA", "documento": "", "valor": 7750.0},
        {"nome": "ANGELA MARIA FERREIRA", "documento": "", "valor": 5000.0},
        {"nome": "AJS DERIVADOS DE PETROLEO LTDA", "documento": "", "valor": 4920.0},
        {"nome": "FRANCISCO BRITO DO NASCIMENTO", "documento": "", "valor": 4250.0},
        {"nome": "M S FEITOSA", "documento": "", "valor": 3201.0},
        {"nome": "ANTONIA RODRIGUES MARQUES GOMES", "documento": "", "valor": 2250.0},
        {"nome": "ALAMO CARIO FERNANDES DE HOLANDA", "documento": "", "valor": 2000.0},
    ],
    "categorias_despesa": [
        {"categoria": "Publicidade por materiais impressos", "valor": 75000.0, "quantidade": 6},
        {"categoria": "Atividades de militância e mobilização de rua", "valor": 22010.0, "quantidade": 15},
        {"categoria": "Alimentação", "valor": 7750.0, "quantidade": 3},
        {"categoria": "Serviços advocatícios", "valor": 5000.0, "quantidade": 1},
        {"categoria": "Combustíveis e lubrificantes", "valor": 4920.0, "quantidade": 1},
        {"categoria": "Serviços contábeis", "valor": 4250.0, "quantidade": 1},
        {"categoria": "Materiais de expediente", "valor": 3201.0, "quantidade": 1},
    ],
    "historico_entregas": [],
    "tem_extratos": False,
    "tem_notas_fiscais": False,
    "observacao_contingencia": (
        "Snapshot final de 2024 usado apenas quando a fonte pública do TSE não responde."
    ),
}


def valor_financeiro(valor):
    try:
        if valor in (None, ""):
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        texto = str(valor).strip().replace("R$", "").replace(" ", "")
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            texto = texto.replace(",", ".")
        return float(texto)
    except (TypeError, ValueError):
        return 0.0


def moeda_pt(valor, casas=2):
    numero = valor_financeiro(valor)
    texto = f"{numero:,.{casas}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def documento_publico_financeiro(valor):
    """Mantém CNPJ legível e mascara CPF no painel executivo."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    if len(digitos) == 14:
        return (
            f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/"
            f"{digitos[8:12]}-{digitos[12:]}"
        )
    if len(digitos) == 11:
        return f"***.{digitos[3:6]}.{digitos[6:9]}-**"
    return str(valor or "")


def data_financeiro_legivel(valor):
    if not valor:
        return "não informada"
    try:
        instante = pd.to_datetime(valor, utc=True)
        if pd.isna(instante):
            return str(valor)
        return instante.tz_convert("America/Rio_Branco").strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _fin_normalizar_texto(valor):
    texto = '' if valor is None else str(valor)
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ascii', errors='ignore').decode('ascii')
    texto = re.sub(r'[^A-Za-z0-9]+', ' ', texto.upper())
    return re.sub(r'\s+', ' ', texto).strip()


def _fin_primeiro(obj, *chaves, default=None):
    for chave in chaves:
        if isinstance(obj, dict) and obj.get(chave) not in (None, ''):
            return obj.get(chave)
    return default


def _fin_lista(payload, *chaves):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for chave in chaves:
            valor = payload.get(chave)
            if isinstance(valor, list):
                return [x for x in valor if isinstance(x, dict)]
    return []


def _fin_get(session, caminho, tentativas=2):
    import time

    url = caminho if caminho.startswith('http') else FINANCEIRO_TSE_BASE + caminho
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            resposta = session.get(
                url,
                headers=FINANCEIRO_TSE_HEADERS,
                timeout=25,
            )
            resposta.raise_for_status()
            return resposta.json()
        except Exception as erro:
            ultimo_erro = erro
            if tentativa + 1 < tentativas:
                time.sleep(1.2 * (tentativa + 1))
    raise RuntimeError(str(ultimo_erro))


def _fin_ids_eleicao(session, ano):
    ids = []
    try:
        payload = _fin_get(session, '/eleicao/ordinarias')
        itens = _fin_lista(payload, 'eleicoes', 'items', 'resultados')
        for item in itens:
            ano_item = _fin_primeiro(item, 'ano', 'anoEleicao', 'anoReferencia')
            id_item = _fin_primeiro(item, 'id', 'idEleicao', 'sqEleicao', 'codigo')
            try:
                if int(ano_item) == int(ano) and int(id_item) not in ids:
                    ids.append(int(id_item))
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    for fallback in FINANCEIRO_CAMPANHAS[ano]['eleicoes']:
        if fallback not in ids:
            ids.append(fallback)
    return ids


def _fin_localizar_candidato(session, ano, eleicao, config):
    try:
        payload = _fin_get(
            session,
            f"/candidatura/listar/{ano}/{config['ue']}/{eleicao}/{config['cargo']}/candidatos",
        )
    except Exception:
        return None
    candidatos = _fin_lista(payload, 'candidatos', 'items', 'resultados')
    for candidato in candidatos:
        nome = _fin_normalizar_texto(
            _fin_primeiro(candidato, 'nomeCompleto', 'nomeUrna', 'nome', 'nmCandidato')
        )
        if 'SAMIR' in nome and 'BESTENE' in nome:
            return candidato
    return None


def _fin_candidato_id(candidato, config):
    valor = _fin_primeiro(
        candidato or {}, 'id', 'idCandidato', 'sqCandidato', 'sequencial', 'sq_candidato'
    )
    return str(valor or config.get('id_candidato') or '')


def _fin_partido_numero(candidato, config):
    partido = candidato.get('partido') if isinstance(candidato, dict) and isinstance(candidato.get('partido'), dict) else {}
    valor = _fin_primeiro(
        candidato or {}, 'numeroPartido', 'nrPartido',
        default=_fin_primeiro(partido, 'numero', 'nrPartido', default=config.get('partido'))
    )
    try:
        return int(valor)
    except (TypeError, ValueError):
        return int(config.get('partido', 11))


def _fin_numero_candidato(candidato, config):
    valor = _fin_primeiro(candidato or {}, 'numero', 'numeroCandidato', 'nrCandidato', default=config['numero'])
    try:
        return int(valor)
    except (TypeError, ValueError):
        return int(config['numero'])


def _fin_consultar_prestador(session, ano, eleicao, config, candidato):
    id_candidato = _fin_candidato_id(candidato, config)
    if not id_candidato:
        raise RuntimeError('Identificador da candidatura não localizado.')
    nr_partido = _fin_partido_numero(candidato, config)
    nr_candidato = _fin_numero_candidato(candidato, config)
    caminhos = [
        f"/prestador/consulta/{eleicao}/{ano}/{config['ue']}/{config['cargo']}/90/90/{id_candidato}",
        f"/prestador/consulta/{eleicao}/{ano}/{config['ue']}/{config['cargo']}/{nr_partido}/{id_candidato}",
        f"/prestador/consulta/{eleicao}/{ano}/{config['ue']}/{config['cargo']}/{nr_partido}/{nr_candidato}/{id_candidato}",
    ]
    erros = []
    for caminho in caminhos:
        try:
            payload = _fin_get(session, caminho)
            if isinstance(payload, dict) and payload:
                return payload, id_candidato
        except Exception as erro:
            erros.append(str(erro))
    raise RuntimeError(' | '.join(erros[-3:]))


def _fin_limpar_ranking(itens, tipo):
    saida = []
    if not isinstance(itens, list):
        return saida
    for item in itens:
        if not isinstance(item, dict):
            continue
        saida.append({
            'nome': str(_fin_primeiro(
                item, 'nome', 'nomeDoador', 'nomeFornecedor', 'nmDoador', 'nmFornecedor',
                default='Não informado'
            )),
            'documento': str(_fin_primeiro(
                item, 'cpfCnpj', 'cpfCnpjDoador', 'cpfCnpjFornecedor', 'nrCpfCnpj', default=''
            )),
            'valor': valor_financeiro(_fin_primeiro(
                item, 'valor', 'vrReceita', 'vrDespesa', 'total', default=0
            )),
            'quantidade': _fin_primeiro(item, 'qntd', 'qtde', 'quantidade', 'qtd', default=''),
            'tipo': tipo,
        })
    return sorted(saida, key=lambda x: x['valor'], reverse=True)


def _fin_limpar_categorias(itens):
    saida = []
    if not isinstance(itens, list):
        return saida
    for item in itens:
        if not isinstance(item, dict):
            continue
        saida.append({
            'categoria': str(_fin_primeiro(
                item, 'dsDRD', 'descricao', 'categoria', 'dsOrigemDespesa', default='Não informado'
            )),
            'valor': valor_financeiro(_fin_primeiro(item, 'valor', 'vrDespesa', 'total', default=0)),
            'quantidade': _fin_primeiro(item, 'qtdeDespesas', 'qtd', 'quantidade', default=''),
        })
    return sorted(saida, key=lambda x: x['valor'], reverse=True)


def _fin_resumir(payload, ano, config, eleicao, id_candidato):
    consolidado = payload.get('dadosConsolidados') or {}
    despesas = payload.get('despesas') or {}
    total_recebido = valor_financeiro(consolidado.get('totalRecebido'))
    total_financeiro = valor_financeiro(consolidado.get('totalFinanceiro'))
    total_estimado = valor_financeiro(consolidado.get('totalEstimados'))
    despesas_contratadas = valor_financeiro(despesas.get('totalDespesasContratadas'))
    despesas_pagas = valor_financeiro(despesas.get('totalDespesasPagas'))
    limite = valor_financeiro(_fin_primeiro(
        despesas, 'valorLimiteDeGastos', 'limiteDeGasto1T', default=0
    ))
    fefc = valor_financeiro(consolidado.get('graphVrReceitaFinFefc'))
    fundo = valor_financeiro(consolidado.get('graphVrReceitaFinFundo'))
    outros_fin = valor_financeiro(consolidado.get('graphVrReceitaFinOutros'))
    if total_financeiro and not any([fefc, fundo, outros_fin]):
        outros_fin = total_financeiro
    origens = [
        {'origem': 'Fundo Eleitoral (FEFC)', 'valor': fefc},
        {'origem': 'Fundo Partidário', 'valor': fundo},
        {'origem': 'Outros recursos financeiros', 'valor': outros_fin},
        {'origem': 'Recursos estimáveis', 'valor': total_estimado},
    ]
    origens = [x for x in origens if x['valor'] > 0]
    natureza = [
        {'natureza': 'Pessoas físicas', 'valor': valor_financeiro(consolidado.get('totalReceitaPF'))},
        {'natureza': 'Partidos', 'valor': valor_financeiro(consolidado.get('totalPartidos'))},
        {'natureza': 'Recursos próprios', 'valor': valor_financeiro(consolidado.get('totalProprios'))},
        {'natureza': 'Outros candidatos/partidos', 'valor': valor_financeiro(consolidado.get('totalReceitaOutCand'))},
        {'natureza': 'Financiamento coletivo', 'valor': valor_financeiro(consolidado.get('totalInternet'))},
    ]
    natureza = [x for x in natureza if x['valor'] > 0]
    return {
        'ano': ano,
        'cargo': config['cargo_nome'],
        'numero': _fin_primeiro(payload, 'nrCandidato', default=config['numero']),
        'partido': _fin_primeiro(payload, 'siglaPartido', default='PP'),
        'cnpj': _fin_primeiro(payload, 'cnpj', default=''),
        'id_eleicao': eleicao,
        'id_candidato': id_candidato,
        'atualizado_tse_em': _fin_primeiro(payload, 'dataUltimaAtualizacaoContas', default=''),
        'resumo': {
            'total_recebido': total_recebido,
            'total_financeiro': total_financeiro,
            'total_estimado': total_estimado,
            'despesas_contratadas': despesas_contratadas,
            'despesas_pagas': despesas_pagas,
            'saldo_caixa_aproximado': max(total_recebido - despesas_pagas, 0),
            'limite_gastos': limite,
            'percentual_limite_contratado': despesas_contratadas / limite * 100 if limite > 0 else 0,
        },
        'origens_recursos': origens,
        'natureza_receitas': natureza,
        'doadores': _fin_limpar_ranking(payload.get('rankingDoadores'), 'doador'),
        'fornecedores': _fin_limpar_ranking(payload.get('rankingFornecedores'), 'fornecedor'),
        'categorias_despesa': _fin_limpar_categorias(payload.get('concentracaoDespesas')),
        'historico_entregas': payload.get('historicoEntregas') if isinstance(payload.get('historicoEntregas'), list) else [],
        'tem_extratos': bool(payload.get('haveExtratos')),
        'tem_notas_fiscais': bool(payload.get('haveNfes')),
        'status': 'ok',
    }


@st.cache_data(ttl=1800)
def coletar_financeiro_tse_ao_vivo():
    """Consulta o TSE somente quando a rota Financeiro é aberta; cache de 30 min."""
    import requests

    resultado = {
        'schema_version': 1,
        'gerado_em': datetime.now(pytz.UTC).isoformat(),
        'fonte': 'TSE — DivulgaCandContas',
        'fonte_url': 'https://divulgacandcontas.tse.jus.br/divulga/',
        'status': 'ok',
        'campanhas': {},
        'erros': [],
        'modo_atualizacao': 'consulta_direta_cache_30min',
    }
    session = requests.Session()
    session.headers.update(FINANCEIRO_TSE_HEADERS)

    for ano in [2026, 2024]:
        config = FINANCEIRO_CAMPANHAS[ano]
        erro_ano = []
        campanha = None
        for eleicao in _fin_ids_eleicao(session, ano):
            candidato = _fin_localizar_candidato(session, ano, eleicao, config)
            try:
                payload, id_candidato = _fin_consultar_prestador(
                    session, ano, eleicao, config, candidato
                )
                campanha = _fin_resumir(payload, ano, config, eleicao, id_candidato)
                break
            except Exception as erro:
                erro_ano.append(f"{eleicao}: {erro}")
        if campanha is None:
            if ano == 2024:
                campanha = json.loads(json.dumps(FINANCEIRO_FALLBACK_2024))
                campanha['erro_atualizacao'] = ' | '.join(erro_ano[-3:])
            else:
                campanha = json.loads(json.dumps(FINANCEIRO_FALLBACK_2026))
                campanha['erro_atualizacao'] = ' | '.join(erro_ano[-3:])
                resultado['status'] = 'parcial'
            resultado['erros'].append({'ano': ano, 'erro': ' | '.join(erro_ano[-3:])})
        resultado['campanhas'][str(ano)] = campanha
    return resultado


@st.cache_data(ttl=300)
def carregar_financeiro_runtime():
    """Prefere snapshot local; sem ele, consulta o TSE ao vivo com cache."""
    if os.path.exists(ARQUIVO_FINANCEIRO_RUNTIME):
        try:
            with open(ARQUIVO_FINANCEIRO_RUNTIME, 'r', encoding='utf-8') as arquivo:
                payload = json.load(arquivo)
            if (
                isinstance(payload, dict)
                and payload.get('gerado_em')
                and isinstance(payload.get('campanhas'), dict)
            ):
                return payload
        except Exception:
            pass
    return coletar_financeiro_tse_ao_vivo()


def campanha_financeira(runtime, ano):
    campanhas = runtime.get('campanhas', {}) if isinstance(runtime, dict) else {}
    campanha = campanhas.get(str(ano), {})
    return campanha if isinstance(campanha, dict) else {}


# ==========================================
# 3. BARRA LATERAL (MENUS E FILTROS)
# ==========================================

# A imagem original da marca tem grandes margens e fundo preto. O tratamento
# acontece somente em memória: o preto fica transparente e o arquivo original
# não é alterado.
def carregar_logo_sidebar(caminho):
    imagem = Image.open(caminho).convert("RGBA")
    luminosidade = imagem.convert("L")

    # A marca é branca sobre preto. Usar a luminosidade como transparência
    # remove o retângulo preto e preserva as bordas suavizadas das letras.
    transparencia = luminosidade.point(lambda pixel: 0 if pixel < 12 else pixel)
    logo_transparente = Image.new("RGBA", imagem.size, (255, 255, 255, 0))
    logo_transparente.putalpha(transparencia)
    caixa_conteudo = transparencia.point(
        lambda pixel: 255 if pixel > 18 else 0
    ).getbbox()

    if not caixa_conteudo:
        return logo_transparente

    esquerda, superior, direita, inferior = caixa_conteudo
    margem_x = max(24, int((direita - esquerda) * 0.04))
    margem_y = max(18, int((inferior - superior) * 0.10))

    return logo_transparente.crop((
        max(0, esquerda - margem_x),
        max(0, superior - margem_y),
        min(logo_transparente.width, direita + margem_x),
        min(logo_transparente.height, inferior + margem_y),
    ))


try:
    logo_sidebar = carregar_logo_sidebar("IMG_6008.PNG")
    st.sidebar.image(logo_sidebar, use_container_width=True)
except Exception:
    st.sidebar.markdown(
        "<h3 style='text-align: center;'>SAMIR BESTENE</h3>",
        unsafe_allow_html=True,
    )

try:
    st.sidebar.image("IMG_3571.PNG", use_container_width=True)
except Exception:
    pass

st.sidebar.header("🧭 Navegação do Sistema")
rotas_menu = {
    "🎯 1. Central de Comando 2026": "🎯 Central de Comando 2026",
    "🛰️ 2. Inteligência Política": "🛰️ Inteligência Política",
    "💰 3. Financeiro": "💰 Financeiro",
    "📊 4. Território e Eleitorado": "📊 1. Desempenho Eleitoral por Território",
    "🗺️ 5. Participação Eleitoral": "🗺️ 3. Participação e Não Comparecimento",
    "📋 6. Concorrência": "📋 4. Panorama da Concorrência",
    "🔗 7. Correlação Territorial": "🔗 5. Correlação territorial",
    "🚜 8. Zona Rural": "🚜 6. Análise Territorial da Zona Rural",
    "🗳️ 9. Cenário 2026": "🗳️ 7. Cenário Eleitoral 2026",
}
opcao_menu = st.sidebar.radio(
    "Selecione o Painel Desejado:",
    list(rotas_menu.keys())
)
menu_selecionado = rotas_menu[opcao_menu]
st.sidebar.markdown("---")

rota_central_comando = menu_selecionado == "🎯 Central de Comando 2026"
rota_inteligencia_politica = menu_selecionado == "🛰️ Inteligência Política"
rota_financeiro = menu_selecionado == "💰 Financeiro"
rota_cenario_2026 = menu_selecionado == "🗳️ 7. Cenário Eleitoral 2026"

if rota_central_comando:
    st.sidebar.header("🎛️ Recorte Executivo")
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

    municipios_central_disponiveis = (
        sorted(eleitorado_2026['NM_MUNICIPIO'].dropna().unique())
        if not eleitorado_2026.empty else []
    )
    municipio_central = st.sidebar.selectbox(
        "Município:",
        ["Todo o Acre"] + municipios_central_disponiveis
    )
    modo_reuniao = st.sidebar.checkbox(
        "📺 Modo reunião",
        value=False,
        help=(
            "Mantém somente a leitura executiva, prioridades e listas curtas, "
            "reduzindo explicações técnicas na tela."
        )
    )
    st.sidebar.caption(
        "A Central cruza o eleitorado atual de 2026 com referências históricas "
        "já existentes no painel."
    )

elif rota_inteligencia_politica:
    st.sidebar.header("🛰️ Filtros do Radar")
    periodo_radar = st.sidebar.selectbox(
        "Período:",
        ["Últimas 24 horas", "Últimos 7 dias", "Últimos 30 dias", "Todo o histórico"]
    )
    nivel_radar = st.sidebar.multiselect(
        "Nível de atenção:",
        ["CRITICO", "IMPORTANTE", "ACOMPANHAR", "INFORMATIVO"],
        default=["CRITICO", "IMPORTANTE", "ACOMPANHAR", "INFORMATIVO"]
    )
    apenas_samir_radar = st.sidebar.checkbox("Somente menções diretas a Samir", value=False)
    st.sidebar.caption(
        "O radar usa somente fontes públicas. A IA não recebe bases internas da campanha."
    )

elif rota_financeiro:
    st.sidebar.header("💰 Financeiro da Campanha")
    runtime_financeiro_sidebar = carregar_financeiro_runtime()
    anos_financeiros = sorted(
        [str(a) for a in runtime_financeiro_sidebar.get("campanhas", {}).keys()],
        reverse=True,
    )
    if not anos_financeiros:
        anos_financeiros = ["2026", "2024"]
    ano_financeiro = st.sidebar.selectbox(
        "Eleição:",
        anos_financeiros,
        index=0,
    )
    st.sidebar.caption(
        "Dados públicos declarados à Justiça Eleitoral. A tela usa um snapshot "
        "automático para permanecer rápida e auditável."
    )

elif rota_cenario_2026:
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

    st.sidebar.caption(
        "Versão 24/08/2026 • Central de Comando + Radar Político"
    )

    st.sidebar.markdown("---")
    mostrar_todas = st.sidebar.checkbox("👁️ Exibir TODOS os locais", value=False)
    limite_slider = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5, disabled=mostrar_todas)
    limite_ranking = 999999 if mostrar_todas else limite_slider

    label_periodo = "Série Histórica Acumulada" if ano_selecionado == 'Todos os Anos (Série Histórica)' else f"Ano de {ano_selecionado}"

# ==========================================
# CENTRAL DE COMANDO 2026 — VISÃO EXECUTIVA
# ==========================================
if menu_selecionado == "🎯 Central de Comando 2026":
    st.title("🎯 Central de Comando 2026")

    escopo_central = (
        "Todo o Acre"
        if municipio_central == "Todo o Acre"
        else municipio_central.title()
    )
    st.markdown(
        f"""
        <div class="cc-hero">
            <div class="cc-kicker">Leitura executiva • {escopo_central}</div>
            <h2>O que exige atenção da coordenação agora</h2>
            <p>Campanha sem leitura territorial reage. Com inteligência territorial, escolhe onde agir.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # A Central usa a base histórica completa carregada no início do aplicativo.
    # O filtro executivo é aplicado localmente para não alterar nenhuma das demais rotas.
    historico_central = dados.copy()
    col_municipio_central = next(
        (
            coluna for coluna in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']
            if coluna in historico_central.columns
        ),
        None
    )
    if municipio_central != "Todo o Acre" and col_municipio_central:
        historico_central = historico_central[
            historico_central[col_municipio_central] == municipio_central
        ].copy()

    if erro_bases_2026:
        eleitorado_central = pd.DataFrame()
        st.warning(
            "A Central abriu com a série histórica, mas as bases independentes de "
            f"2026 não puderam ser carregadas. Detalhe: {erro_bases_2026}"
        )
    else:
        eleitorado_central = eleitorado_2026.copy()
        if municipio_central != "Todo o Acre":
            eleitorado_central = eleitorado_central[
                eleitorado_central['NM_MUNICIPIO'] == municipio_central
            ].copy()

    # Indicadores executivos básicos.
    total_votos_historicos_central = pd.to_numeric(
        historico_central.get('QT_VOTOS_SAMIR', pd.Series(dtype=float)),
        errors='coerce'
    ).fillna(0).sum()

    chaves_local_historico = [
        coluna for coluna in [
            col_municipio_central, 'NR_ZONA', 'NM_LOCAL_VOTACAO'
        ] if coluna and coluna in historico_central.columns
    ]
    total_locais_historicos_central = (
        historico_central[chaves_local_historico].drop_duplicates().shape[0]
        if chaves_local_historico else 0
    )

    total_eleitores_central = (
        pd.to_numeric(eleitorado_central['QT_ELEITOR_SECAO'], errors='coerce')
        .fillna(0).sum()
        if not eleitorado_central.empty else 0
    )
    total_locais_2026_central = (
        eleitorado_central['ID_LOCAL_2026'].nunique()
        if not eleitorado_central.empty and 'ID_LOCAL_2026' in eleitorado_central
        else 0
    )
    total_secoes_2026_central = (
        eleitorado_central['ID_SECAO_2026'].nunique()
        if not eleitorado_central.empty and 'ID_SECAO_2026' in eleitorado_central
        else 0
    )

    matriz_central = pd.DataFrame()
    cobertura_central = 0.0
    comparaveis_central = pd.DataFrame()
    oportunidades_central = pd.DataFrame()
    consolidar_central = pd.DataFrame()
    mediana_eleitores_central = 0.0
    mediana_penetracao_central = 0.0

    if not eleitorado_central.empty:
        matriz_central, cobertura_central = construir_matriz_oportunidades_2026(
            eleitorado_central,
            historico_central
        )
        if not matriz_central.empty:
            comparaveis_central = matriz_central[
                matriz_central['COBERTURA_SECOES_PCT'] > 0
            ].copy()

        if not comparaveis_central.empty:
            mediana_eleitores_central = comparaveis_central[
                'ELEITORES_2026'
            ].median()
            mediana_penetracao_central = comparaveis_central[
                'PENETRACAO_REFERENCIA_PCT'
            ].median()

            alta_escala = (
                comparaveis_central['ELEITORES_2026']
                >= mediana_eleitores_central
            )
            baixa_penetracao = (
                comparaveis_central['PENETRACAO_REFERENCIA_PCT']
                < mediana_penetracao_central
            )
            comparaveis_central['LEITURA_EXECUTIVA'] = np.select(
                [
                    alta_escala & baixa_penetracao,
                    alta_escala & ~baixa_penetracao,
                    ~alta_escala & baixa_penetracao,
                ],
                [
                    'INVESTIGAR EXPANSÃO',
                    'CONSOLIDAR PRESENÇA',
                    'MONITORAR / ESCUTAR',
                ],
                default='PRESENÇA LOCAL / MONITORAR'
            )

            oportunidades_central = comparaveis_central[
                comparaveis_central['LEITURA_EXECUTIVA']
                == 'INVESTIGAR EXPANSÃO'
            ].sort_values(
                ['ELEITORES_2026', 'PENETRACAO_REFERENCIA_PCT'],
                ascending=[False, True]
            )
            consolidar_central = comparaveis_central[
                comparaveis_central['LEITURA_EXECUTIVA']
                == 'CONSOLIDAR PRESENÇA'
            ].sort_values(
                ['ELEITORES_2026', 'VOTOS_REFERENCIA_2022'],
                ascending=[False, False]
            )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Eleitorado 2026", inteiro_pt(total_eleitores_central))
    k2.metric("Locais em 2026", inteiro_pt(total_locais_2026_central))
    k3.metric(
        "Votos históricos registrados",
        inteiro_pt(total_votos_historicos_central),
        help="Soma dos registros disponíveis de 2020, 2022 e 2024 no recorte."
    )
    k4.metric(
        "Cobertura da referência 2022",
        percentual_pt(cobertura_central, 1) if not matriz_central.empty else "—",
        help="Percentual das seções de 2026 que encontrou referência territorial em 2022."
    )
    st.caption(
        f"Recorte executivo: {escopo_central}. "
        f"{inteiro_pt(total_secoes_2026_central)} seções atuais e "
        f"{inteiro_pt(total_locais_historicos_central)} locais históricos únicos identificados."
    )

    # Radar político das últimas 24h. Falhas do coletor não derrubam a Central.
    radar_central = filtrar_radar_periodo(carregar_radar_politico(), "Últimas 24 horas")
    if not radar_central.empty:
        nivel_central = radar_central.get('NIVEL_ATENCAO', pd.Series(index=radar_central.index, dtype=str)).astype(str).str.upper()
        samir_central = radar_bool(radar_central.get('SAMIR_DIRETO', pd.Series(index=radar_central.index, dtype=str)))
        pesquisa_central = radar_bool(radar_central.get('PESQUISA_ELEITORAL', pd.Series(index=radar_central.index, dtype=str)))
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Radar político • 24h", inteiro_pt(len(radar_central)))
        rc2.metric("Alertas relevantes", inteiro_pt(nivel_central.isin(['CRITICO', 'IMPORTANTE']).sum()))
        rc3.metric("Menções diretas a Samir", inteiro_pt(samir_central.sum()))
        rc4.metric("Pesquisas detectadas", inteiro_pt(pesquisa_central.sum()))
        top_radar_central = radar_central.assign(_ORDEM=nivel_central.map({'CRITICO': 1, 'IMPORTANTE': 2, 'ACOMPANHAR': 3, 'INFORMATIVO': 4}).fillna(5)).sort_values(['_ORDEM', 'COLETADO_EM'], ascending=[True, False]).head(1)
        if not top_radar_central.empty:
            alerta = top_radar_central.iloc[0]
            st.info(
                f"🛰️ **Radar:** {alerta.get('NIVEL_ATENCAO', 'INFORMATIVO')} — "
                f"{alerta.get('RESUMO') or alerta.get('TITULO', 'Nova ocorrência pública detectada.')}"
            )
    else:
        erro_radar_central = carregar_radar_politico().attrs.get('erro_carregamento')
        if erro_radar_central and not modo_reuniao:
            st.caption("🛰️ Radar político ainda sem base disponível. A Central territorial continua funcionando normalmente.")

    # Concentração histórica por local físico, sem misturar o mesmo local apenas por ano.
    concentracao_top5 = 0.0
    top_historico_central = pd.DataFrame()
    if not historico_central.empty and 'NM_LOCAL_VOTACAO' in historico_central:
        chaves_presenca = [
            coluna for coluna in [
                col_municipio_central, 'NR_ZONA', 'NM_LOCAL_VOTACAO'
            ] if coluna and coluna in historico_central.columns
        ]
        top_historico_central = historico_central.groupby(
            chaves_presenca,
            as_index=False,
            dropna=False
        ).agg(VOTOS_HISTORICOS=('QT_VOTOS_SAMIR', 'sum')).sort_values(
            'VOTOS_HISTORICOS', ascending=False
        )
        total_presenca = top_historico_central['VOTOS_HISTORICOS'].sum()
        if total_presenca > 0:
            concentracao_top5 = (
                top_historico_central.head(5)['VOTOS_HISTORICOS'].sum()
                / total_presenca * 100
            )

    revisar_eleitores = 0
    revisar_locais = 0
    if not eleitorado_central.empty and 'TERRITORIO_2026' in eleitorado_central:
        revisar_base = eleitorado_central[
            eleitorado_central['TERRITORIO_2026'] == 'REVISAR CLASSIFICAÇÃO'
        ]
        revisar_eleitores = pd.to_numeric(
            revisar_base['QT_ELEITOR_SECAO'], errors='coerce'
        ).fillna(0).sum()
        revisar_locais = revisar_base['ID_LOCAL_2026'].nunique()

    st.subheader("🧭 Leitura Executiva")
    if comparaveis_central.empty:
        st.info(
            "Ainda não há volume comparável suficiente entre o eleitorado de 2026 "
            "e a referência de 2022 neste recorte. A Central preserva os indicadores "
            "disponíveis sem fabricar prioridade automática."
        )
    else:
        leitura_partes = [
            f"O recorte reúne **{inteiro_pt(total_eleitores_central)} eleitores** "
            f"em **{inteiro_pt(total_locais_2026_central)} locais de votação**.",
            f"Entre **{inteiro_pt(len(comparaveis_central))} locais comparáveis**, "
            f"**{inteiro_pt(len(oportunidades_central))}** combinam alta escala com "
            "presença histórica abaixo da mediana e merecem investigação de campo.",
            f"Outros **{inteiro_pt(len(consolidar_central))}** combinam alta escala "
            "com presença histórica acima da mediana e merecem proteção e consolidação.",
        ]
        if concentracao_top5 > 0:
            leitura_partes.append(
                f"Os cinco locais de maior volume concentram "
                f"**{percentual_pt(concentracao_top5, 1)}** da presença histórica registrada."
            )
        st.info(" ".join(leitura_partes))

    st.subheader("⚡ O que merece atenção agora")
    alerta1, alerta2, alerta3 = st.columns(3)

    with alerta1:
        top_op = oportunidades_central.head(1)
        if not top_op.empty:
            linha = top_op.iloc[0]
            st.markdown(
                f"""
                <div class="cc-card">
                    <div class="cc-tag">INVESTIGAR EXPANSÃO</div>
                    <h4>{linha['NM_LOCAL_VOTACAO']}</h4>
                    <div class="cc-numero">{inteiro_pt(linha['ELEITORES_2026'])}</div>
                    <p>eleitores em {str(linha['NM_MUNICIPIO']).title()}. Presença histórica de referência: {percentual_pt(linha['PENETRACAO_REFERENCIA_PCT'], 2)}.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="cc-card">
                    <div class="cc-tag">EXPANSÃO</div>
                    <h4>Nenhum alerta automático</h4>
                    <p>O recorte atual não gerou local de alta escala abaixo da mediana de presença histórica.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with alerta2:
        top_cons = consolidar_central.head(1)
        if not top_cons.empty:
            linha = top_cons.iloc[0]
            st.markdown(
                f"""
                <div class="cc-card">
                    <div class="cc-tag">CONSOLIDAR PRESENÇA</div>
                    <h4>{linha['NM_LOCAL_VOTACAO']}</h4>
                    <div class="cc-numero">{inteiro_pt(linha['VOTOS_REFERENCIA_2022'])}</div>
                    <p>votos de referência em 2022, com {inteiro_pt(linha['ELEITORES_2026'])} eleitores atualmente.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="cc-card">
                    <div class="cc-tag">CONSOLIDAÇÃO</div>
                    <h4>Nenhum destaque automático</h4>
                    <p>Não há local de alta escala acima da mediana histórica no recorte comparável atual.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with alerta3:
        if revisar_locais > 0:
            st.markdown(
                f"""
                <div class="cc-card">
                    <div class="cc-tag">QUALIDADE TERRITORIAL</div>
                    <h4>{inteiro_pt(revisar_locais)} locais exigem revisão</h4>
                    <div class="cc-numero">{inteiro_pt(revisar_eleitores)}</div>
                    <p>eleitores estão em locais cuja classificação territorial ainda precisa de conferência.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="cc-card">
                    <div class="cc-tag">CONCENTRAÇÃO HISTÓRICA</div>
                    <h4>Top 5 locais</h4>
                    <div class="cc-numero">{percentual_pt(concentracao_top5, 1) if concentracao_top5 else '—'}</div>
                    <p>da presença histórica registrada no recorte está concentrada nos cinco primeiros locais.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.subheader("📍 Prioridades territoriais do recorte")

    aba_investigar, aba_consolidar, aba_historico = st.tabs([
        "🚀 Investigar expansão",
        "🛡️ Consolidar presença",
        "📚 Presença histórica",
    ])

    with aba_investigar:
        if oportunidades_central.empty:
            st.info("Nenhum local foi classificado automaticamente nesta faixa.")
        else:
            tabela_investigar = oportunidades_central.head(10)[[
                'NM_MUNICIPIO', 'NM_LOCAL_VOTACAO', 'ELEITORES_2026',
                'VOTOS_REFERENCIA_2022', 'PENETRACAO_REFERENCIA_PCT',
                'COBERTURA_SECOES_PCT'
            ]].copy().rename(columns={
                'NM_MUNICIPIO': 'Município',
                'NM_LOCAL_VOTACAO': 'Local de Votação',
                'ELEITORES_2026': 'Eleitorado 2026',
                'VOTOS_REFERENCIA_2022': 'Votos de Referência 2022',
                'PENETRACAO_REFERENCIA_PCT': 'Presença Histórica (%)',
                'COBERTURA_SECOES_PCT': 'Cobertura das Seções (%)',
            })
            tabela_investigar['Presença Histórica (%)'] = tabela_investigar[
                'Presença Histórica (%)'
            ].round(2)
            tabela_investigar['Cobertura das Seções (%)'] = tabela_investigar[
                'Cobertura das Seções (%)'
            ].round(1)
            st.dataframe(tabela_investigar, use_container_width=True, hide_index=True)
            exibir_acao_pratica(
                "Valide os primeiros locais com presença de campo: liderança, agenda, "
                "acesso, capacidade operacional e problemas locais antes de definir investimento."
            )

    with aba_consolidar:
        if consolidar_central.empty:
            st.info("Nenhum local foi classificado automaticamente nesta faixa.")
        else:
            tabela_consolidar = consolidar_central.head(10)[[
                'NM_MUNICIPIO', 'NM_LOCAL_VOTACAO', 'ELEITORES_2026',
                'VOTOS_REFERENCIA_2022', 'PENETRACAO_REFERENCIA_PCT',
                'COBERTURA_SECOES_PCT'
            ]].copy().rename(columns={
                'NM_MUNICIPIO': 'Município',
                'NM_LOCAL_VOTACAO': 'Local de Votação',
                'ELEITORES_2026': 'Eleitorado 2026',
                'VOTOS_REFERENCIA_2022': 'Votos de Referência 2022',
                'PENETRACAO_REFERENCIA_PCT': 'Presença Histórica (%)',
                'COBERTURA_SECOES_PCT': 'Cobertura das Seções (%)',
            })
            tabela_consolidar['Presença Histórica (%)'] = tabela_consolidar[
                'Presença Histórica (%)'
            ].round(2)
            tabela_consolidar['Cobertura das Seções (%)'] = tabela_consolidar[
                'Cobertura das Seções (%)'
            ].round(1)
            st.dataframe(tabela_consolidar, use_container_width=True, hide_index=True)
            exibir_acao_pratica(
                "Confirme se a presença política atual acompanha o histórico: liderança ativa, "
                "agenda recente, equipe responsável e capacidade de mobilização."
            )

    with aba_historico:
        if top_historico_central.empty:
            st.info("Não há série histórica suficiente para listar presença acumulada.")
        else:
            tabela_historico = top_historico_central.head(10).copy()
            nomes_historico = {}
            if col_municipio_central and col_municipio_central in tabela_historico.columns:
                nomes_historico[col_municipio_central] = 'Município'
            if 'NR_ZONA' in tabela_historico.columns:
                nomes_historico['NR_ZONA'] = 'Zona'
            if 'NM_LOCAL_VOTACAO' in tabela_historico.columns:
                nomes_historico['NM_LOCAL_VOTACAO'] = 'Local de Votação'
            nomes_historico['VOTOS_HISTORICOS'] = 'Votos Históricos Registrados'
            tabela_historico = tabela_historico.rename(columns=nomes_historico)
            st.dataframe(tabela_historico, use_container_width=True, hide_index=True)
            st.caption(
                "A soma histórica reúne eleições e cargos distintos. Ela mede presença "
                "registrada no território e não deve ser lida como projeção de 2026."
            )

    if not modo_reuniao:
        st.markdown("---")
        st.subheader("🔎 Por que o sistema mostrou isso?")
        with st.expander("Entenda as regras da Central de Comando"):
            if comparaveis_central.empty:
                st.write(
                    "Não houve locais comparáveis suficientes para calcular as medianas "
                    "do recorte. Nenhuma prioridade territorial automática foi criada."
                )
            else:
                st.markdown(
                    f"- **Alta escala:** eleitorado do local igual ou superior à mediana "
                    f"do recorte (**{inteiro_pt(mediana_eleitores_central)} eleitores**).\n"
                    f"- **Presença histórica abaixo da mediana:** referência de 2022 abaixo "
                    f"de **{percentual_pt(mediana_penetracao_central, 2)}**.\n"
                    "- **Investigar expansão:** combina alta escala e presença histórica abaixo da mediana.\n"
                    "- **Consolidar presença:** combina alta escala e presença histórica igual ou acima da mediana.\n"
                    f"- **Cobertura da referência de 2022:** {percentual_pt(cobertura_central, 1)} das seções do recorte encontraram correspondência histórica."
                )
            st.warning(
                "A Central organiza prioridades para decisão humana. A referência de 2022 "
                "não é previsão de votos para 2026 e não substitui escuta, liderança local, "
                "capacidade logística ou contexto político."
            )

        st.subheader("🧩 Próxima camada da Central")
        st.info(
            "A versão atual usa somente as bases já existentes neste painel. A próxima "
            "etapa é incorporar indicadores operacionais agregados do Rua | Gestão, "
            "Central de Materiais e Logística, para que a coordenação acompanhe presença, "
            "execução e pendências no mesmo lugar."
        )

# ==========================================
# INTELIGÊNCIA POLÍTICA — RADAR AUTOMÁTICO
# ==========================================
elif menu_selecionado == "🛰️ Inteligência Política":
    st.title("🛰️ Inteligência Política")
    st.markdown(
        """
        <div class="cc-hero">
            <div class="cc-kicker">Radar público • política do Acre • 2026</div>
            <h2>O que mudou no ambiente político</h2>
            <p>Notícias, pesquisas registradas, menções a Samir e sinais que merecem atenção da coordenação.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_atualizar, col_status = st.columns([1, 3])
    with col_atualizar:
        varredura_manual = st.button(
            "🔄 Varredura agora",
            use_container_width=True,
            help="Executa o mesmo coletor do agendamento automático e atualiza a base."
        )
    with col_status:
        st.caption(
            "O agendamento automático é a vigilância principal. Este botão funciona como contingência "
            "quando a coordenação quiser forçar uma busca imediata."
        )

    if varredura_manual:
        if 'gemini_api_key' not in st.secrets:
            st.error(
                "A chave `gemini_api_key` ainda não foi adicionada aos Secrets do Streamlit. "
                "A rota pode ler o radar, mas a varredura manual com IA ainda não está habilitada."
            )
        else:
            with st.spinner("Coletando fontes públicas e classificando novidades..."):
                try:
                    from radar_politico import executar_radar
                    resultado_varredura = executar_radar(
                        service_account=st.secrets["gcp_service_account"],
                        sheet_id=PLANILHA_RADAR_ID,
                        gemini_api_key=st.secrets["gemini_api_key"],
                    )
                    carregar_radar_politico.clear()
                    st.success(
                        f"Varredura concluída: {resultado_varredura.get('novos', 0)} novidade(s), "
                        f"{resultado_varredura.get('criticos', 0)} crítica(s) e "
                        f"{resultado_varredura.get('importantes', 0)} importante(s)."
                    )
                    st.rerun()
                except Exception as erro:
                    st.error(f"A varredura manual não pôde ser concluída: {erro}")

    radar_total = carregar_radar_politico()
    erro_radar = radar_total.attrs.get('erro_carregamento')
    if radar_total.empty:
        st.warning(
            "O Radar ainda não possui registros disponíveis. Assim que o coletor automático "
            "rodar pela primeira vez, as ocorrências aparecerão aqui."
        )
        if erro_radar:
            with st.expander("Detalhe técnico"):
                st.code(erro_radar)
        st.info(
            "A aba do Google Sheets é criada automaticamente pelo coletor. Não é necessário "
            "montar colunas manualmente."
        )
    else:
        radar = filtrar_radar_periodo(radar_total, periodo_radar)
        if 'NIVEL_ATENCAO' in radar.columns and nivel_radar:
            radar = radar[
                radar['NIVEL_ATENCAO'].astype(str).str.upper().isin(nivel_radar)
            ].copy()
        if apenas_samir_radar and 'SAMIR_DIRETO' in radar.columns:
            radar = radar[radar_bool(radar['SAMIR_DIRETO'])].copy()

        if radar.empty:
            st.info("Nenhuma ocorrência corresponde aos filtros selecionados.")
        else:
            nivel = radar.get('NIVEL_ATENCAO', pd.Series(index=radar.index, dtype=str)).astype(str).str.upper()
            samir_direto = radar_bool(radar.get('SAMIR_DIRETO', pd.Series(index=radar.index, dtype=str)))
            pesquisas = radar_bool(radar.get('PESQUISA_ELEITORAL', pd.Series(index=radar.index, dtype=str)))
            relevantes = nivel.isin(['CRITICO', 'IMPORTANTE'])

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Ocorrências no recorte", inteiro_pt(len(radar)))
            r2.metric("Alertas relevantes", inteiro_pt(relevantes.sum()))
            r3.metric("Menções diretas a Samir", inteiro_pt(samir_direto.sum()))
            r4.metric("Pesquisas detectadas", inteiro_pt(pesquisas.sum()))

            ordem_nivel = {'CRITICO': 1, 'IMPORTANTE': 2, 'ACOMPANHAR': 3, 'INFORMATIVO': 4}
            radar['_ORDEM_ATENCAO'] = nivel.map(ordem_nivel).fillna(5)
            radar = radar.sort_values(
                ['_ORDEM_ATENCAO', 'COLETADO_EM'], ascending=[True, False]
            )

            st.subheader("🚨 O que merece atenção agora")
            destaques = radar[radar['NIVEL_ATENCAO'].astype(str).str.upper().isin(
                ['CRITICO', 'IMPORTANTE', 'ACOMPANHAR']
            )].head(8)
            if destaques.empty:
                st.success("Nenhum alerta acima de nível informativo neste recorte.")
            else:
                for _, item in destaques.iterrows():
                    nivel_item = str(item.get('NIVEL_ATENCAO', 'INFORMATIVO')).upper()
                    icone = {'CRITICO': '🔴', 'IMPORTANTE': '🟠', 'ACOMPANHAR': '🟡'}.get(nivel_item, '⚪')
                    titulo = str(item.get('TITULO', '')).strip()
                    resumo = str(item.get('RESUMO', '')).strip()
                    por_que = str(item.get('POR_QUE_IMPORTA', '')).strip()
                    fonte = str(item.get('FONTE', '')).strip()
                    url = str(item.get('URL', '')).strip()
                    st.markdown(f"### {icone} {nivel_item} — {titulo}")
                    if resumo:
                        st.write(resumo)
                    if por_que:
                        st.caption(f"Por que importa: {por_que}")
                    st.caption(f"Fonte: {fonte or 'não informada'}")
                    if url.startswith('http'):
                        st.markdown(f"[Abrir fonte original]({url})")
                    st.markdown("---")

            aba_radar, aba_samir, aba_pesquisas, aba_temas, aba_fontes = st.tabs([
                "Radar completo", "Samir", "Pesquisas", "Temas", "Fontes e método"
            ])

            with aba_radar:
                colunas = [
                    c for c in [
                        'COLETADO_EM', 'NIVEL_ATENCAO', 'FONTE', 'TITULO', 'ATOR_PRINCIPAL',
                        'TEMA', 'TIPO_OCORRENCIA', 'TOM_COBERTURA', 'FATO_ALEGACAO', 'URL'
                    ] if c in radar.columns
                ]
                tabela = radar[colunas].copy()
                if 'COLETADO_EM' in tabela.columns:
                    tabela['COLETADO_EM'] = tabela['COLETADO_EM'].dt.tz_convert('America/Rio_Branco').dt.strftime('%d/%m/%Y %H:%M')
                    tabela = tabela.rename(columns={'COLETADO_EM': 'Detectado em'})
                tabela = tabela.rename(columns={
                    'NIVEL_ATENCAO': 'Atenção', 'FONTE': 'Fonte', 'TITULO': 'Título',
                    'ATOR_PRINCIPAL': 'Ator principal', 'TEMA': 'Tema',
                    'TIPO_OCORRENCIA': 'Tipo', 'TOM_COBERTURA': 'Tom da cobertura',
                    'FATO_ALEGACAO': 'Natureza', 'URL': 'Link'
                })
                st.dataframe(tabela, use_container_width=True, hide_index=True)

            with aba_samir:
                base_samir = radar[samir_direto].copy()
                if base_samir.empty:
                    st.info("Nenhuma menção direta a Samir no recorte atual.")
                else:
                    st.metric("Menções diretas", inteiro_pt(len(base_samir)))
                    if 'TOM_COBERTURA' in base_samir.columns:
                        tom = base_samir.groupby('TOM_COBERTURA', as_index=False).size().rename(columns={'size': 'OCORRENCIAS'})
                        grafico_tom = alt.Chart(tom).mark_bar().encode(
                            x=alt.X('OCORRENCIAS:Q', title='Ocorrências'),
                            y=alt.Y('TOM_COBERTURA:N', title=None, sort='-x'),
                            tooltip=['TOM_COBERTURA:N', 'OCORRENCIAS:Q']
                        ).properties(height=max(220, len(tom) * 45))
                        st.altair_chart(grafico_tom, use_container_width=True)
                    st.caption(
                        "Tom da cobertura não é rejeição eleitoral. Rejeição, aprovação e intenção "
                        "de voto só devem ser tratadas como tais quando uma pesquisa efetivamente as medir."
                    )

            with aba_pesquisas:
                base_pesquisas = radar[pesquisas].copy()
                if base_pesquisas.empty:
                    st.info("Nenhuma pesquisa eleitoral foi detectada no recorte atual.")
                else:
                    st.warning(
                        "Registro no PesqEle comprova a existência do registro, não valida resultado, "
                        "qualidade metodológica ou interpretação divulgada."
                    )
                    cols_p = [c for c in ['PUBLICADO_EM', 'FONTE', 'TITULO', 'RESUMO', 'URL'] if c in base_pesquisas.columns]
                    tp = base_pesquisas[cols_p].copy()
                    if 'PUBLICADO_EM' in tp.columns:
                        tp['PUBLICADO_EM'] = tp['PUBLICADO_EM'].astype(str)
                    st.dataframe(tp, use_container_width=True, hide_index=True)

            with aba_temas:
                if 'TEMA' not in radar.columns:
                    st.info("Ainda não há classificação temática disponível.")
                else:
                    temas = radar.assign(TEMA=radar['TEMA'].replace('', 'Não classificado')).groupby('TEMA', as_index=False).size().rename(columns={'size': 'OCORRENCIAS'}).sort_values('OCORRENCIAS', ascending=False).head(15)
                    grafico_temas = alt.Chart(temas).mark_bar().encode(
                        x=alt.X('OCORRENCIAS:Q', title='Ocorrências'),
                        y=alt.Y('TEMA:N', title=None, sort='-x', axis=alt.Axis(labelLimit=0)),
                        tooltip=['TEMA:N', 'OCORRENCIAS:Q']
                    ).properties(height=max(300, len(temas) * 32))
                    st.altair_chart(grafico_temas, use_container_width=True)
                    st.caption(
                        "Volume de notícias não mede opinião pública. Esta visão serve para perceber "
                        "quais assuntos estão ocupando mais espaço no ambiente informacional monitorado."
                    )

            with aba_fontes:
                st.markdown(
                    "**Malhas de captura da versão 1:** Google Notícias por RSS de busca, GDELT e "
                    "o arquivo oficial de Pesquisas Eleitorais 2026 do TSE/PesqEle."
                )
                st.markdown(
                    "**IA analista:** Gemini 3.6 Flash. A IA recebe somente título, fonte, URL e "
                    "trechos de conteúdo público coletado. Bases internas de apoiadores, logística, "
                    "materiais e estratégia não são enviadas ao modelo."
                )
                st.markdown(
                    "**Escala de atenção:** CRITICO → IMPORTANTE → ACOMPANHAR → INFORMATIVO. "
                    "A classificação é uma triagem para revisão humana, não uma decisão automática."
                )
                st.warning(
                    "O radar reduz o tempo entre publicação e leitura, mas nenhuma fonte externa garante "
                    "indexação instantânea. Por isso a arquitetura usa malhas redundantes e uma varredura "
                    "manual de contingência."
                )



# ==========================================
# FINANCEIRO — CAMPANHA E PRESTAÇÃO DE CONTAS
# ==========================================
elif menu_selecionado == "💰 Financeiro":
    st.title("💰 Financeiro da Campanha")

    col_fin_titulo, col_fin_refresh = st.columns([4, 1])
    with col_fin_refresh:
        if st.button("🔄 Atualizar TSE", use_container_width=True):
            carregar_financeiro_runtime.clear()
            coletar_financeiro_tse_ao_vivo.clear()
            st.rerun()

    runtime_financeiro = carregar_financeiro_runtime()
    campanha_atual = campanha_financeira(runtime_financeiro, ano_financeiro)
    status_campanha = str(campanha_atual.get("status", "indisponivel")).lower()
    resumo_financeiro = campanha_atual.get("resumo", {}) or {}

    cargo_financeiro = campanha_atual.get("cargo", "Campanha eleitoral")
    partido_financeiro = campanha_atual.get("partido", "PP")
    atualizado_tse = campanha_atual.get("atualizado_tse_em")
    gerado_em = runtime_financeiro.get("gerado_em")

    st.markdown(
        f"""
        <div class="cc-hero">
            <div class="cc-kicker">Prestação de contas • {ano_financeiro} • TSE</div>
            <h2>Quanto entrou, quanto foi comprometido e para onde o dinheiro está indo</h2>
            <p>{cargo_financeiro} • {partido_financeiro}. Leitura executiva dos dados públicos declarados à Justiça Eleitoral.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if status_campanha == "indisponivel":
        st.warning(
            "A estrutura do módulo financeiro já está ativa, mas o TSE ainda não "
            "entregou um snapshot utilizável nesta atualização automática."
        )
        erro_financeiro = campanha_atual.get("erro_atualizacao") or runtime_financeiro.get("erro_carregamento")
        if erro_financeiro:
            with st.expander("Detalhe da atualização"):
                st.code(str(erro_financeiro))
    elif status_campanha == "desatualizado":
        st.warning(
            "A última consulta ao TSE falhou temporariamente. O painel preservou o "
            "último snapshot válido e o identifica como desatualizado."
        )
    elif status_campanha == "historico_contingencia":
        st.info(
            "A consulta ao TSE para 2024 não respondeu nesta abertura. Como 2024 já possui "
            "prestação final, o painel está usando o snapshot histórico conferido para essa eleição."
        )

    total_recebido = valor_financeiro(resumo_financeiro.get("total_recebido"))
    despesas_contratadas = valor_financeiro(resumo_financeiro.get("despesas_contratadas"))
    despesas_pagas = valor_financeiro(resumo_financeiro.get("despesas_pagas"))
    saldo_aproximado = valor_financeiro(resumo_financeiro.get("saldo_caixa_aproximado"))
    limite_gastos = valor_financeiro(resumo_financeiro.get("limite_gastos"))
    pct_limite = valor_financeiro(resumo_financeiro.get("percentual_limite_contratado"))

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Receitas recebidas", moeda_pt(total_recebido))
    f2.metric("Despesas contratadas", moeda_pt(despesas_contratadas))
    f3.metric("Despesas pagas", moeda_pt(despesas_pagas))
    f4.metric(
        "Saldo aproximado",
        moeda_pt(saldo_aproximado),
        help=(
            "Receitas recebidas menos despesas pagas no snapshot. Não substitui "
            "o saldo bancário oficial nem considera obrigações ainda não liquidadas."
        ),
    )

    if limite_gastos > 0:
        st.markdown(
            f"**Limite de gastos:** {moeda_pt(limite_gastos)} • "
            f"**{pct_limite:.1f}%** já comprometido em despesas contratadas."
        )
        st.progress(min(max(pct_limite / 100, 0.0), 1.0))

    if total_recebido > 0 or despesas_contratadas > 0:
        percentual_comprometido_receita = (
            despesas_contratadas / total_recebido * 100 if total_recebido else 0
        )
        leitura = (
            f"A campanha declarou **{moeda_pt(total_recebido)} em receitas** e já "
            f"contratou **{moeda_pt(despesas_contratadas)} em despesas**. "
        )
        if total_recebido:
            leitura += (
                f"O valor contratado corresponde a **{percentual_comprometido_receita:.1f}%** "
                "do que entrou até o momento. "
            )
        if despesas_contratadas > despesas_pagas:
            leitura += (
                f"Há **{moeda_pt(despesas_contratadas - despesas_pagas)}** em despesas "
                "contratadas que ainda não aparecem como pagas no snapshot."
            )
        st.info(leitura)
    else:
        st.info(
            "Nenhuma movimentação financeira foi publicada neste snapshot. Isso pode "
            "significar ausência de movimento declarado até agora ou atraso temporário "
            "na disponibilização pública pelo TSE."
        )

    st.caption(
        f"Snapshot do painel: {data_financeiro_legivel(gerado_em)} • "
        f"Última atualização indicada pelo TSE: {data_financeiro_legivel(atualizado_tse)}."
    )

    (
        aba_fin_visao,
        aba_fin_origens,
        aba_fin_doadores,
        aba_fin_despesas,
        aba_fin_historico,
        aba_fin_fonte,
    ) = st.tabs([
        "Visão Geral",
        "Origem dos Recursos",
        "Doadores",
        "Despesas e Fornecedores",
        "2024 × 2026",
        "Fonte e Atualização",
    ])

    with aba_fin_visao:
        st.subheader("📌 Estrutura financeira da campanha")
        dados_visao = pd.DataFrame([
            {"Indicador": "Receitas recebidas", "Valor": total_recebido},
            {"Indicador": "Despesas contratadas", "Valor": despesas_contratadas},
            {"Indicador": "Despesas pagas", "Valor": despesas_pagas},
            {"Indicador": "Saldo aproximado", "Valor": saldo_aproximado},
        ])
        if dados_visao["Valor"].sum() > 0:
            grafico_visao_fin = alt.Chart(dados_visao).mark_bar().encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Indicador:N", title=None, sort="-x"),
                tooltip=[
                    alt.Tooltip("Indicador:N", title="Indicador"),
                    alt.Tooltip("Valor:Q", title="Valor (R$)", format=",.2f"),
                ],
            ).properties(height=250)
            st.altair_chart(grafico_visao_fin, use_container_width=True)

        cnpj_campanha = campanha_atual.get("cnpj")
        if cnpj_campanha:
            st.caption(f"CNPJ da campanha: {documento_publico_financeiro(cnpj_campanha)}")

        entregas = campanha_atual.get("historico_entregas", []) or []
        if entregas:
            st.subheader("Entregas da prestação de contas")
            tabela_entregas = pd.DataFrame(entregas)
            colunas_entrega = [
                c for c in ["dataEntrega", "tipo", "retificadora", "numeroControle"]
                if c in tabela_entregas.columns
            ]
            if colunas_entrega:
                st.dataframe(
                    tabela_entregas[colunas_entrega].head(20),
                    use_container_width=True,
                    hide_index=True,
                )

    with aba_fin_origens:
        st.subheader("💵 De onde vieram os recursos")
        origens = campanha_atual.get("origens_recursos", []) or []
        if origens:
            df_origens = pd.DataFrame(origens)
            total_origens = df_origens["valor"].sum()
            df_origens["participacao"] = np.where(
                total_origens > 0,
                df_origens["valor"] / total_origens * 100,
                0,
            )
            grafico_origens = alt.Chart(df_origens).mark_bar().encode(
                x=alt.X("valor:Q", title="Valor (R$)"),
                y=alt.Y("origem:N", title=None, sort="-x"),
                tooltip=[
                    alt.Tooltip("origem:N", title="Origem"),
                    alt.Tooltip("valor:Q", title="Valor (R$)", format=",.2f"),
                    alt.Tooltip("participacao:Q", title="Participação (%)", format=".1f"),
                ],
            ).properties(height=max(230, len(df_origens) * 48))
            st.altair_chart(grafico_origens, use_container_width=True)

            tabela_origens = df_origens.rename(columns={
                "origem": "Origem",
                "valor": "Valor",
                "participacao": "Participação (%)",
            })
            tabela_origens["Valor"] = tabela_origens["Valor"].apply(moeda_pt)
            tabela_origens["Participação (%)"] = tabela_origens["Participação (%)"].round(1)
            st.dataframe(tabela_origens, use_container_width=True, hide_index=True)
        else:
            st.info("O snapshot ainda não trouxe a decomposição por origem dos recursos.")

        natureza = campanha_atual.get("natureza_receitas", []) or []
        if natureza:
            st.subheader("Natureza dos recebimentos")
            st.caption(
                "Esta classificação é complementar e pode se sobrepor às origens acima; "
                "por isso os valores não devem ser somados entre as duas tabelas."
            )
            df_natureza = pd.DataFrame(natureza).rename(columns={
                "natureza": "Natureza",
                "valor": "Valor",
            })
            df_natureza["Valor"] = df_natureza["Valor"].apply(moeda_pt)
            st.dataframe(df_natureza, use_container_width=True, hide_index=True)

    with aba_fin_doadores:
        st.subheader("🤝 Quem financiou a campanha")
        doadores = campanha_atual.get("doadores", []) or []
        if doadores:
            df_doadores = pd.DataFrame(doadores)
            total_doadores = df_doadores["valor"].sum()
            df_doadores["Participação (%)"] = np.where(
                total_doadores > 0,
                df_doadores["valor"] / total_doadores * 100,
                0,
            )
            tabela_doadores = df_doadores[["nome", "documento", "valor", "Participação (%)"]].copy()
            tabela_doadores["documento"] = tabela_doadores["documento"].apply(documento_publico_financeiro)
            tabela_doadores["valor"] = tabela_doadores["valor"].apply(moeda_pt)
            tabela_doadores["Participação (%)"] = tabela_doadores["Participação (%)"].round(1)
            tabela_doadores.columns = ["Doador / Origem", "Documento", "Valor", "Participação (%)"]
            st.dataframe(tabela_doadores.head(100), use_container_width=True, hide_index=True)

            principal_doador = df_doadores.iloc[0]
            st.info(
                f"A maior origem individual listada no ranking é **{principal_doador['nome']}**, "
                f"com **{moeda_pt(principal_doador['valor'])}**."
            )
        else:
            st.info("Nenhum ranking de doadores foi publicado no snapshot desta campanha.")

    with aba_fin_despesas:
        st.subheader("🧾 Para onde o dinheiro está indo")
        categorias = campanha_atual.get("categorias_despesa", []) or []
        if categorias:
            df_categorias = pd.DataFrame(categorias)
            total_categorias = df_categorias["valor"].sum()
            df_categorias["participacao"] = np.where(
                total_categorias > 0,
                df_categorias["valor"] / total_categorias * 100,
                0,
            )
            grafico_cat = alt.Chart(df_categorias.head(15)).mark_bar().encode(
                x=alt.X("valor:Q", title="Valor (R$)"),
                y=alt.Y("categoria:N", title=None, sort="-x", axis=alt.Axis(labelLimit=0)),
                tooltip=[
                    alt.Tooltip("categoria:N", title="Categoria"),
                    alt.Tooltip("valor:Q", title="Valor (R$)", format=",.2f"),
                    alt.Tooltip("participacao:Q", title="Participação (%)", format=".1f"),
                ],
            ).properties(height=max(300, min(len(df_categorias), 15) * 38))
            st.altair_chart(grafico_cat, use_container_width=True)

            maior_categoria = df_categorias.iloc[0]
            st.info(
                f"A maior categoria de gasto listada é **{maior_categoria['categoria']}**, "
                f"com **{moeda_pt(maior_categoria['valor'])}** "
                f"({maior_categoria['participacao']:.1f}% do total categorizado)."
            )
        else:
            st.info("O TSE ainda não publicou concentração de despesas para este snapshot.")

        st.markdown("---")
        st.subheader("🏢 Principais fornecedores")
        fornecedores = campanha_atual.get("fornecedores", []) or []
        if fornecedores:
            df_fornec = pd.DataFrame(fornecedores)
            total_fornec = df_fornec["valor"].sum()
            df_fornec["Participação (%)"] = np.where(
                total_fornec > 0,
                df_fornec["valor"] / total_fornec * 100,
                0,
            )
            tabela_fornec = df_fornec[["nome", "documento", "valor", "Participação (%)"]].copy()
            tabela_fornec["documento"] = tabela_fornec["documento"].apply(documento_publico_financeiro)
            tabela_fornec["valor"] = tabela_fornec["valor"].apply(moeda_pt)
            tabela_fornec["Participação (%)"] = tabela_fornec["Participação (%)"].round(1)
            tabela_fornec.columns = ["Fornecedor", "Documento", "Valor", "Participação (%)"]
            st.dataframe(tabela_fornec.head(100), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum ranking de fornecedores foi publicado no snapshot desta campanha.")

    with aba_fin_historico:
        st.subheader("📈 2024 × 2026")
        campanhas_runtime = runtime_financeiro.get("campanhas", {}) or {}
        comparacao = []
        for ano_hist in [2024, 2026]:
            camp_hist = campanhas_runtime.get(str(ano_hist), {}) or {}
            res_hist = camp_hist.get("resumo", {}) or {}
            comparacao.append({
                "Ano": str(ano_hist),
                "Receitas": valor_financeiro(res_hist.get("total_recebido")),
                "Despesas contratadas": valor_financeiro(res_hist.get("despesas_contratadas")),
                "Despesas pagas": valor_financeiro(res_hist.get("despesas_pagas")),
            })
        df_comparacao = pd.DataFrame(comparacao)
        if df_comparacao[["Receitas", "Despesas contratadas", "Despesas pagas"]].to_numpy().sum() > 0:
            df_long = df_comparacao.melt(
                id_vars="Ano",
                var_name="Indicador",
                value_name="Valor",
            )
            grafico_comparacao = alt.Chart(df_long).mark_bar().encode(
                x=alt.X("Ano:N", title="Eleição"),
                y=alt.Y("Valor:Q", title="Valor (R$)"),
                xOffset="Indicador:N",
                color=alt.Color("Indicador:N", title=None),
                tooltip=[
                    alt.Tooltip("Ano:N", title="Ano"),
                    alt.Tooltip("Indicador:N", title="Indicador"),
                    alt.Tooltip("Valor:Q", title="Valor (R$)", format=",.2f"),
                ],
            ).properties(height=360)
            st.altair_chart(grafico_comparacao, use_container_width=True)

            tabela_comp = df_comparacao.copy()
            for coluna in ["Receitas", "Despesas contratadas", "Despesas pagas"]:
                tabela_comp[coluna] = tabela_comp[coluna].apply(moeda_pt)
            st.dataframe(tabela_comp, use_container_width=True, hide_index=True)
        else:
            st.info("Ainda não há dados financeiros suficientes para comparar as duas eleições.")

        votos_2024 = 0
        if "ANO_ELEICAO" in dados.columns and "QT_VOTOS_SAMIR" in dados.columns:
            votos_2024 = pd.to_numeric(
                dados.loc[dados["ANO_ELEICAO"] == 2024, "QT_VOTOS_SAMIR"],
                errors="coerce",
            ).fillna(0).sum()
        camp_2024 = campanhas_runtime.get("2024", {}) or {}
        despesa_2024 = valor_financeiro((camp_2024.get("resumo") or {}).get("despesas_pagas"))
        if votos_2024 > 0 and despesa_2024 > 0:
            custo_voto_2024 = despesa_2024 / votos_2024
            cv1, cv2, cv3 = st.columns(3)
            cv1.metric("Votos em 2024", inteiro_pt(votos_2024))
            cv2.metric("Despesa paga em 2024", moeda_pt(despesa_2024))
            cv3.metric("Custo financeiro por voto", moeda_pt(custo_voto_2024))
            st.caption(
                "Custo por voto = despesas pagas declaradas ÷ votos obtidos. É uma medida "
                "retrospectiva de 2024 e não deve ser projetada automaticamente para 2026."
            )

        st.warning(
            "2026 é uma campanha em andamento e para cargo diferente. A comparação mostra "
            "ritmo e escala financeira, não equivalência eleitoral direta."
        )

    with aba_fin_fonte:
        st.subheader("🔎 Fonte, atualização e limites")
        st.markdown(
            "**Fonte primária:** DivulgaCandContas/TSE, com dados públicos informados pelos "
            "prestadores de contas à Justiça Eleitoral."
        )
        st.markdown(
            "**Arquitetura:** um coletor separado consulta a fonte pública e grava apenas um "
            "snapshot compacto no repositório. O Streamlit lê esse arquivo local, reduzindo "
            "lentidão e dependência do TSE a cada acesso."
        )
        st.markdown(
            f"**Atualização do snapshot:** {data_financeiro_legivel(gerado_em)}."
        )
        if status_campanha == "historico_contingencia":
            st.caption(
                "Para 2024, esta abertura utilizou a contingência histórica porque a API pública "
                "não respondeu. A próxima atualização tenta novamente a fonte do TSE."
            )
        st.markdown(
            f"**Extratos bancários disponíveis:** {'sim' if campanha_atual.get('tem_extratos') else 'não no snapshot atual'}.  "
            f"**Notas fiscais disponíveis:** {'sim' if campanha_atual.get('tem_notas_fiscais') else 'não no snapshot atual'}."
        )
        st.warning(
            "Os dados exibidos são declarações públicas em atualização durante a campanha. "
            "Saldo aproximado, rankings e concentrações não substituem a contabilidade interna, "
            "extratos bancários nem a prestação de contas formal."
        )
        if runtime_financeiro.get("erros"):
            with st.expander("Ocorrências da última coleta"):
                st.json(runtime_financeiro.get("erros"))


# ==========================================
# ROTA 1: DESEMPENHO ELEITORAL POR TERRITÓRIO
# ==========================================
elif menu_selecionado == "📊 1. Desempenho Eleitoral por Território":
    st.title(f"📊 Território e Eleitorado - {label_periodo}")

    st.info("""
    **Como interpretar este módulo**

    Este painel reúne desempenho histórico e perfil agregado do eleitorado para
    responder duas perguntas complementares: **onde há presença eleitoral** e
    **como é composto o território**. Comparações entre anos devem considerar
    mudanças de cargo, eleitorado e contexto da eleição.
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
    exibir_acao_pratica(
        "Use o total como referência de escala e os locais mapeados como cobertura; "
        "a prioridade deve nascer do cruzamento entre volume, participação, perfil e logística."
    )

    texto_top = "Todos os Locais" if mostrar_todas else f"Top {limite_ranking}"
    (
        aba_desempenho_visao,
        aba_desempenho_evolucao,
        aba_desempenho_territorio,
        aba_desempenho_perfil,
        aba_desempenho_metas,
        aba_desempenho_metodologia,
    ) = st.tabs([
        "Visão Geral",
        "Evolução Histórica",
        "Leitura Territorial",
        "Perfil do Eleitorado",
        "Metas de Referência",
        "Metodologia",
    ])

    with aba_desempenho_visao:
        st.subheader(f"📍 Mapa de Distribuição Geográfica ({label_periodo} {texto_local})")
        group_cols = ['NM_LOCAL_VOTACAO', 'lat', 'lon']
        if col_municipio:
            group_cols.append(col_municipio)
    
        dados_mapa = dados_filtrados.groupby(group_cols, as_index=False)['QT_VOTOS_SAMIR'].sum()
        dados_mapa = dados_mapa.dropna(subset=['lat', 'lon'])
    
        if not dados_mapa.empty:
            st.map(dados_mapa, latitude='lat', longitude='lon')
            exibir_acao_pratica(
                "Use o mapa para organizar rotas de presença, agrupando locais "
                "próximos na mesma agenda e conferindo os endereços antes da visita."
            )
        else:
            st.info("Nenhum dado geográfico disponível para os filtros selecionados.")
    
        st.markdown("---")
    
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
        exibir_grafico_altair(
            grafico_barras,
            "Proteja os locais de maior votação histórica com presença recorrente "
            "e identifique, entre os locais grandes, onde a participação ainda é baixa."
        )
    
        if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
            top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Participação nos Válidos (%)']
        else:
            top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Participação nos Válidos (%)']
        st.dataframe(top_escolas, use_container_width=True)
    
    with aba_desempenho_evolucao:
        st.subheader("📈 Matriz de Evolução Histórica (Comparativo entre Eleições)")
        if len(anos_disponiveis) > 1:
            tabela_comparativa = dados.pivot_table(index='NM_LOCAL_VOTACAO', columns='ANO_ELEICAO', values='QT_VOTOS_SAMIR', aggfunc='sum').fillna(0)
            ano_recente = anos_disponiveis[0]
            if ano_recente in tabela_comparativa.columns:
                tabela_comparativa = tabela_comparativa.sort_values(by=ano_recente, ascending=False).head(limite_ranking)
            st.dataframe(tabela_comparativa, use_container_width=True)
            exibir_acao_pratica(
                "Separe os locais em crescimento, estabilidade e retração; investigue "
                "com lideranças locais o que mudou antes de definir prioridade."
            )
        else:
            st.info("ℹ️ A base de dados atual possui apenas um ano eleitoral registrado.")
    
    with aba_desempenho_territorio:
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
            exibir_grafico_altair(
                scatter,
                "Nos locais com grande volume de votos válidos e baixa presença "
                "histórica, faça primeiro escuta e reconhecimento de lideranças; "
                "nos redutos, concentre mobilização e retenção."
            )
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
            exibir_grafico_altair(
                scatter_matriz + regra_x + regra_y,
                "Transforme os quadrantes em quatro agendas: defender bases fortes, "
                "expandir em locais grandes de baixa penetração, manter presença nos "
                "locais menores fortes e monitorar os demais."
            )
    
    with aba_desempenho_evolucao:
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
            exibir_grafico_altair(
                area + curva + linha_80,
                "Calcule quantos locais concentram cerca de 80% do histórico e "
                "garanta cobertura mínima neles, sem abandonar a expansão territorial."
            )
    
    with aba_desempenho_perfil:
        st.subheader("👥 Perfil estimado do eleitorado")
        st.info("""
        Esta seção combina a composição agregada do eleitorado do TSE com a
        participação histórica do candidato em cada local. Os resultados são
        estimativas proporcionais: não identificam pessoas e não comprovam o
        perfil de quem votou no candidato.
        """)

        if dados_demo.empty:
            st.error(
                "⚠️ A base `base_demografica_ac.zip` não foi encontrada. "
                "As demais análises territoriais continuam funcionando."
            )
            exibir_detalhes_erro_base(dados_demo)
        else:
            df_demo_macro = aplicar_filtros_base_auxiliar(
                dados_demo,
                ano_selecionado,
                municipios_selecionados if col_municipio else None,
                zona_selecionada
            )

            df_demo_filtrado = df_demo_macro.copy()
            escolas_tse = ["Visão Macro (Todas as Selecionadas)"] + sorted(
                df_demo_filtrado['NM_LOCAL_VOTACAO'].dropna().unique().tolist()
            )
            escola_alvo_perfil = st.selectbox(
                "Aprofundar a análise em um local de votação:",
                escolas_tse,
                key="perfil_local_integrado"
            )

            if escola_alvo_perfil != "Visão Macro (Todas as Selecionadas)":
                df_demo_filtrado = df_demo_filtrado[
                    df_demo_filtrado['NM_LOCAL_VOTACAO'] == escola_alvo_perfil
                ]
                st.markdown(f"**Local analisado:** {escola_alvo_perfil}")
            else:
                st.markdown(f"**Recorte analisado:** {texto_local}")

            total_votos_estimados = df_demo_filtrado[
                'VOTOS_ESTIMADOS_SAMIR'
            ].sum()
            st.metric(
                "Votos históricos distribuídos proporcionalmente no perfil",
                f"{int(total_votos_estimados):,}".replace(',', '.')
            )
            exibir_acao_pratica(
                "Use o perfil dominante para adaptar linguagem, exemplos e canais "
                "de comunicação no território selecionado; valide a hipótese em "
                "reuniões e escutas antes de ampliar a ação."
            )

            (
                aba_perfil_geral_integrado,
                aba_perfil_escolaridade_integrado,
                aba_perfil_territorial_integrado,
                aba_perfil_metodologia_integrado,
            ) = st.tabs([
                "Perfil Geral",
                "Escolaridade",
                "Perfis Territoriais",
                "Metodologia",
            ])

            with aba_perfil_geral_integrado:
                col_graf1, col_graf2 = st.columns(2)
                with col_graf1:
                    st.subheader("Distribuição por gênero")
                    df_genero = df_demo_filtrado.groupby(
                        'DS_GENERO', as_index=False
                    )['VOTOS_ESTIMADOS_SAMIR'].sum()
                    df_genero['VOTOS_ESTIMADOS_SAMIR'] = df_genero[
                        'VOTOS_ESTIMADOS_SAMIR'
                    ].astype(int)
                    df_genero['Percentual'] = np.where(
                        total_votos_estimados > 0,
                        df_genero['VOTOS_ESTIMADOS_SAMIR'] /
                        total_votos_estimados * 100,
                        0
                    )
                    grafico_genero = alt.Chart(df_genero).mark_arc(
                        innerRadius=65
                    ).encode(
                        theta=alt.Theta(
                            field="VOTOS_ESTIMADOS_SAMIR",
                            type="quantitative"
                        ),
                        color=alt.Color(
                            field="DS_GENERO",
                            type="nominal",
                            title="Gênero",
                            scale=alt.Scale(
                                domain=['FEMININO', 'MASCULINO', 'NÃO INFORMADO'],
                                range=['#E83E8C', '#1A73E8', '#808080']
                            )
                        ),
                        tooltip=[
                            alt.Tooltip('DS_GENERO:N', title='Gênero'),
                            alt.Tooltip(
                                'VOTOS_ESTIMADOS_SAMIR:Q',
                                title='Estimativa proporcional',
                                format=','
                            ),
                            alt.Tooltip(
                                'Percentual:Q',
                                title='Participação (%)',
                                format='.1f'
                            )
                        ]
                    ).properties(height=350)
                    exibir_grafico_altair(
                        grafico_genero,
                        "Planeje abordagens inclusivas e compare a presença dos "
                        "grupos com a composição real do território, sem presumir "
                        "preferência eleitoral individual."
                    )

                with col_graf2:
                    st.subheader("Faixa etária do eleitorado")
                    df_idade = df_demo_filtrado.groupby(
                        'DS_FAIXA_ETARIA', as_index=False
                    )['VOTOS_ESTIMADOS_SAMIR'].sum()
                    df_idade['VOTOS_ESTIMADOS_SAMIR'] = df_idade[
                        'VOTOS_ESTIMADOS_SAMIR'
                    ].astype(int)
                    altura_idade = max(350, len(df_idade) * 28)
                    grafico_idade = alt.Chart(df_idade).mark_bar(
                        color="#0A1C2E"
                    ).encode(
                        x=alt.X(
                            'VOTOS_ESTIMADOS_SAMIR:Q',
                            title='Estimativa proporcional',
                            axis=alt.Axis(format='d')
                        ),
                        y=alt.Y(
                            'DS_FAIXA_ETARIA:N',
                            title=None,
                            sort='-x',
                            axis=alt.Axis(labelLimit=0)
                        ),
                        tooltip=[
                            alt.Tooltip('DS_FAIXA_ETARIA:N', title='Faixa etária'),
                            alt.Tooltip(
                                'VOTOS_ESTIMADOS_SAMIR:Q',
                                title='Estimativa proporcional',
                                format=','
                            )
                        ]
                    ).properties(height=altura_idade)
                    exibir_grafico_altair(
                        grafico_idade,
                        "Priorize formatos compatíveis com as faixas mais presentes: "
                        "escuta presencial e serviços para públicos maduros; esporte, "
                        "trabalho e conteúdo digital quando houver maior presença jovem."
                    )

            with aba_perfil_escolaridade_integrado:
                st.subheader("Grau de instrução")
                df_escola = df_demo_filtrado.groupby(
                    'DS_GRAU_ESCOLARIDADE', as_index=False
                )['VOTOS_ESTIMADOS_SAMIR'].sum()
                df_escola['VOTOS_ESTIMADOS_SAMIR'] = df_escola[
                    'VOTOS_ESTIMADOS_SAMIR'
                ].astype(int)
                altura_escola = max(350, len(df_escola) * 28)
                grafico_escola = alt.Chart(df_escola).mark_bar(
                    color="#1A73E8"
                ).encode(
                    x=alt.X(
                        'VOTOS_ESTIMADOS_SAMIR:Q',
                        title='Estimativa proporcional',
                        axis=alt.Axis(format='d')
                    ),
                    y=alt.Y(
                        'DS_GRAU_ESCOLARIDADE:N',
                        title=None,
                        sort='-x',
                        axis=alt.Axis(labelLimit=0)
                    ),
                    tooltip=[
                        alt.Tooltip(
                            'DS_GRAU_ESCOLARIDADE:N',
                            title='Escolaridade'
                        ),
                        alt.Tooltip(
                            'VOTOS_ESTIMADOS_SAMIR:Q',
                            title='Estimativa proporcional',
                            format=','
                        )
                    ]
                ).properties(height=altura_escola)
                exibir_grafico_altair(
                    grafico_escola,
                    "Ajuste a complexidade dos materiais: mensagens diretas, exemplos "
                    "concretos e recursos visuais devem acompanhar documentos mais "
                    "detalhados, sem estigmatizar nenhum grupo."
                )

            with aba_perfil_territorial_integrado:
                st.subheader("📍 Hipóteses por perfil demográfico")
                st.info("""
                A comparação usa os dois perfis de maior estimativa proporcional.
                Ela descreve onde esses grupos estão mais presentes, mas não mede
                intenção de voto nem garante conversão.
                """)

                avatar_df = df_demo_macro.groupby(
                    ['DS_GENERO', 'DS_FAIXA_ETARIA']
                )['VOTOS_ESTIMADOS_SAMIR'].sum().reset_index()
                if not avatar_df.empty:
                    avatar_df = avatar_df.sort_values(
                        by='VOTOS_ESTIMADOS_SAMIR', ascending=False
                    )

                    def renderizar_perfil_territorial(
                        posicao_label, top_avatar_row, cor_barra
                    ):
                        avatar_genero = top_avatar_row['DS_GENERO']
                        avatar_idade = top_avatar_row['DS_FAIXA_ETARIA']
                        st.success(
                            f"**{posicao_label} perfil estimado de maior volume:** "
                            f"**{avatar_genero}**, faixa **{avatar_idade}**."
                        )
                        df_alvo_perfil = df_demo_macro[
                            (df_demo_macro['DS_GENERO'] == avatar_genero) &
                            (df_demo_macro['DS_FAIXA_ETARIA'] == avatar_idade)
                        ].copy()
                        df_alvo_perfil['DIFERENCA_PERFIL_ESTIMATIVA'] = (
                            df_alvo_perfil['QT_ELEITORES_PERFIL'] -
                            df_alvo_perfil['VOTOS_ESTIMADOS_SAMIR']
                        ).clip(lower=0)
                        radar_df = df_alvo_perfil.groupby(
                            'NM_LOCAL_VOTACAO', as_index=False
                        ).agg(
                            QT_ELEITORES_PERFIL=('QT_ELEITORES_PERFIL', 'sum'),
                            VOTOS_ESTIMADOS_SAMIR=(
                                'VOTOS_ESTIMADOS_SAMIR', 'sum'
                            ),
                            DIFERENCA_PERFIL_ESTIMATIVA=(
                                'DIFERENCA_PERFIL_ESTIMATIVA', 'sum'
                            )
                        ).sort_values(
                            by='DIFERENCA_PERFIL_ESTIMATIVA', ascending=False
                        ).head(limite_ranking)

                        grafico_radar = alt.Chart(radar_df).mark_bar(
                            color=cor_barra
                        ).encode(
                            x=alt.X(
                                'DIFERENCA_PERFIL_ESTIMATIVA:Q',
                                title='Diferença entre perfil e estimativa',
                                axis=alt.Axis(format='d')
                            ),
                            y=alt.Y(
                                'NM_LOCAL_VOTACAO:N',
                                sort='-x',
                                title=None,
                                axis=alt.Axis(
                                    labelLimit=0,
                                    labelOverlap=False
                                )
                            ),
                            tooltip=[
                                alt.Tooltip(
                                    'NM_LOCAL_VOTACAO:N',
                                    title='Local de Votação'
                                ),
                                alt.Tooltip(
                                    'DIFERENCA_PERFIL_ESTIMATIVA:Q',
                                    title='Diferença estimada',
                                    format=','
                                ),
                                alt.Tooltip(
                                    'QT_ELEITORES_PERFIL:Q',
                                    title='Total do perfil no local',
                                    format=','
                                )
                            ]
                        ).properties(height=max(400, len(radar_df) * 35))
                        exibir_grafico_altair(
                            grafico_radar,
                            "Selecione os primeiros locais para uma rodada de escuta "
                            "com esse público e registre problemas, lideranças e temas; "
                            "só depois transforme a hipótese em agenda de campanha."
                        )

                        tabela_radar = radar_df.copy()
                        tabela_radar.columns = [
                            'Local de Votação',
                            f'Eleitorado do perfil {avatar_genero.title()} — {avatar_idade}',
                            'Estimativa proporcional',
                            'Diferença entre perfil e estimativa'
                        ]
                        st.dataframe(tabela_radar, use_container_width=True)

                    if len(avatar_df) >= 1:
                        renderizar_perfil_territorial(
                            "1º", avatar_df.iloc[0], "#FF8C00"
                        )
                    if len(avatar_df) >= 2:
                        st.markdown("---")
                        renderizar_perfil_territorial(
                            "2º", avatar_df.iloc[1], "#1A73E8"
                        )
                else:
                    st.warning(
                        "Não há dados demográficos suficientes para a seleção atual."
                    )

            with aba_perfil_metodologia_integrado:
                exibir_metodologia_modulo(
                    ["base_demografica_ac.zip", "dados.csv"],
                    (
                        "A composição agregada do eleitorado é cruzada com a "
                        "participação histórica do candidato em cada local. As "
                        "estimativas são proporcionais e corrigidas para manter o "
                        "total observado."
                    ),
                    (
                        "O resultado descreve grupos agregados. Não identifica "
                        "pessoas, não comprova quem votou e não mede intenção de voto."
                    ),
                )

    with aba_desempenho_metas:
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
                exibir_acao_pratica(
                    "Use a meta somente como referência para dimensionar equipes e "
                    "acompanhar execução; ajuste-a com capacidade local, alianças e "
                    "evidências de campo."
                )
        else:
            st.warning("A coluna de Votos Válidos não está disponível para calcular a proporção da meta.")

    with aba_desempenho_metodologia:
        exibir_metodologia_modulo(
            ["dados.csv"],
            (
                "Os votos do candidato são somados entre as seções e consolidados "
                "por ano, município, zona e local de votação. Os votos válidos são "
                "contados uma única vez por local no período analisado."
            ),
            (
                "2020 e 2024 foram eleições municipais, enquanto 2022 foi uma "
                "eleição geral. As comparações são referências históricas e não "
                "constituem previsão de votos."
            ),
        )

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
        exibir_detalhes_erro_base(dados_adormecidos)
    else:
        df_ador_filtrado = aplicar_filtros_base_auxiliar(
            dados_adormecidos,
            ano_selecionado,
            municipios_selecionados if col_municipio else None,
            zona_selecionada
        )

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
        exibir_acao_pratica(
            "Trate esses números como sinal de dificuldade de participação, não "
            "como votos disponíveis. Priorize escuta sobre acesso, informação, "
            "transporte e confiança política."
        )

        aba_participacao_visao, aba_participacao_ranking, aba_participacao_metodologia = st.tabs([
            "Visão Geral",
            "Ranking de Locais",
            "Metodologia",
        ])

        with aba_participacao_visao:
            st.subheader("📍 Dispersão Geográfica das Abstenções")
            mapa_ador = ador_escola.dropna(subset=['lat', 'lon'])
            if not mapa_ador.empty:
                st.map(mapa_ador, latitude='lat', longitude='lon')
                exibir_acao_pratica(
                    "Agrupe os pontos com maior não comparecimento em rotas de "
                    "diagnóstico e confirme em campo quais barreiras são realmente locais."
                )
            else:
                st.info("Dados de localização não disponíveis para este filtro.")

        with aba_participacao_ranking:
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
            exibir_grafico_altair(
                grafico_ador,
                "Comece pelos locais com grande volume e alta taxa relativa, cruzando "
                "o ranking com eleitorado, distância e capacidade de mobilização."
            )
    
            st.markdown("#### 📋 Detalhamento da Participação")
            tabela_ador = ador_top[['NM_LOCAL_VOTACAO', 'VOTOS_ADORMECIDOS', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_VOTOS_NULOS', 'QT_APTOS']]
            tabela_ador.columns = ['Local de Votação', 'Abstenções + brancos + nulos', 'Abstenções', 'Brancos', 'Nulos', 'Eleitores Aptos']
            st.dataframe(tabela_ador, use_container_width=True)

        with aba_participacao_metodologia:
            exibir_metodologia_modulo(
                ["base_adormecidos_ac.csv", "dados.csv"],
                (
                    "Abstenções, votos brancos e votos nulos são agregados por local "
                    "de votação e comparados ao total de eleitores aptos."
                ),
                (
                    "Esses registros não revelam motivação individual e não devem "
                    "ser tratados como votos disponíveis para uma candidatura."
                ),
            )


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
        exibir_detalhes_erro_base(dados_concorrencia)
    else:
        df_conc_filtrado = aplicar_filtros_base_auxiliar(
            dados_concorrencia,
            ano_selecionado,
            municipios_selecionados if col_municipio else None,
            zona_selecionada
        )

        if df_conc_filtrado.empty:
            st.info(
                "Nenhum dado de concorrência foi encontrado para os filtros "
                "selecionados."
            )
            st.stop()

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
            exibir_acao_pratica(
                "Mapeie quem organiza a votação das candidaturas mais presentes no "
                "local e avalie temas, alianças e barreiras; não presuma transferência de votos."
            )

            aba_concorrencia_distribuicao, aba_concorrencia_tabela, aba_concorrencia_metodologia = st.tabs([
                "Distribuição",
                "Concorrentes no Local",
                "Metodologia",
            ])

            with aba_concorrencia_distribuicao:
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
                exibir_grafico_altair(
                    grafico_adv,
                    "Em locais concentrados, prepare diferenciação clara; em locais "
                    "fragmentados, busque presença comunitária e alianças diversas."
                )

            with aba_concorrencia_tabela:
                st.subheader("Concorrentes no Local")
                tabela_adv = adversarios[['NM_VOTAVEL', 'QT_VOTOS', 'Share (%)']]
                tabela_adv.columns = ['Candidatura', 'Votos no Local', 'Participação (%)']
                tabela_adv['Participação (%)'] = tabela_adv['Participação (%)'].round(2).astype(str) + '%'
                st.dataframe(tabela_adv.head(50), use_container_width=True)

            with aba_concorrencia_metodologia:
                exibir_metodologia_modulo(
                    ["base_concorrencia_ac.zip", "dados.csv"],
                    (
                        "Os votos são agrupados por candidatura no local e cargo "
                        "selecionados. A participação corresponde à proporção de cada "
                        "candidatura no total analisado daquele recorte."
                    ),
                    (
                        "A distribuição é descritiva. Ela não demonstra transferência "
                        "de votos nem comportamento futuro do eleitorado."
                    ),
                )
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

    if dados_concorrencia.empty:
        st.error(
            "⚠️ A base 'base_concorrencia_ac.zip' não pôde ser carregada."
        )
        exibir_detalhes_erro_base(dados_concorrencia)
    elif ano_selecionado == 'Todos os Anos (Série Histórica)':
        st.warning("⚠️ Selecione um **Ano Específico** (por exemplo, 2022 ou 2024). A mistura de eleições e cargos diferentes distorce a correlação.")
    else:
        df_conc_filtrado = aplicar_filtros_base_auxiliar(
            dados_concorrencia,
            ano_selecionado,
            municipios_selecionados if col_municipio else None,
            zona_selecionada
        )

        if df_conc_filtrado.empty:
            st.info(
                "Nenhum dado de concorrência foi encontrado para os filtros "
                "selecionados."
            )
            st.stop()

        cargos_disponiveis = df_conc_filtrado['DS_CARGO'].dropna().unique().tolist()
        cargo_alvo = st.selectbox("🎯 Selecione o Cargo para cruzar com os votos do Samir:", cargos_disponiveis)

        chaves_correlacao = ['NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO']
        votos_samir_secao = dados[
            dados['ANO_ELEICAO'] == int(ano_selecionado)
        ].groupby(
            chaves_correlacao,
            as_index=False,
            dropna=False
        )['QT_VOTOS_SAMIR'].sum()
        df_alvo = df_conc_filtrado[df_conc_filtrado['DS_CARGO'] == cargo_alvo]

        if df_alvo.empty:
            st.info("Nenhum dado encontrado para o cargo selecionado.")
        else:
            pivot_alvo = df_alvo.pivot_table(
                index=chaves_correlacao,
                columns='NM_VOTAVEL',
                values='QT_VOTOS',
                aggfunc='sum'
            ).fillna(0).reset_index()
            base_correlacao = pd.merge(
                votos_samir_secao,
                pivot_alvo,
                on=chaves_correlacao,
                how='inner',
                validate='one_to_one'
            )

            if len(base_correlacao) > 5: 
                matriz_corr = base_correlacao.drop(
                    columns=chaves_correlacao
                ).corr()
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

                    aba_correlacao_grafico, aba_correlacao_tabela, aba_correlacao_metodologia = st.tabs([
                        "Correlações",
                        "Tabela de Resultados",
                        "Metodologia",
                    ])

                    with aba_correlacao_grafico:
                        altura_corr = max(500, len(corr_samir) * 35)
    
                        grafico_corr = alt.Chart(corr_samir).mark_bar(color="#25D366").encode(
                            x=alt.X('Correlação de Pearson (r):Q', title='Correlação (r)', scale=alt.Scale(domain=[0, 1])),
                            y=alt.Y('Candidatura:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                            tooltip=[
                                alt.Tooltip('Candidatura:N', title='Candidatura'),
                                alt.Tooltip('Correlação de Pearson (r):Q', title='Correlação de Pearson', format='.2f')
                            ]
                        ).properties(height=altura_corr)
                        exibir_grafico_altair(
                            grafico_corr,
                            "Use correlações apenas para formular hipóteses de "
                            "sobreposição territorial e orientar reuniões exploratórias; "
                            "valide qualquer parceria com evidências políticas e de campo."
                        )

                    with aba_correlacao_tabela:
                        corr_samir['Correlação de Pearson (r)'] = corr_samir['Correlação de Pearson (r)'].round(3)
                        st.dataframe(corr_samir, use_container_width=True)

                    with aba_correlacao_metodologia:
                        exibir_metodologia_modulo(
                            ["base_concorrencia_ac.zip", "dados.csv"],
                            (
                                "O coeficiente de Pearson compara, seção a seção, a "
                                "variação dos votos do candidato com as demais "
                                "candidaturas do mesmo ano e cargo."
                            ),
                            (
                                "Correlação mede associação linear; não prova voto "
                                "casado, aliança, causalidade ou transferência de votos."
                            ),
                        )
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
    exibir_acao_pratica(
        "Defina a prioridade rural combinando quatro fatores: eleitorado, votação "
        "histórica, participação nos válidos e viabilidade logística. Evite decidir "
        "somente pelo maior número absoluto."
    )

    if incluir_revisao:
        st.warning(
            "Mapa, resumo municipal e ranking incluem pendências. Os indicadores "
            "do cabeçalho continuam usando somente rurais confirmados."
        )

    (
        aba_rural_visao,
        aba_rural_locais,
        aba_rural_evolucao,
        aba_rural_qualidade,
        aba_rural_metodologia,
    ) = st.tabs([
        "Visão Geral",
        "Locais Rurais",
        "Evolução Histórica",
        "Qualidade dos Dados",
        "Metodologia",
    ])

    with aba_rural_visao:
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
            exibir_acao_pratica(
                "Monte circuitos de visita por proximidade, confirme acesso e tempo "
                "de deslocamento com lideranças locais e registre responsável por cada rota."
            )
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
        exibir_acao_pratica(
            "Compare tamanho rural e presença histórica por município para distribuir "
            "dias de agenda, equipe, transporte e busca de lideranças."
        )

    with aba_rural_locais:
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
                y=alt.Y(
                    'LOCAL_EXIBICAO:N',
                    title=None,
                    sort='-x',
                    axis=alt.Axis(
                        labelLimit=0,
                        labelOverlap=False,
                        labelFontSize=11,
                        labelPadding=8
                    )
                ),
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
            exibir_grafico_altair(
                grafico_rural,
                "Use o critério selecionado para formar uma lista operacional: "
                "responsável local, data de visita, tema de escuta, custo de acesso "
                "e retorno esperado para cada escola."
            )
    
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

    with aba_rural_evolucao:
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
            exibir_grafico_altair(
                grafico_evolucao_rural,
                "Investigue aumentos e quedas por contexto eleitoral, cargo, mudança "
                "de local e presença de lideranças; use a tendência como pergunta, "
                "não como previsão automática."
            )
        st.caption(
            "A comparação é descritiva. Mudanças de cargo, seções, eleitorado e contexto "
            "eleitoral podem afetar os resultados entre anos."
        )
        evolucao_rural['PARTICIPACAO_VALIDOS_PCT'] = evolucao_rural[
            'PARTICIPACAO_VALIDOS_PCT'
        ].round(2)
        st.dataframe(evolucao_rural, use_container_width=True)

    with aba_rural_qualidade:
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
        exibir_acao_pratica(
            "Resolva primeiro os registros de maior eleitorado que estejam pendentes "
            "ou sem coordenada; documente a fonte de cada correção para manter a defesa metodológica."
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

    with aba_rural_metodologia:
        exibir_metodologia_modulo(
            [
                "tse_locais_acre_2020.csv.xlsx",
                "tse_locais_acre_2022.csv.xlsx",
                "tse_locais_acre_2024.csv.xlsx",
                "dados.csv",
                "base_concorrencia_ac.zip",
            ],
            (
                "As seções são vinculadas por ano, município, zona e número da "
                "seção. O local é confirmado como rural quando a identificação "
                "territorial do TSE é explícita; indícios permanecem em revisão."
            ),
            (
                "A cobertura de votos do candidato varia conforme o ano e o cargo. "
                "Ausência de registro não comprova votação igual a zero, e a série "
                "histórica não deve ser interpretada como previsão."
            ),
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
    exibir_acao_pratica(
        "Use estes totais para dimensionar cobertura e equipe no recorte escolhido; "
        "não converta eleitorado cadastrado diretamente em meta de votos."
    )

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
            exibir_acao_pratica(
                "Agrupe locais próximos em rotas e priorize os maiores pontos que "
                "também tenham liderança identificada e acesso operacional viável."
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
            exibir_grafico_altair(
                grafico_municipios_2026,
                "Distribua presença estadual proporcionalmente ao eleitorado e ao "
                "tipo de território, reservando estratégia própria para áreas rurais."
            )

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
            exibir_acao_pratica(
                "Converta o resumo municipal em calendário: município, dias de agenda, "
                "responsável territorial, meta de reuniões e custo logístico."
            )

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
        exibir_acao_pratica(
            "Dimensione uma frente rural específica com rotas, transporte, tempo de "
            "deslocamento, lideranças e temas locais, sem confundir eleitorado com apoio."
        )

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
            exibir_grafico_altair(
                grafico_rural_2026,
                "Ordene os municípios por eleitorado rural, mas valide a prioridade "
                "com distância, custo, presença de equipe e capacidade de mobilização."
            )

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
            exibir_acao_pratica(
                "Use os agrupamentos do mapa para criar circuitos rurais completos, "
                "evitando viagens isoladas para apenas um local."
            )
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
            exibir_acao_pratica(
                "Revise primeiro os locais com mais eleitores; confirme bairro, acesso "
                "e condição rural com fonte documentada antes de incluí-los nas metas."
            )
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
            exibir_acao_pratica(
                "Se a cobertura histórica estiver baixa, trate a matriz como parcial; "
                "use-a para selecionar territórios de investigação, não para projetar resultado."
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
                exibir_grafico_altair(
                    grafico_oportunidades,
                    "Priorize para escuta os locais de alta escala e baixa penetração; "
                    "nos de alta presença histórica, organize retenção, lideranças e mobilização."
                )
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
            exibir_acao_pratica(
                "Planeje comunicação pública acessível e eventos com condições de "
                "participação, considerando o perfil agregado sem identificar indivíduos."
            )

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
            exibir_grafico_altair(
                grafico_genero_2026,
                "Equilibre porta-vozes, temas e formatos para representar a composição "
                "do eleitorado, sem pressupor preferência por gênero."
            )

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
            exibir_grafico_altair(
                grafico_faixa_2026,
                "Ajuste canais, horários e temas às faixas mais numerosas e mantenha "
                "ações específicas para juventude, trabalhadores e pessoas idosas."
            )

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
            exibir_grafico_altair(
                grafico_escolaridade_2026,
                "Produza materiais em camadas: resumo simples, propostas objetivas e "
                "documento detalhado para quem deseja aprofundamento."
            )

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
        exibir_acao_pratica(
            "Antes de defender uma conclusão, confira cobertura, data da extração e "
            "diferenças registradas; decisões críticas devem usar somente recortes auditáveis."
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
