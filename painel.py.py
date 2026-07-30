import streamlit as st
import pandas as pd
import numpy as np

# 1. Configuração da Página em Modo Largo (Widescreen)
st.set_page_config(page_title="Monitor Estratégico de Campanha", page_icon="🎯", layout="wide")
st.title("🎯 Painel Estratégico de Campanha - Sala de Guerra")
st.markdown("---")

# 2. Carregamento dos Dados com Cache e Geolocalização Única por Escola
@st.cache_data
def carregar_dados():
    df = pd.read_csv("dados.csv")
    
    centros_acre = {
        'RIO BRANCO': (-9.9749, -67.8243),
        'SENA MADUREIRA': (-9.3356, -68.6558),
        'TARAUACA': (-8.1578, -70.8675),
        'XAPURI': (-10.6514, -68.5078),
        'PORTO ACRE': (-9.5847, -67.5342),
        'SENADOR GUIOMARD': (-10.1503, -67.7408),
        'PLACIDO DE CASTRO': (-10.2742, -67.1908),
        'RODRIGUES ALVES': (-7.7428, -72.6506),
        'SANTA ROSA DO PURUS': (-9.4353, -70.4903),
        'CRUZEIRO DO SUL': (-7.6311, -72.6756),
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
            
            escola_coords[esc] = (
                center_lat + np.random.normal(0, 0.03),
                center_lon + np.random.normal(0, 0.03)
            )
            
        df['lat'] = df['NM_LOCAL_VOTACAO'].map(lambda x: escola_coords[x][0])
        df['lon'] = df['NM_LOCAL_VOTACAO'].map(lambda x: escola_coords[x][1])
    else:
        df['lat'] = df['lat'].fillna(-9.9749)
        df['lon'] = df['lon'].fillna(-67.8243)
        
    return df

try:
    dados = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar o arquivo 'dados.csv'. Detalhe: {e}")
    st.stop()

# 3. Barra Lateral (Filtros Mestres)
st.sidebar.header("🎛️ Filtros de Controle Estratégico")

anos_disponiveis = sorted(dados['ANO_ELEICAO'].unique(), reverse=True)
opcoes_ano = ['Todos os Anos (Série Histórica)'] + [str(a) for a in anos_disponiveis]
ano_selecionado = st.sidebar.selectbox("Selecione o Período / Ano:", opcoes_ano)

col_municipio = None
for col in ['NM_MUNICIPIO', 'MUNICIPIO', 'Cidade', 'cidade']:
    if col in dados.columns:
        col_municipio = col
        break

if col_municipio:
    municipios_disponiveis = sorted(dados[col_municipio].dropna().unique())
    municipios_selecionados = st.sidebar.multiselect("Filtrar por Município(s):", municipios_disponiveis, default=municipios_disponiveis)
    dados = dados[dados[col_municipio].isin(municipios_selecionados)]

limite_ranking = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5)

if ano_selecionado == 'Todos os Anos (Série Histórica)':
    dados_filtrados = dados.copy()
    label_periodo = "Série Histórica Acumulada"
else:
    dados_filtrados = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()
    label_periodo = f"Ano de {ano_selecionado}"

# 4. Cartões de Métricas Executivas
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

col1, col2, col3 = st.columns(3)
col1.metric(label=f"Total de Votos ({label_periodo})", value=f"{total_votos:,}".replace(",", "."))
col2.metric(label="Locais de Votação Mapeados", value=total_escolas)

if not dados_filtrados.empty:
    escolas_ranking = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().sort_values(ascending=False)
    top_20_porcento = max(1, int(len(escolas_ranking) * 0.2))
    votos_top_20 = escolas_ranking.head(top_20_porcento).sum()
    pct_pareto = (votos_top_20 / total_votos * 100) if total_votos > 0 else 0
    col3.metric(label="Concentração (Regra de Pareto)", value=f"{pct_pareto:.1f}%", help="Percentual de votos concentrados nos 20% principais redutos.")
else:
    col3.metric(label="Concentração (Regra de Pareto)", value="0%")

st.markdown("---")

# ======== ANÁLISE 1: MAPA LIMPO (PONTOS PRECISOS POR ESCOLA) ========
st.subheader(f"📍 Mapa de Distribuição Geográfica ({label_periodo})")

group_cols = ['NM_LOCAL_VOTACAO', 'lat', 'lon']
if col_municipio:
    group_cols.append(col_municipio)

dados_mapa = dados_filtrados.groupby(group_cols, as_index=False)['QT_VOTOS_SAMIR'].sum()
dados_mapa = dados_mapa.dropna(subset=['lat', 'lon'])

if not dados_mapa.empty:
    # Removemos o parâmetro 'size' para exibir marcadores limpios e elegantes
    st.map(dados_mapa, latitude='lat', longitude='lon')
else:
    st.info("Nenhum dado geográfico disponível para os filtros selecionados.")

st.markdown("---")

# ======== ANÁLISE 2: RAIO-X COM GRÁFICO E MARKET SHARE ========
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

st.markdown(f"#### 📉 Gráfico de Desempenho (Top {limite_ranking} Redutos)")
chart_data = top_escolas.set_index('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR']
st.bar_chart(chart_data)

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
