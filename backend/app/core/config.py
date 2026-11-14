"""App settings loaded from .env"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "Flame in Freefall API"
    DATA_RAW_DIR: Path = ROOT_DIR / "data" / "raw"
    DATA_PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"
    VECTORSTORE_DIR: Path = ROOT_DIR / "data" / "vectorstore"
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR / 'data' / 'flame.db'}"

    # LLM: "ollama" (local, free) or "gemini" / "openai"
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3.1"
    LLM_API_KEY: str = ""
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")


settings = Settings()
