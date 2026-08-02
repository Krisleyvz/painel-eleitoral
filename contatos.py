import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import numpy as np
import urllib.parse
import folium
from streamlit_folium import st_folium
import pytz
import gspread
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="App de Rua | Gestão", page_icon="📱", layout="centered")

# ==========================================
# SISTEMA DE LOGIN E SEGURANÇA
# ==========================================
def registrar_log(usuario):
    """Registra o acesso silenciosamente na mesma aba do Google Sheets."""
    fuso_acre = pytz.timezone('America/Rio_Branco')
    agora = datetime.now(fuso_acre)
    data_formatada = agora.strftime("%d/%m/%Y")
    hora_formatada = agora.strftime("%H:%M:%S")
    
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credenciais = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], 
            scopes=scopes
        )
        cliente = gspread.authorize(credenciais)
        
        # ID da sua planilha principal (a mesma do outro painel)
        planilha_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
        
        # Abre a aba de logs
        aba_logs = cliente.open_by_key(planilha_id).worksheet("Logs_Acesso")
        
        # Insere a nova linha indicando que o login foi no App de Rua
        aba_logs.append_row([f"{usuario} (App de Rua)", data_formatada, hora_formatada])
        
    except Exception as e:
        print(f"❌ Falha ao registrar log no Sheets: {e}")

