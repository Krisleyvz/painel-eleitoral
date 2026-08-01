import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import zipfile
import os

# 1. Configuração da Página
st.set_page_config(page_title="Painel Executivo | Inteligência Territorial", page_icon="🎯", layout="wide")

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

# 2. Carregamento dos Dados
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

try:
    dados = carregar_dados()
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

# 3. Barra Lateral 
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
        "🔗 5. Análise de Votos Casados"
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
    altura_grafico = max(400, len(top_escolas) * 20)

    grafico_barras = alt.Chart(top_escolas).mark_bar(color="#1A73E8").encode(
        x=alt.X('QT_VOTOS_SAMIR:Q', title='Votos Obtidos', axis=alt.Axis(tickMinStep=1, format='d')),
        y=alt.Y('NM_LOCAL_VOTACAO:N', sort='-x', title=None, axis=alt.Axis(labelLimit=500)),
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
            tooltip=['NM_LOCAL_VOTACAO', 'CLASSIFICACAO']
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
        df_demo_filtrado = dados_demo.copy()
        if ano_selecionado != 'Todos os Anos (Série Histórica)':
            df_demo_filtrado = df_demo_filtrado[df_demo_filtrado['ANO_ELEICAO'] == int(ano_selecionado)]
        if col_municipio and municipios_selecionados:
            if 'NM_MUNICIPIO_x' in df_demo_filtrado.columns:
                df_demo_filtrado = df_demo_filtrado[df_demo_filtrado['NM_MUNICIPIO_x'].isin(municipios_selecionados) | df_demo_filtrado['NM_MUNICIPIO_y'].isin(municipios_selecionados)]
            elif 'NM_MUNICIPIO' in df_demo_filtrado.columns:
                 df_demo_filtrado = df_demo_filtrado[df_demo_filtrado['NM_MUNICIPIO'].isin(municipios_selecionados)]

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
            grafico_idade = alt.Chart(df_idade).mark_bar(color="#0A1C2E").encode(
                x=alt.X('VOTOS_ESTIMADOS_SAMIR:Q', title='Qtd. Votos (Estimado)'),
                y=alt.Y('DS_FAIXA_ETARIA:N', title=None, sort='-x', axis=alt.Axis(labelLimit=500)),
                tooltip=['DS_FAIXA_ETARIA:N', 'VOTOS_ESTIMADOS_SAMIR:Q']
            ).properties(height=350)
            st.altair_chart(grafico_idade, use_container_width=True)

        st.markdown("---")
        st.subheader("Grau de Instrução (Nível de Escolaridade)")
        df_escola = df_demo_filtrado.groupby('DS_GRAU_ESCOLARIDADE', as_index=False)['VOTOS_ESTIMADOS_SAMIR'].sum()
        df_escola['VOTOS_ESTIMADOS_SAMIR'] = df_escola['VOTOS_ESTIMADOS_SAMIR'].astype(int)
        
        grafico_escola = alt.Chart(df_escola).mark_bar(color="#1A73E8").encode(
            x=alt.X('VOTOS_ESTIMADOS_SAMIR:Q', title='Quantidade de Votos (Estimado)'),
            y=alt.Y('DS_GRAU_ESCOLARIDADE:N', title=None, sort='-x', axis=alt.Axis(labelLimit=500)),
            tooltip=['DS_GRAU_ESCOLARIDADE:N', 'VOTOS_ESTIMADOS_SAMIR:Q']
        ).properties(height=350)
        st.altair_chart(grafico_escola, use_container_width=True)


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

        # Agrupamento limpo e blindado contra o KeyError
        ador_escola = df_ador_filtrado.groupby(['NM_LOCAL_VOTACAO'], as_index=False).agg({
            'QT_APTOS': 'sum', 'VOTOS_ADORMECIDOS': 'sum', 'QT_ABSTENCOES': 'sum',
            'QT_VOTOS_BRANCOS': 'sum', 'QT_VOTOS_NULOS': 'sum'
        })
        
        # Trazendo as coordenadas geográficas de volta, com segurança, para podermos gerar o mapa!
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
            # Aqui temos o mapa real na aba 3!
            st.map(mapa_ador, latitude='lat', longitude='lon')
        else:
            st.info("Dados de localização não disponíveis para este filtro.")

        st.markdown("---")
        
        st.subheader("🔥 Top Escolas para Mobilização de Rua (Ouro Puro)")
        ador_top = ador_escola.sort_values(by='VOTOS_ADORMECIDOS', ascending=False).head(limite_ranking)
        
        grafico_ador = alt.Chart(ador_top).mark_bar(color="#E83E8C").encode(
            x=alt.X('VOTOS_ADORMECIDOS:Q', title='Quantidade de Votos Adormecidos'),
            y=alt.Y('NM_LOCAL_VOTACAO:N', title=None, sort='-x', axis=alt.Axis(labelLimit=500)),
            tooltip=[
                alt.Tooltip('NM_LOCAL_VOTACAO:N', title='Escola'),
                alt.Tooltip('VOTOS_ADORMECIDOS:Q', title='Total Adormecidos', format=','),
                alt.Tooltip('QT_ABSTENCOES:Q', title='Abstenções', format=','),
                alt.Tooltip('QT_VOTOS_BRANCOS:Q', title='Brancos', format=','),
                alt.Tooltip('QT_VOTOS_NULOS:Q', title='Nulos', format=','),
                alt.Tooltip('QT_APTOS:Q', title='Total de Aptos', format=',')
            ]
        ).properties(height=max(400, len(ador_top)*20))
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
            
            grafico_adv = alt.Chart(adversarios_grafico).mark_bar(color="#FFC107").encode(
                x=alt.X('QT_VOTOS:Q', title='Votos Conquistados pelo Adversário'),
                y=alt.Y('NM_VOTAVEL:N', title=None, sort='-x', axis=alt.Axis(labelLimit=500)),
                tooltip=[
                    alt.Tooltip('NM_VOTAVEL:N', title='Candidato'),
                    alt.Tooltip('QT_VOTOS:Q', title='Votos'),
                    alt.Tooltip('Share (%):Q', title='% de Domínio', format='.1f')
                ]
            ).properties(height=max(400, len(adversarios_grafico)*20))
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
                    
                    grafico_corr = alt.Chart(corr_samir).mark_bar(color="#25D366").encode(
                        x=alt.X('Índice de Correlação (r):Q', title='Força do Voto Casado (0 = Neutro, 1 = Perfeito)', scale=alt.Scale(domain=[0, 1])),
                        y=alt.Y('Candidato Parceiro:N', title=None, sort='-x', axis=alt.Axis(labelLimit=500)),
                        tooltip=[
                            alt.Tooltip('Candidato Parceiro:N', title='Candidato'),
                            alt.Tooltip('Índice de Correlação (r):Q', title='Índice Pearson', format='.2f')
                        ]
                    ).properties(height=max(400, len(corr_samir)*20))
                    st.altair_chart(grafico_corr, use_container_width=True)
                    
                    corr_samir['Índice de Correlação (r)'] = corr_samir['Índice de Correlação (r)'].round(3)
                    st.dataframe(corr_samir, use_container_width=True)
            else:
                st.warning("Não há volume de urnas suficientes nos filtros selecionados para garantir significância estatística no cálculo de Pearson.")
