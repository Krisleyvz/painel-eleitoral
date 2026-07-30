import streamlit as st
import pandas as pd

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Gestão", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E ESTILO
# ==========================================
st.markdown("""
<style>
    .stApp {
        background-color: #0A1C2E !important;
    }
    h1, h2, h3, p, label, div.stMarkdown, .stMetricValue {
        color: #FFFFFF !important;
    }
    .card-item {
        background-color: #152b45;
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid #1A73E8;
        margin-bottom: 10px;
    }
    input, select {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Logo Centralizada no Topo
col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("📱 Gestão de Rua")

st.markdown("---")

# Base de dados simulada (que depois puxará da planilha)
dados_gerais = pd.DataFrame([
    {"Nome": "Ádalo Lima do Nascimento", "Telefone": "68999454436", "Bairro": "Laélia Alcântara", "Regional": "Calafate", "Lideranca": "João Pedro", "Aniversario": "30/07"},
    {"Nome": "Adriana Maria Vieira Lobao", "Telefone": "68992836226", "Bairro": "Boa União", "Regional": "Baixada", "Lideranca": "Maria Silva", "Aniversario": "15/08"},
    {"Nome": "Advagner Lopes Prado", "Telefone": "68999857787", "Bairro": "Vitória", "Regional": "São Francisco", "Lideranca": "João Pedro", "Aniversario": "30/07"},
    {"Nome": "Aglanair M F Pascoal Nogueira", "Telefone": "68992831522", "Bairro": "Estação Experimental", "Regional": "Estação", "Lideranca": "Carlos Mendes", "Aniversario": "10/09"},
    {"Nome": "Ana Maria Matos", "Telefone": "68992435030", "Bairro": "Tancredo Neves", "Regional": "Tancredo Neves", "Lideranca": "Maria Silva", "Aniversario": "30/07"}
])

# ==========================================
# ABAS DO APLICATIVO (IGUAL AO APPSHEET)
# ==========================================
aba1, aba2, aba3, aba4, aba5 = st.tabs(["🏠 Início", "🎂 Aniversário", "📍 Bairros", "🏆 Liderança", "🗺️ Mapa"])

# --- ABA 1: INÍCIO (Métricas de Acompanhamento) ---
with aba1:
    st.subheader("📊 Resumo de Hoje")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(label="Cadastros de Hoje", value="2")
    with col_m2:
        st.metric(label="Total de Cadastros", value="329")
        
    st.markdown("---")
    st.info("💡 **Dica:** Utilize as abas acima para navegar entre os aniversariantes do dia, filtrar bairros por rota, acompanhar o ranking de lideranças ou ver o mapa.")

# --- ABA 2: ANIVERSARIANTES ---
with aba2:
    st.subheader("🎂 Aniversariantes do Dia")
    st.markdown("Envie os parabéns diretamente pelo WhatsApp com um toque:")
    
    # Filtra aniversariantes (simulando o dia de hoje)
    aniversariantes_hoje = dados_gerais[dados_gerais['Aniversario'] == "30/07"]
    
    if aniversariantes_hoje.empty:
        st.info("Nenhum aniversariante registrado para hoje.")
    else:
        for idx, row in aniversariantes_hoje.iterrows():
            tel_num = ''.join(filter(str.isdigit, str(row['Telefone'])))
            st.markdown(f"""
            <div class="card-item">
                <b>🎉 {row['Nome']}</b><br>
                📞 {row['Telefone']} | Bairro: {row['Bairro']}
            </div>
            """, unsafe_allow_html=True)
            
            # Botão WhatsApp Direto
            msg = f"Parabéns {row['Nome'].split()[0]}! O Samir Bestene e toda a nossa equipe desejam um feliz aniversário com muita saúde e paz!"
            link_wpp = f"https://wa.me/55{tel_num}?text={msg.replace(' ', '%20')}"
            st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 8px; border-radius: 5px; text-decoration: none; font-weight: bold;'>💬 Enviar Parabéns no WhatsApp</a>", unsafe_allow_html=True)
            st.markdown("")

# --- ABA 3: FILTRO DE BAIRROS E ROTAS ---
with aba3:
    st.subheader("📍 Filtro por Bairro / Regional")
    
    bairro_selecionado = st.selectbox("Selecione o Bairro:", ["Todos"] + list(dados_gerais['Bairro'].unique()))
    
    if bairro_selecionado != "Todos":
        filtrados = dados_gerais[dados_gerais['Bairro'] == bairro_selecionado]
    else:
        filtrados = dados_gerais
        
    for idx, row in filtrados.iterrows():
        tel_num = ''.join(filter(str.isdigit, str(row['Telefone'])))
        st.markdown(f"""
        <div class="card-item">
            <b>👤 {row['Nome']}</b><br>
            📍 <b>Bairro:</b> {row['Bairro']}<br>
            📞 <a href='tel:{tel_num}' style='color: #4da6ff;'>{row['Telefone']}</a>
        </div>
        """, unsafe_allow_html=True)

# --- ABA 4: RANKING DE LIDERANÇAS ---
with aba4:
    st.subheader("🏆 Ranking de Lideranças")
    st.markdown("Quem está mobilizando mais apoiadores:")
    
    # Conta quantos cadastros cada liderança tem
    ranking = dados_gerais['Lideranca'].value_counts().reset_index()
    ranking.columns = ['Liderança', 'Total de Cadastros']
    
    for idx, row in ranking.iterrows():
        posicao = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else "📌"))
        st.markdown(f"""
        <div class="card-item">
            <b>{posicao} {row['Liderança']}</b><br>
            📊 {row['Total de Cadastros']} apoiadores cadastrados
        </div>
        """, unsafe_allow_html=True)

# --- ABA 5: MAPA DE APOIADORES ---
with aba5:
    st.subheader("🗺️ Mapa de Apoio")
    st.markdown("Visualização das concentrações de apoiadores geolocalizados.")
    
    # Criação de um mapa simulado com coordenadas de Rio Branco - AC
    mapa_dados = pd.DataFrame({
        'lat': [-9.9749, -9.9650, -9.9820, -9.9550],
        'lon': [-67.8243, -67.8100, -67.8400, -67.8000]
    })
    st.map(mapa_dados, zoom=12)
