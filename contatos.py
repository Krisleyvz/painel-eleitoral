import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import urllib.parse
import folium
from streamlit_folium import st_folium

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
        display: block; 
        text-align: center; 
        background-color: #334e68; 
        color: #8899a6; 
        padding: 6px; 
        border-radius: 4px; 
        font-size: 14px; 
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
    tel_limpo = tel_str.split('.')[0]
    tel_num = ''.join(filter(str.isdigit, tel_limpo))
    if len(tel_num) < 8: 
        return "", tel_str
    return tel_num, tel_limpo

# Função para carregar os dados direto via link público
@st.cache_data(ttl=30)
def carregar_dados_planilha():
    spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
    sheet_name = "Form_Responses"
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

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
aba1, aba2, aba3, aba4, aba5 = st.tabs(["🎂 Aniver.", "📍 Bairros", "📞 Contatos", "🗺️ Mapa", "🏆 Lideranças"])

# --- ABA 1: ANIVERSARIANTES ---
with aba1:
    st.subheader("🎂 Aniversariantes")
    st.markdown("Próximos a celebrar (Ordenado pela data mais próxima):")
    
    if not df.empty and 'Data de Nascimento' in df.columns:
        df_aniver = df.dropna(subset=['Data de Nascimento']).copy()
        
        if not df_aniver.empty:
            hoje = datetime.now()
            hoje_data = datetime(hoje.year, hoje.month, hoje.day)
            
            def calc_dias_para_aniv(data_str):
                try:
                    partes = str(data_str).strip().split('/')
                    dia = int(partes[0])
                    mes = int(partes[1])
                    if mes == 2 and dia == 29: 
                        dia = 28
                    aniv = datetime(hoje.year, mes, dia)
                    if aniv < hoje_data:
                        aniv = datetime(hoje.year + 1, mes, dia)
                    return (aniv - hoje_data).days
                except:
                    return 99999 
            
            df_aniver['DiasFaltando'] = df_aniver['Data de Nascimento'].apply(calc_dias_para_aniv)
            df_aniver = df_aniver.sort_values(by='DiasFaltando')
            
            for idx, row in df_aniver.iterrows():
                if row['DiasFaltando'] == 99999:
                    continue
                    
                nome = str(row.get('Nome Completo', 'Sem Nome'))
                bairro = str(row.get('Bairro', ''))
                nascimento = str(row.get('Data de Nascimento', ''))
                dias = row['DiasFaltando']
                
                tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
                
                classe_css = "contato-card card-aniversario-hoje" if dias == 0 else "contato-card"
                texto_dias = "🔥 **É HOJE!**" if dias == 0 else f"Faltam {dias} dias"
                
                st.markdown(f"""
                <div class="{classe_css}">
                    <b>🎂 {nome}</b> <span style="float: right; color: #4da6ff; font-size: 14px;">{nascimento} ({texto_dias})</span><br>
                    📍 Bairro: {bairro} | 📞 {tel_exibicao}
                </div>
                """, unsafe_allow_html=True)
                
                bc1, bc2 = st.columns(2)
                with bc1:
                    if tel_num:
                        primeiro_nome = nome.split()[0]
                        texto_aniver = f"Olá {primeiro_nome}! Em nome do Samir Bestene e de toda a nossa equipe, desejo um feliz aniversário! Que sua vida seja repleta de alegrias, muita saúde e sucesso. É uma honra ter você caminhando ao nosso lado. A luta continua 🚀"
                        texto_codificado = urllib.parse.quote(texto_aniver)
                        link_wpp_aniver = f"https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_codificado}"
                        
                        st.markdown(f"<a href='{link_wpp_aniver}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 Mandar Parabéns</a>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                with bc2:
                    if tel_num:
                        st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
                st.markdown("")
        else:
            st.info("Nenhuma data de nascimento válida encontrada.")
    else:
        st.info("Coluna de data de nascimento não localizada na planilha.")

# --- ABA 2: BAIRROS ---
with aba2:
    st.subheader("📍 Filtro por Bairro")
    if not df.empty and 'Bairro' in df.columns:
        lista_bairros = sorted([str(b).strip() for b in df['Bairro'].dropna().unique() if str(b).strip() != ''])
        bairros_disp = ["Todos"] + lista_bairros
        
        bairro_sel = st.selectbox("Selecione o Bairro:", bairros_disp)
        filtrados = df if bairro_sel == "Todos" else df[df['Bairro'].astype(str).str.strip() == bairro_sel]
        
        st.markdown(f"**Total encontrado:** {len(filtrados)} pessoa(s)")
        st.markdown("")
        
        for idx, row in filtrados.iterrows():
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            bairro = str(row.get('Bairro', ''))
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(f"""
            <div class="contato-card">
                <b>👤 {nome}</b><br>
                📍 <b>Bairro:</b> {bairro} | 📞 {tel_exibicao}
            </div>
            """, unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num:
                    primeiro_nome = nome.split()[0]
                    texto_padrao = urllib.parse.quote(f"Olá {primeiro_nome}, tudo bem?")
                    link_wpp = f"https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_padrao}"
                    st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
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
            bairro = str(row.get('Bairro', ''))
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            st.markdown(f"""
            <div class="contato-card">
                <b>👤 {nome}</b><br>
                📍 Bairro: {bairro} | 📞 {tel_exibicao}
            </div>
            """, unsafe_allow_html=True)
            
            bc1, bc2 = st.columns(2)
            with bc1:
                if tel_num:
                    primeiro_nome = nome.split()[0]
                    texto_padrao = urllib.parse.quote(f"Olá {primeiro_nome}, tudo bem?")
                    link_wpp = f"https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_padrao}"
                    st.markdown(f"<a href='{link_wpp}' target='_blank' style='display: block; text-align: center; background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>💬 WhatsApp</a>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            with bc2:
                if tel_num:
                    st.markdown(f"<a href='tel:{tel_num}' style='display: block; text-align: center; background-color: #1A73E8; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: bold;'>📞 Ligar</a>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='btn-disabled'>S/ Número</div>", unsafe_allow_html=True)
            st.markdown("")
    else:
        st.info("Nenhum contato encontrado.")

# --- ABA 4: MAPA INTERATIVO CATEGORIZADO ---
with aba4:
    st.subheader("🗺️ Dispersão de Apoiadores")
    st.markdown("Toque nos pinos para abrir as informações do contato.")
    
    st.markdown("""
    <div style='background-color: #152b45; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px; text-align: center;'>
        <b>Legenda Tática:</b><br>
        🔴 Liderança &nbsp;|&nbsp; 🟣 Parceria Estratégica <br>
        🟢 Manutenção &nbsp;|&nbsp; 🔵 Padrão / Outros
    </div>
    """, unsafe_allow_html=True)
    
    if not df.empty and 'Bairro' in df.columns:
        coord_referencia = {
            'SENA MADUREIRA': (-9.0658, -68.6571),
            'CRUZEIRO DO SUL': (-7.6311, -72.6714),
            'TARAUACÁ': (-8.1614, -70.7656),
            'XAPURI': (-10.6515, -68.5044),
            'PORTO ACRE': (-9.5878, -67.5333),
            'BRASILÉIA': (-11.0116, -68.7483),
            'CENTRO': (-9.9749, -67.8243),
            'DOCA FURTADO': (-9.9650, -67.8100),
            'FLORESTA': (-9.9820, -67.8400),
            'PARQUE DOS SABIÁS': (-9.9550, -67.8000),
            'VILA ACRE': (-10.0100, -67.7800),
            'UNIVERSITÁRIO': (-9.9500, -67.8600),
            'ESTAÇÃO EXPERIMENTAL': (-9.9580, -67.8250),
            'CALAFATE': (-9.9600, -67.8700),
            'BAIXADA': (-9.9800, -67.8000),
            'SÃO FRANCISCO': (-9.9600, -67.8500),
            'TANCREDO NEVES': (-9.9400, -67.8400)
        }
        
        mapa = folium.Map(location=[-9.9749, -67.8243], zoom_start=12, tiles="CartoDB positron")
        np.random.seed(42) 
        
        col_mun = None
        for col in df.columns:
            if "Município" in str(col) or "Municipio" in str(col):
                col_mun = col
                break
                
        for idx, row in df.iterrows():
            mun = str(row.get(col_mun, 'Rio Branco')).strip().upper()
            bairro = str(row.get('Bairro', '')).strip().upper()
            nome = str(row.get('Nome Completo', 'Sem Nome'))
            
            # ---------------------------------------------------------
            # LÓGICA DE CATEGORIZAÇÃO SEMÂNTICA
            # ---------------------------------------------------------
            classificacao = str(row.get('Classificação Interna', '')).strip().upper()
            
            if "LIDER" in classificacao or "LIDERANÇA" in classificacao:
                cor_pino = "red"
                icone_pino = "star"
            elif "PARCERIA" in classificacao or "ESTRATÉGICA" in classificacao or "ESTRATEGICA" in classificacao:
                cor_pino = "purple"
                icone_pino = "briefcase"
            elif "MANUTENÇÃO" in classificacao or "MANUTENCAO" in classificacao:
                cor_pino = "green"
                icone_pino = "ok"
            else:
                cor_pino = "blue"
                icone_pino = "info-sign"
            # ---------------------------------------------------------
            
            if mun != 'RIO BRANCO' and mun in coord_referencia:
                base_lat, base_lon = coord_referencia[mun]
            else:
                base_lat, base_lon = coord_referencia.get(bairro, coord_referencia['CENTRO'])
                
            espalhamento_geo = 0.005 
            lat_final = base_lat + np.random.normal(0, espalhamento_geo)
            lon_final = base_lon + np.random.normal(0, espalhamento_geo)
            
            tel_num, tel_exibicao = tratar_telefone(row.get('Telefone', ''))
            
            if tel_num:
                primeiro_nome = nome.split()[0]
                texto_wpp = urllib.parse.quote(f"Olá {primeiro_nome}, tudo bem?")
                link_wpp = f"https://api.whatsapp.com/send?phone=55{tel_num}&text={texto_wpp}"
                btn_html = f"<a href='{link_wpp}' target='_blank' style='background-color: #25D366; color: white; padding: 6px; border-radius: 4px; text-decoration: none; font-family: Arial; font-size: 13px; display: block; text-align: center; margin-top: 8px;'>💬 Abrir WhatsApp</a>"
            else:
                btn_html = "<div style='background-color: #ccc; color: #666; padding: 6px; border-radius: 4px; font-family: Arial; font-size: 13px; text-align: center; margin-top: 8px;'>Sem Número</div>"
            
            popup_html = f"""
            <div style="min-width: 150px; font-family: Arial;">
                <strong style="font-size: 15px; color: #0A1C2E;">{nome}</strong><br>
                <span style="font-size: 13px; color: #555;">📍 {bairro.title()}</span><br>
                <span style="font-size: 13px; color: #555;">📞 {tel_exibicao}</span>
                {btn_html}
            </div>
            """
            
            folium.Marker(
                location=[lat_final, lon_final],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color=cor_pino, icon=icone_pino)
            ).add_to(mapa)
            
        st_folium(mapa, use_container_width=True, height=500, returned_objects=[])
    else: 
        st.warning("Não há dados suficientes de localidade para gerar o mapa.")

# --- ABA 5: RANKING DE LIDERANÇAS ---
with aba5:
    st.subheader("🏆 Ranking de Lideranças")
    st.markdown("Engajamento: Quem está indicando mais pessoas?")
    
    col_indicacao = None
    for col in df.columns:
        if "Através de quem" in str(col):
            col_indicacao = col
            break
    
    if not df.empty and col_indicacao is not None:
        df_lideres = df.dropna(subset=[col_indicacao]).copy()
        df_lideres = df_lideres[df_lideres[col_indicacao].astype(str).str.strip() != ""]
        df_lideres[col_indicacao] = df_lideres[col_indicacao].astype(str).str.strip().str.title()
        
        if not df_lideres.empty:
            ranking = df_lideres.groupby(col_indicacao).size().reset_index(name='Qtd')
            ranking = ranking.sort_values(by='Qtd', ascending=False).reset_index(drop=True)
            
            top1 = ranking.iloc[0]
            pct_top1 = (top1['Qtd'] / total_cadastros) * 100
            st.metric(label="🥇 Liderança Destaque", value=top1[col_indicacao], delta=f"{top1['Qtd']} indicações ({pct_top1:.1f}% da base)")
            st.markdown("---")
            
            for idx, row in ranking.iterrows():
                lider = row[col_indicacao]
                qtd = row['Qtd']
                pct = (qtd / total_cadastros) * 100
                posicao = idx + 1
                
                with st.expander(f"#{posicao} | {lider} - {qtd} pessoa(s) ({pct:.1f}%)"):
                    apoiados = df_lideres[df_lideres[col_indicacao] == lider]
                    
                    for _, apoiado in apoiados.iterrows():
                        nome_ap = str(apoiado.get('Nome Completo', 'Sem Nome'))
                        bairro_ap = str(apoiado.get('Bairro', ''))
                        tel_num_ap, tel_exibicao_ap = tratar_telefone(apoiado.get('Telefone', ''))
                        
                        if tel_num_ap:
                            link_wpp_ap = f"https://api.whatsapp.com/send?phone=55{tel_num_ap}"
                            tel_html = f"📞 <a href='{link_wpp_ap}' target='_blank' style='color: #4da6ff; text-decoration: none;'>{tel_exibicao_ap}</a>"
                        else:
                            tel_html = f"📞 <span style='color: #8899a6;'>Sem Número</span>"
                        
                        st.markdown(f"""
                        <div class="apoiador-lider">
                            <b>{nome_ap}</b><br>
                            <span style="font-size: 14px; color: #a9b9cc;">
                                📍 {bairro_ap} | {tel_html}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Ainda não há dados suficientes de indicações preenchidos.")
    else:
        st.warning("A coluna de indicação não foi encontrada na planilha. Verifique o formulário.")
