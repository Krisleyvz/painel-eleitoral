import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

# 1. Configuração Global da Página (Focada em Mobile)
st.set_page_config(page_title="Comitê Digital | Samir Bestene", page_icon="📱", layout="centered")

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO PADRÃO
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0A1C2E !important; }
    h1, h2, h3, p, label, div.stMarkdown, .stRadio label span { color: #FFFFFF !important; }
    .card-item {
        background-color: #152b45;
        padding: 12px 15px;
        border-radius: 8px;
        border-left: 4px solid #1A73E8;
        margin-bottom: 12px;
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

# Função Universal para Ler a Planilha (Via Link Público - Zero Erros)
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    spreadsheet_id = "COLOQUE_O_ID_DA_PLANILHA_AQUI"  # Substitua pelo ID longo da sua URL
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

# Função para Salvar Cadastro na Planilha (Via API do Google Sheets)
def conectar_google_sheets():
    scope = ["https://www.spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["gcp_json"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    planilha = client.open("Samir Bestene - Apoiadores (Respostas)")
    return planilha.worksheet("Form_Responses")

# ==========================================
# MENU DE NAVEGAÇÃO LATERAL (O ÚNICO LINK QUE IMPORTA)
# ==========================================
st.sidebar.markdown("## 🧭 Menu de Navegação")
menu = st.sidebar.radio("Escolha a seção:", ["📝 Novo Cadastro", "🚚 Logística de Entregas", "📱 Gestão de Contatos", "📊 Painel Geral"])

st.sidebar.markdown("---")
st.sidebar.info("💡 Samir Bestene | Comitê 2026")

# ==========================================
# SEÇÃO 1: NOVO CADASTRO
# ==========================================
if menu == "📝 Novo Cadastro":
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        try:
            st.image("IMG_6009.PNG", use_container_width=True)
        except:
            st.title("📝 Cadastro")
    
    st.markdown("---")
    
    with st.form(key="form_cad_unico", clear_on_submit=True):
        st.subheader("👤 Dados Pessoais")
        nome = st.text_input("Nome Completo*")
        telefone = st.text_input("WhatsApp (Apenas números)*", placeholder="Ex: 68999999999")
        nascimento = st.text_input("Data de Nascimento", placeholder="Ex: 07/06/1991")
        
        st.subheader("📍 Endereço")
        cep = st.text_input("CEP", placeholder="Ex: 69900000")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            rua_numero = st.text_input("Rua e Número* (Ex: Av. Ceará, 4449)")
        with c2:
            bairro = st.text_input("Bairro*")
            
        complemento = st.text_input("Complemento / Ponto de Referência")
        
        st.subheader("📌 Participação")
        participacao = st.selectbox("Como gostaria de participar?", [
            "Apenas receber propostas no WhatsApp",
            "Quero materiais de campanha (adesivos, etc.)",
            "Quero ser um multiplicador / voluntário no meu bairro",
            "Gostaria de organizar uma reunião na minha rua/bairro",
            "Abrir portas para juventude"
        ])
        
        indicacao = st.text_input("Através de quem você conheceu o nosso projeto?")
        
        submit = st.form_submit_button("✅ SALVAR CADASTRO", use_container_width=True)
        
        if submit:
            if not nome.strip() or not telefone.strip() or not rua_numero.strip() or not bairro.strip():
                st.error("⚠️ Preencha os campos obrigatórios (Nome, WhatsApp, Rua e Bairro)!")
            else:
                try:
                    sheet = conectar_google_sheets()
                    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    endereco_completo = f"{rua_numero}, {bairro}, Rio Branco - AC, {cep}"
                    
                    novo_registro = [
                        data_atual, nome, telefone, cep, rua_numero, bairro, 
                        complemento, participacao, "Aceito", nascimento, 
                        endereco_completo, "", indicacao, "Rio Branco"
                    ]
                    sheet.append_row(novo_registro)
                    st.success(f"🎉 Registro de {nome} salvo com sucesso na planilha!")
                except Exception as e:
                    st.error(f"⚠️ Erro ao salvar: {e}")

# ==========================================
# SEÇÃO 2: LOGÍSTICA DE ENTREGAS
# ==========================================
elif menu == "🚚 Logística de Entregas":
    st.title("🚚 Logística de Entregas")
    st.markdown("Rotas e endereços atualizados em tempo real.")
    st.markdown("---")
    
    df = carregar_dados_planilha()
    if not df.empty:
        bairros_disp = ["Todos"] + list(df['Bairro'].dropna().unique()) if 'Bairro' in df.columns else ["Todos"]
        bairro_filtro = st.selectbox("Filtrar por Bairro para Logística:", bairros_disp)
        
        if bairro_filtro != "Todos" and 'Bairro' in df.columns:
            df = df[df['Bairro'] == bairro_filtro]
            
        st.markdown("---")
        for idx, row in df.iterrows():
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            telefone = str(row.get('Telefone', ''))
            rua = str(row.get('Rua e Número', ''))
            bairro = str(row.get('Bairro', ''))
            complemento = str(row.get('Complemento', ''))
            tel_num = ''.join(filter(str.isdigit, telefone))
            
            st.markdown(f"""
            <div class="card-item">
                <b>👤 {nome}</b><br>
                📞 Tel: <a href="tel:{tel_num}" style="color: #4da6ff;">{telefone}</a><br>
                📍 <b>Endereço:</b> {rua} - {bairro}<br>
                💬 <b>Complemento:</b> {complemento if complemento != 'nan' else 'Nenhum'}
            </div>
            """, unsafe_allow_html=True)
            
            end_mapa = f"{rua}, {bairro}, Rio Branco - AC"
            link_mapa = f"https://www.google.com/maps/search/?api=1&query={end_mapa.replace(' ', '+')}"
            link_wpp = f"https://wa.me/55{tel_num}?text=Olá%20{nome.split()[0]},%20estamos%20a%20caminho!"
            
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown(f"<a href='{link_mapa}' target='_blank' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>🗺️ Rota</a>", unsafe_allow_html=True)
            with bc2:
                st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
            st.markdown("")
    else:
        st.info("Nenhum registro encontrado.")

# ==========================================
# SEÇÃO 3: GESTÃO DE CONTATOS
# ==========================================
elif menu == "📱 Gestão de Contatos":
    st.title("📱 Gestão de Contatos")
    st.markdown("Lista completa de apoiadores e aniversariantes.")
    st.markdown("---")
    
    df = carregar_dados_planilha()
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🎂 Aniversariantes", "🔍 Pesquisar", "📍 Por Bairro"])
    
    with sub_tab1:
        if not df.empty and 'Data de Nascimento' in df.columns:
            df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
            for idx, row in df_aniver.iterrows():
                nome = str(row.get('Nome Completo', ''))
                telefone = str(row.get('Telefone', ''))
                bairro = str(row.get('Bairro', ''))
                nascimento = str(row.get('Data de Nascimento', ''))
                tel_num = ''.join(filter(str.isdigit, telefone))
                
                st.markdown(f"""
                <div class="card-item">
                    <b>🎂 {nome}</b> <span style="float: right; color: #4da6ff;">{nascimento}</span><br>
                    📍 Bairro: {bairro} | 📞 {telefone}
                </div>
                """, unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    st.markdown(f"<a href='https://wa.me/55{tel_num}?text=Parabéns%20{nome.split()[0]}!' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>💬 Parabéns</a>", unsafe_allow_html=True)
                with bc2:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                st.markdown("")
        else:
            st.info("Nenhum aniversariante cadastrado.")
            
    with sub_tab2:
        busca = st.text_input("Digite o nome do apoiador:", placeholder="Pesquisar...")
        if not df.empty and 'Nome Completo' in df.columns:
            res = df[df['Nome Completo'].str.contains(busca, case=False, na=False)] if busca else df
            st.markdown(f"**Encontrados: {len(res)}**")
            for idx, row in res.iterrows():
                nome = str(row.get('Nome Completo', ''))
                telefone = str(row.get('Telefone', ''))
                bairro = str(row.get('Bairro', ''))
                tel_num = ''.join(filter(str.isdigit, telefone))
                
                st.markdown(f"""
                <div class="card-item">
                    <b>👤 {nome}</b><br>📍 Bairro: {bairro} | 📞 {telefone}
                </div>
                """, unsafe_allow_html=True)
                bc1, bc2 = st.columns(2)
                with bc1:
                    st.markdown(f"<a href='https://wa.me/55{tel_num}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                with bc2:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                st.markdown("")

    with sub_tab3:
        if not df.empty and 'Bairro' in df.columns:
            bairros_l = list(df['Bairro'].dropna().unique())
            b_sel = st.selectbox("Escolha o Bairro:", bairros_l)
            res_b = df[df['Bairro'] == b_sel]
            st.markdown(f"**Total no bairro {b_sel}: {len(res_b)}**")
            for idx, row in res_b.iterrows():
                nome = str(row.get('Nome Completo', ''))
                telefone = str(row.get('Telefone', ''))
                tel_num = ''.join(filter(str.isdigit, telefone))
                st.markdown(f"""
                <div class="card-item">
                    <b>👤 {nome}</b><br>📞 {telefone}
                </div>
                """, unsafe_allow_html=True)

# ==========================================
# SEÇÃO 4: PAINEL GERAL
# ==========================================
elif menu == "📊 Painel Geral":
    st.title("📊 Painel Geral da Campanha")
    st.markdown("Indicadores consolidados da base de apoiadores.")
    st.markdown("---")
    
    df = carregar_dados_planilha()
    if not df.empty:
        total = len(df)
        st.metric(label="Total de Cadastros", value=total)
        st.markdown("---")
        st.subheader("📍 Apoiadores por Bairro")
        if 'Bairro' in df.columns:
            contagem_bairros = df['Bairro'].value_counts().reset_index()
            contagem_bairros.columns = ['Bairro', 'Total']
            st.dataframe(contagem_bairros, use_container_width=True)
    else:
        st.info("Aguardando dados na planilha.")
