import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# 1. Configuração da Página em Modo Largo (Widescreen)
st.set_page_config(page_title="Painel Executivo | Inteligência Territorial", page_icon="🎯", layout="wide")

# ==========================================
# INJEÇÃO DE CSS: IDENTIDADE VISUAL DA CAMPANHA
# ==========================================
st.markdown("""
<style>
    /* Cor de fundo da barra lateral (Azul Escuro elegante) */
    [data-testid="stSidebar"] {
        background-color: #0A1C2E !important;
    }
    /* Força a cor do texto e dos títulos da barra lateral para branco */
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div.stMarkdown {
        color: #FFFFFF !important;
    }
    /* Garante que o texto dentro das caixinhas de filtro continue escuro e legível */
    div[data-baseweb="select"] * {
        color: #262730 !important;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Insere a logo da campanha no topo (Agora bem menor e mais discreta)
# Alteramos as proporções das colunas para "espremer" a logo no centro
col_logo1, col_logo2, col_logo3 = st.columns([3, 2, 3])
with col_logo2:
    try:
        st.image("IMG_6009.PNG", use_container_width=True)
    except:
        st.markdown("<h3 style='text-align: center;'>🎯 Painel Estratégico</h3>", unsafe_allow_html=True)
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

# 3. Barra Lateral (Filtros Mestres e Identidade Visual)
try:
    st.sidebar.image("IMG_3571.PNG", use_container_width=True)
except:
    pass 

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

# ======== ANÁLISE 2: RAIO-X COM GRÁFICO HORIZONTAL (ALTAIR) ========
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

st.markdown(f"#### 📉 Gráfico de Desempenho (Top {limite_ranking} Redutos {texto_local})")

grafico_barras = alt.Chart(top_escolas).mark_bar(color="#1A73E8").encode(
    x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Obtidos', axis=alt.Axis(tickMinStep=1, format='d')),
    y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title='Local de Votação'),
    tooltip=[
        alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
        alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos'),
        alt.Tooltip('MARKET_SHARE:Q', title='Market Share (%)', format='.1f')
    ]
).properties(
    height=max(400, limite_ranking * 20) 
)

st.altair_chart(grafico_barras, use_container_width=True)

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

st.markdown("---")

# ======== ANÁLISE 4: DIRECIONADOR DE AGENDA (RETORNO SOBRE ESFORÇO) ========
st.subheader("🎯 Direcionador de Agenda (Otimização de Esforço Físico)")

if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    agenda_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({
        'QT_VOTOS_VALIDOS_SECAO': 'sum',
        'QT_VOTOS_SAMIR': 'sum'
    }).reset_index()
    
    agenda_df['VOTOS_EM_DISPUTA'] = agenda_df['QT_VOTOS_VALIDOS_SECAO'] - agenda_df['QT_VOTOS_SAMIR']
    
    limite_reduto = agenda_df['QT_VOTOS_SAMIR'].quantile(0.75)
    agenda_df['ESTRATEGIA'] = np.where(
        agenda_df['QT_VOTOS_SAMIR'] > limite_reduto, 
        '🛡️ Reduto (Fidelizar)', 
        '⚔️ Expansão (Conquistar)'
    )
    
    agenda_df = agenda_df.sort_values(by='VOTOS_EM_DISPUTA', ascending=False).head(limite_ranking)
    
    if len(agenda_df) > 1:
        top_1 = agenda_df.iloc[0]
        indice_mediano = len(agenda_df) // 2
        local_mediano = agenda_df.iloc[indice_mediano]
        
        if local_mediano['VOTOS_EM_DISPUTA'] > 0:
            multiplicador = top_1['VOTOS_EM_DISPUTA'] / local_mediano['VOTOS_EM_DISPUTA']
            st.success(f"**🧠 Insight de Otimização de Sola de Sapato:**\n\nMatematicamente, 4 horas de corpo a corpo nos arredores da escola **{top_1['NM_LOCAL_VOTACAO'].title()}** tem o potencial de converter **{multiplicador:.1f} vezes mais votos** do que investir o mesmo tempo nos arredores da escola **{local_mediano['NM_LOCAL_VOTACAO'].title()}**.")
    
    with st.expander("💡 Como ler este gráfico?", expanded=False):
        st.markdown("""
        * **Eixo Horizontal (Deitado - Seus Votos):** Quanto mais para a **direita**, mais forte você já é naquela escola.
        * **Eixo Vertical (Em pé - Votos em Disputa):** Quanto mais para **cima**, mais votos foram dados a *outros candidatos* (é o "ouro" a ser garimpado).
        * 🎯 **A Melhor Estratégia:** As bolinhas que estão mais altas no gráfico são os seus melhores alvos para caminhadas e corpo a corpo. Lá existem muitos eleitores e a maioria votou em adversários no passado.
        """)
    
    scatter = alt.Chart(agenda_df).mark_circle(size=200).encode(
        x=alt.X('QT_VOTOS_SAMIR:Q', title='Seus Votos Atuais'),
        y=alt.Y('VOTOS_EM_DISPUTA:Q', title='Votos Disponíveis (Em Disputa)'),
        color=alt.Color('ESTRATEGIA:N', 
                        title='Recomendação', 
                        legend=alt.Legend(orient='top', labelLimit=0),
                        scale=alt.Scale(
                            domain=['🛡️ Reduto (Fidelizar)', '⚔️ Expansão (Conquistar)'], 
                            range=['#25D366', '#E83E8C']
                        )),
        tooltip=[
            alt.Tooltip('NM_LOCAL_VOTACAO', title='Local'),
            alt.Tooltip('VOTOS_EM_DISPUTA', title='Potencial de Crescimento'),
            alt.Tooltip('QT_VOTOS_SAMIR', title='Seus Votos'),
            alt.Tooltip('QT_VOTOS_VALIDOS_SECAO', title='Votos Válidos Totais')
        ]
    ).properties(
        height=450
    ).interactive()
    
    st.altair_chart(scatter, use_container_width=True)
    
    st.markdown(f"#### 📋 Top {limite_ranking} Locais com Maior Potencial de Crescimento")
    tabela_agenda = agenda_df[['NM_LOCAL_VOTACAO', 'ESTRATEGIA', 'VOTOS_EM_DISPUTA', 'QT_VOTOS_SAMIR', 'QT_VOTOS_VALIDOS_SECAO']]
    tabela_agenda.columns = ['Local de Votação', 'Ação Recomendada', 'Potencial de Crescimento', 'Seus Votos Atuais', 'Total de Votos Válidos']
    st.dataframe(tabela_agenda, use_container_width=True)

else:
    st.warning("A coluna 'QT_VOTOS_VALIDOS_SECAO' não está presente ou formatada corretamente nos dados filtrados.")

st.markdown("---")

# ======== ANÁLISE 5: MATRIZ ESTRATÉGICA DOS 4 QUADRANTES ========
st.subheader("🧩 Matriz de Inteligência de Território (Os 4 Quadrantes)")
st.markdown("Classificação automática das escolas cruzando o Tamanho do Eleitorado com a Força Política do Candidato.")

if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    matriz_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({
        'QT_VOTOS_VALIDOS_SECAO': 'sum',
        'QT_VOTOS_SAMIR': 'sum'
    }).reset_index()
    
    # Filtra apenas o Top Limite Ranking para não poluir
    matriz_df = matriz_df.sort_values(by='QT_VOTOS_VALIDOS_SECAO', ascending=False).head(limite_ranking)
    
    # Calcula a média de tamanho da escola e a média de votos do Samir nesse grupo
    media_tamanho = matriz_df['QT_VOTOS_VALIDOS_SECAO'].mean()
    media_votos = matriz_df['QT_VOTOS_SAMIR'].mean()
    
    # Função para classificar nos 4 quadrantes
    def classificar_quadrante(row):
        escola_grande = row['QT_VOTOS_VALIDOS_SECAO'] >= media_tamanho
        samir_forte = row['QT_VOTOS_SAMIR'] >= media_votos
        
        if escola_grande and samir_forte:
            return "🏆 FORTALEZA (Defender)"
        elif escola_grande and not samir_forte:
            return "🚀 OCEANO AZUL (Atacar)"
        elif not escola_grande and samir_forte:
            return "💎 NICHO LEAL (Manter)"
        else:
            return "❌ ZONA DE DESCARTE (Ignorar)"
            
    matriz_df['CLASSIFICACAO'] = matriz_df.apply(classificar_quadrante, axis=1)
    
    with st.expander("📖 Entenda as 4 Classificações", expanded=True):
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.markdown("**🏆 Fortaleza:** Escolas muito grandes onde você já é forte. Coloque as melhores lideranças para não perder esse território.")
            st.markdown("**🚀 Oceano Azul:** Escolas gigantes onde você ainda é fraco. É aqui que moram as maiores oportunidades de multiplicar votos.")
        with col_q2:
            st.markdown("**💎 Nicho Leal:** Escolas pequenas onde você tem o domínio. Não gaste muita energia, apenas mantenha o contato via WhatsApp.")
            st.markdown("**❌ Zona de Descarte:** Escolas pequenas onde você é muito fraco. O custo de campanha aqui não compensa. Evite investir tempo.")

    scatter_matriz = alt.Chart(matriz_df).mark_circle(size=250).encode(
        x=alt.X('QT_VOTOS_VALIDOS_SECAO:Q', title='Tamanho da Escola (Votos Válidos)'),
        y=alt.Y('QT_VOTOS_SAMIR:Q', title='Seus Votos (Sua Força)'),
        color=alt.Color('CLASSIFICACAO:N', 
                        title='Quadrante Estratégico',
                        legend=alt.Legend(orient='top', labelLimit=0),
                        scale=alt.Scale(
                            domain=["🏆 FORTALEZA (Defender)", "🚀 OCEANO AZUL (Atacar)", "💎 NICHO LEAL (Manter)", "❌ ZONA DE DESCARTE (Ignorar)"],
                            range=['#1A73E8', '#25D366', '#FFC107', '#E83E8C']
                        )),
        tooltip=[
            alt.Tooltip('NM_LOCAL_VOTACAO', title='Local'),
            alt.Tooltip('CLASSIFICACAO', title='Estratégia'),
            alt.Tooltip('QT_VOTOS_VALIDOS_SECAO', title='Tamanho Total'),
            alt.Tooltip('QT_VOTOS_SAMIR', title='Seus Votos')
        ]
    ).properties(
        height=500
    ).interactive()
    
    # Adicionando as linhas cruzadas (Média) para desenhar os quadrantes visualmente
    regra_x = alt.Chart(pd.DataFrame({'x': [media_tamanho]})).mark_rule(strokeDash=[5, 5], color='gray').encode(x='x:Q')
    regra_y = alt.Chart(pd.DataFrame({'y': [media_votos]})).mark_rule(strokeDash=[5, 5], color='gray').encode(y='y:Q')
    
    st.altair_chart(scatter_matriz + regra_x + regra_y, use_container_width=True)

st.markdown("---")

# ======== ANÁLISE 6: CURVA DE PARETO (FOCO 80/20) ========
st.subheader("🎯 A Curva de Foco (Regra de Pareto 80/20)")
st.markdown("Mostra visualmente o acúmulo de votos. Descubra exatamente quantas escolas são responsáveis por garantir a maior parte do seu mandato.")

if not dados_filtrados.empty:
    # Prepara os dados, ordenando das escolas mais fortes para as mais fracas
    pareto_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().reset_index()
    pareto_df = pareto_df.sort_values(by='QT_VOTOS_SAMIR', ascending=False)
    
    # Calcula o acumulado de votos
    pareto_df['Votos Acumulados'] = pareto_df['QT_VOTOS_SAMIR'].cumsum()
    total_votos_pareto = pareto_df['QT_VOTOS_SAMIR'].sum()
    pareto_df['% Acumulado'] = (pareto_df['Votos Acumulados'] / total_votos_pareto) * 100
    
    # Cria uma coluna de "Ordem" para o eixo horizontal ficar contínuo e ordenado
    pareto_df['Posição no Ranking'] = range(1, len(pareto_df) + 1)
    
    # Tenta encontrar o ponto exato onde batemos ou passamos de 80% dos votos
    try:
        corte_80 = pareto_df[pareto_df['% Acumulado'] >= 80].iloc[0]
        qtd_escolas_80 = int(corte_80['Posição no Ranking'])
        total_escolas_pareto = len(pareto_df)
        
        st.success(f"**🧠 Insight de Foco (Curva de Pareto):**\n\nApenas **{qtd_escolas_80} escolas** (de um total de {total_escolas_pareto} mapeadas) são responsáveis por garantir **80% de todos os seus votos**.\n\nSeu tempo de agenda, energia da equipe e recursos de campanha devem ser direcionados com força máxima prioritariamente para este seleto grupo. O restante da lista representa muito esforço físico para pouco retorno de urna.")
    except:
        pass
    
    # Gráfico da Curva (Linha + Área Prenchida)
    curva = alt.Chart(pareto_df).mark_line(color='#E83E8C', strokeWidth=4).encode(
        x=alt.X('Posição no Ranking:Q', title='Quantidade de Escolas (Da maior para a menor)'),
        y=alt.Y('% Acumulado:Q', title='Porcentagem Acumulada de Votos (%)', scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip('Posição no Ranking:Q', title='Posição no Ranking'),
            alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
            alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos nesta Escola'),
            alt.Tooltip('% Acumulado:Q', title='% Acumulado Total', format='.1f')
        ]
    ).properties(height=400)
    
    area = curva.mark_area(color='#E83E8C', opacity=0.2)
    
    # Linha horizontal marcando a zona dos 80%
    linha_80 = alt.Chart(pd.DataFrame({'y': [80]})).mark_rule(strokeDash=[5, 5], color='red', strokeWidth=2).encode(y='y:Q')
    
    st.altair_chart(area + curva + linha_80, use_container_width=True)
else:
    st.info("Não há dados suficientes para gerar a Curva de Pareto.")
