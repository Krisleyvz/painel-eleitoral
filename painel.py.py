import streamlit as st
import pandas as pd

# 1. Configuração Inicial da Página
st.set_page_config(page_title="Painel Eleitoral - Estratégico", layout="wide")

st.title("🎯 Painel Estratégico de Campanha")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    return pd.read_csv("dados.csv")

dados = carregar_dados()

# 3. Barra Lateral (Filtros)
st.sidebar.header("Filtros de Análise")
ano_selecionado = st.sidebar.selectbox("Selecione o Ano:", sorted(dados['ANO_ELEICAO'].unique(), reverse=True))

dados_filtrados = dados[dados['ANO_ELEICAO'] == ano_selecionado].copy()

# 4. Métricas Principais no Topo
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

col1, col2 = st.columns(2)
col1.metric(label=f"Total de Votos em {ano_selecionado}", value=f"{total_votos:,}".replace(",", "."))
col2.metric(label="Locais de Votação Mapeados", value=total_escolas)

st.markdown("---")

# 5. Cálculo de Market Share (Eficiência por Seção)
# Verifica se a coluna de votos válidos existe na base para calcular a dominância
if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    dados_filtrados['MARKET_SHARE'] = (dados_filtrados['QT_VOTOS_SAMIR'] / dados_filtrados['QT_VOTOS_VALIDOS_SECAO']) * 100
    dados_filtrados['MARKET_SHARE'] = dados_filtrados['MARKET_SHARE'].fillna(0).round(1)
else:
    dados_filtrados['MARKET_SHARE'] = 0.0

# 6. Raio-X Detalhado das Escolas
st.subheader("📊 Raio-X e Dominância por Escola (Top 10)")

# Seleciona as colunas de exibição de forma segura
colunas_exibir = ['NM_LOCAL_VOTACAO', 'QT_VOTOS_SAMIR']
if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    colunas_exibir.append('QT_VOTOS_VALIDOS_SECAO')
colunas_exibir.append('MARKET_SHARE')

top_escolas = dados_filtrados[colunas_exibir].sort_values(by='QT_VOTOS_SAMIR', ascending=False).head(10)

# Renomeia para ficar com visual executivo/profissional
top_escolas.columns = [col.replace('NM_LOCAL_VOTACAO', 'Local de Votação')
                          .replace('QT_VOTOS_SAMIR', 'Votos Obtidos')
                          .replace('QT_VOTOS_VALIDOS_SECAO', 'Votos Válidos Seção')
                          .replace('MARKET_SHARE', 'Market Share (%)') for col in top_escolas.columns]

st.dataframe(top_escolas, use_container_width=True)