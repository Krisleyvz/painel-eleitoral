import streamlit as st
import pandas as pd

# 1. Configuração da Página em Modo Largo (Widescreen)
st.set_page_config(page_title="Painel Estratégico de Campanha - Sala de Guerra", layout="wide")

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

# 3. Barra Lateral (Filtros Mestres Avançados)
st.sidebar.header("🎛️ Filtros de Controle Estratégico")

# Filtro de Ano / Série Histórica
anos_disponiveis = sorted(dados['ANO_ELEICAO'].unique(), reverse=True)
opcoes_ano = ['Todos os Anos (Série Histórica)'] + [str(a) for a in anos_disponiveis]
ano_selecionado = st.sidebar.selectbox("Selecione o Período / Ano:", opcoes_ano)

# Filtro Dinâmico de Municípios (Se a coluna existir na base)
col_municipio = None
for col in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']:
    if col in dados.columns:
        col_municipio = col
        break

if col_municipio:
    municipios_disponiveis = sorted(dados[col_municipio].dropna().unique())
    municipios_selecionados = st.sidebar.multiselect("Filtrar por Município(s):", municipios_disponiveis, default=municipios_disponiveis)
    dados = dados[dados[col_municipio].isin(municipios_selecionados)]

# Controle de Amplitude do Ranking (Adeus Top 10 fixo)
limite_ranking = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5)

# 4. Filtragem de Dados conforme escolha de Período
if ano_selecionado == 'Todos os Anos (Série Histórica)':
    dados_filtrados = dados.copy()
    label_periodo = "Série Histórica Acumulada"
else:
    dados_filtrados = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()
    label_periodo = f"Ano de {ano_selecionado}"

# 5. Cartões de Métricas Executivas no Topo
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

col1, col2, col3 = st.columns(3)
col1.metric(label=f"Total de Votos ({label_periodo})", value=f"{total_votos:,}".replace(",", "."))
col2.metric(label="Locais de Votação Mapeados", value=total_escolas)

# Regra de Pareto 80/20
if not dados_filtrados.empty:
    escolas_ranking = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().sort_values(ascending=False)
    top_20_porcento = max(1, int(len(escolas_ranking) * 0.2))
    votos_top_20 = escolas_ranking.head(top_20_porcento).sum()
    pct_pareto = (votos_top_20 / total_votos * 100) if total_votos > 0 else 0
    col3.metric(label="Concentração (Regra de Pareto)", value=f"{pct_pareto:.1f}%", help="Percentual de votos concentrados nos 20% principais redutos.")
else:
    col3.metric(label="Concentração (Regra de Pareto)", value="0%")

st.markdown("---")

# ======== ANÁLISE 1: MAPA DE CALOR TERRITORIAL ========
st.subheader(f"📍 Mapa de Calor - Distribuição Geográfica ({label_periodo})")
if 'lat' in dados_filtrados.columns and 'lon' in dados_filtrados.columns:
    dados_mapa = dados_filtrados.dropna(subset=['lat', 'lon']).copy()
    if not dados_mapa.empty:
        dados_mapa['tamanho_bolha'] = dados_mapa['QT_VOTOS_SAMIR'] * 25
        st.map(dados_mapa, latitude='lat', longitude='lon', size='tamanho_bolha')
    else:
        st.info("Preencha as colunas 'lat' e 'lon' na planilha para visualizar o mapa interativo.")
else:
    st.info("💡 Dica Estratégica: Adicione as colunas 'lat' e 'lon' na sua planilha para acionar o mapa de calor.")

st.markdown("---")

# ======== ANÁLISE 2: RAIO-X EXPANDIDO COM GRÁFICO E MARKET SHARE ========
st.subheader(f"📊 Raio-X, Dominância e Desempenho Visual (Top {limite_ranking} - {label_periodo})")

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

# Gráfico de Barras Dinâmico com a amplitude escolhida
st.markdown(f"#### 📉 Gráfico de Desempenho (Top {limite_ranking} Redutos)")
chart_data = top_escolas.set_index('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR']
st.bar_chart(chart_data)

# Ajuste de colunas para exibição na tabela
if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Market Share (%)']
else:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Market Share (%)']

st.markdown("#### 📋 Detalhamento Analítico Completo")
st.dataframe(top_escolas, use_container_width=True)

st.markdown("---")

# ======== ANÁLISE 3: MATRIZ DE EVOLUÇÃO E RETENÇÃO TEMPORAL ========
st.subheader("📈 Matriz de Evolução Histórica (Comparativo entre Eleições)")
if len(anos_disponiveis) > 1:
    tabela_comparativa = dados.pivot_table(
        index='NM_LOCAL_VOTACAO', 
        columns='ANO_ELEICAO', 
        values='QT_VOTOS_SAMIR', 
        aggfunc='sum'
    ).fillna(0)
    
    ano_recente = anos_disponiveis[0]
    if ano_recente in tabela_comparativa.columns:
        tabela_comparativa = tabela_comparativa.sort_values(by=ano_recente, ascending=False).head(limite_ranking)
        
    st.dataframe(tabela_comparativa, use_container_width=True)
else:
    st.info("ℹ️ A base de dados atual possui apenas um ano eleitoral registrado. Assim que houver múltiplos anos, a matriz e os comparativos temporais serão ativados.")