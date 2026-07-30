import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Gestão", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E CARTÕES LIMPOS
# ==========================================
st.markdown("""
<style>
    .stApp {
        background-color: #0A1C2E !important;
    }
    h1, h2, h3, p, label, div.stMarkdown, .stMetricValue {
        color: #FFFFFF !important;
    }
    .contato-card {
        background-color: #152b45;
        padding: 12px 15px;
        border-radius: 8px;
        border-left: 4px solid #1A73E8;
        margin-bottom: 12px;
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
    # Substitua abaixo pelo ID real da sua planilha (o trecho longo entre /d/ e /edit na URL)
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
        st.title("📱 Gestão de Contatos")

st.markdown("---")

try:
    df = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha. Verifique se o link está público. Detalhe: {e}")
    df = pd.DataFrame()

total_cadastros = len(df) if not df.empty else 0

# Abas do Aplicativo Organizadas
aba1, aba2, aba3, aba4 = st.tabs(["🎂 Aniversário", "📍 Bairros", "📞 Contatos", "🗺️ Mapa"])

# --- ABA 1: ANIVERSARIANTES ---
with aba1:
    st.subheader("🎂 Aniversariantes")
    st.markdown("Contatos com data de nascimento cadastrada:")
    
    if not df.empty and 'Data de Nascimento' in df.columns:
        df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
        
        if df_aniver.empty:
            st.info("Nenhuma data de nascimento encontrada na planilha.")
        else:
            for idx, row in df_aniver.iterrows():
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                telefone = str(row.get('Telefone', ''))
                bairro = str(row.get('Bairro', ''))
                nascimento = str(row.get('Data de Nascimento', ''))
                
                tel_num = ''.join(filter(str.isdigit, telefone))
                
                st.markdown(f"""
                <div class="contato-card">
                    <b>🎂 {nome}</b> <span style="float: right; color: #4da6ff;">{nascimento}</span><br>
                    📍 Bairro: {bairro} | 📞 {telefone}
                </div>
                """, unsafe_allow_html=True)
                
                # Botões compactos lado a lado
                bc1, bc2 = st.columns(2)
                with bc1:
                    link_wpp_aniver = f"https://wa.me/55{tel_num}?text=Parabéns%20{nome.split()[0]}!%20Muitas%20felicidades!"
                    st.markdown(f"<a href='{link_wpp_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Parabéns Wpp</a>", unsafe_allow_html=True)
                with bc2:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                st.markdown("")
    else:
        st.info("Coluna de data de nascimento não localizada.")

# --- ABA 2: BAIRROS ---
with aba2:
    st.subheader("📍 Filtro por Bairro")
    if not df.empty and 'Bairro' in df.columns:
        bairros_disp = ["Todos"] + list(df['Bairro'].dropna().unique())
        bairro_sel = st.selectbox("Selecione o Bairro:", bairros_disp)
        
        filtrados = df if bairro_sel == "Todos" else df[df['Bairro'] == bairro_sel]
        
        st.markdown(f"**Total encontrado:** {len(filtrados)} pessoa(s)")
        st.markdown("")
        
        for idx, row in filtrados.iterrows():
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            telefone = str(row.get('Telefone', ''))
            bairro = str(row.get('Bairro', ''))
            tel_num = ''.join(filter(str.isdigit, telefone))
            
            st.markdown(f"""
            <div class="contato-card">
                <b>👤 {nome}</b><br>
                📍 <b>Bairro:</b> {bairro} | 📞 {telefone}
            </div>
            """, unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                link_wpp = f"https://wa.me/55{tel_num}?text=Olá%20{nome.split()[0]},%20tudo%20bem?"
                st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
            with bc2:
                st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
            st.markdown("")
    else:
        st.info("Nenhum dado de bairro encontrado.")

# --- ABA 3: CONTATOS ---
with aba3:
    st.subheader("📞 Pesquisa de Contatos")
    busca = st.text_input("🔍 Digite o nome para buscar:", placeholder="Ex: Maria...")
    
    if not df.empty and 'Nome Completo' in df.columns:
        df_contatos = df
        if busca:
            df_contatos = df[df['Nome Completo'].str.contains(busca, case=False, na=False)]
            
        st.markdown(f"**Exibindo {len(df_contatos)} contato(s)**")
        st.markdown("")
        
        for idx, row in df_contatos.iterrows():
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            telefone = str(row.get('Telefone', ''))
            bairro = str(row.get('Bairro', ''))
            tel_num = ''.join(filter(str.isdigit, telefone))
            
            st.markdown(f"""
            <div class="contato-card">
                <b>👤 {nome}</b><br>
                📍 Bairro: {bairro} | 📞 {telefone}
            </div>
            """, unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                link_wpp = f"https://wa.me/55{tel_num}?text=Olá%20{nome.split()[0]},%20tudo%20bem?"
                st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
            with bc2:
                st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
            st.markdown("")
    else:
        st.info("Nenhum contato encontrado.")

# --- ABA 4: MAPA ---
with aba4:
    st.subheader("🗺️ Visão Geral")
    st.markdown("Mapa de concentração dos apoiadores em Rio Branco.")
    mapa_dados = pd.DataFrame({
        'lat': [-9.9749, -9.9650, -9.9820, -9.9550],
        'lon': [-67.8243, -67.8100, -67.8400, -67.8000]
    })
    st.map(mapa_dados, zoom=12)
