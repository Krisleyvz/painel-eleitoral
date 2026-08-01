import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re # Biblioteca para reconstrução de texto

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

# Função para conectar ao Google Sheets (COM RECONSTRUTOR DE CHAVE)
def conectar_google_sheets():
    scope = ["https://www.spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # ---------------------------------------------------------
    # OPÇÃO NUCLEAR: RECONSTRUTOR ESTRUTURAL DA CHAVE PEM
    # ---------------------------------------------------------
    chave_bruta = str(creds_dict["private_key"])
    
    # 1. Remove cabeçalhos, rodapés e qualquer lixo invisível
    corpo_chave = re.sub(r'-----.*?-----', '', chave_bruta)
    # 2. Deixa apenas os caracteres puros do código base64 (remove espaços, \n, \r, etc)
    corpo_chave = re.sub(r'[^A-Za-z0-9+/=]', '', corpo_chave) 
    
    # 3. Fatie o código exatamente a cada 64 caracteres (Padrão rigoroso do Google)
    linhas = [corpo_chave[i:i+64] for i in range(0, len(corpo_chave), 64)]
    
    # 4. Remonta a chave com as quebras de linha perfeitas
    chave_perfeita = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(linhas) + "\n-----END PRIVATE KEY-----\n"
    
    # Devolve a chave perfeita para as credenciais
    creds_dict["private_key"] = chave_perfeita
    # ---------------------------------------------------------
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    planilha = client.open("Samir Bestene - Apoiadores (Respostas)")
    aba = planilha.worksheet("Form_Responses")
    return aba

# 2. Cabeçalho Visual
col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
with col_logo2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("📝 Cadastro de Rua")

st.markdown("---")

# 3. Criação do Formulário Mapeado
with st.form(key="form_cadastro", clear_on_submit=True):
    
    st.subheader("👤 Dados Pessoais")
    nome = st.text_input("Nome Completo*")
    telefone = st.text_input("WhatsApp (Apenas números)*", placeholder="Ex: 68999999999")
    nascimento = st.text_input("Data de Nascimento*", placeholder="Ex: 27/04/1996")
    
    st.subheader("📍 Endereço")
    cep = st.text_input("CEP", placeholder="Ex: 69900000")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        rua = st.text_input("Rua e Número (Ex: Avenida Ceará, 4449)")
    with col2:
        bairro = st.text_input("Bairro")
        
    complemento = st.text_input("Complemento / Ponto de Referência")
    municipio = st.text_input("Município de Residência", value="Rio Branco")
    
    st.subheader("📌 Participação e Engajamento")
    participacao = st.selectbox("Como você gostaria de participar da nossa caminhada?", [
        "Apenas receber propostas no WhatsApp",
        "Quero materiais de campanha (adesivos, etc.)",
        "Quero ser um multiplicador / voluntário no meu bairro",
        "Gostaria de organizar uma reunião na minha rua/bairro",
        "Abrir portas para juventude"
    ])
    
    indicacao = st.text_input("Através de quem você conheceu o nosso projeto?")
    
    st.markdown("---")
    consentimento = st.checkbox("Li e concordo com o uso dos meus dados e contato.")
    
    submit = st.form_submit_button("✅ SALVAR CADASTRO", use_container_width=True)
    
    # 4. Lógica de Alinhamento e Envio
    if submit:
        if nome.strip() == "" or telefone.strip() == "" or nascimento.strip() == "":
            st.error("⚠️ Os campos Nome, WhatsApp e Data de Nascimento são obrigatórios!")
        elif not consentimento:
            st.error("⚠️ Você precisa concordar com o uso dos dados marcando a caixa acima para prosseguir.")
        else:
            try:
                sheet = conectar_google_sheets()
                data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                texto_consentimento = "Li e concordo com o uso"
                
                novo_registro = [
                    data_atual,           # Coluna A
                    nome,                 # Coluna B
                    telefone,             # Coluna C
                    cep,                  # Coluna D
                    rua,                  # Coluna E
                    bairro,               # Coluna F
                    complemento,          # Coluna G
                    participacao,         # Coluna H
                    texto_consentimento,  # Coluna I
                    nascimento,           # Coluna J
                    "",                   # Coluna K
                    "",                   # Coluna L
                    indicacao,            # Coluna M
                    municipio             # Coluna N
                ]
                
                sheet.append_row(novo_registro)
                st.success(f"🎉 Registro de {nome} salvo com sucesso direto na planilha do Google Sheets!")
                
            except Exception as e:
                st.error(f"⚠️ Erro ao salvar na planilha. Detalhe: {e}")
