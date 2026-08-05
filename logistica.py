import hashlib
import hmac
import html
import json
import math
import re
import unicodedata
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from PIL import Image


# =========================================================
# CONFIGURAÇÃO GERAL
# =========================================================
st.set_page_config(
    page_title="App de Rua | Logística",
    page_icon="🚚",
    layout="centered",
)

SPREADSHEET_ID = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
ABA_RESPOSTAS = "Samir Bestene - Apoiadores (Respostas)"
ABA_CONTROLE = "Controle_Entregas"
ABA_LOGS_ACESSO = "Logs_Acesso"
ARQUIVO_LOGO = "IMG_6008.PNG"
VERSAO_APP = "2026.08.05-INPUT-RESPONSIVO"
FUSO_ACRE = ZoneInfo("America/Rio_Branco")

# Para acrescentar outro motorista, inclua o nome nesta lista.
MOTORISTAS = ["Tancremildo Filho"]

# Se o login usar o nome abaixo, o motorista será escolhido automaticamente.
# Outros usuários autorizados verão a lista MOTORISTAS.
MOTORISTA_POR_USUARIO = {
    "tancremildo": "Tancremildo Filho",
}

STATUS = [
    "PENDENTE",
    "EM ROTA",
    "ENTREGUE",
    "REAGENDAR",
    "NÃO LOCALIZADO",
    "NÃO DESEJA CONTATO",
]

STATUS_LABEL = {
    "PENDENTE": "⏳ Pendente",
    "EM ROTA": "🚚 Em rota",
    "ENTREGUE": "✅ Entregue",
    "REAGENDAR": "📅 Reagendar",
    "NÃO LOCALIZADO": "📍 Não localizado",
    "NÃO DESEJA CONTATO": "🚫 Não deseja contato",
}

STATUS_CLASSE = {
    "PENDENTE": "status-pendente",
    "EM ROTA": "status-rota",
    "ENTREGUE": "status-entregue",
    "REAGENDAR": "status-reagendar",
    "NÃO LOCALIZADO": "status-problema",
    "NÃO DESEJA CONTATO": "status-bloqueado",
}

COLUNAS_CONTROLE = [
    "ID_ENTREGA",
    "STATUS",
    "MOTORISTA",
    "ATUALIZADO_EM",
    "OBSERVACAO",
    "TENTATIVAS",
    "TELEFONE",
    "NOME",
    "ENDERECO",
    "MUNICIPIO",
    "BAIRRO",
    "USUARIO",
]

CABECALHO_LOGS_ACESSO = ["USUARIO", "DATA", "HORA"]


