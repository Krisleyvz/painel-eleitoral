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
        
        planilha_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
        aba_logs = cliente.open_by_key(planilha_id).worksheet("Logs_Acesso")
        aba_logs.append_row([usuario, data_formatada, hora_formatada])
        
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

col_logo1, col_logo2, col_logo3 = st.columns([3, 2, 3])
with col_logo2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.markdown("<h3 style='text-align: center;'>🎯 Painel Estratégico</h3>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# CARREGAMENTO DOS DADOS E INTEGRAÇÃO DE ZONAS E TSE
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

def aplicar_base_tse(df_principal):
    try:
        arquivo_tse = None
        for f in os.listdir('.'):
            if f.startswith('tse_locais_acre'):
                arquivo_tse = f
                break

        if arquivo_tse and os.path.exists(arquivo_tse):
            # Leitor inteligente que detecta se é Excel (.xlsx) ou CSV
            if arquivo_tse.endswith('.xlsx') or 'xlsx' in arquivo_tse:
                df_tse = pd.read_excel(arquivo_tse)
            else:
                try:
                    df_tse = pd.read_csv(arquivo_tse, sep=';', encoding='utf-8', low_memory=False)
                except:
                    try:
                        df_tse = pd.read_csv(arquivo_tse, sep=',', encoding='utf-8', low_memory=False)
                    except:
                        df_tse = pd.read_csv(arquivo_tse, sep=';', encoding='latin1', low_memory=False)

            df_tse['NM_LOCAL_VOTACAO'] = df_tse['NM_LOCAL_VOTACAO'].str.strip().str.upper()
            df_principal['NM_LOCAL_VOTACAO'] = df_principal['NM_LOCAL_VOTACAO'].str.strip().str.upper()

            bairros_rurais = ['ZONA RURAL', 'AREA RURAL', 'PROJETO DE ASSENTAMENTO', 'POLO AGROFLORESTAL', 'COMUNIDADE RURAL']
            df_tse['TIPO_ZONA_OFICIAL'] = 'URBANA'
            
            if 'NM_BAIRRO' in df_tse.columns:
                df_tse['NM_BAIRRO'] = df_tse['NM_BAIRRO'].astype(str).str.upper()
                df_tse.loc[df_tse['NM_BAIRRO'].isin(bairros_rurais), 'TIPO_ZONA_OFICIAL'] = 'RURAL'
                
            tse_agrupado = df_tse.groupby(['NM_LOCAL_VOTACAO', 'TIPO_ZONA_OFICIAL'], as_index=False)['QT_ELEITOR_SECAO'].sum()
            tse_agrupado.rename(columns={'QT_ELEITOR_SECAO': 'TOTAL_APTOS_TSE'}, inplace=True)

            df_cruzado = pd.merge(df_principal, tse_agrupado, on='NM_LOCAL_VOTACAO', how='right')
            df_cruzado['QT_VOTOS_SAMIR'] = df_cruzado['QT_VOTOS_SAMIR'].fillna(0)
            df_cruzado['ANO_ELEICAO'] = df_cruzado['ANO_ELEICAO'].fillna(2020)
            df_cruzado['TIPO_ZONA'] = df_cruzado['TIPO_ZONA_OFICIAL']
            
            return df_cruzado
        else:
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
            df_principal['TIPO_ZONA'] = np.where(df_principal['NM_LOCAL_VOTACAO'].isin(escolas_rurais), 'RURAL', 'URBANA')
            df_principal['TOTAL_APTOS_TSE'] = 0
            return df_principal
    except Exception as e:
        df_principal['TIPO_ZONA'] = 'URBANA'
        df_principal['TOTAL_APTOS_TSE'] = 0
        return df_principal

try:
    dados = carregar_dados()
    dados = aplicar_base_tse(dados)
except:
    st.error("Erro ao carregar os arquivos base.")
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
        "🚜 6. Análise Campo vs. Cidade",
        "🗺️ 7. Territórios Inexplorados"
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

# ==========================================
# ROTA 2: PERFIL ESTIMADO DO ELEITOR
# ==========================================
elif menu_selecionado == "👥 2. Perfil Estimado do Eleitor":
    st.title(f"👥 Perfil Estimado do Eleitor (Samir Bestene) - {label_periodo}")
    if dados_demo.empty:
        st.info("⚠️ A base 'base_demografica_ac.zip' não foi encontrada.")
    else:
        st.write("Dados demográficos carregados com sucesso.")

# ==========================================
# ROTA 3: MAPA DE VOTOS ADORMECIDOS
# ==========================================
elif menu_selecionado == "🗺️ 3. Mapa de Votos Adormecidos":
    st.title(f"🗺️ Mapa de Votos Adormecidos (Abstenções, Brancos e Nulos) - {label_periodo}")
    if dados_adormecidos.empty:
        st.info("⚠️ A base 'base_adormecidos_ac.csv' não foi encontrada.")

# ==========================================
# ROTA 4: RAIO-X DA CONCORRÊNCIA
# ==========================================
elif menu_selecionado == "⚔️ 4. Raio-X da Concorrência":
    st.title(f"⚔️ Raio-X da Concorrência (Mapeamento de Adversários) - {label_periodo}")
    if dados_concorrencia.empty:
        st.info("⚠️ A base 'base_concorrencia_ac.zip' não foi encontrada.")

# ==========================================
# ROTA 5: ANÁLISE DE VOTOS CASADOS
# ==========================================
elif menu_selecionado == "🔗 5. Análise de Votos Casados":
    st.title(f"🔗 Análise de Voto Casado (Matriz de Correlação) - {label_periodo}")

# ==========================================
# ROTA 6: EVOLUÇÃO CAMPO VS. CIDADE
# ==========================================
elif menu_selecionado == "🚜 6. Análise Campo vs. Cidade":
    st.title("🚜 Análise Comparativa: Zona Rural vs. Zona Urbana")
    if not dados.empty and 'TIPO_ZONA' in dados.columns:
        total_rural = dados[dados['TIPO_ZONA'] == 'RURAL']['QT_VOTOS_SAMIR'].sum() if 'QT_VOTOS_SAMIR' in dados.columns else 0
        total_urbano = dados[dados['TIPO_ZONA'] == 'URBANA']['QT_VOTOS_SAMIR'].sum() if 'QT_VOTOS_SAMIR' in dados.columns else 0
        st.metric("Votos na Zona Urbana", f"{int(total_urbano):,}".replace(',', '.'))
        st.metric("Votos na Zona Rural", f"{int(total_rural):,}".replace(',', '.'))

# ==========================================
# ROTA 7: TERRITÓRIOS INEXPLORADOS (Oceano Azul)
# ==========================================
elif menu_selecionado == "🗺️ 7. Territórios Inexplorados":
    st.title("🗺️ Mapa do Oceano Azul: Territórios Inexplorados")
    
    st.info("""
    **💡 Fundamentação Estratégica: O Verdadeiro Tamanho do Mercado**
    Esta análise cruza o seu histórico de votos com a base oficial do TSE de todos os colégios eleitorais do Acre. 
    Aqui revelamos as escolas onde existem milhares de eleitores aptos a votar, mas onde a campanha possui "Pontos Cegos" (zero ou pouquíssimos votos registrados).
    """)

    if 'TOTAL_APTOS_TSE' not in dados.columns or dados['TOTAL_APTOS_TSE'].sum() == 0:
        st.warning("⚠️ Os dados do TSE não foram carregados corretamente. Verifique se o arquivo está na pasta.")
    else:
        ano_analise = int(ano_selecionado) if ano_selecionado != 'Todos os Anos (Série Histórica)' else dados['ANO_ELEICAO'].max()
        df_oportunidade = dados[dados['ANO_ELEICAO'] == ano_analise].groupby(['NM_LOCAL_VOTACAO', 'TIPO_ZONA'], as_index=False).agg({
            'TOTAL_APTOS_TSE': 'max',
            'QT_VOTOS_SAMIR': 'sum'
        })
        
        df_oportunidade['MARGEM_CRESCIMENTO'] = df_oportunidade['TOTAL_APTOS_TSE'] - df_oportunidade['QT_VOTOS_SAMIR']
        
        locais_cegos = df_oportunidade[(df_oportunidade['QT_VOTOS_SAMIR'] < 10) & (df_oportunidade['MARGEM_CRESCIMENTO'] > 0)]
        locais_cegos = locais_cegos.sort_values(by='MARGEM_CRESCIMENTO', ascending=False).head(limite_ranking)

        col1, col2 = st.columns(2)
        col1.metric("Escolas Inexploradas Mapeadas", len(df_oportunidade[df_oportunidade['QT_VOTOS_SAMIR'] == 0]))
        col2.metric("Eleitores Soltos Nessas Áreas", f"{int(locais_cegos['MARGEM_CRESCIMENTO'].sum()):,} ({texto_local})".replace(',', '.'))

        st.markdown("---")
        st.subheader("🔥 Top Escolas com Zero Presença (Maior Margem de Expansão)")

        grafico_cegos = alt.Chart(locais_cegos).mark_bar(color="#00BCD4").encode(
            x=alt.X('MARGEM_CRESCIMENTO:Q', title='Eleitores Disponíveis', axis=alt.Axis(format='d')),
            y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x', axis=alt.Axis(labelLimit=1000)),
            tooltip=[
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
                alt.Tooltip('TIPO_ZONA:N', title='Território'),
                alt.Tooltip('TOTAL_APTOS_TSE:Q', title='Eleitores no Local', format=','),
                alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Seus Votos Atuais', format=',')
            ]
        ).properties(height=max(400, len(locais_cegos) * 35))
        st.altair_chart(grafico_cegos, use_container_width=True)

        tabela_cega = locais_cegos[['NM_LOCAL_VOTACAO', 'TIPO_ZONA', 'TOTAL_APTOS_TSE', 'QT_VOTOS_SAMIR', 'MARGEM_CRESCIMENTO']]
        tabela_cega.columns = ['Local de Votação', 'Zona', 'Eleitores do TSE', 'Seus Votos', '🔥 Potencial de Crescimento']
        st.dataframe(tabela_cega, use_container_width=True)
