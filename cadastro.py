import streamlit as st

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Cadastro", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: BOTÕES MAIORES PARA CELULAR
# ==========================================
st.markdown("""
<style>
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
st.markdown("Preencha os dados abaixo para registar uma nova liderança ou pedido de material.")

# 2. Criação do Formulário de Coleta
with st.form(key="form_cadastro", clear_on_submit=True):
    
    st.subheader("👤 Dados Pessoais")
    nome = st.text_input("Nome Completo*")
    telefone = st.text_input("WhatsApp (Apenas números)*", placeholder="Ex: 68999999999")
    
    st.subheader("📍 Endereço")
    col1, col2 = st.columns([3, 1])
    with col1:
        rua = st.text_input("Rua/Avenida")
    with col2:
        numero = st.text_input("Número")
    
    bairro = st.text_input("Bairro")
    
    # --- CORREÇÃO: LÓGICA DA REGIONAL ---
    opcoes_regionais = ["Selecione", "Calafate", "São Francisco", "Baixada", "Estação Experimental", "Floresta", "Tancredo Neves", "Outra"]
    regional_selecionada = st.selectbox("Regional*", opcoes_regionais)
    
    # A caixa fica sempre visível, mas com uma instrução de preenchimento condicional
    regional_outra = st.text_input("Se escolheu 'Outra' acima, digite aqui o nome da regional:")
    # ------------------------------------
    
    st.subheader("📦 Pedido de Material")
    adesivo = st.checkbox("Adesivo para Residência")
    perfurado = st.checkbox("Perfurado (Carro)")
    santinho = st.checkbox("Santinhos/Adesivos Menores")
    
    st.subheader("📌 Informações Adicionais")
    observacao = st.text_area("Observações / Ponto de Referência", placeholder="Ex: Av. Ceará, perto do latão (15:30)")
    
    submit = st.form_submit_button("✅ Salvar Cadastro", use_container_width=True)
    
    # 3. Lógica ao Clicar no Botão Salvar
    if submit:
        # Define a regional final com base no preenchimento
        if regional_selecionada == "Outra":
            regional_final = regional_outra
        else:
            regional_final = regional_selecionada

        # Travas de segurança e validação
        if nome.strip() == "" or telefone.strip() == "":
            st.error("⚠️ Os campos Nome e WhatsApp são obrigatórios!")
        elif regional_selecionada == "Selecione":
            st.error("⚠️ Por favor, selecione uma Regional.")
        elif regional_selecionada == "Outra" and regional_outra.strip() == "":
            st.error("⚠️ Selecionou 'Outra'. Por favor, digite o nome da regional na caixa abaixo.")
        else:
            st.success(f"🎉 Registo de {nome} realizado com sucesso na regional {regional_final}!")
            st.info("Status do pedido: Pendente de Entrega 🚚")
