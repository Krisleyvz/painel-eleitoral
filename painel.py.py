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

# Insere a logo da campanha no topo (bem menor e discreta)
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

st.sidebar.markdown("---")
mostrar_todas = st.sidebar.checkbox("👁️ Exibir TODAS as escolas", value=False, help="Desativa o limite e renderiza 100% da base nos gráficos e tabelas.")
limite_slider = st.sidebar.slider("Amplitude do Ranking (Exibir Top X Locais):", min_value=10, max_value=100, value=25, step=5, disabled=mostrar_todas)
limite_ranking = 999999 if mostrar_todas else limite_slider

if ano_selecionado == 'Todos os Anos (Série Histórica)':
    dados_filtrados = dados.copy()
    label_periodo = "Série Histórica Acumulada"
else:
    dados_filtrados = dados[dados['ANO_ELEICAO'] == int(ano_selecionado)].copy()
    label_periodo = f"Ano de {ano_selecionado}"

# 4. Cartões de Métricas Executivas
total_votos = dados_filtrados['QT_VOTOS_SAMIR'].sum()
total_escolas = dados_filtrados['NM_LOCAL_VOTACAO'].nunique()

col1, col2 = st.columns(2)
col1.metric(label=f"Total de Votos ({label_periodo})", value=f"{total_votos:,}".replace(",", "."))
col2.metric(label="Locais de Votação Mapeados", value=total_escolas)

st.markdown("---")

# ======== ANÁLISE 1: MAPA LIMPO ========
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

# ======== ANÁLISE 2: RAIO-X COM GRÁFICO HORIZONTAL ========
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

st.markdown(f"#### 📉 Gráfico de Desempenho ({texto_top} {texto_local})")

altura_grafico = max(400, len(top_escolas) * 20)

grafico_barras = alt.Chart(top_escolas).mark_bar(color="#1A73E8").encode(
    x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Obtidos', axis=alt.Axis(tickMinStep=1, format='d')),
    y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title='Local de Votação'),
    tooltip=[
        alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Local'),
        alt.Tooltip('QT_VOTOS_SAMIR:Q', title='Votos'),
        alt.Tooltip('MARKET_SHARE:Q', title='Market Share (%)', format='.1f')
    ]
).properties(
    height=altura_grafico 
)
st.altair_chart(grafico_barras, use_container_width=True)

if 'QT_VOTOS_VALIDOS_SECAO' in top_escolas.columns:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Votos Válidos Totais', 'Market Share (%)']
else:
    top_escolas.columns = ['Local de Votação', 'Votos Obtidos', 'Market Share (%)']

st.markdown("#### 📋 Detalhamento Analítico Completo")
st.dataframe(top_escolas, use_container_width=True)

st.markdown("---")

