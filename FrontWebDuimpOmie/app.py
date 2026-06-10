"""
Importação de DUIMP → XML — Front Streamlit (Sillion)
Envia o NÚMERO da DUIMP + email para o backend N8N (POST JSON).
O N8N autentica no Portal Único, consulta a DUIMP, gera o XML estruturado
e devolve o arquivo no email informado.

Arquitetura:
- app.py        → lógica Python (config, envio, widgets de input)
- styles/       → CSS (visual)
- templates/    → HTML estrutural (header, hero, footer, etc.)
"""

import re
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

# ============================================================
# Caminhos
# ============================================================
BASE_DIR = Path(__file__).parent
CSS_PATH = BASE_DIR / "styles" / "main.css"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ============================================================
# Recursos externos
# ============================================================
LOGO_EXTERNO = "https://www.sillion.com.br/wp-content/themes/sillion/images/logo-black-tm.svg"
LOGO_LOCAL_FILE = STATIC_DIR / "logo-sillion.svg"


def resolver_logo_url() -> str:
    """
    Retorna o caminho do logo:
    - Se houver `static/logo-sillion.svg`, usa a versão local (mais rápida e offline).
    - Caso contrário, cai para a URL externa do site da Sillion.
    Streamlit sanitiza o atributo `onerror` em HTML, então o fallback
    precisa ser feito no Python, não no navegador.
    """
    if LOGO_LOCAL_FILE.exists():
        return "app/static/logo-sillion.svg"
    return LOGO_EXTERNO

# ============================================================
# Config da página
# ============================================================
st.set_page_config(
    page_title="Sillion · DUIMP → XML",
    page_icon="https://www.sillion.com.br/wp-content/themes/sillion/images/logo-white-tm.svg",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================================
# Constantes
# ============================================================
# Apenas emails @sillion.com.br são aceitos (case-insensitive)
DOMINIO_PERMITIDO = "sillion.com.br"
EMAIL_REGEX = re.compile(
    rf"^[A-Za-z0-9._%+\-]+@{re.escape(DOMINIO_PERMITIDO)}$",
    re.IGNORECASE,
)

TIMEOUT_REQ = 120  # segundos


# ============================================================
# Helpers de renderização (templates + CSS)
# ============================================================
def render_template(nome: str, **variaveis) -> str:
    """
    Lê um arquivo .html em templates/ e substitui placeholders no
    formato {{nome_da_variavel}} pelos valores passados.
    """
    caminho = TEMPLATES_DIR / f"{nome}.html"
    html = caminho.read_text(encoding="utf-8")
    for chave, valor in variaveis.items():
        html = html.replace(f"{{{{{chave}}}}}", str(valor))
    return html


def inject(html: str) -> None:
    """Injeta um trecho HTML na página."""
    st.markdown(html, unsafe_allow_html=True)


def carregar_css(caminho: Path) -> None:
    """Lê o arquivo CSS e injeta na página via st.markdown."""
    try:
        css = caminho.read_text(encoding="utf-8")
        inject(f"<style>{css}</style>")
    except FileNotFoundError:
        st.warning(f"Arquivo de estilos não encontrado: {caminho}")


# Carrega meta tags + CSS antes de qualquer conteúdo
inject(render_template("meta"))
carregar_css(CSS_PATH)


# ============================================================
# Configuração segura: URL do webhook
# ============================================================
try:
    WEBHOOK_URL = st.secrets["N8N_WEBHOOK_URL"]
except (KeyError, FileNotFoundError):
    WEBHOOK_URL = None


# ============================================================
# Helpers de negócio
# ============================================================
def email_valido(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email.strip()))


def numero_duimp_valido(numero: str) -> bool:
    """Validação leve: não vazio e com tamanho mínimo de uma DUIMP."""
    return len(re.sub(r"[^0-9A-Za-z]", "", numero)) >= 10


