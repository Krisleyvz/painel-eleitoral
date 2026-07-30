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
    /* Estilo dos cartões de entrega para destacar na rua */
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

# 2. Logo Centralizada
col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image("IMG_6008.PNG", use_container_width=True)
    except:
        st.title("🚚 Logística de Entregas")

st.markdown("---")
st.subheader("📦 Rotas e Entregas Pendentes")

# 3. Filtro rápido por Regional para o motorista focar na rota dele
regional_filtro = st.selectbox(
    "Filtrar por Regional de Atendimento:", 
    ["Todas as Regionais", "Calafate", "São Francisco", "Baixada", "Estação Experimental", "Floresta", "Tancredo Neves"]
)

st.markdown("---")

# Simulação temporária de dados (Até integrarmos com a planilha no final)
# Depois, isso será puxado ao vivo do banco de dados
dados_exemplo = pd.DataFrame([
    {
        "ID": 1, "Nome": "Jordão Serém Pereira", "Telefone": "68999625598", 
        "Endereco": "Rua Flamengo, 637", "Bairro": "Laélia Alcântara", 
        "Regional": "Calafate", "Material": "Adesivo para Residência", 
        "Observacao": "Próximo do latão (15:30)", "Status": "Pendente"
    },
    {
        "ID": 2, "Nome": "Clever Braga Asbeque", "Telefone": "68999460193", 
        "Endereco": "Avenida Iguaçu da Glória, 329", "Bairro": "Vitória", 
        "Regional": "São Francisco", "Material": "Perfurado (3)", 
        "Observacao": "Para entregar no carro", "Status": "Pendente"
    }
])

# Aplica o filtro de regional se selecionado
if regional_filtro != "Todas as Regionais":
    dados_exemplo = dados_exemplo[dados_exemplo['Regional'] == regional_filtro]

# 4. Listagem interativa para o motorista dar baixa
if dados_exemplo.empty:
    st.info("🎉 Nenhuma entrega pendente nesta regional no momento!")
else:
    for index, row in dados_exemplo.iterrows():
        with st.container():
            st.markdown(f"""
            <div class="entrega-card">
                <b>👤 {row['Nome']}</b><br>
                📞 Tel: <a href="tel:{row['Telefone']}" style="color: #4da6ff;">{row['Telefone']}</a><br>
                📍 <b>Endereço:</b> {row['Endereco']} - {row['Bairro']} ({row['Regional']})<br>
                📦 <b>Material:</b> {row['Material']}<br>
                💬 <b>Obs:</b> {row['Observacao']}
            </div>
            """, unsafe_allow_html=True)
            
            # Botão de Ação Rápida para o Motorista
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                # Link automático que abre a rota no Google Maps/Wazes do celular
                endereco_completo = f"{row['Endereco']}, {row['Bairro']}, Rio Branco - AC"
                link_mapa = f"https://www.google.com/maps/search/?api=1&query={endereco_completo.replace(' ', '+')}"
                st.markdown(f"[🗺️ Abrir Rota]({link_mapa})", unsafe_allow_html=True)
                
            with col_b2:
                if st.button(f"✅ Confirmar Entrega", key=f"btn_{row['ID']}"):
                    st.success(f"Entrega para {row['Nome']} marcada como ENTREGUE!")
                    # Aqui, futuramente, o código atualizará o status na planilha em tempo real
            
            st.markdown("")
