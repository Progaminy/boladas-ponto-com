import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
APP_NAME = "Boladas-ponto-com"
APP_VERSION = "0.4.0"
PLATFORM_CONTACT_NUMBER = "872599084"
DB_PATH = DATA_DIR / "posts.db"

B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APP_KEY = os.environ.get("B2_APP_KEY")
B2_BUCKET = os.environ.get("B2_BUCKET", "pensador-sem-fronteiras-media")
B2_REGION = os.environ.get("B2_REGION", "us-east-005")
B2_MEDIA_PREFIX = os.environ.get("B2_MEDIA_PREFIX", "").strip().lstrip("/")
if B2_MEDIA_PREFIX and not B2_MEDIA_PREFIX.endswith("/"):
    B2_MEDIA_PREFIX += "/"

MAX_POSTS_PER_USER_PER_DAY = int(os.environ.get("MAX_POSTS_PER_USER_PER_DAY", "10"))
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or os.urandom(32).hex()
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower() in {"1", "true", "sim"}
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower() or None


def b2_configured() -> bool:
    return bool(B2_KEY_ID and B2_APP_KEY and B2_BUCKET and B2_REGION)
