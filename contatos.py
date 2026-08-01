import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np

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
    .card-aniversario-hoje {
        border-left: 5px solid #25D366 !important; /* Destaque verde para aniversariantes do dia */
        background-color: #1a3a30;
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

# Função para carregar os dados direto via link público
@st.cache_data(ttl=30)
def carregar_dados_planilha():
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

# --- ABA 1: ANIVERSARIANTES (ORDENADOS POR DATA) ---
with aba1:
    st.subheader("🎂 Aniversariantes")
    st.markdown("Próximos a celebrar (Ordenado pela data mais próxima):")
    
    if not df.empty and 'Data de Nascimento' in df.columns:
        df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
        
        if not df_aniver.empty:
            hoje = datetime.now()
            hoje_data = datetime(hoje.year, hoje.month, hoje.day)
            
            # Lógica para calcular quantos dias faltam para o próximo aniversário
            def calc_dias_para_aniv(data_str):
                try:
                    partes = str(data_str).strip().split('/')
                    dia = int(partes[0])
                    mes = int(partes[1])
                    
                    # Trata o ano bissexto para evitar quebrar o app
                    if mes == 2 and dia == 29: 
                        dia = 28
                        
                    aniv = datetime(hoje.year, mes, dia)
                    # Se já fez aniversário esse ano, joga a meta para o ano que vem
                    if aniv < hoje_data:
                        aniv = datetime(hoje.year + 1, mes, dia)
                    return (aniv - hoje_data).days
                except:
                    return 99999 # Se digitaram a data errada, joga pro fim da lista
            
            # Aplica o cálculo e ordena
            df_aniver['DiasFaltando'] = df_aniver['Data de Nascimento'].apply(calc_dias_para_aniv)
            df_aniver = df_aniver.sort_values(by='DiasFaltando')
            
            for idx, row in df_aniver.iterrows():
                # Pula dados totalmente inválidos
                if row['DiasFaltando'] == 99999:
                    continue
                    
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                telefone = str(row.get('Telefone', ''))
                bairro = str(row.get('Bairro', ''))
                nascimento = str(row.get('Data de Nascimento', ''))
                dias = row['DiasFaltando']
                
                tel_num = ''.join(filter(str.isdigit, telefone))
                
                # Destaca visualmente se o aniversário for HOJE
                classe_css = "contato-card card-aniversario-hoje" if dias == 0 else "contato-card"
                texto_dias = "🔥 **É HOJE!**" if dias == 0 else f"Faltam {dias} dias"
                
                st.markdown(f"""
                <div class="{classe_css}">
                    <b>🎂 {nome}</b> <span style="float: right; color: #4da6ff; font-size: 14px;">{nascimento} ({texto_dias})</span><br>
                    📍 Bairro: {bairro} | 📞 {telefone}
                </div>
                """, unsafe_allow_html=True)
                
                # Botões compactos lado a lado
                bc1, bc2 = st.columns(2)
                with bc1:
                    link_wpp_aniver = f"https://wa.me/55{tel_num}?text=Parabéns%20{nome.split()[0]}!%20Muitas%20felicidades!"
                    st.markdown(f"<a href='{link_wpp_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Mandar Parabéns</a>", unsafe_allow_html=True)
                with bc2:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                st.markdown("")
        else:
            st.info("Nenhuma data de nascimento válida encontrada.")
    else:
        st.info("Coluna de data de nascimento não localizada na planilha.")

# --- ABA 2: BAIRROS (ORDENADOS ALFABETICAMENTE) ---
with aba2:
    st.subheader("📍 Filtro por Bairro")
    if not df.empty and 'Bairro' in df.columns:
        # A Mágica da Ordem Alfabética A-Z
        lista_bairros = sorted([str(b).strip() for b in df['Bairro'].dropna().unique() if str(b).strip() != ''])
        bairros_disp = ["Todos"] + lista_bairros
        
        bairro_sel = st.selectbox("Selecione o Bairro:", bairros_disp)
        
        filtrados = df if bairro_sel == "Todos" else df[df['Bairro'].str.strip() == bairro_sel]
        
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

# --- ABA 4: MAPA (COM DADOS GEOLOCALIZADOS) ---
with aba4:
    st.subheader("🗺️ Dispersão de Apoiadores")
    st.markdown("Mapa estimado baseado nos bairros de residência (para fins de visualização tática).")
    
    if not df.empty and 'Bairro' in df.columns:
        # Coordenadas aproximadas de ancoragem para Rio Branco
        coord_referencia = {
            'DOCA FURTADO': (-9.9650, -67.8100),
            'FLORESTA': (-9.9820, -67.8400),
            'PARQUE DOS SABIÁS': (-9.9550, -67.8000),
            'VILA ACRE': (-10.0100, -67.7800),
            'UNIVERSITÁRIO': (-9.9500, -67.8600),
            'CENTRO': (-9.9749, -67.8243)
        }
        
        latitudes = []
        longitudes = []
        
        np.random.seed(42) # Mantém os pontos no mesmo lugar ao recarregar a página
        
        for bairro in df['Bairro']:
            b_upper = str(bairro).strip().upper()
            # Pega a âncora do bairro (se não tiver, joga pro Centro)
            base_lat, base_lon = coord_referencia.get(b_upper, (-9.9749, -67.8243))
            
            # Espalhamento para os pontos não sumirem um debaixo do outro (aprox 200 metros)
            latitudes.append(base_lat + np.random.normal(0, 0.002))
            longitudes.append(base_lon + np.random.normal(0, 0.002))
            
        mapa_df = pd.DataFrame({'lat': latitudes, 'lon': longitudes})
        st.map(mapa_df, zoom=12)
    else:
        st.warning("Não há dados suficientes de bairro para gerar a mancha do mapa.")
