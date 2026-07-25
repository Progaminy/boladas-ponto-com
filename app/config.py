import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_NAME = "Boladas-ponto-com"
APP_VERSION = "0.2.0"

# Número da plataforma para mediação entre compradores e vendedores.
# Não é um campo por post — é uma constante mostrada em toda a aplicação.
PLATFORM_CONTACT_NUMBER = "872599084"

DB_PATH = DATA_DIR / "posts.db"

B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APP_KEY = os.environ.get("B2_APP_KEY")
B2_BUCKET = os.environ.get("B2_BUCKET", "pensador-sem-fronteiras-media")

# Provedor de IA. Em "auto", tenta o Vertex AI Express primeiro e recorre ao
# GMICloud se o primeiro não estiver configurado ou falhar.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "auto").strip().lower()
if AI_PROVIDER not in {"auto", "vertex", "gmicloud"}:
    AI_PROVIDER = "auto"

# Gemini via Vertex AI Express (genai.Client(vertexai=True, api_key=...)).
VERTEX_EXPRESS_API_KEY = os.environ.get("VERTEX_EXPRESS_API_KEY")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
GEMINI_CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash")

GMI_API_KEY = os.environ.get("GMI_API_KEY")
GMI_IMAGE_MODEL = os.environ.get("GMI_IMAGE_MODEL", "seedream-5.0-lite")
GMI_CHAT_MODEL = os.environ.get("GMI_CHAT_MODEL", "deepseek-ai/DeepSeek-V3-0324")

IMAGE_SIZE_PX = 1080

# Protege os créditos do provedor de IA contra abuso: máximo de posts que um
# utilizador pode gerar por dia (janela deslizante de 24h).
MAX_POSTS_PER_USER_PER_DAY = int(os.environ.get("MAX_POSTS_PER_USER_PER_DAY", "10"))

# Usado para assinar o cookie de sessão (login). Em produção define um valor
# aleatório fixo em .env — se não definido, gera-se um por processo (as
# sessões não sobrevivem a um restart, o que é aceitável em dev).
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or os.urandom(32).hex()

# O email que se registar com este endereço fica automaticamente admin
# (acesso a /admin/moderacao). Define no .env antes de te registares.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower() or None


def b2_configured() -> bool:
    return bool(B2_KEY_ID and B2_APP_KEY and B2_BUCKET)


def vertex_configured() -> bool:
    return bool(VERTEX_EXPRESS_API_KEY)


def gmi_configured() -> bool:
    return bool(GMI_API_KEY)


def ai_provider_order() -> list[str]:
    """Ordem real de tentativa dos provedores configurados. Só devolve
    provedores que estão mesmo configurados — uma lista vazia significa que
    não há forma de gerar, e a aplicação deve dizê-lo em vez de fingir."""
    if AI_PROVIDER == "vertex":
        return ["vertex"] if vertex_configured() else []
    if AI_PROVIDER == "gmicloud":
        return ["gmicloud"] if gmi_configured() else []

    providers: list[str] = []
    if vertex_configured():
        providers.append("vertex")
    if gmi_configured():
        providers.append("gmicloud")
    return providers
