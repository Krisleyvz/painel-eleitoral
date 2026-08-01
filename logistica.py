import streamlit as st
import pandas as pd

# 1. Configuração da Página (Focada em Mobile)
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
    input, select {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função para carregar os dados direto via link público (Zero Erros de Chave)
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    # Substitua abaixo pelo ID real da sua planilha (o trecho longo entre /d/ e /edit na URL do navegador)
    spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

# Logo Centralizada
col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("🚚 Logística de Entregas")

st.markdown("---")
st.subheader("📦 Rotas e Endereços da Planilha")

try:
    df = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha. Verifique se o ID está correto e a planilha está pública para leitura. Detalhe: {e}")
    df = pd.DataFrame()

if not df.empty:
    # Filtro rápido por Bairro (coluna F da planilha) ORDENADO ALFABETICAMENTE
    if 'Bairro' in df.columns:
        bairros_disponiveis = ["Todos"] + sorted(list(df['Bairro'].dropna().astype(str).unique()))
    else:
        bairros_disponiveis = ["Todos"]
        
    bairro_filtro = st.selectbox("Filtrar por Bairro:", bairros_disponiveis)
    
    if bairro_filtro != "Todos" and 'Bairro' in df.columns:
        df = df[df['Bairro'] == bairro_filtro]
        
    st.markdown("---")
    
    for index, row in df.iterrows():
        nome = str(row.get('Nome Completo', 'Sem Nome'))
        telefone = str(row.get('Telefone', ''))
        rua = str(row.get('Rua e Número', ''))
        bairro = str(row.get('Bairro', ''))
        complemento = str(row.get('Complemento', ''))
        
        tel_num = ''.join(filter(str.isdigit, telefone))
        
        st.markdown(f"""
        <div class="entrega-card">
            <b>👤 {nome}</b><br>
            📞 Tel: <a href="tel:{tel_num}" style="color: #4da6ff;">{telefone}</a><br>
            📍 <b>Endereço:</b> {rua} - {bairro}<br>
            💬 <b>Complemento:</b> {complemento if complemento != 'nan' else 'Nenhum'}
        </div>
        """, unsafe_allow_html=True)
        
        # Links de Ação Rápida para o Motorista
        endereco_completo = f"{rua}, {bairro}, Rio Branco - AC"
        link_mapa = f"https://www.google.com/maps/search/?api=1&query={endereco_completo.replace(' ', '+')}"
        link_wpp = f"https://wa.me/55{tel_num}?text=Olá%20{nome.split()[0]},%20estamos%20a%20caminho%20da%20sua%20residência!"
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.markdown(f"<a href='{link_mapa}' target='_blank' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 8px; border-radius: 5px; text-decoration: none; font-weight: bold;'>🗺️ Abrir Rota</a>", unsafe_allow_html=True)
        with col_b2:
            st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 8px; border-radius: 5px; text-decoration: none; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
            
        st.markdown("")
else:
    st.info("Nenhum registro encontrado na planilha.")
