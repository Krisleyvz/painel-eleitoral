import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Cadastro", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E BOTÕES
# ==========================================
st.markdown("""
<style>
    .stApp {
        background-color: #0A1C2E !important;
    }
    h1, h2, h3, p, label, div.stMarkdown, .stCheckbox label span {
        color: #FFFFFF !important;
    }
    div[data-testid="stFormSubmitButton"] button {
        background-color: #1A73E8 !important;
        color: white !important;
        height: 55px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 8px !important;
    }
    input, select, textarea {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função para conectar ao Google Sheets de forma segura
def conectar_google_sheets():
    scope = ["https://www.spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    # Nome exato da planilha e da aba que vimos na sua imagem
    planilha = client.open("Samir Bestene - Apoiadores (Respostas)")
    aba = planilha.worksheet("Form_Responses")
    return aba

# 2. Cabeçalho Visual (Logo Centralizada)
col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
with col_logo2:
    try:
        st.image("IMG_6009.PNG", use_container_width=True)
    except:
        st.title("📝 Cadastro de Rua")

st.markdown("---")

# 3. Criação do Formulário de Coleta
with st.form(key="form_cadastro", clear_on_submit=True):
    
    st.subheader("👤 Dados Pessoais")
    nome = st.text_input("Nome Completo*")
    telefone = st.text_input("WhatsApp (Apenas números)*", placeholder="Ex: 68999999999")
    
    st.subheader("📍 Endereço")
    cep = st.text_input("CEP", placeholder="Ex: 69900000")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        rua = st.text_input("Rua e Número (Ex: Avenida Ceará, 4449)")
    with col2:
        bairro = st.text_input("Bairro")
        
    complemento = st.text_input("Complemento / Ponto de Referência")
    
    opcoes_regionais = ["Selecione", "Calafate", "São Francisco", "Baixada", "Estação Experimental", "Floresta", "Tancredo Neves", "Outra"]
    regional_selecionada = st.selectbox("Regional*", opcoes_regionais)
    regional_outra = st.text_input("Se escolheu 'Outra' acima, digite aqui o nome:")
    
    st.subheader("📌 Participação")
    participacao = st.selectbox("Como gostaria de participar?", [
        "Apenas receber propostas no WhatsApp",
        "Quero materiais de campanha (adesivos, etc.)",
        "Quero ser um multiplicador / voluntário no meu bairro",
        "Gostaria de organizar uma reunião na minha rua/bairro",
        "Abrir portas para juventude"
    ])
    
    submit = st.form_submit_button("✅ SALVAR CADASTRO", use_container_width=True)
    
    # 4. Lógica ao Clicar no Botão Salvar (Com gravação na planilha real)
    if submit:
        if regional_selecionada == "Outra":
            regional_final = regional_outra
        else:
            regional_final = regional_selecionada

        # Travas de segurança
        if nome.strip() == "" or telefone.strip() == "":
            st.error("⚠️ Os campos Nome e WhatsApp são obrigatórios!")
        elif regional_selecionada == "Selecione":
            st.error("⚠️ Por favor, selecione uma Regional.")
        elif regional_selecionada == "Outra" and regional_outra.strip() == "":
            st.error("⚠️ Selecionou 'Outra'. Por favor, digite o nome da regional na caixa abaixo.")
        else:
            try:
                sheet = conectar_google_sheets()
                
                # Pega a data e hora atual no formato exato da sua coluna A (ex: 30/07/2026 13:56:52)
                data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                # Monta a linha seguindo exatamente as colunas da sua planilha:
                # Carimbo | Nome | Telefone | CEP | Rua | Bairro | Complemento | Participação | Regional
                novo_registro = [
                    data_atual, 
                    nome, 
                    telefone, 
                    cep, 
                    rua, 
                    bairro, 
                    complemento, 
                    participacao, 
                    regional_final
                ]
                
                sheet.append_row(novo_registro)
                
                st.success(f"🎉 Registo de {nome} salvo com sucesso direto na planilha do Google Sheets!")
            except Exception as e:
                st.error(f"⚠️ Erro ao salvar na planilha. Detalhe: {e}")
