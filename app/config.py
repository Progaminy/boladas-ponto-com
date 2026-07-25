import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_NAME = "Boladas-ponto-com"
APP_VERSION = "0.1.0"

# Número da plataforma para mediação entre compradores e vendedores.
# Não é um campo por post — é uma constante mostrada em toda a aplicação.
PLATFORM_CONTACT_NUMBER = "872599084"

DB_PATH = DATA_DIR / "posts.db"

B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APP_KEY = os.environ.get("B2_APP_KEY")
B2_BUCKET = os.environ.get("B2_BUCKET", "pensador-sem-fronteiras-media")

GMI_API_KEY = os.environ.get("GMI_API_KEY")
GMI_IMAGE_MODEL = os.environ.get("GMI_IMAGE_MODEL", "seedream-5.0-lite")
GMI_CHAT_MODEL = os.environ.get("GMI_CHAT_MODEL", "deepseek-ai/DeepSeek-V3-0324")

IMAGE_SIZE_PX = 1080

# Protege os créditos do GMICloud contra abuso: máximo de posts que um
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


def gmi_configured() -> bool:
    return bool(GMI_API_KEY)
