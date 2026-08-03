import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import zipfile
import os
import re
import unicodedata
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="Painel Executivo | Inteligência Territorial", page_icon="🎯", layout="wide")

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
        st.markdown("<h3 style='text-align: center;'>🎯 Painel Estratégico</h3>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# CARREGAMENTO DOS DADOS E CLASSIFICAÇÃO TERRITORIAL
# ==========================================

ARQUIVOS_LOCAIS_TSE = {
    2020: "tse_locais_acre_2020.csv.xlsx",
    2022: "tse_locais_acre_2022.csv.xlsx",
    2024: "tse_locais_acre_2024.csv.xlsx",
}

# Use esta tabela somente depois de uma conferência documental ou em campo.
# Formato da chave: ANO|CD_MUNICIPIO|NR_ZONA|NR_LOCAL_VOTACAO
# Exemplo:
# AJUSTES_MANUAIS_ZONA = {
#     "2024|1392|1|2810": {
#         "TIPO_ZONA": "RURAL",
#         "OBSERVACAO_ZONA": "Confirmado pela coordenação local em 01/08/2026",
#     }
# }
AJUSTES_MANUAIS_ZONA = {}


def normalizar_texto(valor):
    """Padroniza nomes sem alterar os textos exibidos ao usuário."""
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = texto.encode("ascii", "ignore").decode("ascii").upper()
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return " ".join(texto.split())


def normalizar_coordenada(valor, minimo_absoluto, maximo_absoluto):
    """Recupera coordenadas TSE que chegaram ao XLSX sem separador decimal."""
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
    for potencia in range(0, 10):
        candidato = numero / (10 ** potencia)
        if minimo_absoluto <= candidato <= maximo_absoluto:
            return sinal * candidato
    return np.nan


@st.cache_data
def carregar_locais_tse():
    """Carrega as bases oficiais de locais/seções e classifica o território."""
    bases = []
    arquivos_ausentes = []
    erros_leitura = []

    for ano, caminho in ARQUIVOS_LOCAIS_TSE.items():
        if not os.path.exists(caminho):
            arquivos_ausentes.append(caminho)
            continue

        try:
            df = pd.read_excel(caminho, engine="openpyxl")
        except Exception as erro:
            erros_leitura.append(
                f"{caminho}: confirme se o arquivo abre no Excel e se foi enviado "
                f"integralmente ao GitHub. Detalhe: {erro}"
            )
            continue
        colunas_obrigatorias = {
            "AA_ELEICAO", "NR_TURNO", "CD_MUNICIPIO", "NM_MUNICIPIO",
            "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO",
            "NM_BAIRRO", "DS_ENDERECO", "QT_ELEITOR_SECAO",
            "NR_LATITUDE", "NR_LONGITUDE"
        }
        faltantes = colunas_obrigatorias.difference(df.columns)
        if faltantes:
            raise ValueError(
                f"O arquivo {caminho} não contém: {', '.join(sorted(faltantes))}"
            )

        # Primeiro turno evita duplicar seções em eleições com segundo turno.
        df = df[df["NR_TURNO"] == 1].copy()
        df = df.rename(columns={"AA_ELEICAO": "ANO_ELEICAO"})
        for coluna_codigo in [
            "ANO_ELEICAO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO",
            "NR_LOCAL_VOTACAO"
        ]:
            df[coluna_codigo] = pd.to_numeric(
                df[coluna_codigo], errors="coerce"
            ).astype("Int64")

        df["lat"] = df["NR_LATITUDE"].apply(
            lambda x: normalizar_coordenada(x, 7, 12)
        )
        df["lon"] = df["NR_LONGITUDE"].apply(
            lambda x: normalizar_coordenada(x, 65, 75)
        )

        df["NM_LOCAL_NORMALIZADO"] = df["NM_LOCAL_VOTACAO"].apply(normalizar_texto)
        df["NM_MUNICIPIO_NORMALIZADO"] = df["NM_MUNICIPIO"].apply(normalizar_texto)
        df["NM_BAIRRO_NORMALIZADO"] = df["NM_BAIRRO"].apply(normalizar_texto)
        df["DS_ENDERECO_NORMALIZADO"] = df["DS_ENDERECO"].apply(normalizar_texto)
        df["ID_LOCAL_ANO"] = (
            df["ANO_ELEICAO"].astype(str) + "|" +
            df["CD_MUNICIPIO"].astype(str) + "|" +
            df["NR_ZONA"].astype(str) + "|" +
            df["NR_LOCAL_VOTACAO"].astype(str)
        )
        # Zona + número do local evitam confundir unidades de mesmo nome no município.
        df["ID_LOCAL_HISTORICO"] = (
            df["CD_MUNICIPIO"].astype(str) + "|" +
            df["NR_ZONA"].astype(str) + "|" +
            df["NR_LOCAL_VOTACAO"].astype(str)
        )
        df["RURAL_DECLARADO_TSE"] = df["NM_BAIRRO_NORMALIZADO"].str.contains(
            r"\bRURAL\b", regex=True, na=False
        )
        bases.append(df)

    if not bases:
        raise FileNotFoundError(
            "Nenhuma planilha válida de locais do TSE foi encontrada. "
            + " ".join(erros_leitura)
        )

    locais = pd.concat(bases, ignore_index=True)

    # Se o mesmo número de local apareceu como rural em outro ano, preservamos a
    # evidência, mas deixamos a unidade em REVISAR para não tratá-la como confirmação
    # atual sem validação documental.
    ids_rurais_historicos = set(
        locais.loc[locais["RURAL_DECLARADO_TSE"], "ID_LOCAL_HISTORICO"]
    )
    locais["RURAL_HISTORICO_TSE"] = locais["ID_LOCAL_HISTORICO"].isin(
        ids_rurais_historicos
    )

    texto_territorial = (
        locais["NM_LOCAL_NORMALIZADO"] + " " +
        locais["NM_BAIRRO_NORMALIZADO"] + " " +
        locais["DS_ENDERECO_NORMALIZADO"]
    )
    padrao_indicio_rural = (
        r"\bRURAL\b|RAMAL|SERINGAL|COLONIA|COMUNIDADE|ASSENTAMENTO|"
        r"ALDEIA|RESERVA|RODOVIA|\bBR\s*\d|\bAC\s*\d|\bKM\s*\d"
    )
    locais["INDICIO_RURAL"] = texto_territorial.str.contains(
        padrao_indicio_rural, regex=True, na=False
    )

    locais["TIPO_ZONA"] = np.select(
        [
            locais["RURAL_DECLARADO_TSE"],
            locais["RURAL_HISTORICO_TSE"],
            locais["INDICIO_RURAL"],
        ],
        ["RURAL", "REVISAR", "REVISAR"],
        default="URBANA",
    )
    locais["FONTE_CLASSIFICACAO"] = np.select(
        [
            locais["RURAL_DECLARADO_TSE"],
            locais["RURAL_HISTORICO_TSE"],
            locais["INDICIO_RURAL"],
        ],
        [
            "Bairro informado como rural no TSE",
            "Histórico do mesmo local no TSE",
            "Indício no nome, bairro ou endereço",
        ],
        default="Sem indício rural na base TSE",
    )
    locais["NIVEL_CONFIANCA"] = np.select(
        [
            locais["RURAL_DECLARADO_TSE"],
            locais["RURAL_HISTORICO_TSE"],
            locais["INDICIO_RURAL"],
        ],
        ["ALTA", "MÉDIA", "BAIXA"],
        default="MÉDIA",
    )
    locais["OBSERVACAO_ZONA"] = ""

    for chave, ajuste in AJUSTES_MANUAIS_ZONA.items():
        mascara = locais["ID_LOCAL_ANO"] == chave
        if mascara.any():
            locais.loc[mascara, "TIPO_ZONA"] = ajuste.get("TIPO_ZONA", "REVISAR")
            locais.loc[mascara, "FONTE_CLASSIFICACAO"] = "Revisão manual documentada"
            locais.loc[mascara, "NIVEL_CONFIANCA"] = "ALTA"
            locais.loc[mascara, "OBSERVACAO_ZONA"] = ajuste.get(
                "OBSERVACAO_ZONA", ""
            )

    locais.attrs["arquivos_ausentes"] = arquivos_ausentes
    locais.attrs["erros_leitura"] = erros_leitura
    return locais


@st.cache_data
def carregar_dados():
    df = pd.read_csv("dados.csv")
    for coluna_codigo in ["ANO_ELEICAO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]:
        if coluna_codigo in df.columns:
            df[coluna_codigo] = pd.to_numeric(
                df[coluna_codigo], errors="coerce"
            ).astype("Int64")
    locais = carregar_locais_tse()

    chaves = ["ANO_ELEICAO", "NR_ZONA", "NR_SECAO"]
    if "CD_MUNICIPIO" in df.columns:
        chaves.insert(1, "CD_MUNICIPIO")

    colunas_contexto = [
        "NM_MUNICIPIO", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO", "NM_BAIRRO",
        "DS_ENDERECO", "lat", "lon", "ID_LOCAL_ANO", "ID_LOCAL_HISTORICO",
        "TIPO_ZONA", "FONTE_CLASSIFICACAO", "NIVEL_CONFIANCA",
        "OBSERVACAO_ZONA", "QT_ELEITOR_SECAO"
    ]
    mapa = locais[chaves + colunas_contexto].drop_duplicates(subset=chaves)
    mapa = mapa.rename(columns={c: f"{c}_TSE" for c in colunas_contexto})
    df = pd.merge(df, mapa, on=chaves, how="left")

    # A base oficial de locais prevalece; o valor anterior é mantido apenas quando
    # uma seção não encontra correspondência nas planilhas anexadas.
    for coluna in colunas_contexto:
        coluna_tse = f"{coluna}_TSE"
        if coluna in df.columns:
            df[coluna] = df[coluna_tse].combine_first(df[coluna])
        else:
            df[coluna] = df[coluna_tse]
    df = df.drop(
        columns=[f"{c}_TSE" for c in colunas_contexto], errors="ignore"
    )
    df["TIPO_ZONA"] = df["TIPO_ZONA"].fillna("REVISAR")
    df["FONTE_CLASSIFICACAO"] = df["FONTE_CLASSIFICACAO"].fillna(
        "Sem correspondência com a base de locais TSE"
    )
    df["NIVEL_CONFIANCA"] = df["NIVEL_CONFIANCA"].fillna("BAIXA")
    return df


def anexar_contexto_territorial(base, df_votos):
    """Inclui município, local e classificação sem criar colunas _x/_y."""
    if base.empty or df_votos.empty:
        return base

    chaves = ['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO']
    if 'CD_MUNICIPIO' in base.columns and 'CD_MUNICIPIO' in df_votos.columns:
        chaves.insert(1, 'CD_MUNICIPIO')
    if not set(chaves).issubset(base.columns) or not set(chaves).issubset(df_votos.columns):
        return base

    base = base.copy()
    votos_contexto = df_votos.copy()
    for chave in chaves:
        base[chave] = pd.to_numeric(base[chave], errors='coerce').astype('Int64')
        votos_contexto[chave] = pd.to_numeric(
            votos_contexto[chave], errors='coerce'
        ).astype('Int64')

    contexto = [
        'NM_MUNICIPIO', 'NM_LOCAL_VOTACAO', 'NR_LOCAL_VOTACAO',
        'TIPO_ZONA', 'FONTE_CLASSIFICACAO', 'NIVEL_CONFIANCA',
        'ID_LOCAL_ANO', 'lat', 'lon'
    ]
    contexto = [c for c in contexto if c in votos_contexto.columns]
    mapa = votos_contexto[chaves + contexto].drop_duplicates(subset=chaves)
    mapa = mapa.rename(columns={c: f"{c}_PAINEL" for c in contexto})
    base = pd.merge(base, mapa, on=chaves, how='inner')

    for coluna in contexto:
        coluna_painel = f"{coluna}_PAINEL"
        if coluna in base.columns:
            base[coluna] = base[coluna_painel].combine_first(base[coluna])
        else:
            base[coluna] = base[coluna_painel]
    return base.drop(
        columns=[f"{c}_PAINEL" for c in contexto], errors='ignore'
    )

try:
    dados = carregar_dados()
    locais_tse = carregar_locais_tse()
except Exception as erro:
    st.error(f"Erro ao carregar as bases eleitorais: {erro}")
    st.stop()

problemas_bases_tse = (
    locais_tse.attrs.get("arquivos_ausentes", [])
    + locais_tse.attrs.get("erros_leitura", [])
)
if problemas_bases_tse:
    st.warning(
        "Algumas planilhas de locais do TSE não foram carregadas. Os anos válidos "
        "continuam disponíveis. Verifique: " + " | ".join(problemas_bases_tse)
    )

@st.cache_data
def carregar_demografia(df_votos):
    """Carrega somente a composição agregada do eleitorado por seção."""
    try:
        df_demo = pd.DataFrame()
        if os.path.exists("base_demografica_ac.zip"):
            with zipfile.ZipFile("base_demografica_ac.zip", 'r') as z:
                nome_arquivo = z.namelist()[0]
                with z.open(nome_arquivo) as f:
                    df_demo = pd.read_csv(f)
        else:
             return pd.DataFrame() 

        if (
            not df_votos.empty and not df_demo.empty
            and 'NR_ZONA' in df_votos.columns and 'NR_SECAO' in df_votos.columns
            and 'NM_LOCAL_VOTACAO' in df_votos.columns
        ):
            chaves = ['ANO_ELEICAO', 'NR_ZONA', 'NR_SECAO']
            if 'CD_MUNICIPIO' in df_demo.columns and 'CD_MUNICIPIO' in df_votos.columns:
                chaves.insert(1, 'CD_MUNICIPIO')
            colunas_mapa = chaves + [
                'NM_LOCAL_VOTACAO', 'NM_MUNICIPIO', 'TIPO_ZONA',
                'FONTE_CLASSIFICACAO', 'NIVEL_CONFIANCA'
            ]
            colunas_mapa = [c for c in colunas_mapa if c in df_votos.columns]
            mapa_escolas = df_votos[colunas_mapa].drop_duplicates(subset=chaves)
            df_demo = pd.merge(df_demo, mapa_escolas, on=chaves, how='inner')
        return df_demo
    except Exception as erro:
        print(f"Falha ao carregar demografia: {erro}")
        return pd.DataFrame()

@st.cache_data
def carregar_adormecidos(df_votos):
    try:
        if os.path.exists("base_adormecidos_ac.csv"):
            df_ador = pd.read_csv("base_adormecidos_ac.csv")
            return anexar_contexto_territorial(df_ador, df_votos)
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

        return anexar_contexto_territorial(df_conc, df_votos)
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
        "🔗 5. Correlação Territorial",
        "🚜 6. Análise Territorial da Zona Rural"
    ]
)
st.sidebar.markdown("---")

