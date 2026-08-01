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
    /* Estilo para botão desativado quando não há telefone */
    .btn-disabled {
        display: block; 
        text-align: center; 
        background-color: #334e68; 
        color: #8899a6; 
        padding: 8px; 
        border-radius: 5px; 
        font-size: 16px; 
        font-weight: bold;
        cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função blindada para tratar telefones
def tratar_telefone(tel_raw):
    tel_str = str(tel_raw).strip()
    if tel_str.lower() == 'nan' or tel_str == '':
        return "", "Sem telefone"
    
    # Remove o ".0" no final caso o pandas tenha lido como float
    tel_limpo = tel_str.split('.')[0]
    # Pega só os números
    tel_num = ''.join(filter(str.isdigit, tel_limpo))
    
    if len(tel_num) < 8: # Número muito curto pra ser válido
        return "", tel_str
        
    return tel_num, tel_limpo

# Função para carregar os dados direto via link público
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip() # Limpeza extra de segurança
    return df

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
    # Filtro rápido por Bairro ORDENADO ALFABETICAMENTE
    if 'Bairro' in df.columns:
        bairros_disponiveis = ["Todos"] + sorted([str(b).strip() for b in df['Bairro'].dropna().unique() if str(b).strip() != ''])
    else:
        bairros_disponiveis = ["Todos"]
        
    bairro_filtro = st.selectbox("Filtrar por Bairro:", bairros_disponiveis)
    
    if bairro_filtro != "Todos" and 'Bairro' in df.columns:
        df = df[df['Bairro'].astype(str).str.strip() == bairro_filtro]
        
    st.markdown("---")
    
    for index, row in df.iterrows():
        nome = str(row.get('Nome Completo', 'Sem Nome'))
        rua = str(row.get('Rua e Número', ''))
        bairro = str(row.get('Bairro', ''))
        complemento = str(row.get('Complemento', ''))
        
        # Passa o telefone pela função de tratamento
        tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
        
        st.markdown(f"""
        <div class="entrega-card">
            <b>👤 {nome}</b><br>
            📞 Tel: <a href="tel:{tel_num}" style="color: #4da6ff;">{tel_exibicao}</a><br>
            📍 <b>Endereço:</b> {rua} - {bairro}<br>
            💬 <b>Complemento:</b> {complemento if complemento != 'nan' else 'Nenhum'}
        </div>
        """, unsafe_allow_html=True)
        
        # Links de Ação Rápida para o Motorista
        endereco_completo = f"{rua}, {bairro}, Rio Branco - AC"
        link_mapa = f"https://www.google.com/maps/search/?api=1&query={endereco_completo.replace(' ', '+')}"
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.markdown(f"<a href='{link_mapa}' target='_blank' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 8px; border-radius: 5px; text-decoration: none; font-weight: bold;'>🗺️ Abrir Rota</a>", unsafe_allow_html=True)
        with col_b2:
            if tel_num:
                link_wpp = f"https://api.whatsapp.com/send?phone=55{tel_num}&text=Olá%20{nome.split()[0]},%20estamos%20a%20caminho%20da%20sua%20residência!"
                st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 8px; border-radius: 5px; text-decoration: none; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            
        st.markdown("")
else:
    st.info("Nenhum registro encontrado na planilha.")
