import json
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_SECRET_KEY_FILE = BACKEND_DIR / ".secret_key"


def _load_or_create_secret_key() -> str:
    """Persist a random signing key on first run so tokens survive restarts."""
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    _SECRET_KEY_FILE.chmod(0o600)
    return key


_DISCOVERY_FILE = BACKEND_DIR / ".discovery.json"


def _load_or_create_discovery() -> dict:
    """Random, private ntfy channel + signing key used to tell the app the tunnel's current address."""
    if _DISCOVERY_FILE.exists():
        return json.loads(_DISCOVERY_FILE.read_text())
    data = {"topic": f"paperly-{secrets.token_urlsafe(18)}", "key": secrets.token_hex(32)}
    _DISCOVERY_FILE.write_text(json.dumps(data))
    _DISCOVERY_FILE.chmod(0o600)
    return data


class Settings(BaseSettings):
    APP_NAME: str = "Paperly"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security & Auth. Leave SECRET_KEY empty to use an auto-generated key stored in .secret_key
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Database
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'paperly.db'}"

    # Storage
    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    GENERATED_PAPERS_DIR: str = str(BACKEND_DIR / "generated_papers")
    MAX_UPLOAD_MB: int = 15

    # AI Service (Google Gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    # Gemini 3.x thinking depth: low | medium | high. Chat turns always use "low".
    GEMINI_THINKING_LEVEL: str = "medium"

    # Address discovery: the phone posts its (signed) tunnel URL here so apps follow URL changes automatically.
    DISCOVERY_SERVER: str = "https://ntfy.sh"
    DISCOVERY_TOPIC: str = ""
    DISCOVERY_KEY: str = ""

    # Performance & Concurrency on Termux
    MAX_CONCURRENT_GENERATIONS: int = 4

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.GEMINI_API_KEY) and self.GEMINI_API_KEY not in (
            "dummy_key_for_testing",
            "your_gemini_api_key_here",
        )

    @property
    def DOCS_DIR(self) -> str:
        return str(Path(self.UPLOAD_DIR) / "documents")

    def ensure_directories(self) -> None:
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DOCS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.GENERATED_PAPERS_DIR).mkdir(parents=True, exist_ok=True)


settings = Settings()
if not settings.SECRET_KEY or settings.SECRET_KEY.startswith("change_this"):
    settings.SECRET_KEY = _load_or_create_secret_key()
if not settings.DISCOVERY_TOPIC or not settings.DISCOVERY_KEY:
    _discovery = _load_or_create_discovery()
    settings.DISCOVERY_TOPIC = settings.DISCOVERY_TOPIC or _discovery["topic"]
    settings.DISCOVERY_KEY = settings.DISCOVERY_KEY or _discovery["key"]
settings.ensure_directories()