st.sidebar.header("🎛️ Filtros de Análise")
anos_disponiveis = sorted(
    [int(a) for a in dados['ANO_ELEICAO'].dropna().unique()], reverse=True
)
opcoes_ano = ['Todos os Anos (Série Histórica)'] + [str(a) for a in anos_disponiveis]
ano_selecionado = st.sidebar.selectbox("Selecione o Período / Ano:", opcoes_ano)

col_municipio = None
municipios_selecionados = []
texto_local = "em Todo o Estado" 
for col in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']:
    if col in dados.columns:
        col_municipio = col
        break

if col_municipio:
    municipios_disponiveis = sorted(dados[col_municipio].dropna().unique())
    municipios_selecionados = st.sidebar.multiselect("Filtrar por Município(s):", municipios_disponiveis, default=municipios_disponiveis)
    if municipios_selecionados:
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
zonas_disponiveis = ['Todas as Zonas', 'URBANA', 'RURAL', 'REVISAR']
zona_selecionada = st.sidebar.selectbox("Selecione o Tipo de Zona:", zonas_disponiveis)

if (
    zona_selecionada != 'Todas as Zonas'
    and menu_selecionado != "🚜 6. Análise Territorial da Zona Rural"
):
    dados = dados[dados['TIPO_ZONA'] == zona_selecionada]