# =========================================================
# IDENTIDADE VISUAL MOBILE
# =========================================================
st.markdown(
    """
    <style>
        .stApp {
            background-color: #0A1C2E !important;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 780px;
            padding-top: 4.25rem !important;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4, p, label, div.stMarkdown, div[data-testid="stMetric"] {
            color: #FFFFFF !important;
        }

        [data-testid="stCaptionContainer"] p {
            color: #B8C8D9 !important;
        }

        div[data-baseweb="select"] > div,
        textarea {
            background-color: #152B45 !important;
            color: #FFFFFF !important;
            border-color: #315A82 !important;
        }

        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] div[data-baseweb="input"] > div,
        [data-testid="stTextInput"] input {
            background-color: #F5F7FA !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextInput"] input:focus {
            color: #0A1C2E !important;
            caret-color: #0A1C2E !important;
            -webkit-text-fill-color: #0A1C2E !important;
        }

        [data-testid="stTextInput"] input::placeholder {
            color: #66788A !important;
            -webkit-text-fill-color: #66788A !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] input:-webkit-autofill,
        [data-testid="stTextInput"] input:-webkit-autofill:hover,
        [data-testid="stTextInput"] input:-webkit-autofill:focus {
            -webkit-text-fill-color: #0A1C2E !important;
            -webkit-box-shadow: 0 0 0 1000px #F5F7FA inset !important;
            caret-color: #0A1C2E !important;
        }

        [data-testid="stTextInput"] button,
        [data-testid="stTextInput"] svg {
            color: #0A1C2E !important;
            fill: #0A1C2E !important;
        }

        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input {
            color: #FFFFFF !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: #122943;
            border: 1px solid #284A6B !important;
            border-radius: 14px !important;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.16);
        }

        [data-testid="stMetric"] {
            background: #122943;
            border: 1px solid #284A6B;
            border-radius: 12px;
            padding: 0.65rem 0.8rem;
        }

        [data-testid="stMetricLabel"] p {
            color: #B8C8D9 !important;
            font-size: 0.78rem !important;
        }

        [data-testid="stMetricValue"] {
            color: #FFFFFF !important;
        }

        .status-chip {
            display: inline-block;
            padding: 0.25rem 0.62rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.76rem;
            margin-bottom: 0.4rem;
        }

        .status-pendente { background: #244666; color: #DCEBFA; }
        .status-rota { background: #0C5EAF; color: #FFFFFF; }
        .status-entregue { background: #147A42; color: #FFFFFF; }
        .status-reagendar { background: #8A6412; color: #FFFFFF; }
        .status-problema { background: #9C3B3B; color: #FFFFFF; }
        .status-bloqueado { background: #5D6470; color: #FFFFFF; }

        .linha-suave {
            height: 1px;
            background: #284A6B;
            margin: 0.8rem 0;
        }

        .endereco-principal {
            font-size: 1.02rem;
            font-weight: 700;
            color: #FFFFFF;
            line-height: 1.35;
        }

        .cabecalho-operacao {
            background: linear-gradient(135deg, #102A45 0%, #183C60 100%);
            border: 1px solid #315A82;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
        }

        .cabecalho-operacao strong { color: #FFFFFF; }
        .cabecalho-operacao span { color: #B8C8D9; }

        .stButton > button,
        [data-testid="stDownloadButton"] button,
        [data-testid="stLinkButton"] a {
            min-height: 44px;
            border-radius: 9px !important;
            font-weight: 700 !important;
        }

        .stButton > button,
        [data-testid="stDownloadButton"] button {
            background: #1769C2 !important;
            border: 1px solid #4B8ED6 !important;
            color: #FFFFFF !important;
        }

        .stButton > button p,
        .stButton > button span,
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span {
            color: #FFFFFF !important;
        }

        .stButton > button:hover,
        [data-testid="stDownloadButton"] button:hover {
            background: #2080E5 !important;
            border-color: #7DB4EE !important;
        }

        .stButton > button:disabled,
        [data-testid="stDownloadButton"] button:disabled {
            background: #334E68 !important;
            border-color: #526B82 !important;
            opacity: 0.72;
        }

        .botao-link-acao {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 44px;
            box-sizing: border-box;
            padding: 0.55rem 0.7rem;
            border: 1px solid #3D6790;
            border-radius: 9px;
            color: #FFFFFF !important;
            font-weight: 700;
            line-height: 1.15;
            text-align: center;
            text-decoration: none !important;
            transition: filter 0.15s ease, transform 0.05s ease;
        }

        .botao-link-acao:hover {
            filter: brightness(1.12);
            color: #FFFFFF !important;
        }

        .botao-link-acao:active {
            transform: translateY(1px);
        }

        .botao-rota { background: #1769C2; }
        .botao-whatsapp { background: #147A42; }
        .botao-telefone { background: #244666; }

        hr {
            border-color: #284A6B !important;
        }

        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
                padding-top: 4rem !important;
            }

            h1 { font-size: 1.65rem !important; }
            h2 { font-size: 1.35rem !important; }
            h3 { font-size: 1.12rem !important; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FUNÇÕES DE LIMPEZA E IDENTIFICAÇÃO
# =========================================================
def agora_acre():
    return datetime.now(FUSO_ACRE)


def texto_limpo(valor):
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return texto


def normalizar_texto(valor):
    texto = texto_limpo(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    texto = re.sub(r"\s+", " ", texto).strip().upper()
    return texto


def tornar_colunas_unicas(colunas):
    resultado = []
    contagem = {}
    for indice, coluna in enumerate(colunas, start=1):
        nome = texto_limpo(coluna) or f"COLUNA_{indice}"
        contagem[nome] = contagem.get(nome, 0) + 1
        if contagem[nome] > 1:
            nome = f"{nome}_{contagem[nome]}"
        resultado.append(nome)
    return resultado


def encontrar_coluna(df, aliases, termos=None):
    mapa = {normalizar_texto(coluna): coluna for coluna in df.columns}

    for alias in aliases:
        encontrada = mapa.get(normalizar_texto(alias))
        if encontrada:
            return encontrada

    if termos:
        termos_normalizados = [normalizar_texto(termo) for termo in termos]
        for coluna_normalizada, coluna_original in mapa.items():
            if all(termo in coluna_normalizada for termo in termos_normalizados):
                return coluna_original
    return None


def identificar_colunas(df):
    return {
        "data": encontrar_coluna(
            df,
            ["Carimbo de data/hora", "Timestamp", "Data do cadastro"],
            ["CARIMBO"],
        ),
        "nome": encontrar_coluna(df, ["Nome Completo", "Nome"], ["NOME", "COMPLETO"]),
        "telefone": encontrar_coluna(df, ["Telefone", "WhatsApp", "Celular"], ["TELEFONE"]),
        "cep": encontrar_coluna(df, ["CEP", "Código Postal"], ["CEP"]),
        "rua": encontrar_coluna(
            df,
            ["Rua e Número", "Rua e Numero", "Logradouro", "Endereço"],
            ["RUA", "NUMERO"],
        ),
        "bairro": encontrar_coluna(df, ["Bairro"], ["BAIRRO"]),
        "complemento": encontrar_coluna(df, ["Complemento", "Ponto de Referência"], ["COMPLEMENTO"]),
        "municipio": encontrar_coluna(
            df,
            [
                "Município da Residência",
                "Municipio da Residencia",
                "Município",
                "Cidade",
            ],
            ["MUNICIPIO", "RESIDENCIA"],
        ),
        "endereco_completo": encontrar_coluna(
            df,
            ["Endereço Completo", "Endereco Completo"],
            ["ENDERECO", "COMPLETO"],
        ),
        "participacao": encontrar_coluna(
            df,
            [
                "Como você gostaria de participar da nossa caminhada?",
                "Como gostaria de participar",
            ],
            ["PARTICIPAR"],
        ),
        "consentimento": encontrar_coluna(
            df,
            [
                "Declaro e Consinto",
                "Consentimento para uso dos dados",
                "Autorização para uso dos dados",
            ],
            ["DECLARO", "CONSINTO"],
        ),
    }


def valor_da_linha(row, coluna):
    if not coluna:
        return ""
    return texto_limpo(row.get(coluna, ""))


def normalizar_telefone(valor):
    original = texto_limpo(valor)
    digitos = re.sub(r"\D", "", original)

    if digitos.startswith("0") and len(digitos) in {11, 12}:
        digitos = digitos[1:]

    if digitos.startswith("55") and len(digitos) in {12, 13}:
        nacional = digitos[2:]
    elif len(digitos) in {10, 11}:
        nacional = digitos
    elif len(digitos) in {8, 9}:
        nacional = "68" + digitos
    else:
        return "", original or "Sem telefone"

    if len(nacional) not in {10, 11}:
        return "", original or "Sem telefone"

    ddd = nacional[:2]
    numero = nacional[2:]
    if len(numero) == 9:
        exibicao = f"({ddd}) {numero[:5]}-{numero[5:]}"
    else:
        exibicao = f"({ddd}) {numero[:4]}-{numero[4:]}"
    return "55" + nacional, exibicao


def montar_endereco(row, colunas):
    endereco_informado = valor_da_linha(row, colunas["endereco_completo"])
    rua = valor_da_linha(row, colunas["rua"])
    bairro = valor_da_linha(row, colunas["bairro"])
    municipio = valor_da_linha(row, colunas["municipio"])
    cep = valor_da_linha(row, colunas["cep"])

    partes = []
    if endereco_informado:
        partes.append(endereco_informado)
    else:
        partes.extend([rua, bairro])

    endereco_normalizado = normalizar_texto(" ".join(partes))
    if municipio and normalizar_texto(municipio) not in endereco_normalizado:
        partes.append(municipio)
    if cep and normalizar_texto(cep) not in endereco_normalizado:
        partes.append(cep)
    partes.extend(["Acre", "Brasil"])

    endereco = ", ".join(parte for parte in partes if texto_limpo(parte))
    possui_logradouro = bool(endereco_informado or rua)
    possui_municipio = bool(municipio)
    return endereco, possui_logradouro and possui_municipio


def gerar_link_mapa(endereco):
    parametros = urllib.parse.urlencode(
        {
            "api": "1",
            "destination": endereco,
            "travelmode": "driving",
            "dir_action": "navigate",
            "utm_source": "app_de_rua_samir_bestene",
            "utm_campaign": "directions_request",
        }
    )
    return f"https://www.google.com/maps/dir/?{parametros}"


def gerar_link_rota_multipla(enderecos):
    enderecos = [texto_limpo(endereco) for endereco in enderecos if texto_limpo(endereco)]
    enderecos = enderecos[:4]
    if not enderecos:
        return ""

    parametros = {
        "api": "1",
        "destination": enderecos[-1],
        "travelmode": "driving",
        "dir_action": "navigate",
        "utm_source": "app_de_rua_samir_bestene",
        "utm_campaign": "multi_stop_directions",
    }
    if len(enderecos) > 1:
        parametros["waypoints"] = "|".join(enderecos[:-1])
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(parametros)


def gerar_link_whatsapp(telefone_e164, nome, motorista):
    primeiro_nome = texto_limpo(nome).split()[0] if texto_limpo(nome) else ""
    saudacao = f"Olá, {primeiro_nome}!" if primeiro_nome else "Olá!"
    mensagem = (
        f"{saudacao} Aqui é {motorista}, da equipe do Samir Bestene. "
        "Estou organizando a entrega dos materiais que você solicitou. "
        "Posso confirmar se você está no endereço informado no cadastro?"
    )
    return (
        "https://api.whatsapp.com/send?phone="
        f"{telefone_e164}&text={urllib.parse.quote(mensagem)}"
    )


def renderizar_link_acao(rotulo, url, classe="botao-rota", nova_aba=True):
    """Renderiza um botão-link sem criar IDs duplicados de widgets no Streamlit."""
    destino = html.escape(texto_limpo(url), quote=True)
    texto = html.escape(texto_limpo(rotulo))
    classe_segura = classe if classe in {
        "botao-rota",
        "botao-whatsapp",
        "botao-telefone",
    } else "botao-rota"
    alvo = "_blank" if nova_aba else "_self"
    st.markdown(
        f'<a class="botao-link-acao {classe_segura}" href="{destino}" '
        f'target="{alvo}" rel="noopener noreferrer">{texto}</a>',
        unsafe_allow_html=True,
    )


def gerar_id_entrega(row, colunas):
    componentes = [
        str(row.get("_LINHA_PLANILHA", "")),
        valor_da_linha(row, colunas["data"]),
        valor_da_linha(row, colunas["nome"]),
        valor_da_linha(row, colunas["telefone"]),
        valor_da_linha(row, colunas["rua"]),
        valor_da_linha(row, colunas["municipio"]),
    ]
    base = "|".join(normalizar_texto(item) for item in componentes)
    resumo = hashlib.sha256(base.encode("utf-8")).hexdigest()[:12].upper()
    return f"ENT-{resumo}"


def inteiro_seguro(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


# =========================================================
# PLANILHA PRIVADA E ABAS DE CONTROLE
# =========================================================
@st.cache_resource
def abrir_planilha():
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        if "gcp_json" in st.secrets:
            valor_gcp = st.secrets["gcp_json"]
            if not isinstance(valor_gcp, str):
                raise RuntimeError("O Secret `gcp_json` precisa ser um texto JSON.")
            informacoes = json.loads(valor_gcp)
        elif "gcp_service_account" in st.secrets:
            # Compatibilidade com o formato em seção TOML.
            informacoes = dict(st.secrets["gcp_service_account"])
        else:
            raise RuntimeError(
                "Não foi encontrado `gcp_json` nem `[gcp_service_account]` nos Secrets."
            )
    except json.JSONDecodeError as erro:
        raise RuntimeError(
            "O conteúdo de `gcp_json` não é um JSON válido. "
            "Substitua-o pelo conteúdo integral da nova chave da conta de serviço."
        ) from erro

    if not isinstance(informacoes, dict):
        raise RuntimeError("A credencial do Google precisa ser um objeto JSON.")

    chave_privada = informacoes.get("private_key")
    if isinstance(chave_privada, str) and "\\n" in chave_privada:
        informacoes["private_key"] = chave_privada.replace("\\n", "\n")

    credenciais = Credentials.from_service_account_info(informacoes, scopes=escopos)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_key(SPREADSHEET_ID)


def obter_ou_criar_aba(nome, cabecalho, linhas=3000):
    planilha = abrir_planilha()
    try:
        aba = planilha.worksheet(nome)
    except WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=nome,
            rows=linhas,
            cols=max(len(cabecalho), 12),
        )

    valores = aba.get_all_values()
    if not valores:
        aba.update(
            range_name=f"A1:{chr(64 + len(cabecalho))}1",
            values=[cabecalho],
        )
    elif valores[0][: len(cabecalho)] != cabecalho:
        raise RuntimeError(
            f"A aba `{nome}` existe, mas o cabeçalho foi alterado. "
            "Restaure o cabeçalho esperado antes de continuar."
        )
    return aba


def normalizar_titulo_aba(titulo):
    titulo = normalizar_texto(titulo)
    return re.sub(r"[^A-Z0-9]+", " ", titulo).strip()


def localizar_aba_respostas():
    """Localiza a aba mesmo com variações de espaços, hífen ou nome antigo."""
    planilha = abrir_planilha()
    abas = planilha.worksheets()
    por_titulo = {normalizar_titulo_aba(aba.title): aba for aba in abas}

    candidatos = [
        ABA_RESPOSTAS,
        "Samir Bestene – Apoiadores (Respostas)",
        "Form_Responses",
        "Form Responses",
    ]
    for candidato in candidatos:
        encontrada = por_titulo.get(normalizar_titulo_aba(candidato))
        if encontrada:
            return encontrada

    for titulo_normalizado, aba in por_titulo.items():
        if "APOIADORES" in titulo_normalizado and "RESPOSTAS" in titulo_normalizado:
            return aba

    titulos = ", ".join(aba.title for aba in abas) or "nenhuma aba visível"
    raise RuntimeError(
        "A aba de respostas não foi encontrada. "
        f"Abas visíveis para a conta de serviço: {titulos}."
    )


@st.cache_data(ttl=120, show_spinner=False)
def carregar_respostas():
    aba = localizar_aba_respostas()
    valores = aba.get_all_values()
    if len(valores) < 2:
        return pd.DataFrame()

    colunas = tornar_colunas_unicas(valores[0])
    df = pd.DataFrame(valores[1:], columns=colunas)
    df["_LINHA_PLANILHA"] = range(2, len(df) + 2)
    return df


@st.cache_data(ttl=30, show_spinner=False)
def carregar_controle():
    aba = obter_ou_criar_aba(ABA_CONTROLE, COLUNAS_CONTROLE)
    valores = aba.get_all_values()
    if len(valores) < 2:
        return pd.DataFrame(columns=COLUNAS_CONTROLE)
    return pd.DataFrame(valores[1:], columns=COLUNAS_CONTROLE)


def registrar_acesso(usuario):
    """Acrescenta o acesso ao Logs_Acesso sem mudar seu cabeçalho A:C."""
    try:
        aba = abrir_planilha().worksheet(ABA_LOGS_ACESSO)
        cabecalho_atual = [
            normalizar_texto(valor)
            for valor in aba.row_values(1)[:3]
        ]
        if cabecalho_atual != CABECALHO_LOGS_ACESSO:
            raise RuntimeError(
                f"A aba `{ABA_LOGS_ACESSO}` deve começar com "
                "`Usuário`, `Data` e `Hora`, nessa ordem."
            )

        agora = agora_acre()
        motorista = MOTORISTA_POR_USUARIO.get(usuario)
        identificacao = motorista or texto_limpo(usuario)
        identificacao = f"{identificacao} (Logística)"
        aba.append_row(
            [
                identificacao,
                agora.strftime("%d/%m/%Y"),
                agora.strftime("%H:%M:%S"),
            ],
            value_input_option="RAW",
        )
    except Exception as erro:
        # Uma falha no log não deve bloquear o trabalho do motorista.
        print(f"Falha ao registrar acesso da logística: {erro}")


def salvar_status(row, novo_status, observacao, motorista, usuario):
    aba = obter_ou_criar_aba(ABA_CONTROLE, COLUNAS_CONTROLE)
    id_entrega = row["ID_ENTREGA"]
    tentativas_atuais = inteiro_seguro(row.get("TENTATIVAS", 0))
    incremento = 1 if novo_status in {"EM ROTA", "NÃO LOCALIZADO"} else 0
    tentativas = tentativas_atuais + incremento

    valores = [
        id_entrega,
        novo_status,
        motorista,
        agora_acre().strftime("%d/%m/%Y %H:%M:%S"),
        texto_limpo(observacao),
        str(tentativas),
        row["TELEFONE_EXIBICAO"],
        row["NOME"],
        row["ENDERECO_COMPLETO"],
        row["MUNICIPIO"],
        row["BAIRRO"],
        usuario,
    ]

    # O controle é histórico: cada mudança gera uma nova linha. Na leitura,
    # o aplicativo usa a última linha de cada ID como situação atual.
    aba.append_row(valores, value_input_option="RAW")
    carregar_controle.clear()


def atualizar_entrega_interface(row, novo_status, observacao, motorista, usuario):
    try:
        salvar_status(
            row,
            novo_status,
            observacao,
            motorista,
            usuario,
        )
        st.session_state["mensagem_operacao"] = (
            f"Entrega de {row['NOME']} atualizada para "
            f"{STATUS_LABEL[novo_status]}."
        )
        st.rerun()
    except Exception as erro:
        st.error("Não foi possível salvar a atualização.")
        st.code(str(erro))


# =========================================================
# LOGIN
# =========================================================
def verificar_login():
    if st.session_state.get("autenticado_logistica"):
        return True

    st.markdown("## 🔐 Acesso da equipe de logística")
    st.caption("Entre com o usuário e a senha cadastrados nos Secrets do Streamlit.")

    try:
        senhas = dict(st.secrets["senhas"])
    except Exception:
        st.error(
            "A seção `[senhas]` não foi encontrada nos Secrets. "
            "Siga o passo a passo fornecido junto com este arquivo."
        )
        return False

    usuario = st.text_input("Usuário", key="login_usuario").strip()
    senha = st.text_input("Senha", type="password", key="login_senha")

    if st.button("Entrar", type="primary", use_container_width=True):
        senha_cadastrada = str(senhas.get(usuario, ""))
        if usuario in senhas and hmac.compare_digest(senha, senha_cadastrada):
            st.session_state["autenticado_logistica"] = True
            st.session_state["usuario_logistica"] = usuario
            registrar_acesso(usuario)
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    return False


def encerrar_sessao():
    for chave in [
        "autenticado_logistica",
        "usuario_logistica",
        "login_usuario",
        "login_senha",
    ]:
        st.session_state.pop(chave, None)
    st.rerun()


# =========================================================
# LOGO COM RECORTE DA TRANSPARÊNCIA
# =========================================================
@st.cache_resource
def carregar_logo_recortada(caminho):
    imagem = Image.open(caminho).convert("RGBA")
    caixa = imagem.getchannel("A").getbbox()
    if caixa:
        imagem = imagem.crop(caixa)
    return imagem


def exibir_logo():
    caminho = Path(ARQUIVO_LOGO)
    if not caminho.exists():
        st.markdown(
            "<h2 style='text-align:center;margin-bottom:0;'>SAMIR BESTENE</h2>",
            unsafe_allow_html=True,
        )
        return

    coluna_esquerda, coluna_logo, coluna_direita = st.columns([1, 1.35, 1])
    with coluna_logo:
        st.image(carregar_logo_recortada(str(caminho)), use_container_width=True)


# =========================================================
# PREPARAÇÃO DA FILA DE ENTREGA
# =========================================================
def preparar_entregas(respostas, controle):
    if respostas.empty:
        return pd.DataFrame(), {}, []

    colunas = identificar_colunas(respostas)
    faltantes = [
        rotulo
        for rotulo, chave in [
            ("Nome Completo", "nome"),
            ("Telefone", "telefone"),
            ("Bairro", "bairro"),
            ("Município da Residência", "municipio"),
            ("Como gostaria de participar", "participacao"),
        ]
        if not colunas[chave]
    ]

    if not colunas["rua"] and not colunas["endereco_completo"]:
        faltantes.append("Rua e Número ou Endereço Completo")

    if faltantes:
        return pd.DataFrame(), colunas, faltantes

    df = respostas.copy()
    participacao = df[colunas["participacao"]].astype(str)
    filtro = participacao.str.contains(
        r"materia|multiplicador",
        case=False,
        na=False,
        regex=True,
    )
    if colunas["consentimento"]:
        consentimento = df[colunas["consentimento"]].astype(str)
        filtro &= consentimento.str.contains(
            r"concordo|consinto|autorizo|\bsim\b",
            case=False,
            na=False,
            regex=True,
        )
    df = df[filtro].copy()

    registros = []
    for _, row in df.iterrows():
        nome = valor_da_linha(row, colunas["nome"]) or "Nome não informado"
        telefone_e164, telefone_exibicao = normalizar_telefone(
            valor_da_linha(row, colunas["telefone"])
        )
        endereco, endereco_valido = montar_endereco(row, colunas)
        municipio = valor_da_linha(row, colunas["municipio"])
        bairro = valor_da_linha(row, colunas["bairro"])
        complemento = valor_da_linha(row, colunas["complemento"])
        solicitacao = valor_da_linha(row, colunas["participacao"])
        data_cadastro = valor_da_linha(row, colunas["data"])

        registros.append(
            {
                "ID_ENTREGA": gerar_id_entrega(row, colunas),
                "LINHA_ORIGEM": row["_LINHA_PLANILHA"],
                "DATA_CADASTRO": data_cadastro,
                "NOME": nome,
                "TELEFONE_E164": telefone_e164,
                "TELEFONE_EXIBICAO": telefone_exibicao,
                "MUNICIPIO": municipio,
                "BAIRRO": bairro,
                "ENDERECO_COMPLETO": endereco,
                "ENDERECO_VALIDO": endereco_valido,
                "COMPLEMENTO": complemento,
                "SOLICITACAO": solicitacao,
            }
        )

    entregas = pd.DataFrame(registros)
    if entregas.empty:
        return entregas, colunas, []

    entregas["CHAVE_DUPLICIDADE"] = (
        entregas["TELEFONE_E164"].fillna("").astype(str)
        + "|"
        + entregas["ENDERECO_COMPLETO"].map(normalizar_texto)
    )
    chave_valida = entregas["CHAVE_DUPLICIDADE"].str.replace("|", "", regex=False).str.len() > 5
    entregas["POSSIVEL_DUPLICIDADE"] = (
        entregas.duplicated("CHAVE_DUPLICIDADE", keep=False) & chave_valida
    )

    if controle.empty:
        entregas["STATUS"] = "PENDENTE"
        entregas["MOTORISTA"] = ""
        entregas["ATUALIZADO_EM"] = ""
        entregas["OBSERVACAO"] = ""
        entregas["TENTATIVAS"] = 0
        entregas["USUARIO"] = ""
    else:
        controle_reduzido = controle[
            [
                "ID_ENTREGA",
                "STATUS",
                "MOTORISTA",
                "ATUALIZADO_EM",
                "OBSERVACAO",
                "TENTATIVAS",
                "USUARIO",
            ]
        ].drop_duplicates("ID_ENTREGA", keep="last")
        entregas = entregas.merge(
            controle_reduzido,
            on="ID_ENTREGA",
            how="left",
        )
        entregas["STATUS"] = entregas["STATUS"].where(
            entregas["STATUS"].isin(STATUS),
            "PENDENTE",
        )
        for coluna in ["MOTORISTA", "ATUALIZADO_EM", "OBSERVACAO", "USUARIO"]:
            entregas[coluna] = entregas[coluna].fillna("")
        entregas["TENTATIVAS"] = entregas["TENTATIVAS"].fillna(0).map(inteiro_seguro)

    entregas["LINK_MAPA"] = entregas["ENDERECO_COMPLETO"].map(gerar_link_mapa)
    return entregas, colunas, []


def aplicar_filtro_status(df, opcao):
    if opcao == "Pendentes e em andamento":
        return df[df["STATUS"].isin(["PENDENTE", "EM ROTA", "REAGENDAR", "NÃO LOCALIZADO"])]
    if opcao == "Todos os status":
        return df
    mapa = {rotulo: status for status, rotulo in STATUS_LABEL.items()}
    status = mapa.get(opcao)
    return df[df["STATUS"] == status] if status else df


def ordenar_entregas(df, criterio):
    df = df.copy()
    if criterio == "Bairro e endereço":
        return df.sort_values(["MUNICIPIO", "BAIRRO", "ENDERECO_COMPLETO", "NOME"])
    if criterio == "Mais recentes primeiro":
        return df.sort_values("LINHA_ORIGEM", ascending=False)
    if criterio == "Status e bairro":
        ordem = {status: posicao for posicao, status in enumerate(STATUS)}
        df["ORDEM_STATUS"] = df["STATUS"].map(ordem).fillna(99)
        return df.sort_values(["ORDEM_STATUS", "MUNICIPIO", "BAIRRO", "ENDERECO_COMPLETO"])
    return df.sort_values("LINHA_ORIGEM", ascending=True)


def criar_manifesto(df):
    colunas = [
        "ID_ENTREGA",
        "STATUS",
        "MOTORISTA",
        "NOME",
        "TELEFONE_EXIBICAO",
        "MUNICIPIO",
        "BAIRRO",
        "ENDERECO_COMPLETO",
        "COMPLEMENTO",
        "SOLICITACAO",
        "OBSERVACAO",
        "TENTATIVAS",
    ]
    manifesto = df[colunas].copy()
    manifesto.columns = [
        "ID",
        "Status",
        "Motorista",
        "Nome",
        "Telefone",
        "Município",
        "Bairro",
        "Endereço",
        "Complemento",
        "Solicitação",
        "Observação",
        "Tentativas",
    ]
    return manifesto.to_csv(index=False).encode("utf-8-sig")


def diagnosticar_erro_operacao(erro):
    tipo = type(erro).__name__
    detalhe = texto_limpo(erro)
    busca = normalizar_texto(f"{tipo} {detalhe}")

    if "SPREADSHEETNOTFOUND" in busca or "PERMISSION DENIED" in busca or "403" in busca:
        return (
            "A conta de serviço não conseguiu acessar ou editar a planilha.",
            "Compartilhe a planilha com o `client_email` da nova chave como Editor.",
        )
    if "ABA DE RESPOSTAS NAO FOI ENCONTRADA" in busca:
        return (
            "A planilha abriu, mas a aba de respostas não foi localizada.",
            "Abra os detalhes técnicos: a lista de abas visíveis mostrará o nome reconhecido.",
        )
    if "CABECALHO FOI ALTERADO" in busca:
        return (
            "A aba Controle_Entregas existe com um cabeçalho diferente do esperado.",
            "Não apague a aba. Abra os detalhes técnicos e confira qual cabeçalho precisa ser restaurado.",
        )
    if "GCP_JSON" in busca or "CREDENCIAL" in busca or "PRIVATE KEY" in busca:
        return (
            "A credencial salva nos Secrets não pôde ser interpretada.",
            "Gere novamente o TOML com o conversor offline e substitua o conteúdo dos Secrets.",
        )
    return (
        "Não foi possível concluir a leitura da operação de logística.",
        "Abra os detalhes técnicos abaixo e informe somente o nome e a mensagem do erro; não envie credenciais.",
    )


# =========================================================
# APLICAÇÃO
# =========================================================
exibir_logo()

if not verificar_login():
    st.stop()

usuario_logado = st.session_state.get("usuario_logistica", "")
motorista_padrao = MOTORISTA_POR_USUARIO.get(usuario_logado)

st.markdown("## 📦 Operação de Entrega de Materiais")
st.caption(f"Versão do aplicativo: {VERSAO_APP}")

if motorista_padrao:
    motorista = motorista_padrao
else:
    motorista = st.selectbox("Motorista responsável:", MOTORISTAS)

st.markdown(
    f"""
    <div class="cabecalho-operacao">
        <strong>🚚 Motorista: {motorista}</strong><br>
        <span>Usuário conectado: {usuario_logado}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

coluna_atualizar, coluna_sair = st.columns(2)
with coluna_atualizar:
    if st.button("🔄 Atualizar dados", use_container_width=True):
        carregar_respostas.clear()
        carregar_controle.clear()
        st.session_state["mensagem_operacao"] = "Dados atualizados."
        st.rerun()
with coluna_sair:
    if st.button("Sair", use_container_width=True):
        encerrar_sessao()

if st.session_state.get("mensagem_operacao"):
    st.success(st.session_state.pop("mensagem_operacao"))

try:
    with st.spinner("Carregando a fila de entregas..."):
        respostas = carregar_respostas()
        controle = carregar_controle()
        entregas, colunas_identificadas, colunas_faltantes = preparar_entregas(
            respostas,
            controle,
        )
except Exception as erro:
    mensagem_erro, orientacao_erro = diagnosticar_erro_operacao(erro)
    st.error(mensagem_erro)
    st.warning(orientacao_erro)
    with st.expander("Detalhes técnicos"):
        st.code(f"{type(erro).__name__}: {erro}")
    st.stop()

if colunas_faltantes:
    st.error(
        "Não foi possível identificar estas colunas obrigatórias na aba "
        f"`{ABA_RESPOSTAS}`: {', '.join(colunas_faltantes)}."
    )
    st.caption(
        "O sistema interrompe a fila para impedir que pessoas que não pediram "
        "material sejam incluídas por engano."
    )
    st.stop()

if entregas.empty:
    st.info(
        "Nenhum cadastro solicitou materiais ou se identificou como multiplicador."
    )
    st.stop()

st.markdown("---")
st.subheader("🔎 Filtros da rota")

municipios_disponiveis = sorted(
    municipio
    for municipio in entregas["MUNICIPIO"].dropna().astype(str).str.strip().unique()
    if municipio
)
municipio_filtro = st.selectbox(
    "Município:",
    ["Todos os municípios"] + municipios_disponiveis,
)

base_bairros = entregas.copy()
if municipio_filtro != "Todos os municípios":
    base_bairros = base_bairros[base_bairros["MUNICIPIO"] == municipio_filtro]

bairros_disponiveis = sorted(
    bairro
    for bairro in base_bairros["BAIRRO"].dropna().astype(str).str.strip().unique()
    if bairro
)
bairro_filtro = st.selectbox(
    "Bairro:",
    ["Todos os bairros"] + bairros_disponiveis,
)

opcoes_status = ["Pendentes e em andamento", "Todos os status"] + [
    STATUS_LABEL[status] for status in STATUS
]
status_filtro = st.selectbox("Situação:", opcoes_status)

busca = st.text_input(
    "Pesquisar:",
    placeholder="Nome, telefone, rua, bairro ou município",
)

criterio_ordenacao = st.selectbox(
    "Ordenar por:",
    [
        "Bairro e endereço",
        "Mais antigos primeiro",
        "Mais recentes primeiro",
        "Status e bairro",
    ],
)

entregas_filtradas = entregas.copy()
if municipio_filtro != "Todos os municípios":
    entregas_filtradas = entregas_filtradas[
        entregas_filtradas["MUNICIPIO"] == municipio_filtro
    ]
if bairro_filtro != "Todos os bairros":
    entregas_filtradas = entregas_filtradas[
        entregas_filtradas["BAIRRO"] == bairro_filtro
    ]

if busca.strip():
    termo = normalizar_texto(busca)
    mascara_busca = (
        entregas_filtradas[
            [
                "NOME",
                "TELEFONE_EXIBICAO",
                "MUNICIPIO",
                "BAIRRO",
                "ENDERECO_COMPLETO",
            ]
        ]
        .fillna("")
        .astype(str)
        .apply(lambda linha: termo in normalizar_texto(" ".join(linha)), axis=1)
    )
    entregas_filtradas = entregas_filtradas[mascara_busca]

base_metricas = entregas_filtradas.copy()
entregas_filtradas = aplicar_filtro_status(entregas_filtradas, status_filtro)
entregas_filtradas = ordenar_entregas(entregas_filtradas, criterio_ordenacao)

total_selecao = len(entregas_filtradas)
total_area = len(base_metricas)
pendentes = int((base_metricas["STATUS"] == "PENDENTE").sum())
entregues_total = int((base_metricas["STATUS"] == "ENTREGUE").sum())
problemas = int(
    base_metricas["STATUS"].isin(
        ["REAGENDAR", "NÃO LOCALIZADO", "NÃO DESEJA CONTATO"]
    ).sum()
)

metrica_1, metrica_2 = st.columns(2)
metrica_1.metric("Cadastros na área", total_area)
metrica_2.metric("Pendentes", pendentes)
metrica_3, metrica_4 = st.columns(2)
metrica_3.metric("Entregues", entregues_total)
metrica_4.metric("Ocorrências", problemas)

if total_area:
    progresso = entregues_total / total_area
    st.progress(
        progresso,
        text=f"Progresso da área pesquisada: {progresso * 100:.1f}%",
    )

st.caption(f"Entregas exibidas com o filtro de situação: {total_selecao}")

duplicidades = int(entregas_filtradas["POSSIVEL_DUPLICIDADE"].sum())
enderecos_invalidos = int((~entregas_filtradas["ENDERECO_VALIDO"]).sum())
if duplicidades:
    st.warning(
        f"Há {duplicidades} cadastro(s) com possível duplicidade de telefone e endereço."
    )
if enderecos_invalidos:
    st.warning(
        f"Há {enderecos_invalidos} cadastro(s) sem endereço ou município suficiente para navegação."
    )

coluna_manifesto, coluna_rota = st.columns(2)
with coluna_manifesto:
    st.download_button(
        "⬇️ Baixar manifesto",
        data=criar_manifesto(entregas_filtradas),
        file_name=f"manifesto_entregas_{agora_acre():%Y%m%d_%H%M}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=entregas_filtradas.empty,
    )

enderecos_rota = entregas_filtradas[
    entregas_filtradas["ENDERECO_VALIDO"]
    & ~entregas_filtradas["STATUS"].isin(["ENTREGUE", "NÃO DESEJA CONTATO"])
]["ENDERECO_COMPLETO"].head(4).tolist()
link_rota_multipla = gerar_link_rota_multipla(enderecos_rota)

with coluna_rota:
    if link_rota_multipla:
        renderizar_link_acao(
            "🧭 Rota de até 4 paradas",
            link_rota_multipla,
            "botao-rota",
        )
    else:
        st.button(
            "🧭 Sem rota disponível",
            disabled=True,
            use_container_width=True,
        )

if link_rota_multipla:
    st.caption(
        "A rota múltipla usa as primeiras quatro entregas válidas na ordem exibida. "
        "Ela organiza a sequência, mas não calcula a rota ótima."
    )

st.markdown("---")

if entregas_filtradas.empty:
    st.info("Nenhuma entrega encontrada para os filtros selecionados.")
    st.stop()

itens_por_pagina = st.selectbox(
    "Entregas por página:",
    [10, 20, 30],
    index=1,
)
total_paginas = max(1, math.ceil(total_selecao / itens_por_pagina))

if st.session_state.get("pagina_entregas", 1) > total_paginas:
    st.session_state["pagina_entregas"] = 1

pagina = st.number_input(
    "Página:",
    min_value=1,
    max_value=total_paginas,
    step=1,
    key="pagina_entregas",
)

inicio = (pagina - 1) * itens_por_pagina
fim = inicio + itens_por_pagina
pagina_df = entregas_filtradas.iloc[inicio:fim]

st.caption(
    f"Página {pagina} de {total_paginas} • exibindo "
    f"{inicio + 1}–{min(fim, total_selecao)} de {total_selecao}"
)

for numero, (_, row) in enumerate(pagina_df.iterrows(), start=inicio + 1):
    status_atual = row["STATUS"]
    classe_status = STATUS_CLASSE.get(status_atual, "status-pendente")
    rotulo_status = STATUS_LABEL.get(status_atual, status_atual)

    with st.container(border=True):
        st.markdown(
            f'<span class="status-chip {classe_status}">{rotulo_status}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"### {numero:02d}. {row['NOME']}")
        endereco_seguro = html.escape(str(row["ENDERECO_COMPLETO"]))
        st.markdown(
            f'<div class="endereco-principal">📍 {endereco_seguro}</div>',
            unsafe_allow_html=True,
        )

        if row["COMPLEMENTO"]:
            st.write(f"💬 **Referência:** {row['COMPLEMENTO']}")
        st.write(f"📦 **Solicitação:** {row['SOLICITACAO']}")
        st.write(f"📞 **Telefone:** {row['TELEFONE_EXIBICAO']}")

        if row["POSSIVEL_DUPLICIDADE"]:
            st.warning("Possível cadastro duplicado. Confirme antes de separar novo material.")
        if not row["ENDERECO_VALIDO"]:
            st.error("Endereço incompleto: confirme rua e município antes da saída.")
        if row["ATUALIZADO_EM"]:
            st.caption(
                f"Última atualização: {row['ATUALIZADO_EM']} • "
                f"{row['MOTORISTA'] or 'motorista não informado'}"
            )

        if row["OBSERVACAO"]:
            st.info(f"Observação registrada: {row['OBSERVACAO']}")

        coluna_navegar, coluna_whatsapp = st.columns(2)
        with coluna_navegar:
            if row["ENDERECO_VALIDO"]:
                renderizar_link_acao(
                    "🧭 Iniciar navegação",
                    row["LINK_MAPA"],
                    "botao-rota",
                )
            else:
                st.button(
                    "🧭 Endereço incompleto",
                    disabled=True,
                    use_container_width=True,
                    key=f"mapa_invalido_{row['ID_ENTREGA']}",
                )

        with coluna_whatsapp:
            pode_contatar = bool(row["TELEFONE_E164"]) and status_atual != "NÃO DESEJA CONTATO"
            if pode_contatar:
                renderizar_link_acao(
                    "💬 WhatsApp",
                    gerar_link_whatsapp(row["TELEFONE_E164"], row["NOME"], motorista),
                    "botao-whatsapp",
                )
            else:
                st.button(
                    "💬 Contato indisponível",
                    disabled=True,
                    use_container_width=True,
                    key=f"wpp_invalido_{row['ID_ENTREGA']}",
                )

        if row["TELEFONE_E164"] and status_atual != "NÃO DESEJA CONTATO":
            renderizar_link_acao(
                "📞 Ligar",
                f"tel:+{row['TELEFONE_E164']}",
                "botao-telefone",
                nova_aba=False,
            )

        if status_atual not in {"ENTREGUE", "NÃO DESEJA CONTATO"}:
            coluna_em_rota, coluna_entregue = st.columns(2)
            with coluna_em_rota:
                if st.button(
                    "🚚 Marcar em rota",
                    use_container_width=True,
                    disabled=status_atual == "EM ROTA",
                    key=f"rapido_rota_{row['ID_ENTREGA']}",
                ):
                    atualizar_entrega_interface(
                        row,
                        "EM ROTA",
                        row["OBSERVACAO"],
                        motorista,
                        usuario_logado,
                    )
            with coluna_entregue:
                if st.button(
                    "✅ Confirmar entrega",
                    type="primary",
                    use_container_width=True,
                    key=f"rapido_entregue_{row['ID_ENTREGA']}",
                ):
                    atualizar_entrega_interface(
                        row,
                        "ENTREGUE",
                        row["OBSERVACAO"],
                        motorista,
                        usuario_logado,
                    )

        with st.expander("📝 Atualizar situação da entrega"):
            indice_status = STATUS.index(status_atual) if status_atual in STATUS else 0
            novo_status = st.selectbox(
                "Situação:",
                STATUS,
                index=indice_status,
                format_func=lambda valor: STATUS_LABEL[valor],
                key=f"status_{row['ID_ENTREGA']}",
            )
            observacao = st.text_area(
                "Observação:",
                value=row["OBSERVACAO"],
                placeholder="Ex.: morador ausente; retornar após 18h.",
                key=f"obs_{row['ID_ENTREGA']}",
            )
            if st.button(
                "Salvar atualização",
                type="primary",
                use_container_width=True,
                key=f"salvar_{row['ID_ENTREGA']}",
            ):
                atualizar_entrega_interface(
                    row,
                    novo_status,
                    observacao,
                    motorista,
                    usuario_logado,
                )

st.markdown("---")
st.caption(
    "Os dados pessoais desta ferramenta devem ser utilizados exclusivamente pela "
    "equipe autorizada para cumprir as solicitações registradas."
)