def montar_payload(email: str, numero_duimp: str, versao: str) -> dict:
    """Monta o JSON enviado ao N8N: número da DUIMP + versão + email."""
    return {
        "email": email.strip(),
        "tipo": "duimp",
        "numeroDuimp": numero_duimp.strip(),
        "versao": (versao.strip() or "1"),
        "enviado_em": datetime.now().isoformat(timespec="seconds"),
    }


def enviar_para_n8n(url: str, payload: dict) -> requests.Response:
    return requests.post(
        url,
        json=payload,
        timeout=TIMEOUT_REQ,
        headers={"Content-Type": "application/json"},
    )


# ============================================================
# UI — Header + Hero (vindos dos templates HTML)
# ============================================================
inject(render_template("header", logo_url=resolver_logo_url()))
inject(render_template(
    "hero",
    titulo="Importação de DUIMP",
    subtitulo="Informe o número da DUIMP para processamento automático. "
              "O XML estruturado retornará no seu email.",
))


# ============================================================
# Verificação de configuração
# ============================================================
if not WEBHOOK_URL:
    st.error(
        "⚠️ A URL do webhook N8N não foi configurada. "
        "Crie o arquivo `.streamlit/secrets.toml` com a chave `N8N_WEBHOOK_URL` "
        "ou configure-a no painel do Streamlit Community Cloud."
    )
    st.stop()


# ============================================================
# UI — Formulário (widgets Streamlit — precisam falar com Python)
# ============================================================
email = st.text_input(
    "Email corporativo",
    placeholder=f"usuario@{DOMINIO_PERMITIDO}",
    help=f"Apenas emails do domínio @{DOMINIO_PERMITIDO} são aceitos. "
         "O XML gerado será enviado para este endereço.",
)

numero_duimp = st.text_input(
    "Número da DUIMP",
    placeholder="26BR0000407051-9",
    help="Informe o número da DUIMP a ser consultada no Portal Único.",
)

versao = st.text_input(
    "Versão",
    value="1",
    help="Versão da DUIMP. Em geral é 1, salvo retificações.",
)

st.write("")
enviar = st.button("Gerar XML", type="primary", use_container_width=True)


# ============================================================
# Lógica de envio
# ============================================================
if enviar:
    erros = []

    if not email.strip():
        erros.append("Informe o email.")
    elif not email_valido(email):
        erros.append(
            f"Email inválido. Use um endereço corporativo @{DOMINIO_PERMITIDO} "
            "(ex: seu.nome@" + DOMINIO_PERMITIDO + ")."
        )
    if not numero_duimp.strip():
        erros.append("Informe o número da DUIMP.")
    elif not numero_duimp_valido(numero_duimp):
        erros.append("Número da DUIMP inválido. Confira o número informado.")

    if erros:
        for e in erros:
            st.error(e)
    else:
        with st.spinner("Enviando a DUIMP para processamento..."):
            try:
                payload = montar_payload(email, numero_duimp, versao)
                resp = enviar_para_n8n(WEBHOOK_URL, payload)

                if 200 <= resp.status_code < 300:
                    @st.dialog("Envio realizado")
                    def confirmacao():
                        st.success("DUIMP enviada com sucesso!")
                        st.write(
                            f"O XML da DUIMP **{numero_duimp.strip()}** será "
                            f"encaminhado para **{email.strip()}** assim que o "
                            "backend concluir o processamento."
                        )
                        st.caption(
                            f"Enviado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"
                        )
                        if st.button("OK", use_container_width=True):
                            st.rerun()

                    confirmacao()
                else:
                    st.error(f"O backend respondeu com status {resp.status_code}.")
                    with st.expander("Detalhes da resposta"):
                        st.code(resp.text or "(sem corpo)")
            except requests.exceptions.Timeout:
                st.error("Tempo de resposta excedido. Verifique se o N8N está acessível.")
            except requests.exceptions.ConnectionError:
                st.error("Falha de conexão. Verifique a URL do webhook.")
            except Exception as exc:
                st.error(f"Erro inesperado: {exc}")


# ============================================================
# UI — Footer (vindo do template HTML)
# ============================================================
inject(render_template("footer", ano=datetime.now().year))