def verificar_senha():
    """Retorna True se o usuário inserir as credenciais corretas."""
    def senha_inserida():
        usuario = st.session_state["usuario_input"].strip()
        senha = st.session_state["senha_input"].strip()
        
        if usuario in st.secrets["senhas"] and senha == st.secrets["senhas"][usuario]:
            st.session_state["autenticado"] = True
            st.session_state["usuario_logado"] = usuario
            del st.session_state["senha_input"] 
            registrar_log(usuario)
        else:
            st.session_state["autenticado"] = False

    if "autenticado" not in st.session_state:
        st.markdown("<br><br><h2 style='text-align: center; color: #FFFFFF;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Usuário", key="usuario_input")
            st.text_input("Senha", type="password", key="senha_input")
            st.button("Entrar no Sistema", on_click=senha_inserida, use_container_width=True)
        return False
    
    elif not st.session_state["autenticado"]:
        st.markdown("<br><br><h2 style='text-align: center; color: #FFFFFF;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("Usuário", key="usuario_input")
            st.text_input("Senha", type="password", key="senha_input")
            st.button("Entrar no Sistema", on_click=senha_inserida, use_container_width=True)
            st.error("😕 Usuário ou senha incorretos. Tente novamente.")
        return False
    
    return True

if not verificar_senha():
    st.stop()

# ==========================================
# INJEÇÃO DE CSS: TEMA AZUL MARINHO E CARTÕES LIMPOS
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0A1C2E !important; }
    h1, h2, h3, p, label, div.stMarkdown, .stMetricValue { color: #FFFFFF !important; }
    .contato-card {
        background-color: #152b45;
        padding: 12px 15px;
        border-radius: 8px;
        border-left: 4px solid #1A73E8;
        margin-bottom: 12px;
    }
    .card-aniversario-hoje {
        border-left: 5px solid #25D366 !important; 
        background-color: #1a3a30;
    }
    .apoiador-lider {
        background-color: #0e2439;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        border-left: 3px solid #25D366;
    }
    input, select {
        background-color: #152b45 !important;
        color: white !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 5px !important;
    }
    [data-testid="stExpander"] {
        background-color: #152b45 !important;
        border: 1px solid #1A73E8 !important;
        border-radius: 8px !important;
    }
    [data-testid="stExpander"] p {
        font-weight: bold !important;
        font-size: 16px !important;
    }
    .btn-disabled {
        display: block; text-align: center; background-color: #334e68; color: #8899a6; 
        padding: 6px; border-radius: 4px; font-size: 14px; font-weight: bold; cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================

# Função para tratar telefones
def tratar_telefone(tel_raw):
    tel_str = str(tel_raw).strip()
    if tel_str.lower() == 'nan' or tel_str == '':
        return "", "Sem telefone"
    tel_limpo = tel_str.split('.')[0]
    tel_num = ''.join(filter(str.isdigit, tel_limpo))
    if len(tel_num) < 8: 
        return "", tel_str
    return tel_num, tel_limpo

# Carregar os dados
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

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
    st.error(f"Erro ao conectar com a planilha. Detalhe: {e}")
    df = pd.DataFrame()

total_cadastros = len(df) if not df.empty else 0

# Identifica a coluna do Município dinamicamente para usar no app todo
col_mun = None
if not df.empty:
    for col in df.columns:
        if "Município" in str(col) or "Municipio" in str(col):
            col_mun = col
            break

# Função para formatar o cartão padrão limpo
def card_html(nome, tel_exibicao, cidade, bairro, extra=""):
    cidade_str = cidade if cidade and cidade.lower() != 'nan' else 'Rio Branco'
    return f"""
    <div class="contato-card">
        <b>👤 {nome}</b> {extra}<br>
        📞 {tel_exibicao} &nbsp;|&nbsp; 📍 {cidade_str} - {bairro}
    </div>
    """

aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(["🎂 Aniver.", "📍 Bairros", "📞 Contatos", "🗺️ Mapa", "🏆 Lid.", "🤝 Reuniões"])

# --- ABA 1: ANIVERSARIANTES ---
with aba1:
    st.subheader("🎂 Aniversariantes")
    if not df.empty and 'Data de Nascimento' in df.columns:
        df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
        if not df_aniver.empty:
            fuso_acre = timezone(timedelta(hours=-5))
            hoje = datetime.now(fuso_acre)
            hoje_data = datetime(hoje.year, hoje.month, hoje.day)
            
            def calc_dias_para_aniv(data_str):
                try:
                    partes = str(data_str).strip().split('/')
                    dia, mes = int(partes[0]), int(partes[1])
                    if mes == 2 and dia == 29: dia = 28
                    aniv = datetime(hoje.year, mes, dia)
                    if aniv < hoje_data: aniv = datetime(hoje.year + 1, mes, dia)
                    return (aniv - hoje_data).days
                except: return 99999 
            
            df_aniver['DiasFaltando'] = df_aniver['Data de Nascimento'].apply(calc_dias_para_aniv)
            df_aniver = df_aniver.sort_values(by='DiasFaltando')
            
            for idx, row in df_aniver.iterrows():
                if row['DiasFaltando'] == 99999: continue
                
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                bairro = str(row.get('Bairro', ''))
                cidade = str(row.get(col_mun, 'Rio Branco')).strip()
                nascimento = str(row.get('Data de Nascimento', ''))
                dias = row['DiasFaltando']
                tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
                
                texto_dias = "🔥 **É HOJE!**" if dias == 0 else f"Faltam {dias} dias"
                extra_html = f"<span style='float: right; color: #4da6ff; font-size: 14px;'>{nascimento} ({texto_dias})</span>"
                
                if dias == 0:
                    st.markdown(card_html(nome, tel_exibicao, cidade, bairro, extra_html).replace('contato-card', 'contato-card card-aniversario-hoje').replace('👤', '🎂'), unsafe_allow_html=True)
                else:
                    st.markdown(card_html(nome, tel_exibicao, cidade, bairro, extra_html).replace('👤', '🎂'), unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    if tel_num:
                        texto_aniver = urllib.parse.quote(f"Olá {nome.split()[0]}! Em nome do Vereador Samir Bestene e de toda a nossa equipe, desejo um feliz aniversário! Que sua vida seja repleta de alegrias, muita saúde e sucesso. 🎉 Gostaríamos muito de preparar uma homenagem para você nas redes sociais do Samir. Você tem alguma objeção? Se estiver tudo bem, nos mande aqui uma foto sua que você mais gosta para montarmos a arte! É uma honra ter você caminhando ao nosso lado. A luta continua 🚀")
                        st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Mandar Parabéns</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")

# --- ABA 2: BAIRROS ---
with aba2:
    st.subheader("📍 Filtro por Bairro")
    if not df.empty and 'Bairro' in df.columns:
        bairros_disp = ["Todos"] + sorted([str(b).strip() for b in df['Bairro'].dropna().unique() if str(b).strip() != ''])
        bairro_sel = st.selectbox("Selecione o Bairro:", bairros_disp)
        filtrados = df if bairro_sel == "Todos" else df[df['Bairro'].astype(str).str.strip() == bairro_sel]
        
        st.markdown(f"**Total encontrado:** {len(filtrados)} pessoa(s)")
        
        for idx, row in filtrados.iterrows():
            nome, bairro = str(row.get('Nome Completo', 'Sem Nome')), str(row.get('Bairro', ''))
            cidade = str(row.get(col_mun, 'Rio Branco')).strip()
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num: st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={urllib.parse.quote(f'Olá {nome.split()[0]}, tudo bem?')}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            st.markdown("")

# --- ABA 3: CONTATOS ---
with aba3:
    st.subheader("📞 Pesquisa de Contatos")
    busca = st.text_input("🔍 Digite o nome para buscar:", placeholder="Ex: Maria...")
    if not df.empty and 'Nome Completo' in df.columns:
        df_contatos = df[df['Nome Completo'].str.contains(busca, case=False, na=False)] if busca else df
        st.markdown(f"**Exibindo {len(df_contatos)} contato(s)**")
        
        for idx, row in df_contatos.iterrows():
            nome, bairro = str(row.get('Nome Completo', 'Sem Nome')), str(row.get('Bairro', ''))
            cidade = str(row.get(col_mun, 'Rio Branco')).strip()
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num: st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={urllib.parse.quote(f'Olá {nome.split()[0]}, tudo bem?')}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            st.markdown("")

# --- ABA 4: MAPA ---
with aba4:
    st.subheader("🗺️ Dispersão de Apoiadores")
    st.markdown("Toque nos pontos coloridos para abrir as informações.")
    st.markdown("""
    <div style='background-color: #152b45; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px; text-align: center;'>
        <b>Legenda Tática:</b><br>
        <span style="color:#DC3545; font-size: 18px;">●</span> Liderança &nbsp;|&nbsp; <span style="color:#6F42C1; font-size: 18px;">●</span> Parceria<br>
        <span style="color:#28A745; font-size: 18px;">●</span> Manutenção &nbsp;|&nbsp; <span style="color:#007BFF; font-size: 18px;">●</span> Padrão
    </div>
    """, unsafe_allow_html=True)
    
    if not df.empty and 'Bairro' in df.columns:
        coord_referencia = {'SENA MADUREIRA': (-9.0658, -68.6571), 'CRUZEIRO DO SUL': (-7.6311, -72.6714), 'TARAUACÁ': (-8.1614, -70.7656), 'XAPURI': (-10.6515, -68.5044), 'PORTO ACRE': (-9.5878, -67.5333), 'BRASILÉIA': (-11.0116, -68.7483), 'CENTRO': (-9.9749, -67.8243), 'DOCA FURTADO': (-9.9650, -67.8100), 'FLORESTA': (-9.9820, -67.8400), 'PARQUE DOS SABIÁS': (-9.9550, -67.8000), 'VILA ACRE': (-10.0100, -67.7800), 'UNIVERSITÁRIO': (-9.9500, -67.8600), 'ESTAÇÃO EXPERIMENTAL': (-9.9580, -67.8250), 'CALAFATE': (-9.9600, -67.8700), 'BAIXADA': (-9.9800, -67.8000), 'SÃO FRANCISCO': (-9.9600, -67.8500), 'TANCREDO NEVES': (-9.9400, -67.8400)}
        mapa = folium.Map(location=[-9.9749, -67.8243], zoom_start=12, tiles="CartoDB positron")
        np.random.seed(42) 
        
        for idx, row in df.iterrows():
            mun = str(row.get(col_mun, 'Rio Branco')).strip().upper()
            bairro = str(row.get('Bairro', '')).strip().upper()
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            classificacao = str(row.get('Classificação Interna', '')).strip().upper()
            
            if "LIDER" in classificacao or "LIDERANÇA" in classificacao: cor_ponto = "#DC3545" 
            elif "PARCERIA" in classificacao or "ESTRATÉGICA" in classificacao or "ESTRATEGICA" in classificacao: cor_ponto = "#6F42C1" 
            elif "MANUTENÇÃO" in classificacao or "MANUTENCAO" in classificacao: cor_ponto = "#28A745" 
            else: cor_ponto = "#007BFF" 
            
            base_lat, base_lon = coord_referencia[mun] if mun != 'RIO BRANCO' and mun in coord_referencia else coord_referencia.get(bairro, coord_referencia['CENTRO'])
            lat_final = base_lat + np.random.normal(0, 0.005)
            lon_final = base_lon + np.random.normal(0, 0.005)
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            cidade_popup = str(row.get(col_mun, 'Rio Branco')).strip()
            if cidade_popup.lower() == 'nan' or cidade_popup == '': cidade_popup = 'Rio Branco'
            
            btn_html = f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={urllib.parse.quote(f'Olá {nome.split()[0]}, tudo bem?')}' target='_blank' style='background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-family: Arial; font-size: 13px; display: block; text-align: center; margin-top: 8px;'>💬 Abrir WhatsApp</a>" if tel_num else "<div style='background-color: #ccc; color: #666; padding: 6px; border-radius: 4px; font-family: Arial; font-size: 13px; text-align: center; margin-top: 8px;'>Sem Número</div>"
            popup_html = f"<div style='min-width: 150px; font-family: Arial;'><strong style='font-size: 15px; color: #0A1C2E;'>{nome}</strong><br><span style='font-size: 13px; color: #555;'>📍 {cidade_popup} - {bairro.title()}</span><br><span style='font-size: 13px; color: #555;'>📞 {tel_exibicao}</span>{btn_html}</div>"
            
            folium.CircleMarker(location=[lat_final, lon_final], radius=7, popup=folium.Popup(popup_html, max_width=250), color="white", weight=1, fill=True, fill_color=cor_ponto, fill_opacity=0.9).add_to(mapa)
        st_folium(mapa, use_container_width=True, height=500, returned_objects=[])

# --- ABA 5: RANKING DE LIDERANÇAS ---
with aba5:
    st.subheader("🏆 Ranking de Lideranças")
    col_indicacao = next((col for col in df.columns if "Através de quem" in str(col)), None)
    if not df.empty and col_indicacao:
        df_lideres = df.dropna(subset=[col_indicacao]).copy()
        df_lideres = df_lideres[df_lideres[col_indicacao].astype(str).str.strip() != ""]
        df_lideres[col_indicacao] = df_lideres[col_indicacao].astype(str).str.strip().str.title()
        
        if not df_lideres.empty:
            ranking = df_lideres.groupby(col_indicacao).size().reset_index(name='Qtd').sort_values(by='Qtd', ascending=False).reset_index(drop=True)
            top1 = ranking.iloc[0]
            st.metric(label="🥇 Liderança Destaque", value=top1[col_indicacao], delta=f"{top1['Qtd']} indicações ({(top1['Qtd'] / total_cadastros) * 100:.1f}% da base)")
            st.markdown("---")
            
            for idx, row in ranking.iterrows():
                lider, qtd = row[col_indicacao], row['Qtd']
                with st.expander(f"#{idx + 1} | {lider} - {qtd} pessoa(s) ({(qtd / total_cadastros) * 100:.1f}%)"):
                    for _, apoiado in df_lideres[df_lideres[col_indicacao] == lider].iterrows():
                        nome_ap = str(apoiado.get('Nome Completo', 'Sem Nome'))
                        bairro_ap = str(apoiado.get('Bairro', ''))
                        cidade_ap = str(apoiado.get(col_mun, 'Rio Branco')).strip()
                        if cidade_ap.lower() == 'nan' or cidade_ap == '': cidade_ap = 'Rio Branco'
                        
                        tel_num_ap, tel_exibicao_ap = tratar_telefone(apoiado.get('Telefone', ''))
                        tel_html = f"📞 <a href='https://api.whatsapp.com/send?phone=55{tel_num_ap}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{tel_exibicao_ap}</a>" if tel_num_ap else "📞 <span style='color: #8899a6;'>Sem Número</span>"
                        
                        st.markdown(f"<div class='apoiador-lider'><b>{nome_ap}</b><br><span style='font-size: 14px; color: #a9b9cc;'>📍 {cidade_ap} - {bairro_ap} | {tel_html}</span></div>", unsafe_allow_html=True)
        else: st.info("Ainda não há dados suficientes de indicações preenchidos.")
    else: st.warning("A coluna de indicação não foi encontrada.")

# --- ABA 6: REUNIÕES E AJUNTAMENTOS ---
with aba6:
    st.subheader("🤝 Agendar Reuniões")
    col_participacao = next((col for col in df.columns if "participar" in str(col).lower()), None)
            
    if not df.empty and col_participacao:
        df_reunioes = df[df[col_participacao].astype(str).str.contains("reunião|reuniao", case=False, na=False)].copy()
        if not df_reunioes.empty:
            df_reunioes = df_reunioes.sort_values(by='Nome Completo')
            st.markdown(f"**Total de interessados:** {len(df_reunioes)}")
            
            for idx, row in df_reunioes.iterrows():
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                bairro = str(row.get('Bairro', ''))
                cidade = str(row.get(col_mun, 'Rio Branco')).strip()
                if cidade.lower() == 'nan' or cidade == '': cidade = 'Rio Branco'
                tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
                
                st.markdown(card_html(nome, tel_exibicao, cidade, bairro), unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    if tel_num:
                        texto_reuniao = urllib.parse.quote(f"Olá {nome.split()[0]}, tudo bem? Aqui é da equipe do Samir Bestene. Vimos no seu cadastro que você tem interesse em organizar uma reunião aí na sua rua/bairro! Ficamos muito animados com esse apoio. Vamos fazer acontecer? Qual seria o melhor dia da semana e horário para você reunir alguns amigos e vizinhos para um bate-papo com o Samir? Estamos à disposição para agendar. A luta continua 🚀")
                        st.markdown(f"<a href='https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_reuniao}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Agendar Reunião</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num: st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else: st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")
        else: st.info("Nenhum apoiador sinalizou interesse em organizar reunião até o momento.")
