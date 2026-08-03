import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import zipfile
import os
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

try:
    dados = carregar_dados()
    dados = aplicar_zonas(dados) # Aplica a classificação urbana/rural com precisão
except:
    st.error("Erro ao carregar o arquivo 'dados.csv'.")
    st.stop()

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
            votos_escola = df_votos.groupby(['ANO_ELEICAO', 'NM_LOCAL_VOTACAO'], as_index=False).agg({'QT_VOTOS_SAMIR': 'sum', 'QT_VOTOS_VALIDOS_SECAO': 'sum'})
            votos_escola['MARKET_SHARE'] = np.where(votos_escola['QT_VOTOS_VALIDOS_SECAO'] > 0, votos_escola['QT_VOTOS_SAMIR'] / votos_escola['QT_VOTOS_VALIDOS_SECAO'], 0)
            df_demo = pd.merge(df_demo, votos_escola[['ANO_ELEICAO', 'NM_LOCAL_VOTACAO', 'QT_VOTOS_SAMIR', 'MARKET_SHARE']], on=['ANO_ELEICAO', 'NM_LOCAL_VOTACAO'], how='left')
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
        "📊 1. Inteligência de Votos", 
        "👥 2. Perfil Estimado do Eleitor", 
        "🗺️ 3. Mapa de Votos Adormecidos",
        "⚔️ 4. Raio-X da Concorrência",
        "🔗 5. Análise de Votos Casados",
        "🚜 6. Análise Territorial da Zona Rural"
    ]
)
st.sidebar.markdown("---")

st.sidebar.header("🎛️ Filtros de Controle Estratégico")
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

st.sidebar.markdown("---")
mostrar_todas = st.sidebar.checkbox("👁️ Exibir TODAS as escolas", value=False)
limite_slider = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5, disabled=mostrar_todas)
limite_ranking = 999999 if mostrar_todas else limite_slider

label_periodo = "Série Histórica Acumulada" if ano_selecionado == 'Todos os Anos (Série Histórica)' else f"Ano de {ano_selecionado}"

