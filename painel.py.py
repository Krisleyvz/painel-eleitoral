import streamlit as st
import pandas as pd

# Conectando a sua planilha (cole o link CSV aqui dentro das aspas)
url_planilha = "dados.csv"
dados = pd.read_csv(url_planilha)

# Construindo a Tela
st.title("Painel Eleitoral - Samir")

# Filtro interativo
ano_selecionado = st.sidebar.selectbox("Filtre o Ano:", dados['ANO_ELEICAO'].unique())
dados_filtrados = dados[dados['ANO_ELEICAO'] == ano_selecionado]
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()

# Resultados
st.metric(label=f"Total de Votos em {ano_selecionado}", value=f"{total_votos} votos")

st.subheader("Raio-X das Escolas (Top 10)")
top_escolas = dados_filtrados[['NM_LOCAL_VOTACAO', 'QT_VOTOS_SAMIR']].sort_values(by='QT_VOTOS_SAMIR', ascending=False).head(10)
st.dataframe(top_escolas)