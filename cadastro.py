import streamlit as st

# 1. Configuração da Página (Focada em Mobile)
st.set_page_config(page_title="App de Rua | Cadastro", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E BOTÕES
# ==========================================
st.markdown("""
<style>
    /* Muda a cor de fundo de todo o aplicativo para Azul Marinho */
    .stApp {
        background-color: #0A1C2E !important;
    }
    
    /* Força todos os textos, títulos e rótulos a ficarem brancos para dar contraste */
    h1, h2, h3, p, label, div.stMarkdown, .stCheckbox label span {
        color: #FFFFFF !important;
    }
    
    /* Estilo do botão de Salvar gigante e chamativo */
    div[data-testid="stFormSubmitButton"] button {
        background-color: #1A73E8 !important; /* Azul mais claro para dar destaque no fundo escuro */
        color: white !important;
        height: 55px !important;
        font-size: 20px !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 8px !important;
    }
    
    /* Suaviza as caixinhas de preenchimento para não ficarem brancas demais no olho */
    input, select, textarea {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# 2. Cabeçalho Visual (Foto + Logo)
# Cria duas colunas para o celular: Foto na esquerda, Logo na direita
col1, col2 = st.columns([1, 1.2], vertical_alignment="center")

with col1:
    try:
        st.image("IMG_7402.jpg", use_container_width=True)
    except:
        pass

with col2:
    try:
        st.image("IMG_6009.jpg", use_container_width=True)
    except:
        st.title("📝 Cadastro")

st.markdown("---")

# 3. Criação do Formulário de Coleta
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
    
    # --- LÓGICA DA REGIONAL ---
    opcoes_regionais = ["Selecione", "Calafate", "São Francisco", "Baixada", "Estação Experimental", "Floresta", "Tancredo Neves", "Outra"]
    regional_selecionada = st.selectbox("Regional*", opcoes_regionais)
    
    regional_outra = st.text_input("Se escolheu 'Outra' acima, digite aqui o nome:")
    
    st.subheader("📦 Pedido de Material")
    adesivo = st.checkbox("Adesivo para Residência")
    perfurado = st.checkbox("Perfurado (Carro)")
    santinho = st.checkbox("Santinhos/Adesivos Menores")
    
    st.subheader("📌 Informações Adicionais")
    observacao = st.text_area("Observações / Ponto de Referência", placeholder="Ex: Av. Ceará, perto do latão")
    
    submit = st.form_submit_button("✅ SALVAR CADASTRO", use_container_width=True)
    
    # 4. Lógica ao Clicar no Botão Salvar
    if submit:
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
            st.success(f"🎉 Registo de {nome} realizado com sucesso!")
            st.info("Status do pedido: Pendente de Entrega 🚚")