# ==========================================
# ROTA 1: PAINEL DE INTELIGÊNCIA DE VOTOS 
# ==========================================
if menu_selecionado == "📊 1. Inteligência de Votos":
    st.title(f"📊 Inteligência de Votos e Dominância - {label_periodo}")

    st.info("""
    **💡 Fundamentação Estratégica: Alocação Eficiente de Recursos e Análise Espacial**

    A gestão moderna de campanhas exige o banimento de ações pautadas em achismos geográficos. Este módulo processa a distribuição espacial e a densidade de votos históricos para aplicar a *Regra de Pareto (80/20)*, permitindo alocar recursos logísticos e financeiros finitos estritamente nas zonas de maior tração eleitoral.

    As Matrizes Estratégicas fornecidas abaixo atuam como um sistema de priorização: categorizando territórios para Ações de Blindagem (Defesa de Redutos) e Ações de Avanço (Oceano Azul), maximizando o impacto territorial de cada movimento do candidato.
    """)

    if ano_selecionado == 'Todos os Anos (Série Histórica)':
        dados_filtrados = dados.copy()
    else:
        dados_filtrados = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()

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

    texto_top = "Todas as Escolas" if mostrar_todas else f"Top {limite_ranking}"
    st.subheader(f"📊 Raio-X, Dominância e Desempenho Visual ({texto_top} - {label_periodo})")

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
        tooltip=['NM_LOCAL_VOTACAO:N', 'QT_VOTOS_SAMIR:Q', alt.Tooltip('MARKET_SHARE:Q', format='.1f')]
    ).properties(height=altura_grafico)
    st.altair_chart(grafico_barras, use_container_width=True)

    if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
        top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Market Share (%)']
    else:
        top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Market Share (%)']
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

    st.subheader("🎯 Direcionador de Agenda (Otimização de Esforço Físico)")
    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        agenda_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        agenda_df['VOTOS_EM_DISPUTA'] = agenda_df['QT_VOTOS_VALIDOS_SECAO'] - agenda_df['QT_VOTOS_SAMIR']
        limite_reduto = agenda_df['QT_VOTOS_SAMIR'].quantile(0.75)
        agenda_df['ESTRATEGIA'] = np.where(agenda_df['QT_VOTOS_SAMIR'] > limite_reduto, '🛡️ Reduto (Fidelizar)', '⚔️ Expansão (Conquistar)')
        agenda_df = agenda_df.sort_values(by='VOTOS_EM_DISPUTA', ascending=False).head(limite_ranking)

        scatter = alt.Chart(agenda_df).mark_circle(size=350).encode(
            x=alt.X('QT_VOTOS_SAMIR:Q', title='Seus Votos Atuais'),
            y=alt.Y('VOTOS_EM_DISPUTA:Q', title='Votos Disponíveis (Em Disputa)'),
            color=alt.Color('ESTRATEGIA:N', legend=None, scale=alt.Scale(domain=['🛡️ Reduto (Fidelizar)', '⚔️ Expansão (Conquistar)'], range=['#25D366', '#E83E8C'])),
            tooltip=['NM_LOCAL_VOTACAO', 'VOTOS_EM_DISPUTA', 'QT_VOTOS_SAMIR']
        ).properties(height=450)
        st.altair_chart(scatter, use_container_width=True)
    else:
        st.warning("A coluna 'QT_VOTOS_VALIDOS_SECAO' não está presente.")

    st.markdown("---")

    st.subheader("🧩 Matriz de Inteligência de Território (Os 4 Quadrantes)")

    st.markdown("""
    > 📖 **COMO LER ESTE GRÁFICO INSTANTANEAMENTE:**
    > * **Eixo Horizontal (Esquerda para Direita):** Tamanho da escola (Total de Votos Válidos). Quanto mais para a **direita**, maior é o colégio eleitoral.
    > * **Eixo Vertical (Baixo para Cima):** Sua força atual (quantos votos você tem). Quanto mais para **cima**, mais votos você já possui ali.
    > * **As Linhas Pontilhadas Cruzadas:** Dividem o gráfico na média geral do estado, formando 4 quadrantes estratégicos:
    >   * 🔵 **Azul (Fortaleza):** Escolas grandes onde você já é forte. **Ação:** Defender e blindar.
    >   * 🟢 **Verde (Nicho Leal):** Escolas menores onde sua proporção de votos é boa. **Ação:** Manter relacionamento.
    >   * 🟡 **Amarelo (Oceano Azul):** Escolas grandes onde você ainda tem poucos votos. **Ação:** Atacar com força total (aqui está a maior mina de votos em disputa!).
    >   * 🔴/🟣 **Rosa (Zona de Descarte):** Escolas menores e com poucos votos seus. **Ação:** Ignorar para não desperdiçar energia física da equipe.
    """)

    if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
        matriz_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({'QT_VOTOS_VALIDOS_SECAO': 'sum', 'QT_VOTOS_SAMIR': 'sum'}).reset_index()
        matriz_df = matriz_df.sort_values(by='QT_VOTOS_VALIDOS_SECAO', ascending=False).head(limite_ranking)
        media_tamanho = matriz_df['QT_VOTOS_VALIDOS_SECAO'].mean()
        media_votos = matriz_df['QT_VOTOS_SAMIR'].mean()

        def classificar_quadrante(row):
            escola_grande = row['QT_VOTOS_VALIDOS_SECAO'] >= media_tamanho
            samir_forte = row['QT_VOTOS_SAMIR'] >= media_votos
            if escola_grande and samir_forte: return "🏆 FORTALEZA (Defender)"
            elif escola_grande and not samir_forte: return "🚀 OCEANO AZUL (Atacar)"
            elif not escola_grande and samir_forte: return "💎 NICHO LEAL (Manter)"
            else: return "❌ ZONA DE DESCARTE (Ignorar)"

        matriz_df['CLASSIFICACAO'] = matriz_df.apply(classificar_quadrante, axis=1)

        scatter_matriz = alt.Chart(matriz_df).mark_circle(size=400).encode(
            x=alt.X('QT_VOTOS_VALIDOS_SECAO:Q', title='Tamanho da Escola (Votos Válidos)'),
            y=alt.Y('QT_VOTOS_SAMIR:Q', title='Seus Votos (Sua Força)'),
            color=alt.Color('CLASSIFICACAO:N', legend=None, scale=alt.Scale(domain=["🏆 FORTALEZA (Defender)", "🚀 OCEANO AZUL (Atacar)", "💎 NICHO LEAL (Manter)", "❌ ZONA DE DESCARTE (Ignorar)"], range=['#1A73E8', '#25D366', '#FFC107', '#E83E8C'])),
            tooltip=['NM_LOCAL_VOTACAO', 'CLASSIFICACAO', alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', format=','), alt.Tooltip('QT_VOTOS_SAMIR:Q', format=',')]
        ).properties(height=500)

        regra_x = alt.Chart(pd.DataFrame({'x': [media_tamanho]})).mark_rule(strokeDash=[5, 5], color='gray').encode(x='x:Q')
        regra_y = alt.Chart(pd.DataFrame({'y': [media_votos]})).mark_rule(strokeDash=[5, 5], color='gray').encode(y='y:Q')
        st.altair_chart(scatter_matriz + regra_x + regra_y, use_container_width=True)

    st.markdown("---")

    st.subheader("🎯 A Curva de Foco (Regra de Pareto 80/20)")
    if not dados_filtrados.empty:
        pareto_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().reset_index().sort_values(by='QT_VOTOS_SAMIR', ascending=False)
        pareto_df['Votos Acumulados'] = pareto_df['QT_VOTOS_SAMIR'].cumsum()
        pareto_df['% Acumulado'] = (pareto_df['Votos Acumulados'] / pareto_df['QT_VOTOS_SAMIR'].sum()) * 100
        pareto_df['Posição no Ranking'] = range(1, len(pareto_df) + 1)

        curva = alt.Chart(pareto_df).mark_line(color='#E83E8C', strokeWidth=4, point=alt.OverlayMarkDef(color='#E83E8C', size=150)).encode(
            x=alt.X('Posição no Ranking:Q', title='Quantidade de Escolas'),
            y=alt.Y('% Acumulado:Q', title='% Acumulada', scale=alt.Scale(domain=[0, 100])),
            tooltip=['NM_LOCAL_VOTACAO:N', alt.Tooltip('% Acumulado:Q', format='.1f')]
        ).properties(height=400)

        area = curva.mark_area(color='#E83E8C', opacity=0.2)
        linha_80 = alt.Chart(pd.DataFrame({'y': [80]})).mark_rule(strokeDash=[5, 5], color='red', strokeWidth=2).encode(y='y:Q')
        st.altair_chart(area + curva + linha_80, use_container_width=True)

    st.markdown("---")

    st.subheader("🏁 Simulador de Metas de Vitória (Distribuidor de Cotas)")

    st.info("""
    **💡 Fundamentação Estratégica: Descentralização de Metas e Cobrança Matemática**
    
    Comandar uma equipe dizendo "precisamos de 15.000 votos no total" gera ansiedade, não gera ação direcional. Dizer a uma liderança "sua meta exclusiva na Escola do Bosque é de 134 votos, faltam apenas 40 para bater a sua cota" gera foco absoluto. 
    
    Este simulador encerra o 'achismo' das lideranças bairristas. Ele distribui a responsabilidade da vitória nas costas de toda a equipe de forma estritamente proporcional e inquestionável baseada no teto de votos válidos da seção. É a profissionalização definitiva da cobrança eleitoral.
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
            metas_df['Meta Justa da Escola'] = (meta_global * metas_df['Peso_Calc']).astype(int)

            metas_df['Votos a Conquistar (Esforço)'] = metas_df['Meta Justa da Escola'] - metas_df['QT_VOTOS_SAMIR']
            metas_df['Votos a Conquistar (Esforço)'] = metas_df['Votos a Conquistar (Esforço)'].apply(lambda x: max(0, x))

            metas_df['Peso da Escola'] = (metas_df['Peso_Calc'] * 100).round(2).astype(str) + '%'

            metas_df = metas_df.sort_values(by='Votos a Conquistar (Esforço)', ascending=False).head(limite_ranking)

            tabela_final_metas = metas_df[['NM_LOCAL_VOTACAO', 'Peso da Escola', 'Meta Justa da Escola', 'QT_VOTOS_SAMIR', 'Votos a Conquistar (Esforço)']]
            tabela_final_metas.columns = ['Local de Votação', 'Peso na Eleição', 'Cota (Meta) da Escola', 'Votos Históricos (Base)', '🔥 Votos a Conquistar']

            st.markdown(f"#### 📋 Distribuição Matemática de Metas ({texto_top})")
            st.dataframe(tabela_final_metas, use_container_width=True)
    else:
        st.warning("A coluna de Votos Válidos não está disponível para calcular a proporção da meta.")

# ==========================================
# ROTA 2: PERFIL ESTIMADO DO ELEITOR
# ==========================================
elif menu_selecionado == "👥 2. Perfil Estimado do Eleitor":
    st.title(f"👥 Perfil Estimado do Eleitor (Samir Bestene) - {label_periodo}")

    st.info("""
    **💡 Fundamentação Estratégica: Inferência Ecológica e Microtargeting Demográfico**
    
    O sigilo do voto impede o mapeamento exato da demografia individual. Contudo, superamos essa limitação legal aplicando o modelo de *Inferência Ecológica*. O sistema cruza os dados sociodemográficos oficiais do TSE (por colégio eleitoral) com a dominância tática (*Market Share*) do candidato na mesma jurisdição.
    
    O resultado entrega a probabilidade estatística do Perfil do Eleitor. Isso permite à coordenação de campanha moldar o *Microtargeting* no impulsionamento de tráfego pago (Redes Sociais) e ajustar a linguagem semântica e estética dos discursos para que ressoem perfeitamente com a demografia que já sustenta a base, garantindo a blindagem e retenção do eleitorado primário.
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
        escola_alvo = st.selectbox("🎯 Aprofundar o Raio-X em um Local de Votação:", escolas_tse)

        if escola_alvo != "Visão Macro (Todas as Selecionadas)":
            df_demo_filtrado = df_demo_filtrado[df_demo_filtrado['NM_LOCAL_VOTACAO'] == escola_alvo]
            st.markdown(f"**Analisando a Base em:** {escola_alvo}")
        else:
            st.markdown(f"**Analisando a Base:** {texto_local}")

        total_votos_estimados = df_demo_filtrado['VOTOS_ESTIMADOS_SAMIR'].sum()
        st.metric("Total de Votos Analisados na Seleção", f"{int(total_votos_estimados):,}".replace(',', '.'))
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
            st.altair_chart(grafico_genero, use_container_width=True)

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
            st.altair_chart(grafico_idade, use_container_width=True)

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
        st.altair_chart(grafico_escola, use_container_width=True)

        st.markdown("---")

        # --- FUNÇÃO: RADAR DE EXPANSÃO (AVATAR 1 E AVATAR 2) ---
        st.subheader("🚀 Radar de Expansão (O Mapa do Tesouro Demográfico)")

        st.info("""
        **💡 Fundamentação Estratégica: Expansão de Base por "Lookalike" (Públicos Semelhantes) e Teto Demográfico**
        
        No marketing político de alta precisão, o custo de converter um eleitor cujo perfil demográfico já possui afinidade orgânica com o candidato é drasticamente menor. Este módulo aplica a lógica de *Lookalike Audiences* (Públicos Semelhantes). 
        
        O algoritmo identifica os seus dois principais **"Eleitores Avatars"** (os extratos sociodemográficos que mais votam em você) e varre a base do TSE cruzando com o seu *Market Share*. O resultado aponta cirurgicamente em quais territórios os seus perfis ideais existem em abundância, mas ainda não foram conquistados. Isso revela o verdadeiro mapa do tesouro para o impulsionamento de tráfego pago geolocalizado e para direcionar agendas de rua com conversão garantida.
        """)

        avatar_df = df_demo_macro.groupby(['DS_GENERO', 'DS_FAIXA_ETARIA'])['VOTOS_ESTIMADOS_SAMIR'].sum().reset_index()
        if not avatar_df.empty:
            avatar_df = avatar_df.sort_values(by='VOTOS_ESTIMADOS_SAMIR', ascending=False)

            def renderizar_radar_avatar(posicao_label, top_avatar_row, cor_barra):
                avatar_genero = top_avatar_row['DS_GENERO']
                avatar_idade = top_avatar_row['DS_FAIXA_ETARIA']

                st.success(f"**{posicao_label} Eleitor Avatar:** O perfil de maior tração é **{avatar_genero}**, na faixa etária de **{avatar_idade}**.")

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

                tabela_radar.columns = ['Local de Votação', f'Total de {avatar_genero.title()}s ({avatar_idade})', 'Já Votam em Você (Estimado)', '🔥 Potencial de Crescimento (Alvo)']
                st.dataframe(tabela_radar, use_container_width=True)

                grafico_radar = alt.Chart(radar_df).mark_bar(color=cor_barra).encode(
                    x=alt.X('VOTOS_NAO_CONQUISTADOS:Q', title='Eleitores do seu Perfil a Conquistar', axis=alt.Axis(format='d')),
                    y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title=None, axis=alt.Axis(labelLimit=1000)),
                    tooltip=[
                        alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
                        alt.Tooltip('VOTOS_NAO_CONQUISTADOS:Q', title='Potencial a Conquistar', format=','),
                        alt.Tooltip('QT_ELEITORES_PERFIL:Q', title='Total deste Perfil na Escola', format=',')
                    ]
                ).properties(height=max(400, len(radar_df) * 35))
                st.altair_chart(grafico_radar, use_container_width=True)

            # Renderiza o 1º Avatar
            if len(avatar_df) >= 1:
                renderizar_radar_avatar("1º", avatar_df.iloc[0], "#FF8C00") # Laranja

            # Renderiza o 2º Avatar
            if len(avatar_df) >= 2:
                st.markdown("---")
                renderizar_radar_avatar("2º", avatar_df.iloc[1], "#1A73E8") # Azul Corporativo
        else:
            st.warning("Não há dados demográficos suficientes para calcular o Avatar do eleitor nesta seleção.")


# ==========================================
# ROTA 3: MAPA DE VOTOS ADORMECIDOS
# ==========================================
elif menu_selecionado == "🗺️ 3. Mapa de Votos Adormecidos":
    st.title(f"🗺️ Mapa de Votos Adormecidos (Abstenções, Brancos e Nulos) - {label_periodo}")

    st.info("""
    **💡 Fundamentação Estratégica: O Custo de Aquisição de Votos (CAV)**
    
    Na ciência política e no marketing eleitoral corporativo, o *Custo de Aquisição de Votos (CAV)* em redutos amplamente dominados por adversários é altíssimo, pois exige desconstruir a preferência do eleitor para então tentar reconstruir a confiança.
    
    Em contrapartida, as **Abstenções, Brancos e Nulos** representam um "Oceano Azul" de eleitores que não possuem rejeição direta à campanha, mas sim apatia ou desilusão orgânica com o processo. Matematicamente, mobilizar a estrutura de rua (militância, panfletagem direcional e logística) para áreas com altíssima concentração de 'Votos Adormecidos' garante um **Retorno sobre o Investimento (ROI)** de campanha brutalmente superior. É estatística e financeiramente mais eficiente motivar um eleitor neutro a ir às urnas do que converter um eleitor já fidelizado.
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
        col1.metric("Total de Votos Adormecidos", f"{int(total_adormecidos):,}".replace(',', '.'))
        col2.metric("Taxa de Desperdício", f"{taxa_adormecidos:.1f}%")
        col3.metric("Só de Abstenções (Faltaram)", f"{int(ador_escola['QT_ABSTENCOES'].sum()):,}".replace(',', '.'))

        st.markdown("---")

        st.subheader("📍 Dispersão Geográfica das Abstenções")
        mapa_ador = ador_escola.dropna(subset=['lat', 'lon'])
        if not mapa_ador.empty:
            st.map(mapa_ador, latitude='lat', longitude='lon')
        else:
            st.info("Dados de localização não disponíveis para este filtro.")

        st.markdown("---")

        st.subheader("🔥 Top Escolas para Mobilização de Rua (Ouro Puro)")
        ador_top = ador_escola.sort_values(by='VOTOS_ADORMECIDOS', ascending=False).head(limite_ranking)

        altura_ador = max(500, len(ador_top) * 35)

        grafico_ador = alt.Chart(ador_top).mark_bar(color="#E83E8C").encode(
            x=alt.X('VOTOS_ADORMECIDOS:Q', title='Quantidade de Votos Adormecidos', axis=alt.Axis(format='d')),
            y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
            tooltip=[
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
                alt.Tooltip('VOTOS_ADORMECIDOS:Q', title='Total Adormecidos', format=','),
                alt.Tooltip('QT_ABSTENCOES:Q', title='Abstenções', format=','),
                alt.Tooltip('QT_VOTOS_BRANCOS:Q', title='Brancos', format=','),
                alt.Tooltip('QT_VOTOS_NULOS:Q', title='Nulos', format=','),
                alt.Tooltip('QT_APTOS:Q', title='Total de Aptos', format=',')
            ]
        ).properties(height=altura_ador)
        st.altair_chart(grafico_ador, use_container_width=True)

        st.markdown("#### 📋 Detalhamento dos Votos Perdidos")
        tabela_ador = ador_top[['NM_LOCAL_VOTACAO', 'VOTOS_ADORMECIDOS', 'QT_ABSTENCOES', 'QT_VOTOS_BRANCOS', 'QT_VOTOS_NULOS', 'QT_APTOS']]
        tabela_ador.columns = ['Local de Votação', 'Total Adormecidos (Alvo)', 'Faltaram (Abstenção)', 'Brancos', 'Nulos', 'Eleitores Aptos']
        st.dataframe(tabela_ador, use_container_width=True)


# ==========================================
# ROTA 4: RAIO-X DA CONCORRÊNCIA
# ==========================================
elif menu_selecionado == "⚔️ 4. Raio-X da Concorrência":
    st.title(f"⚔️ Raio-X da Concorrência (Mapeamento de Adversários) - {label_periodo}")

    st.info("""
    **💡 Fundamentação Estratégica: O Índice de Fragmentação e Concentração de Mercado (HHI)**
    
    Avançar em territórios sem mapear o grau de monopolização dos votos é uma falha tática gravíssima. Este painel permite analisar o *Market Share* dos concorrentes através do conceito de Índice de Herfindahl-Hirschman (HHI) adaptado à realidade eleitoral.
    
    Entrar em uma escola onde um único "cacique" local domina 80% dos votos exige um esforço colossal de enfrentamento e desconstrução. Por outro lado, territórios com "Alta Fragmentação" — onde os votos estão diluídos entre dezenas de candidatos periféricos — são terrenos altamente vulneráveis e receptivos à infiltração de uma nova liderança. Use este mapa para escolher as batalhas de menor atrito e maior rentabilidade.
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
        escola_alvo = st.selectbox("🎯 Selecione a Escola para Analisar os Adversários (Oceano Azul):", escolas_conc)

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

            st.markdown(f"#### 📊 Donos do Território em: **{escola_alvo}**")

            col1, col2 = st.columns(2)
            col1.metric("Principal Adversário", top_1['NM_VOTAVEL'])
            col2.metric("Domínio do Líder", f"{top_1['Share (%)']:.1f}%")

            st.markdown("---")

            adversarios_grafico = adversarios.head(20) 
            altura_adv = max(500, len(adversarios_grafico) * 35)

            grafico_adv = alt.Chart(adversarios_grafico).mark_bar(color="#FFC107").encode(
                x=alt.X('QT_VOTOS:Q', title='Votos Conquistados pelo Adversário', axis=alt.Axis(format='d')),
                y=alt.Y('NM_VOTAVEL:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                tooltip=[
                    alt.Tooltip('NM_VOTAVEL:N', title='Candidato'),
                    alt.Tooltip('QT_VOTOS:Q', title='Votos', format=','),
                    alt.Tooltip('Share (%):Q', title='% de Domínio', format='.1f')
                ]
            ).properties(height=altura_adv)
            st.altair_chart(grafico_adv, use_container_width=True)

            st.markdown("#### 📋 Detalhamento da Tropa Inimiga")
            tabela_adv = adversarios[['NM_VOTAVEL', 'QT_VOTOS', 'Share (%)']]
            tabela_adv.columns = ['Nome do Adversário', 'Votos na Escola', 'Fatia de Domínio (%)']
            tabela_adv['Fatia de Domínio (%)'] = tabela_adv['Fatia de Domínio (%)'].round(2).astype(str) + '%'
            st.dataframe(tabela_adv.head(50), use_container_width=True)
        else:
            st.warning("Não há dados de concorrência suficientes para esta escola/cargo nos filtros selecionados.")


# ==========================================
# ROTA 5: ANÁLISE DE VOTOS CASADOS
# ==========================================
elif menu_selecionado == "🔗 5. Análise de Votos Casados":
    st.title(f"🔗 Análise de Voto Casado (Matriz de Correlação) - {label_periodo}")

    st.info("""
    **💡 Fundamentação Estratégica: Coeficiente de Correlação de Pearson e Simbiose Eleitoral**
    
    A política de alianças baseada em instinto é ineficiente. Este painel utiliza o *Coeficiente de Correlação de Pearson (r)* aplicado à variância de votos urna por urna para medir a força da "simbiose eleitoral" entre dois candidatos. Quando a curva de votos do candidato central sobe em uma determinada seção eleitoral, a curva de qual outro candidato sobe simultaneamente?
    
    Um índice próximo a +1.0 indica uma transferência de votos (voto casado) quase perfeita. Com este dado matemático em mãos, negociações institucionais para formações de chapas, dobradinhas não oficiais ou rateio de fundos partidários deixam de ser baseadas em promessas e passam a ser balizadas por comportamento empírico do eleitorado.
    """)

    if dados_concorrencia.empty or ano_selecionado == 'Todos os Anos (Série Histórica)':
        st.warning("⚠️ Para calcular o Voto Casado com precisão matemática, selecione um **Ano Específico** no filtro lateral (ex: 2022 ou 2024). O cálculo histórico distorce a variância devido às mudanças de cargo.")
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
                corr_samir.columns = ['Candidato Parceiro', 'Índice de Correlação (r)']

                corr_samir = corr_samir[corr_samir['Índice de Correlação (r)'] > 0.1]
                corr_samir = corr_samir[~corr_samir['Candidato Parceiro'].str.contains("SAMIR", case=False, na=False)]
                corr_samir = corr_samir.sort_values(by='Índice de Correlação (r)', ascending=False).head(limite_ranking)

                if corr_samir.empty:
                    st.warning("Não foi detectada nenhuma correlação matemática positiva forte com os candidatos deste cargo.")
                else:
                    st.markdown(f"#### 🧬 Ranking de Dobradinhas Orgânicas (Cargo: {cargo_alvo})")

                    top_1_corr = corr_samir.iloc[0]
                    st.success(f"**Principal Simbiose:** Matematicamente, a curva de crescimento de votos mais parecida com a sua pertence a **{top_1_corr['Candidato Parceiro']}** (Índice r = {top_1_corr['Índice de Correlação (r)']:.2f}). Seus eleitores estão depositando forte confiança neste perfil.")

                    altura_corr = max(500, len(corr_samir) * 35)

                    grafico_corr = alt.Chart(corr_samir).mark_bar(color="#25D366").encode(
                        x=alt.X('Índice de Correlação (r):Q', title='Força do Voto Casado (0 = Neutro, 1 = Perfeito)', scale=alt.Scale(domain=[0, 1])),
                        y=alt.Y('Candidato Parceiro:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
                        tooltip=[
                            alt.Tooltip('Candidato Parceiro:N', title='Candidato'),
                            alt.Tooltip('Índice de Correlação (r):Q', title='Índice Pearson', format='.2f')
                        ]
                    ).properties(height=altura_corr)
                    st.altair_chart(grafico_corr, use_container_width=True)

                    corr_samir['Índice de Correlação (r)'] = corr_samir['Índice de Correlação (r)'].round(3)
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
        [int(a) for a in locais_tse_rural['ANO_ELEICAO'].dropna().unique()],
        reverse=True
    )
    if ano_selecionado == 'Todos os Anos (Série Histórica)':
        ano_rural = anos_tse[0]
        st.caption(
            f"Visão principal em {ano_rural}, o ano mais recente disponível. "
            "A série histórica aparece mais abaixo."
        )
    else:
        ano_rural = int(ano_selecionado)

    incluir_revisao = st.checkbox(
        "Incluir locais pendentes de revisão no mapa, resumo e ranking",
        value=False,
        help=(
            "Os indicadores do cabeçalho permanecem restritos aos locais rurais "
            "confirmados."
        )
    )

    locais_ano = locais_tse_rural[
        locais_tse_rural['ANO_ELEICAO'] == ano_rural
    ].copy()
    if col_municipio and municipios_selecionados:
        locais_ano = locais_ano[
            locais_ano['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]

    colunas_local = [
        'ID_LOCAL_ANO', 'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA',
        'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'DS_ENDERECO',
        'CLASSIFICACAO_RURAL', 'FONTE_CLASSIFICACAO_RURAL',
        'CONFIANCA_CLASSIFICACAO', 'OBSERVACAO_CLASSIFICACAO'
    ]
    locais_resumo = locais_ano.groupby(
        colunas_local, as_index=False, dropna=False
    ).agg(
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
    votos_ano = votos_completos[
        votos_completos['ANO_ELEICAO'] == ano_rural
    ].copy()

    mapa_secao = locais_ano[[
        'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'ID_LOCAL_ANO'
    ]].drop_duplicates()
    votos_ano = pd.merge(
        votos_ano,
        mapa_secao,
        on=['ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
        how='inner'
    )
    votos_por_local = votos_ano.groupby(
        'ID_LOCAL_ANO', as_index=False
    ).agg(
        QT_VOTOS_SAMIR=('QT_VOTOS_SAMIR', 'sum'),
        QT_VOTOS_VALIDOS_SECAO=('QT_VOTOS_VALIDOS_SECAO', 'sum')
    )

    base_rural = pd.merge(
        locais_analise, votos_por_local, on='ID_LOCAL_ANO', how='left'
    )
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
    m1.metric("Locais Examinados", f"{len(locais_resumo):,}".replace(',', '.'))
    m2.metric("Rurais Confirmados", f"{len(rurais_confirmados):,}".replace(',', '.'))
    m3.metric("Seções Rurais", f"{int(rurais_confirmados['QT_SECOES'].sum()):,}".replace(',', '.'))
    m4.metric("Eleitores Rurais", f"{int(eleitorado_rural):,}".replace(',', '.'))

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Votos Históricos do Candidato", f"{int(total_votos_samir):,}".replace(',', '.'))
    m6.metric("Votos Válidos Rurais", f"{int(total_validos_rural):,}".replace(',', '.'))
    m7.metric("Demais Votos Válidos", f"{int(demais_validos_rural):,}".replace(',', '.'))
    m8.metric("Participação nos Válidos", f"{participacao_rural:.2f}%")
    st.caption(
        f"Os locais rurais representam {pct_eleitorado_rural:.1f}% do eleitorado "
        "da seleção atual. 'Demais votos válidos' é uma medida histórica e não "
        "significa que esses votos estejam automaticamente disponíveis."
    )

    if incluir_revisao:
        st.warning(
            "Mapa, resumo municipal e ranking incluem pendências. Os indicadores "
            "do cabeçalho continuam usando somente rurais confirmados."
        )

    st.markdown("---")
    st.subheader("📍 Mapa dos Locais Rurais")
    mapa_rural = base_rural.dropna(subset=['lat', 'lon'])
    if not mapa_rural.empty:
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
        VOTOS_VALIDOS=('QT_VOTOS_VALIDOS_SECAO', 'sum')
    )
    resumo_municipal['PARTICIPACAO_VALIDOS_PCT'] = np.where(
        resumo_municipal['VOTOS_VALIDOS'] > 0,
        resumo_municipal['VOTOS_SAMIR'] /
        resumo_municipal['VOTOS_VALIDOS'] * 100,
        0
    )
    eleitorado_total_municipio = locais_resumo.groupby(
        'NM_MUNICIPIO', as_index=False
    )['QT_ELEITORES'].sum().rename(
        columns={'QT_ELEITORES': 'ELEITORADO_TOTAL_MUNICIPIO'}
    )
    resumo_municipal = pd.merge(
        resumo_municipal,
        eleitorado_total_municipio,
        on='NM_MUNICIPIO',
        how='left'
    )
    resumo_municipal['ELEITORADO_RURAL_PCT'] = np.where(
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] > 0,
        resumo_municipal['ELEITORES'] /
        resumo_municipal['ELEITORADO_TOTAL_MUNICIPIO'] * 100,
        0
    )
    resumo_municipal = resumo_municipal.sort_values(
        'ELEITORES', ascending=False
    ).rename(columns={
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
    st.dataframe(
        resumo_municipal[[
            'Município', 'Locais', 'Seções', 'Eleitores Rurais',
            'Eleitorado Rural no Município (%)', 'Votos do Candidato',
            'Votos Válidos', 'Participação nos Válidos (%)'
        ]],
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("📋 Desempenho Histórico por Local Rural")
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
        grafico_rural = alt.Chart(ranking_rural).mark_bar(
            color="#28A745"
        ).encode(
            x=alt.X(f'{coluna_ranking}:Q', title=criterio_rural),
            y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x'),
            tooltip=[
                alt.Tooltip('NM_MUNICIPIO:N', title='Município'),
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
                alt.Tooltip('QT_ELEITORES:Q', title='Eleitores', format=','),
                alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos', format=','),
                alt.Tooltip('QT_VOTOS_VALIDOS_SECAO:Q', title='Válidos', format=','),
                alt.Tooltip('PARTICIPACAO_VALIDOS:Q', title='Participação (%)', format='.2f'),
                alt.Tooltip('CLASSIFICACAO_RURAL:N', title='Classificação')
            ]
        ).properties(height=max(450, len(ranking_rural) * 34))
        st.altair_chart(grafico_rural, use_container_width=True)

        tabela_ranking = ranking_rural[[
            'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
            'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'QT_SECOES', 'QT_ELEITORES',
            'QT_VOTOS_SAMIR', 'QT_VOTOS_VALIDOS_SECAO',
            'PARTICIPACAO_VALIDOS', 'CLASSIFICACAO_RURAL',
            'CONFIANCA_CLASSIFICACAO'
        ]].copy()
        tabela_ranking.columns = [
            'Município', 'Zona', 'Nº Local', 'Local de Votação', 'Bairro',
            'Seções', 'Eleitores', 'Votos do Candidato', 'Votos Válidos',
            'Participação nos Válidos (%)', 'Classificação', 'Confiança'
        ]
        tabela_ranking['Participação nos Válidos (%)'] = tabela_ranking[
            'Participação nos Válidos (%)'
        ].round(2)
        st.dataframe(tabela_ranking, use_container_width=True)
    else:
        st.info("Nenhum local rural encontrado para os filtros selecionados.")

    st.markdown("---")
    st.subheader("📈 Evolução Histórica Rural")
    locais_hist = locais_tse_rural.copy()
    votos_hist = carregar_dados()
    if col_municipio and municipios_selecionados:
        locais_hist = locais_hist[
            locais_hist['NM_MUNICIPIO'].isin(municipios_selecionados)
        ]
        votos_hist = votos_hist[
            votos_hist[col_municipio].isin(municipios_selecionados)
        ]

    mapa_hist_secao = locais_hist[[
        'ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO',
        'ID_LOCAL_ANO', 'CLASSIFICACAO_RURAL'
    ]].drop_duplicates()
    votos_hist = pd.merge(
        votos_hist,
        mapa_hist_secao,
        on=['ANO_ELEICAO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'],
        how='inner'
    )
    votos_hist = votos_hist[
        votos_hist['CLASSIFICACAO_RURAL'] == 'RURAL'
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
        st.altair_chart(grafico_evolucao_rural, use_container_width=True)
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
    q2.metric("Locais Pendentes de Revisão", len(locais_revisar))
    q3.metric(
        "Locais sem Coordenada",
        int(locais_resumo[['lat', 'lon']].isna().any(axis=1).sum())
    )

    if not locais_revisar.empty:
        tabela_revisao = locais_revisar[[
            'ID_LOCAL_ANO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_LOCAL_VOTACAO',
            'NM_LOCAL_VOTACAO', 'NM_BAIRRO', 'DS_ENDERECO', 'QT_ELEITORES',
            'FONTE_CLASSIFICACAO_RURAL', 'CONFIANCA_CLASSIFICACAO'
        ]].copy()
        tabela_revisao.columns = [
            'ID Local/Ano', 'Município', 'Zona', 'Nº Local',
            'Local de Votação', 'Bairro', 'Endereço', 'Eleitores',
            'Motivo', 'Confiança'
        ]
        st.dataframe(tabela_revisao, use_container_width=True)
        st.download_button(
            "Baixar lista de locais pendentes",
            data=tabela_revisao.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"locais_rurais_revisar_{ano_rural}.csv",
            mime="text/csv"
        )
