import streamlit as st
from datetime import datetime

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Cadastro", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: BOTÕES MAIORES PARA CELULAR
# ==========================================
st.markdown("""
<style>
    /* Aumenta o tamanho do botão de salvar para facilitar o clique na rua */
    div[data-testid="stFormSubmitButton"] button {
        background-color: #1A73E8;
        color: white;
        height: 50px;
        font-size: 18px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

st.title("📝 Novo Cadastro")
st.markdown("Preencha os dados abaixo para registrar uma nova liderança ou pedido de material.")

# 2. Criação do Formulário de Coleta
# O 'clear_on_submit=True' faz com que a tela limpe sozinha após salvar, pronta para o próximo
with st.form(key="form_cadastro", clear_on_submit=True):
    
    st.subheader("👤 Dados Pessoais")
    nome = st.text_input("Nome Completo*")
    # Coloquei o DDD 68 como padrão visual para facilitar
    telefone = st.text_input("WhatsApp (Apenas números)*", placeholder="Ex: 68999999999")
    
    st.subheader("📍 Endereço")
    col1, col2 = st.columns([3, 1])
    with col1:
        rua = st.text_input("Rua/Avenida")
    with col2:
        numero = st.text_input("Número")
    
    bairro = st.text_input("Bairro")
    regional = st.selectbox("Regional", ["Selecione", "Calafate", "São Francisco", "Baixada", "Estação Experimental", "Floresta", "Tancredo Neves", "Outra"])
    
    st.subheader("📦 Pedido de Material")
    # Caixinhas de seleção iguais às do seu formulário de papel/AppSheet
    adesivo = st.checkbox("Adesivo para Residência")
    perfurado = st.checkbox("Perfurado (Carro)")
    santinho = st.checkbox("Santinhos/Adesivos Menores")
    
    st.subheader("📌 Informações Adicionais")
    observacao = st.text_area("Observações / Ponto de Referência", placeholder="Ex: Av. Ceará, perto do latão (15:30)")
    
    # O use_container_width=True faz o botão ocupar a largura toda da tela do celular
    submit = st.form_submit_button("✅ Salvar Cadastro", use_container_width=True)
    
    # 3. Lógica ao Clicar no Botão Salvar
    if submit:
        # Trava de segurança: não deixa salvar se esquecer o nome ou telefone
        if nome == "" or telefone == "":
            st.warning("⚠️ Os campos Nome e WhatsApp são obrigatórios para o cadastro!")
        else:
            # Aqui entrará a automação para jogar os dados na sua planilha do Google Sheets!
            st.success(f"🎉 Cadastro de {nome} realizado com sucesso!")
            st.info("Status do pedido: Pendente de Entrega 🚚")