st.sidebar.markdown("---")
mostrar_todas = st.sidebar.checkbox("👁️ Exibir TODOS os locais", value=False)
limite_slider = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5, disabled=mostrar_todas)
limite_ranking = 999999 if mostrar_todas else limite_slider

label_periodo = "Série Histórica" if ano_selecionado == 'Todos os Anos (Série Histórica)' else f"Ano de {ano_selecionado}"

# ==========================================
# ROTA 1: DESEMPENHO ELEITORAL POR TERRITÓRIO
# ==========================================
if menu_selecionado == "📊 1. Desempenho Eleitoral por Território":
    st.title(f"📊 Desempenho Eleitoral por Território - {label_periodo}")

    st.info("""
    **Como interpretar este módulo**

    Os gráficos descrevem a distribuição histórica dos votos por local de votação.
    Resultados de anos diferentes devem ser comparados com cautela quando o cargo,
    o eleitorado ou o contexto da eleição forem distintos.
    """)

    if ano_selecionado == 'Todos os Anos (Série Histórica)':
        dados_filtrados = dados.copy()
    else:
        dados_filtrados = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()

    total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
    total_escolas = dados_filtrados['ID_LOCAL_ANO'].nunique() if 'ID_LOCAL_ANO' in dados_filtrados.columns else dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

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
        top_escolas['PARTICIPACAO_VALIDOS'] = np.where(
            top_escolas['QT_VOTOS_VALIDOS_SECAO'] > 0,
            (top_escolas['QT_VOTOS_SAMIR'] / top_escolas['QT_VOTOS_VALIDOS_SECAO']) * 100,
            0,
        ).round(1)
    else:
        top_escolas['PARTICIPACAO_VALIDOS'] = 0.0

    top_escolas = top_escolas.sort_values(by='QT_VOTOS_SAMIR', ascending=False).head(limite_ranking)
    altura_grafico = max(500, len(top_escolas) * 35)

    grafico_barras = alt.Chart(top_escolas).mark_bar(color="#1A73E8").encode(
        x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Obtidos', axis=alt.Axis(tickMinStep=1, format='d')),
        y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title=None, axis=alt.Axis(labelLimit=1000, labelOverlap=False)),
        tooltip=[
            'NM_LOCAL_VOTACAO:N', 'QT_VOTOS_SAMIR:Q',
            alt.Tooltip('PARTICIPACAO_VALIDOS:Q', title='Participação nos válidos (%)', format='.1f')
        ]
    ).properties(height=altura_grafico)
    st.altair_chart(grafico_barras, use_container_width=True)

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

    st.subheader("📍 Distribuição entre Votos do Candidato e Demais Votos Válidos")
    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        agenda_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        agenda_df['DEMAIS_VOTOS_VALIDOS'] = (
            agenda_df['QT_VOTOS_VALIDOS_SECAO'] - agenda_df['QT_VOTOS_SAMIR']
        ).clip(lower=0)
        limite_desempenho = agenda_df['QT_VOTOS_SAMIR'].quantile(0.75)
        agenda_df['FAIXA_DESEMPENHO'] = np.where(
            agenda_df['QT_VOTOS_SAMIR'] > limite_desempenho,
            'Alta votação histórica', 'Demais locais'
        )
        agenda_df = agenda_df.sort_values(by='DEMAIS_VOTOS_VALIDOS', ascending=False).head(limite_ranking)

        scatter = alt.Chart(agenda_df).mark_circle(size=350).encode(
            x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Históricos do Candidato'),
            y=alt.Y('DEMAIS_VOTOS_VALIDOS:Q', title='Votos Válidos Atribuídos a Outras Candidaturas'),
            color=alt.Color(
                'FAIXA_DESEMPENHO:N', title='Faixa de desempenho',
                scale=alt.Scale(
                    domain=['Alta votação histórica', 'Demais locais'],
                    range=['#1A73E8', '#A7B0BE']
                )
            ),
            tooltip=['NM_LOCAL_VOTACAO', 'DEMAIS_VOTOS_VALIDOS', 'QT_VOTOS_SAMIR']
        ).properties(height=450)
        st.altair_chart(scatter, use_container_width=True)
    else:
        st.warning("A coluna 'QT_VOTOS_VALIDOS_SECAO' não está presente.")

    st.markdown("---")

    st.subheader("🧩 Matriz Descritiva dos Locais de Votação")

    st.markdown("""
    > **Como ler:** o eixo horizontal mostra o total de votos válidos e o eixo
    > vertical mostra os votos históricos do candidato. As linhas usam as medianas
    > de toda a seleção, evitando que a classificação mude somente porque a
    > quantidade de locais exibidos foi alterada.
    """)

    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        matriz_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        media_tamanho = matriz_df['QT_VOTOS_VALIDOS_SECAO'].median()
        media_votos = matriz_df['QT_VOTOS_SAMIR'].median()

        def classificar_quadrante(row):
            escola_grande = row['QT_VOTOS_VALIDOS_SECAO'] >= media_tamanho
            samir_forte = row['QT_VOTOS_SAMIR'] >= media_votos
            if escola_grande and samir_forte:
                return "Alto volume | Alta votação"
            if escola_grande and not samir_forte:
                return "Alto volume | Baixa votação"
            if not escola_grande and samir_forte:
                return "Baixo volume | Alta votação"
            return "Baixo volume | Baixa votação"

        matriz_df['CLASSIFICACAO'] = matriz_df.apply(classificar_quadrante, axis=1)
        matriz_exibicao = matriz_df.sort_values(
            by='QT_VOTOS_VALIDOS_SECAO', ascending=False
        ).head(limite_ranking)

        scatter_matriz = alt.Chart(matriz_exibicao).mark_circle(size=400).encode(
            x=alt.X('QT_VOTOS_VALIDOS_SECAO:Q', title='Total de Votos Válidos'),
            y=alt.Y('QT_VOTOS_SAMIR:Q', title='Votos Históricos do Candidato'),
            color=alt.Color(
                'CLASSIFICACAO:N', title='Classificação descritiva',
                scale=alt.Scale(
                    domain=[
                        "Alto volume | Alta votação", "Alto volume | Baixa votação",
                        "Baixo volume | Alta votação", "Baixo volume | Baixa votação"
                    ],
                    range=['#1A73E8', '#25D366', '#FFC107', '#A7B0BE']
                )
            ),
            tooltip=['NM_LOCAL_VOTACAO', 'CLASSIFICACAO', alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', format=','), alt.Tooltip('QT_VOTOS_SAMIR:Q', format=',')]
        ).properties(height=500)

        regra_x = alt.Chart(pd.DataFrame({'x': [media_tamanho]})).mark_rule(strokeDash=[5, 5], color='gray').encode(x='x:Q')
        regra_y = alt.Chart(pd.DataFrame({'y': [media_votos]})).mark_rule(strokeDash=[5, 5], color='gray').encode(y='y:Q')
        st.altair_chart(scatter_matriz + regra_x + regra_y, use_container_width=True)

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
        st.altair_chart(area + curva + linha_80, use_container_width=True)

    st.markdown("---")

    st.subheader("🏁 Cenário de Distribuição Proporcional de Meta")

    st.info("""
    Este cenário distribui uma meta global proporcionalmente ao peso histórico de
    cada local nos votos válidos. O resultado é apenas uma referência matemática;
    não representa previsão nem garantia de desempenho futuro.
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
            metas_df['Meta Proporcional do Local'] = (meta_global * metas_df['Peso_Calc']).astype(int)

            metas_df['Diferença para o Cenário'] = metas_df['Meta Proporcional do Local'] - metas_df['QT_VOTOS_SAMIR']
            metas_df['Diferença para o Cenário'] = metas_df['Diferença para o Cenário'].clip(lower=0)

            metas_df['Peso do Local'] = (metas_df['Peso_Calc'] * 100).round(2).astype(str) + '%'

            metas_df = metas_df.sort_values(by='Diferença para o Cenário', ascending=False).head(limite_ranking)

            tabela_final_metas = metas_df[['NM_LOCAL_VOTACAO', 'Peso do Local', 'Meta Proporcional do Local', 'QT_VOTOS_SAMIR', 'Diferença para o Cenário']]
            tabela_final_metas.columns = ['Local de Votação', 'Peso na Eleição', 'Meta Proporcional', 'Votos Históricos', 'Diferença para o Cenário']

            st.markdown(f"#### 📋 Distribuição Matemática de Metas ({texto_top})")
            st.dataframe(tabela_final_metas, use_container_width=True)
    else:
        st.warning("A coluna de Votos Válidos não está disponível para calcular a proporção da meta.")

# ==========================================
# ROTA 2: COMPOSIÇÃO AGREGADA DO ELEITORADO
# ==========================================
elif menu_selecionado == "👥 2. Composição do Eleitorado":
    st.title(f"👥 Composição Agregada do Eleitorado - {label_periodo}")

    st.info("""
    Este módulo descreve o eleitorado cadastrado pelo TSE nas seções selecionadas.
    Os dados são agregados e não identificam quem votou em determinada candidatura.
    Portanto, os gráficos não devem ser interpretados como perfil dos eleitores do candidato.
    """)

    if dados_demo.empty:
        st.error("⚠️ A base 'base_demografica_ac.zip' não foi encontrada no repositório.")
    else:
        df_demo_macro = dados_demo.copy()
        if ano_selecionado != 'Todos os Anos (Série Histórica)':
            df_demo_macro = df_demo_macro[
                df_demo_macro['ANO_ELEICAO'] == int(ano_selecionado)
            ]
        if zona_selecionada != 'Todas as Zonas' and 'TIPO_ZONA' in df_demo_macro.columns:
            df_demo_macro = df_demo_macro[
                df_demo_macro['TIPO_ZONA'] == zona_selecionada
            ]
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_y' in df_demo_macro.columns:
                df_demo_macro = df_demo_macro[
                    df_demo_macro['NM_MUNICIPIO_y'].isin(municipios_selecionados)
                ]
            elif 'NM_MUNICIPIO' in df_demo_macro.columns:
                df_demo_macro = df_demo_macro[
                    df_demo_macro['NM_MUNICIPIO'].isin(municipios_selecionados)
                ]

        df_demo_filtrado = df_demo_macro.copy()
        locais_opcoes = ["Visão geral dos locais selecionados"] + sorted(
            df_demo_filtrado['NM_LOCAL_VOTACAO'].dropna().unique().tolist()
        )
        local_alvo = st.selectbox(
            "Aprofundar a composição em um local de votação:", locais_opcoes
        )
        if local_alvo != "Visão geral dos locais selecionados":
            df_demo_filtrado = df_demo_filtrado[
                df_demo_filtrado['NM_LOCAL_VOTACAO'] == local_alvo
            ]

        total_perfis = df_demo_filtrado['QT_ELEITORES_PERFIL'].sum()
        st.metric(
            "Registros de eleitores representados nos perfis",
            f"{int(total_perfis):,}".replace(',', '.')
        )
        st.caption(
            "O total pode refletir a estrutura multidimensional da base do TSE; "
            "use cada gráfico pela distribuição percentual de sua própria dimensão."
        )
        st.markdown("---")

        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.subheader("Distribuição por Gênero")
            df_genero = df_demo_filtrado.groupby(
                'DS_GENERO', as_index=False
            )['QT_ELEITORES_PERFIL'].sum()
            grafico_genero = alt.Chart(df_genero).mark_arc(innerRadius=65).encode(
                theta=alt.Theta('QT_ELEITORES_PERFIL:Q'),
                color=alt.Color('DS_GENERO:N', title='Gênero'),
                tooltip=[
                    alt.Tooltip('DS_GENERO:N', title='Gênero'),
                    alt.Tooltip('QT_ELEITORES_PERFIL:Q', title='Eleitores', format=',')
                ]
            ).properties(height=350)
            st.altair_chart(grafico_genero, use_container_width=True)

        with col_graf2:
            st.subheader("Faixa Etária")
            df_idade = df_demo_filtrado.groupby(
                'DS_FAIXA_ETARIA', as_index=False
            )['QT_ELEITORES_PERFIL'].sum()
            grafico_idade = alt.Chart(df_idade).mark_bar(color="#0A1C2E").encode(
                x=alt.X('QT_ELEITORES_PERFIL:Q', title='Eleitores'),
                y=alt.Y('DS_FAIXA_ETARIA:N', title=None, sort='-x'),
                tooltip=[
                    alt.Tooltip('DS_FAIXA_ETARIA:N', title='Faixa etária'),
                    alt.Tooltip('QT_ELEITORES_PERFIL:Q', title='Eleitores', format=',')
                ]
            ).properties(height=max(350, len(df_idade) * 28))
            st.altair_chart(grafico_idade, use_container_width=True)

        st.markdown("---")
        st.subheader("Grau de Escolaridade")
        df_escolaridade = df_demo_filtrado.groupby(
            'DS_GRAU_ESCOLARIDADE', as_index=False
        )['QT_ELEITORES_PERFIL'].sum()
        grafico_escolaridade = alt.Chart(df_escolaridade).mark_bar(
            color="#1A73E8"
        ).encode(
            x=alt.X('QT_ELEITORES_PERFIL:Q', title='Eleitores'),
            y=alt.Y('DS_GRAU_ESCOLARIDADE:N', title=None, sort='-x'),
            tooltip=[
                alt.Tooltip('DS_GRAU_ESCOLARIDADE:N', title='Escolaridade'),
                alt.Tooltip('QT_ELEITORES_PERFIL:Q', title='Eleitores', format=',')
            ]
        ).properties(height=max(350, len(df_escolaridade) * 28))
        st.altair_chart(grafico_escolaridade, use_container_width=True)


# ==========================================
# ROTA 3: PARTICIPAÇÃO E NÃO COMPARECIMENTO
# ==========================================
elif menu_selecionado == "🗺️ 3. Participação e Não Comparecimento":
    st.title(f"🗺️ Participação, Abstenções, Brancos e Nulos - {label_periodo}")

    st.info("""
    Este módulo apresenta comportamentos eleitorais observados: não comparecimento,
    votos brancos e votos nulos. Esses grupos não devem ser tratados como eleitores
    automaticamente disponíveis, pois os dados não revelam a motivação individual.
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
        col1.metric("Abstenções, Brancos e Nulos", f"{int(total_adormecidos):,}".replace(',', '.'))
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

        st.subheader("📊 Locais com Maior Volume de Abstenções, Brancos e Nulos")
        ador_top = ador_escola.sort_values(by='VOTOS_ADORMECIDOS', ascending=False).head(limite_ranking)

        altura_ador = max(500, len(ador_top) * 35)

        grafico_ador = alt.Chart(ador_top).mark_bar(color="#E83E8C").encode(
            x=alt.X('VOTOS_ADORMECIDOS:Q', title='Abstenções, Brancos e Nulos', axis=alt.Axis(format='d')),
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
        st.altair_chart(grafico_ador, use_container_width=True)

        st.markdown("#### 📋 Detalhamento da Participação")
        tabela_ador = ador_top[['NM_LOCAL_VOTACAO', 'VOTOS_ADORMECIDOS', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_VOTOS_NULOS', 'QT_APTOS']]
        tabela_ador.columns = ['Local de Votação', 'Abstenções + Brancos + Nulos', 'Abstenções', 'Brancos', 'Nulos', 'Eleitores Aptos']
        st.dataframe(tabela_ador, use_container_width=True)


# ==========================================
# ROTA 4: PANORAMA DA CONCORRÊNCIA
# ==========================================
elif menu_selecionado == "📋 4. Panorama da Concorrência":
    st.title(f"📋 Panorama da Concorrência - {label_periodo}")

    st.info("""
    O Índice de Herfindahl-Hirschman (HHI) descreve o grau de concentração dos
    votos entre candidaturas. Valores menores indicam maior fragmentação e valores
    maiores indicam maior concentração. O índice é descritivo e não mede transferência
    de votos nem intenção atual do eleitorado.
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

        locais_concorrencia = sorted(
            df_conc_filtrado['NM_LOCAL_VOTACAO'].dropna().unique().tolist()
        )
        local_alvo_concorrencia = (
            st.selectbox("Selecione o Local de Votação:", locais_concorrencia)
            if locais_concorrencia else None
        )
        df_alvo = (
            df_conc_filtrado[
                df_conc_filtrado['NM_LOCAL_VOTACAO'] == local_alvo_concorrencia
            ]
            if local_alvo_concorrencia else df_conc_filtrado.iloc[0:0]
        )

        cargos_disponiveis = df_alvo['DS_CARGO'].dropna().unique().tolist()
        cargo_selecionado = (
            st.selectbox("Selecione o Cargo Disputado:", cargos_disponiveis)
            if cargos_disponiveis else None
        )
        if cargo_selecionado:
            df_alvo = df_alvo[df_alvo['DS_CARGO'] == cargo_selecionado]

        todos_candidatos = df_alvo.groupby('NM_VOTAVEL', as_index=False)['QT_VOTOS'].sum()
        todos_candidatos = todos_candidatos.sort_values(by='QT_VOTOS', ascending=False)
        total_votos_escola = todos_candidatos['QT_VOTOS'].sum()

        if total_votos_escola > 0:
            todos_candidatos['Participação (%)'] = (
                todos_candidatos['QT_VOTOS'] / total_votos_escola
            ) * 100
            todos_candidatos['Share_Decimal'] = todos_candidatos['QT_VOTOS'] / total_votos_escola
            hhi = float((todos_candidatos['Share_Decimal'] ** 2).sum())
            if hhi < 0.15:
                classificacao_hhi = "Votação fragmentada"
            elif hhi < 0.25:
                classificacao_hhi = "Concentração moderada"
            else:
                classificacao_hhi = "Votação concentrada"

            demais_candidaturas = todos_candidatos[
                ~todos_candidatos['NM_VOTAVEL'].str.contains("SAMIR", case=False, na=False)
            ].copy()
            if demais_candidaturas.empty:
                st.info("Não há outra candidatura comparável neste local/cargo.")
            else:
                top_1 = demais_candidaturas.iloc[0]

                st.markdown(
                    f"#### 📊 Distribuição em: **{local_alvo_concorrencia}**"
                )

                col1, col2, col3 = st.columns(3)
                col1.metric("Candidatura Mais Votada (exceto Samir)", top_1['NM_VOTAVEL'])
                col2.metric("Participação", f"{top_1['Participação (%)']:.1f}%")
                col3.metric("HHI", f"{hhi:.3f}", delta=classificacao_hhi, delta_color="off")

                st.markdown("---")

                candidaturas_grafico = demais_candidaturas.head(20)
                altura_candidaturas = max(500, len(candidaturas_grafico) * 35)

                grafico_candidaturas = alt.Chart(candidaturas_grafico).mark_bar(
                    color="#FFC107"
                ).encode(
                    x=alt.X('QT_VOTOS:Q', title='Votos da Candidatura', axis=alt.Axis(format='d')),
                    y=alt.Y('NM_VOTAVEL:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                    tooltip=[
                        alt.Tooltip('NM_VOTAVEL:N', title='Candidatura'),
                        alt.Tooltip('QT_VOTOS:Q', title='Votos', format=','),
                        alt.Tooltip('Participação (%):Q', title='Participação (%)', format='.1f')
                    ]
                ).properties(height=altura_candidaturas)
                st.altair_chart(grafico_candidaturas, use_container_width=True)

                st.markdown("#### 📋 Detalhamento das Candidaturas")
                tabela_candidaturas = demais_candidaturas[[
                    'NM_VOTAVEL', 'QT_VOTOS', 'Participação (%)'
                ]].copy()
                tabela_candidaturas.columns = [
                    'Candidatura', 'Votos no Local', 'Participação (%)'
                ]
                tabela_candidaturas['Participação (%)'] = tabela_candidaturas[
                    'Participação (%)'
                ].round(2)
                st.dataframe(tabela_candidaturas.head(50), use_container_width=True)
        else:
            st.warning("Não há dados de concorrência suficientes para este local/cargo nos filtros selecionados.")


# ==========================================
# ROTA 5: CORRELAÇÃO TERRITORIAL
# ==========================================
elif menu_selecionado == "🔗 5. Correlação Territorial":
    st.title(f"🔗 Correlação Territorial entre Candidaturas - {label_periodo}")

    st.info("""
    O coeficiente de Pearson mede se as participações percentuais de duas
    candidaturas variam de forma semelhante entre seções. Correlação não prova
    transferência de votos, aliança, preferência conjunta nem causalidade.
    """)

    if dados_concorrencia.empty or ano_selecionado == 'Todos os Anos (Série Histórica)':
        st.warning("Selecione um ano específico para evitar a mistura de eleições e cargos diferentes.")
    else:
        df_conc_filtrado = dados_concorrencia[
            dados_concorrencia['ANO_ELEICAO'] == int(ano_selecionado)
        ].copy()
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_y' in df_conc_filtrado.columns:
                df_conc_filtrado = df_conc_filtrado[
                    df_conc_filtrado['NM_MUNICIPIO_y'].isin(municipios_selecionados)
                ]
            elif 'NM_MUNICIPIO' in df_conc_filtrado.columns:
                df_conc_filtrado = df_conc_filtrado[
                    df_conc_filtrado['NM_MUNICIPIO'].isin(municipios_selecionados)
                ]

        cargos_disponiveis = df_conc_filtrado['DS_CARGO'].dropna().unique().tolist()
        cargo_alvo = (
            st.selectbox("Selecione o Cargo para Comparação:", cargos_disponiveis)
            if cargos_disponiveis else None
        )
        df_alvo = (
            df_conc_filtrado[df_conc_filtrado['DS_CARGO'] == cargo_alvo]
            if cargo_alvo else df_conc_filtrado.iloc[0:0]
        )

        chaves_secao = ['NR_ZONA', 'NR_SECAO']
        if 'CD_MUNICIPIO' in df_alvo.columns and 'CD_MUNICIPIO' in dados.columns:
            chaves_secao.insert(0, 'CD_MUNICIPIO')

        dados_ano = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()
        agg_samir = {'QT_VOTOS_SAMIR': 'sum'}
        if 'QT_VOTOS_VALIDOS_SECAO' in dados_ano.columns:
            agg_samir['QT_VOTOS_VALIDOS_SECAO'] = 'sum'
        votos_samir_secao = dados_ano.groupby(
            chaves_secao, as_index=False
        ).agg(agg_samir)

        if 'QT_VOTOS_VALIDOS_SECAO' in votos_samir_secao.columns:
            votos_samir_secao['PARTICIPACAO_SAMIR'] = np.where(
                votos_samir_secao['QT_VOTOS_VALIDOS_SECAO'] > 0,
                votos_samir_secao['QT_VOTOS_SAMIR'] /
                votos_samir_secao['QT_VOTOS_VALIDOS_SECAO'],
                0,
            )
        else:
            votos_samir_secao['PARTICIPACAO_SAMIR'] = votos_samir_secao['QT_VOTOS_SAMIR']

        if df_alvo.empty:
            st.info("Nenhum dado encontrado para o cargo selecionado.")
        else:
            pivot_alvo = df_alvo.pivot_table(
                index=chaves_secao, columns='NM_VOTAVEL', values='QT_VOTOS',
                aggfunc='sum', fill_value=0
            )
            total_secao = pivot_alvo.sum(axis=1).replace(0, np.nan)
            pivot_participacao = pivot_alvo.div(total_secao, axis=0).fillna(0).reset_index()
            base_correlacao = pd.merge(
                votos_samir_secao[chaves_secao + ['PARTICIPACAO_SAMIR']],
                pivot_participacao, on=chaves_secao, how='inner'
            )

            if len(base_correlacao) >= 10:
                matriz_corr = base_correlacao.drop(columns=chaves_secao).corr()
                corr_samir = matriz_corr['PARTICIPACAO_SAMIR'].drop(
                    'PARTICIPACAO_SAMIR'
                ).reset_index()
                corr_samir.columns = ['Candidatura', 'Correlação de Pearson (r)']
                corr_samir = corr_samir[
                    ~corr_samir['Candidatura'].str.contains("SAMIR", case=False, na=False)
                ]
                corr_samir = corr_samir.sort_values(
                    by='Correlação de Pearson (r)', ascending=False
                ).head(limite_ranking)

                if corr_samir.empty:
                    st.warning("Não foi possível calcular correlações para esta seleção.")
                else:
                    st.markdown(f"#### Correlações Observadas — Cargo: {cargo_alvo}")
                    st.caption(
                        f"Cálculo baseado em {len(base_correlacao)} seções. "
                        "Resultados próximos de zero indicam pouca associação linear."
                    )
                    grafico_corr = alt.Chart(corr_samir).mark_bar(
                        color="#25D366"
                    ).encode(
                        x=alt.X(
                            'Correlação de Pearson (r):Q', title='Correlação (r)',
                            scale=alt.Scale(domain=[-1, 1])
                        ),
                        y=alt.Y('Candidatura:N', title=None, sort='-x'),
                        tooltip=[
                            alt.Tooltip('Candidatura:N'),
                            alt.Tooltip('Correlação de Pearson (r):Q', format='.3f')
                        ]
                    ).properties(height=max(450, len(corr_samir) * 30))
                    st.altair_chart(grafico_corr, use_container_width=True)
                    corr_samir['Correlação de Pearson (r)'] = corr_samir[
                        'Correlação de Pearson (r)'
                    ].round(3)
                    st.dataframe(corr_samir, use_container_width=True)
            else:
                st.warning("São necessárias pelo menos 10 seções comparáveis para exibir a correlação.")

# ==========================================
# ROTA 6: ANÁLISE TERRITORIAL DA ZONA RURAL
# ==========================================
elif menu_selecionado == "🚜 6. Análise Territorial da Zona Rural":
    st.title("🚜 Análise Territorial da Zona Rural")

    st.info("""
    A análise usa os locais e as seções cadastrados pelo TSE. Um local é confirmado
    como rural quando o bairro do ano selecionado está identificado como rural.
    Evidências históricas ou indícios no nome e endereço permanecem separados na
    categoria **REVISAR**, até que haja validação documental ou territorial.
    """)

    anos_locais = sorted(
        [int(a) for a in locais_tse['ANO_ELEICAO'].dropna().unique()], reverse=True
    )
    if ano_selecionado == 'Todos os Anos (Série Histórica)':
        ano_referencia = anos_locais[0]
        st.caption(
            f"Visão principal utilizando {ano_referencia}, o ano mais recente disponível. "
            "A evolução histórica aparece mais abaixo."
        )
    else:
        ano_referencia = int(ano_selecionado)

    incluir_revisao = st.checkbox(
        "Incluir locais pendentes de revisão nos mapas e rankings",
        value=False,
        help="Os indicadores oficiais de zona rural continuam separados dos locais pendentes."
    )

    locais_ano = locais_tse[
        locais_tse['ANO_ELEICAO'] == ano_referencia
    ].copy()
    if municipios_selecionados:
        locais_ano = locais_ano[
            locais_ano['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]

    # Uma linha por local; o eleitorado é a soma das seções do primeiro turno.
    colunas_local = [
        'ID_LOCAL_ANO', 'ID_LOCAL_HISTORICO', 'CD_MUNICIPIO', 'NM_MUNICIPIO',
        'NR_ZONA', 'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO', 'NM_BAIRRO',
        'DS_ENDERECO', 'TIPO_ZONA', 'FONTE_CLASSIFICACAO', 'NIVEL_CONFIANCA',
        'OBSERVACAO_ZONA'
    ]
    locais_resumo = locais_ano.groupby(
        colunas_local, as_index=False, dropna=False
    ).agg(
        QT_SECOES=('NR_SECAO', 'nunique'),
        QT_ELEITORES=('QT_ELEITOR_SECAO', 'sum'),
        lat=('lat', 'median'),
        lon=('lon', 'median'),
    )

    locais_rurais_confirmados = locais_resumo[
        locais_resumo['TIPO_ZONA'] == 'RURAL'
    ].copy()
    locais_revisar = locais_resumo[
        locais_resumo['TIPO_ZONA'] == 'REVISAR'
    ].copy()
    tipos_incluidos = ['RURAL', 'REVISAR'] if incluir_revisao else ['RURAL']
    locais_analise = locais_resumo[
        locais_resumo['TIPO_ZONA'].isin(tipos_incluidos)
    ].copy()

    # Agrega os votos pela chave oficial do local e os combina com todo o universo
    # rural, inclusive locais em que o candidato teve zero voto.
    votos_ano = dados[dados['ANO_ELEICAO'] == ano_referencia].copy()
    if municipios_selecionados and 'NM_MUNICIPIO' in votos_ano.columns:
        votos_ano = votos_ano[
            votos_ano['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]
    agg_votos = {'QT_VOTOS_SAMIR': 'sum'}
    if 'QT_VOTOS_VALIDOS_SECAO' in votos_ano.columns:
        agg_votos['QT_VOTOS_VALIDOS_SECAO'] = 'sum'
    votos_por_local = votos_ano.dropna(subset=['ID_LOCAL_ANO']).groupby(
        'ID_LOCAL_ANO', as_index=False
    ).agg(agg_votos)

    base_rural = pd.merge(
        locais_analise, votos_por_local, on='ID_LOCAL_ANO', how='left'
    )
    base_rural['QT_VOTOS_SAMIR'] = base_rural['QT_VOTOS_SAMIR'].fillna(0)
    if 'QT_VOTOS_VALIDOS_SECAO' not in base_rural.columns:
        base_rural['QT_VOTOS_VALIDOS_SECAO'] = 0
    base_rural['QT_VOTOS_VALIDOS_SECAO'] = base_rural[
        'QT_VOTOS_VALIDOS_SECAO'
    ].fillna(0)
    base_rural['PARTICIPACAO_VALIDOS'] = np.where(
        base_rural['QT_VOTOS_VALIDOS_SECAO'] > 0,
        (base_rural['QT_VOTOS_SAMIR'] /
         base_rural['QT_VOTOS_VALIDOS_SECAO']) * 100,
        0,
    )
    base_rural['DEMAIS_VOTOS_VALIDOS'] = (
        base_rural['QT_VOTOS_VALIDOS_SECAO'] - base_rural['QT_VOTOS_SAMIR']
    ).clip(lower=0)

    base_rural_confirmada = base_rural[base_rural['TIPO_ZONA'] == 'RURAL']
    total_validos_rural = base_rural_confirmada['QT_VOTOS_VALIDOS_SECAO'].sum()
    total_votos_rural = base_rural_confirmada['QT_VOTOS_SAMIR'].sum()
    demais_validos_rural = max(total_validos_rural - total_votos_rural, 0)
    participacao_rural = (
        total_votos_rural / total_validos_rural * 100
        if total_validos_rural > 0 else 0
    )
    eleitorado_total_selecao = locais_resumo['QT_ELEITORES'].sum()
    eleitorado_rural_total = locais_rurais_confirmados['QT_ELEITORES'].sum()
    percentual_eleitorado_rural = (
        eleitorado_rural_total / eleitorado_total_selecao * 100
        if eleitorado_total_selecao > 0 else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Locais Examinados", f"{len(locais_resumo):,}".replace(',', '.'))
    c2.metric("Locais Rurais Confirmados", f"{len(locais_rurais_confirmados):,}".replace(',', '.'))
    c3.metric("Seções Rurais", f"{int(locais_rurais_confirmados['QT_SECOES'].sum()):,}".replace(',', '.'))
    c4.metric("Eleitores em Locais Rurais", f"{int(eleitorado_rural_total):,}".replace(',', '.'))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Votos Históricos do Candidato", f"{int(total_votos_rural):,}".replace(',', '.'))
    c6.metric("Votos Válidos Rurais", f"{int(total_validos_rural):,}".replace(',', '.'))
    c7.metric("Demais Votos Válidos", f"{int(demais_validos_rural):,}".replace(',', '.'))
    c8.metric("Participação nos Válidos Rurais", f"{participacao_rural:.2f}%")
    st.caption(
        f"Os locais rurais concentram {percentual_eleitorado_rural:.1f}% do eleitorado "
        "dos municípios selecionados. 'Demais votos válidos' é uma medida histórica "
        "e não significa que esses votos estejam disponíveis para uma candidatura."
    )

    if incluir_revisao:
        st.warning(
            "O mapa, o resumo municipal e os rankings abaixo incluem locais pendentes "
            "de revisão. Os indicadores do cabeçalho permanecem restritos aos rurais "
            "confirmados."
        )

    st.markdown("---")
    st.subheader("📍 Mapa dos Locais Rurais")
    mapa_rural = base_rural.dropna(subset=['lat', 'lon']).copy()
    if not mapa_rural.empty:
        try:
            st.map(
                mapa_rural, latitude='lat', longitude='lon',
                size='QT_ELEITORES'
            )
        except TypeError:
            st.map(mapa_rural, latitude='lat', longitude='lon')
    else:
        st.info("Não há coordenadas válidas para os filtros selecionados.")

    st.markdown("---")
    st.subheader("📊 Resumo Rural por Município")
    resumo_municipal = base_rural.groupby(
        'NM_MUNICIPIO', as_index=False
    ).agg(
        LOCAIS=('ID_LOCAL_ANO', 'nunique'),
        SECOES=('QT_SECOES', 'sum'),
        ELEITORES=('QT_ELEITORES', 'sum'),
        VOTOS_SAMIR=('QT_VOTOS_SAMIR', 'sum'),
        VOTOS_VALIDOS=('QT_VOTOS_VALIDOS_SECAO', 'sum'),
    )
    resumo_municipal['PARTICIPACAO_VALIDOS_PCT'] = np.where(
        resumo_municipal['VOTOS_VALIDOS'] > 0,
        resumo_municipal['VOTOS_SAMIR'] /
        resumo_municipal['VOTOS_VALIDOS'] * 100,
        0,
    )

    eleitorado_total_municipio = locais_resumo.groupby(
        'NM_MUNICIPIO', as_index=False
    )['QT_ELEITORES'].sum().rename(
        columns={'QT_ELEITORES': 'ELEITORADO_TOTAL_MUNICIPIO'}
    )
    resumo_municipal = pd.merge(
        resumo_municipal, eleitorado_total_municipio,
        on='NM_MUNICIPIO', how='left'
    )
    resumo_municipal['ELEITORADO_RURAL_PCT'] = np.where(
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] > 0,
        resumo_municipal['ELEITORES'] /
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] * 100,
        0,
    )
    resumo_municipal = resumo_municipal.sort_values(
        by='ELEITORES', ascending=False
    )
    tabela_municipal = resumo_municipal.rename(columns={
        'NM_MUNICIPIO': 'Município', 'LOCAIS': 'Locais', 'SECOES': 'Seções',
        'ELEITORES': 'Eleitores Rurais', 'VOTOS_SAMIR': 'Votos do Candidato',
        'VOTOS_VALIDOS': 'Votos Válidos',
        'PARTICIPACAO_VALIDOS_PCT': 'Participação nos Válidos (%)',
        'ELEITORADO_RURAL_PCT': 'Eleitorado Rural no Município (%)'
    })
    st.dataframe(
        tabela_municipal[[
            'Município', 'Locais', 'Seções', 'Eleitores Rurais',
            'Eleitorado Rural no Município (%)', 'Votos do Candidato',
            'Votos Válidos', 'Participação nos Válidos (%)'
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            'Eleitorado Rural no Município (%)': st.column_config.NumberColumn(format="%.1f%%"),
            'Participação nos Válidos (%)': st.column_config.NumberColumn(format="%.2f%%"),
        }
    )

    st.markdown("---")
    st.subheader("📋 Desempenho Histórico nos Locais Rurais")
    criterio_ranking = st.selectbox(
        "Ordenar os locais por:",
        [
            "Votos do Candidato", "Participação nos Válidos",
            "Eleitorado", "Demais Votos Válidos"
        ]
    )
    mapa_criterios = {
        "Votos do Candidato": 'QT_VOTOS_SAMIR',
        "Participação nos Válidos": 'PARTICIPACAO_VALIDOS',
        "Eleitorado": 'QT_ELEITORES',
        "Demais Votos Válidos": 'DEMAIS_VOTOS_VALIDOS',
    }
    coluna_ranking = mapa_criterios[criterio_ranking]
    ranking_rural = base_rural.sort_values(
        by=coluna_ranking, ascending=False
    ).head(limite_ranking)

    grafico_rural = alt.Chart(ranking_rural).mark_bar(color="#28A745").encode(
        x=alt.X(f'{coluna_ranking}:Q', title=criterio_ranking),
        y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x'),
        tooltip=[
            alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
            alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
            alt.Tooltip('QT_ELEITORES:Q', title='Eleitores', format=','),
            alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos do candidato', format=','),
            alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', title='Votos válidos', format=','),
            alt.Tooltip('PARTICIPACAO_VALIDOS:Q', title='Participação (%)', format='.2f'),
            alt.Tooltip('TIPO_ZONA:N', title='Classificação')
        ]
    ).properties(height=max(450, len(ranking_rural) * 34))
    st.altair_chart(grafico_rural, use_container_width=True)

    tabela_locais = ranking_rural[[
        'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO',
        'NM_BAIRRO', 'QT_SECOES', 'QT_ELEITORES', 'QT_VOTOS_SAMIR',
        'QT_VOTOS_VALIDOS_SECAO', 'PARTICIPACAO_VALIDOS', 'TIPO_ZONA',
        'NIVEL_CONFIANCA'
    ]].copy()
    tabela_locais.columns = [
        'Município', 'Zona', 'Nº Local', 'Local de Votação', 'Bairro',
        'Seções', 'Eleitores', 'Votos do Candidato', 'Votos Válidos',
        'Participação nos Válidos (%)', 'Classificação', 'Confiança'
    ]
    st.dataframe(tabela_locais, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📈 Evolução Histórica Rural")
    dados_rurais_hist = dados[dados['TIPO_ZONA'] == 'RURAL'].copy()
    agg_evolucao = {'QT_VOTOS_SAMIR': 'sum'}
    if 'QT_VOTOS_VALIDOS_SECAO' in dados_rurais_hist.columns:
        agg_evolucao['QT_VOTOS_VALIDOS_SECAO'] = 'sum'
    evolucao_votos = dados_rurais_hist.groupby(
        'ANO_ELEICAO', as_index=False
    ).agg(agg_evolucao).rename(columns={
        'QT_VOTOS_SAMIR': 'VOTOS_SAMIR',
        'QT_VOTOS_VALIDOS_SECAO': 'VOTOS_VALIDOS'
    })
    if 'VOTOS_VALIDOS' not in evolucao_votos.columns:
        evolucao_votos['VOTOS_VALIDOS'] = 0
    evolucao_votos['PARTICIPACAO_VALIDOS_PCT'] = np.where(
        evolucao_votos['VOTOS_VALIDOS'] > 0,
        evolucao_votos['VOTOS_SAMIR'] /
        evolucao_votos['VOTOS_VALIDOS'] * 100,
        0,
    )

    base_locais_rurais_hist = locais_tse[
        locais_tse['TIPO_ZONA'] == 'RURAL'
    ].copy()
    if municipios_selecionados:
        base_locais_rurais_hist = base_locais_rurais_hist[
            base_locais_rurais_hist['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]
    locais_rurais_hist = base_locais_rurais_hist.groupby(
        ['ANO_ELEICAO', 'ID_LOCAL_ANO'], as_index=False
    ).agg(
        NM_MUNICIPIO=('NM_MUNICIPIO', 'first'),
        ELEITORES=('QT_ELEITOR_SECAO', 'sum'),
        SECOES=('NR_SECAO', 'nunique')
    ).groupby('ANO_ELEICAO', as_index=False).agg(
        LOCAIS=('ID_LOCAL_ANO', 'nunique'),
        SECOES=('SECOES', 'sum'),
        ELEITORES=('ELEITORES', 'sum')
    )
    evolucao = pd.merge(
        locais_rurais_hist, evolucao_votos,
        on='ANO_ELEICAO', how='left'
    ).fillna(0)

    if evolucao['ANO_ELEICAO'].nunique() > 1:
        grafico_evolucao = alt.Chart(evolucao).mark_line(
            point=True, color="#28A745", strokeWidth=4
        ).encode(
            x=alt.X('ANO_ELEICAO:O', title='Ano da Eleição'),
            y=alt.Y('PARTICIPACAO_VALIDOS_PCT:Q', title='Participação nos Válidos Rurais (%)'),
            tooltip=[
                alt.Tooltip('ANO_ELEICAO:O', title='Ano'),
                alt.Tooltip('LOCAIS:Q', title='Locais', format=','),
                alt.Tooltip('SECOES:Q', title='Seções', format=','),
                alt.Tooltip('ELEITORES:Q', title='Eleitores', format=','),
                alt.Tooltip('VOTOS_SAMIR:Q', title='Votos do candidato', format=','),
                alt.Tooltip('PARTICIPACAO_VALIDOS_PCT:Q', title='Participação (%)', format='.2f')
            ]
        ).properties(height=400)
        st.altair_chart(grafico_evolucao, use_container_width=True)
    st.caption(
        "A comparação entre anos é descritiva. Mudanças de cargo, eleitorado, "
        "seções e contexto eleitoral podem afetar os resultados."
    )
    st.dataframe(evolucao, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔎 Controle de Qualidade da Classificação")
    sem_coordenada = int(
        locais_resumo[['lat', 'lon']].isna().any(axis=1).sum()
    )
    q1, q2, q3 = st.columns(3)
    q1.metric("Rurais com Confiança Alta", int((locais_rurais_confirmados['NIVEL_CONFIANCA'] == 'ALTA').sum()))
    q2.metric("Pendentes de Revisão", len(locais_revisar))
    q3.metric("Locais sem Coordenada", sem_coordenada)

    if not locais_revisar.empty:
        tabela_revisao = locais_revisar[[
            'ID_LOCAL_ANO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
            'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'DS_ENDERECO', 'QT_ELEITORES',
            'FONTE_CLASSIFICACAO', 'NIVEL_CONFIANCA'
        ]].copy()
        tabela_revisao.columns = [
            'ID Local/Ano', 'Município', 'Zona', 'Nº Local', 'Local de Votação',
            'Bairro', 'Endereço', 'Eleitores', 'Motivo', 'Confiança'
        ]
        st.dataframe(tabela_revisao, use_container_width=True, hide_index=True)
        csv_revisao = tabela_revisao.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "Baixar lista para revisão territorial",
            data=csv_revisao,
            file_name=f"locais_revisar_{ano_referencia}.csv",
            mime="text/csv"
        )