# ======== ANÁLISE 3: MATRIZ DE EVOLUÇÃO TEMPORAL COM NOVO EXPORT ========
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
    
    # --- CÓDIGO DO RELATÓRIO VISUAL (HTML/PDF) ---
    tabela_html = tabela_comparativa.to_html(classes='tabela-bonita', border=0)
    
    html_completo = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Relatório - Matriz de Evolução</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .header h1 {{ color: #0A1C2E; margin: 0; }}
            .header p {{ color: #666; font-size: 14px; }}
            .tabela-bonita {{ width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 0.9em; min-width: 400px; border-radius: 5px 5px 0 0; overflow: hidden; box-shadow: 0 0 20px rgba(0, 0, 0, 0.15); }}
            .tabela-bonita thead tr {{ background-color: #1A73E8; color: #ffffff; text-align: left; font-weight: bold; }}
            .tabela-bonita th, .tabela-bonita td {{ padding: 12px 15px; border: 1px solid #ddd; }}
            .tabela-bonita tbody tr {{ border-bottom: 1px solid #dddddd; }}
            .tabela-bonita tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
            .tabela-bonita tbody tr:last-of-type {{ border-bottom: 2px solid #1A73E8; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎯 Relatório de Inteligência Territorial</h1>
            <p>Matriz de Evolução Histórica (Comparativo entre Eleições) - {texto_local}</p>
        </div>
        {tabela_html}
        <p style="text-align: center; font-size: 12px; color: #777; margin-top: 20px;">Gerado pelo Sistema da Sala de Guerra</p>
    </body>
    </html>
    """
    
    st.download_button(
        label="📑 Baixar Relatório Visual (Abre no navegador, pronto para Salvar como PDF)",
        data=html_completo,
        file_name='relatorio_evolucao_historica.html',
        mime='text/html',
    )
    # ---------------------------------------------
    
else:
    st.info("ℹ️ A base de dados atual possui apenas um ano eleitoral registrado. Assim que houver múltiplos anos, a matriz e os comparativos temporais serão ativados.")

st.markdown("---")

# ======== ANÁLISE 4: DIRECIONADOR DE AGENDA ========
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
        * 🎯 **A Melhor Estratégia:** As bolinhas que estão mais altas no gráfico são os seus melhores alvos para caminhadas e corpo a corpo.
        """)
    
    st.markdown("""
        <div style='display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; margin-bottom: 10px; font-weight: bold;'>
            <div><span style='color: #25D366; font-size: 1.2em;'>●</span> 🛡️ Reduto (Fidelizar)</div>
            <div><span style='color: #E83E8C; font-size: 1.2em;'>●</span> ⚔️ Expansão (Conquistar)</div>
        </div>
    """, unsafe_allow_html=True)
    
    scatter = alt.Chart(agenda_df).mark_circle(size=350).encode(
        x=alt.X('QT_VOTOS_SAMIR:Q', title='Seus Votos Atuais'),
        y=alt.Y('VOTOS_EM_DISPUTA:Q', title='Votos Disponíveis (Em Disputa)'),
        color=alt.Color('ESTRATEGIA:N', 
                        legend=None,
                        scale=alt.Scale(
                            domain=['🛡️ Reduto (Fidelizar)', '⚔️ Expansão (Conquistar)'], 
                            range=['#25D366', '#E83E8C']
                        )),
        tooltip=[
            alt.Tooltip('NM_LOCAL_VOTACAO', title='Local'),
            alt.Tooltip('VOTOS_EM_DISPUTA', title='Potencial de Crescimento'),
            alt.Tooltip('QT_VOTOS_SAMIR', title='Seus Votos')
        ]
    ).properties(height=450)
    
    st.altair_chart(scatter, use_container_width=True)
    
    st.markdown(f"#### 📋 Tabela de Potencial de Crescimento ({texto_top})")
    tabela_agenda = agenda_df[['NM_LOCAL_VOTACAO', 'ESTRATEGIA', 'VOTOS_EM_DISPUTA', 'QT_VOTOS_SAMIR', 'QT_VOTOS_VALIDOS_SECAO']]
    tabela_agenda.columns = ['Local de Votação', 'Ação Recomendada', 'Potencial de Crescimento', 'Seus Votos Atuais', 'Total de Votos Válidos']
    st.dataframe(tabela_agenda, use_container_width=True)

else:
    st.warning("A coluna 'QT_VOTOS_VALIDOS_SECAO' não está presente ou formatada corretamente nos dados filtrados.")

st.markdown("---")

# ======== ANÁLISE 5: MATRIZ ESTRATÉGICA DOS 4 QUADRANTES ========
st.subheader("🧩 Matriz de Inteligência de Território (Os 4 Quadrantes)")

if 'QT_VOTOS_VALIDOS_SECAO' in dados_filtrados.columns:
    matriz_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO').agg({
        'QT_VOTOS_VALIDOS_SECAO': 'sum',
        'QT_VOTOS_SAMIR': 'sum'
    }).reset_index()
    
    matriz_df = matriz_df.sort_values(by='QT_VOTOS_VALIDOS_SECAO', ascending=False).head(limite_ranking)
    
    media_tamanho = matriz_df['QT_VOTOS_VALIDOS_SECAO'].mean()
    media_votos = matriz_df['QT_VOTOS_SAMIR'].mean()
    
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
    
    with st.expander("📖 Entenda as 4 Classificações", expanded=False):
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.markdown("**🏆 Fortaleza:** Escolas muito grandes onde você já é forte.")
            st.markdown("**🚀 Oceano Azul:** Escolas gigantes onde você ainda é fraco. Maior oportunidade de votos.")
        with col_q2:
            st.markdown("**💎 Nicho Leal:** Escolas pequenas onde você tem o domínio.")
            st.markdown("**❌ Zona de Descarte:** Escolas pequenas onde você é fraco. Evite investir tempo.")

    st.markdown("""
        <div style='display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; margin-bottom: 10px; font-weight: bold;'>
            <div><span style='color: #1A73E8; font-size: 1.2em;'>●</span> 🏆 Fortaleza</div>
            <div><span style='color: #25D366; font-size: 1.2em;'>●</span> 🚀 Oceano Azul</div>
            <div><span style='color: #FFC107; font-size: 1.2em;'>●</span> 💎 Nicho Leal</div>
            <div><span style='color: #E83E8C; font-size: 1.2em;'>●</span> ❌ Descarte</div>
        </div>
    """, unsafe_allow_html=True)

    scatter_matriz = alt.Chart(matriz_df).mark_circle(size=400).encode(
        x=alt.X('QT_VOTOS_VALIDOS_SECAO:Q', title='Tamanho da Escola (Votos Válidos)'),
        y=alt.Y('QT_VOTOS_SAMIR:Q', title='Seus Votos (Sua Força)'),
        color=alt.Color('CLASSIFICACAO:N', 
                        legend=None,
                        scale=alt.Scale(
                            domain=["🏆 FORTALEZA (Defender)", "🚀 OCEANO AZUL (Atacar)", "💎 NICHO LEAL (Manter)", "❌ ZONA DE DESCARTE (Ignorar)"],
                            range=['#1A73E8', '#25D366', '#FFC107', '#E83E8C']
                        )),
        tooltip=[
            alt.Tooltip('NM_LOCAL_VOTACAO', title='Local'),
            alt.Tooltip('CLASSIFICACAO', title='Estratégia')
        ]
    ).properties(height=500)
    
    regra_x = alt.Chart(pd.DataFrame({'x': [media_tamanho]})).mark_rule(strokeDash=[5, 5], color='gray').encode(x='x:Q')
    regra_y = alt.Chart(pd.DataFrame({'y': [media_votos]})).mark_rule(strokeDash=[5, 5], color='gray').encode(y='y:Q')
    
    st.altair_chart(scatter_matriz + regra_x + regra_y, use_container_width=True)

st.markdown("---")

# ======== ANÁLISE 6: CURVA DE PARETO (FOCO 80/20) ========
st.subheader("🎯 A Curva de Foco (Regra de Pareto 80/20)")

if not dados_filtrados.empty:
    pareto_df = dados_filtrados.groupby('NM_LOCAL_VOTACAO')['QT_VOTOS_SAMIR'].sum().reset_index()
    pareto_df = pareto_df.sort_values(by='QT_VOTOS_SAMIR', ascending=False)
    
    pareto_df['Votos Acumulados'] = pareto_df['QT_VOTOS_SAMIR'].cumsum()
    total_votos_pareto = pareto_df['QT_VOTOS_SAMIR'].sum()
    pareto_df['% Acumulado'] = (pareto_df['Votos Acumulados'] / total_votos_pareto) * 100
    
    pareto_df['Posição no Ranking'] = range(1, len(pareto_df) + 1)
    
    try:
        corte_80 = pareto_df[pareto_df['% Acumulado'] >= 80].iloc[0]
        qtd_escolas_80 = int(corte_80['Posição no Ranking'])
        total_escolas_pareto = len(pareto_df)
        
        st.success(f"**🧠 Insight de Foco:** Apenas **{qtd_escolas_80} escolas** (de {total_escolas_pareto} mapeadas) garantem **80% de todos os seus votos**.")
    except:
        pass
    
    curva = alt.Chart(pareto_df).mark_line(color='#E83E8C', strokeWidth=4, point=alt.OverlayMarkDef(color='#E83E8C', size=150)).encode(
        x=alt.X('Posição no Ranking:Q', title='Quantidade de Escolas (Da maior para a menor)'),
        y=alt.Y('% Acumulado:Q', title='Porcentagem Acumulada de Votos (%)', scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
            alt.Tooltip('% Acumulado:Q', title='% Acumulado Total', format='.1f')
        ]
    ).properties(height=400)
    
    area = curva.mark_area(color='#E83E8C', opacity=0.2)
    linha_80 = alt.Chart(pd.DataFrame({'y': [80]})).mark_rule(strokeDash=[5, 5], color='red', strokeWidth=2).encode(y='y:Q')
    
    st.altair_chart(area + curva + linha_80, use_container_width=True)
else:
    st.info("Não há dados suficientes para gerar a Curva de Pareto.")

st.markdown("---")

# ======== ANÁLISE 7: SIMULADOR DE METAS (COTA POR ESCOLA) ========
st.subheader("🏁 Simulador de Metas de Vitória (Distribuidor de Cotas)")
st.markdown("Insira a sua meta global. O sistema distribuirá a 'cota' proporcionalmente para cada escola com base no peso eleitoral (Votos Válidos Totais) e calculará quantos votos faltam ser conquistados nas urnas.")

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
        
        st.markdown(f"#### 📋 Distribuição de Metas ({texto_top})")
        st.dataframe(tabela_final_metas, use_container_width=True)
else:
    st.info("A coluna de Votos Válidos não está disponível para calcular a proporção da meta.")
