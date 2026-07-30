import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="App de Rua | Logística", page_icon="🚚", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E CARTÕES
# ==========================================
st.markdown("""
<style>
    .stApp {
        background-color: #0A1C2E !important;
    }
    h1, h2, h3, p, label, div.stMarkdown {
        color: #FFFFFF !important;
    }
    .entrega-card {
        background-color: #152b45;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #1A73E8;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função para carregar os dados reais da planilha
@st.cache_data(ttl=60)
def carregar_dados_planilha():
    scope = ["https://www.spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    planilha = client.open("Samir Bestene - Apoiadores (Respostas)")
    aba = planilha.worksheet("Form_Responses")
    dados = aba.get_all_records()
    return pd.DataFrame(dados)

# Logo Centralizada
col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("🚚 Logística de Entregas")

st.markdown("---")
st.subheader("📦 Rotas e Cadastros da Planilha")

try:
    df = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    df = pd.DataFrame()

if not df.empty:
    # Filtro por Regional baseada na coluna real da planilha
    regionais_disponiveis = ["Todas"] + list(df['Regional'].dropna().unique()) if 'Regional' in df.columns else ["Todas"]
    regional_filtro = st.selectbox("Filtrar por Regional de Atendimento:", regionais_disponiveis)
    
    if regional_filtro != "Todas" and 'Regional' in df.columns:
        df = df[df['Regional'] == regional_filtro]
        
    st.markdown("---")
    
    for index, row in df.iterrows():
        nome = row.get('Nome Completo', 'Sem Nome')
        telefone = str(row.get('Telefone', ''))
        rua = row.get('Rua e Número', '')
        bairro = row.get('Bairro', '')
        regional = row.get('Regional', '')
        
        tel_num = ''.join(filter(str.isdigit, telefone))
        
        st.markdown(f"""
        <div class="entrega-card">
            <b>👤 {nome}</b><br>
            📞 Tel: <a href="tel:{tel_num}" style="color: #4da6ff;">{telefone}</a><br>
            📍 <b>Endereço:</b> {rua} - {bairro} ({regional})
        </div>
        """, unsafe_allow_html=True)
        
        endereco_completo = f"{rua}, {bairro}, Rio Branco - AC"
        link_mapa = f"https://www.google.com/maps/search/?api=1&query={endereco_completo.replace(' ', '+')}"
        st.markdown(f"[🗺️ Abrir Rota no Google Maps]({link_mapa})", unsafe_allow_html=True)
        st.markdown("")
else:
    st.info("Nenhum registro encontrado na planilha.")
