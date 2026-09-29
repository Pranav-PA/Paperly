from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Paperly"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security & Auth
    SECRET_KEY: str = "dev_secret_key_paperly_2026_super_secure_32bytes_min!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Database
    DATABASE_URL: str = "sqlite:///./paperly.db"

    # Storage
    UPLOAD_DIR: str = "./uploads"
    GENERATED_PAPERS_DIR: str = "./generated_papers"

    # AI Service (Google Gemini)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Performance & Concurrency on Termux
    MAX_CONCURRENT_GENERATIONS: int = 2

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self) -> None:
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.GENERATED_PAPERS_DIR).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
