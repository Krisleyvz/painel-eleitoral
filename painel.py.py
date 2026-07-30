import streamlit as st
import pandas as pd

# 1. Configuração da Página em Modo Largo (Widescreen)
st.set_page_config(page_title="Painel Estratégico de Campanha", layout="wide")

st.title("🎯 Painel Estratégico de Campanha - Sala de Guerra")
st.markdown("---")

# 2. Carregamento dos Dados com Cache
@st.cache_data
def carregar_dados():
    return pd.read_csv("dados.csv")

try:
    dados = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar o arquivo 'dados.csv'. Certifique-se de que ele está na mesma pasta. Detalhe: {e}")
    st.stop()

# 3. Barra Lateral (Filtros Mestres)
st.sidebar.header("🎛️ Filtros de Controle")
anos_disponiveis = sorted(dados['ANO_ELEICAO'].unique(), reverse=True)
ano_selecionado = st.sidebar.selectbox("Selecione o Ano de Referência:", anos_disponiveis)

# Filtragem de dados do ano escolhido
dados_filtrados = dados[dados['ANO_ELEICAO'] == ano_selecionado].copy()

# 4. Cartões de Métricas Executivas no Topo
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

col1, col2, col3 = st.columns(3)
col1.metric(label=f"Total de Votos ({ano_selecionado})", value=f"{total_votos:,}".replace(",", "."))
col2.metric(label="Locais de Votação Ativos", value=total_escolas)

# Regra de Pareto 80/20 (Calcula a concentração dos votos nas principais escolas)
if not dados_filtrados.empty:
    escolas_ranking = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().sort_values(ascending=False)
    top_20_porcento = max(1, int(len(escolas_ranking) * 0.2))
    votos_top_20 = escolas_ranking.head(top_20_porcento).sum()
    pct_pareto = (votos_top_20 / total_votos * 100) if total_votos > 0 else 0
    col3.metric(label="Concentração (Top 20% Escolas)", value=f"{pct_pareto:.1f}%")
else:
    col3.metric(label="Concentração (Top 20% Escolas)", value="0%")

st.markdown("---")

# ======== ANÁLISE 1: MAPA DE CALOR TERRITORIAL ========
st.subheader("📍 Mapa de Calor - Distribuição Geográfica dos Votos")
if 'lat' in dados_filtrados.columns and 'lon' in dados_filtrados.columns:
    dados_mapa = dados_filtrados.dropna(subset=['lat', 'lon']).copy()
    if not dados_mapa.empty:
        dados_mapa['tamanho_bolha'] = dados_mapa['QT_VOTOS_SAMIR'] * 25
        st.map(dados_mapa, latitude='lat', longitude='lon', size='tamanho_bolha')
    else:
        st.info("Preencha as colunas 'lat' e 'lon' na planilha para visualizar o mapa interativo.")
else:
    st.info("💡 Dica Estratégica: Adicione as colunas 'lat' e 'lon' na sua planilha para acionar o mapa de calor da cidade.")

st.markdown("---")

# ======== ANÁLISE 2: RAIO-X CONSOLIDADO COM MARKET SHARE ========
st.subheader("📊 Raio-X e Dominância por Escola (Top 10 Consolidado)")

agg_dict = {'QT_VOTOS_SAMIR': 'sum'}
if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    agg_dict['QT_VOTOS_VALIDOS_SECAO'] = 'sum'

top_escolas = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg(agg_dict).reset_index()

if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
    top_escolas['MARKET_SHARE'] = (top_escolas['QT_VOTOS_SAMIR'] / top_escolas['QT_VOTOS_VALIDOS_SECAO']) * 100
    top_escolas['MARKET_SHARE'] = top_escolas['MARKET_SHARE'].fillna(0).round(1)
else:
    top_escolas['MARKET_SHARE'] = 0.0

top_escolas = top_escolas.sort_values(by='QT_VOTOS_SAMIR', ascending=False).head(10)

if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Market Share (%)']
else:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Market Share (%)']

st.dataframe(top_escolas, use_container_width=True)

st.markdown("---")

# ======== ANÁLISE 3: MATRIZ DE EVOLUÇÃO E RETENÇÃO TEMPORAL ========
st.subheader("📈 Matriz de Evolução Histórica (Comparativo de Eleições)")
if len(anos_disponiveis) > 1:
    tabela_comparativa = dados.pivot_table(
        index='NM_LOCAL_VOTACAO', 
        columns='ANO_ELEICAO', 
        values='QT_VOTOS_SAMIR', 
        aggfunc='sum'
    ).fillna(0)
    
    ano_recente = anos_disponiveis[0]
    if ano_recente in tabela_comparativa.columns:
        tabela_comparativa = tabela_comparativa.sort_values(by=ano_recente, ascending=False).head(10)
        
    st.dataframe(tabela_comparativa, use_container_width=True)
else:
    st.info("Para ativar a Matriz de Evolução Histórica, garanta que sua planilha possua registros de mais de um ano eleitoral.")