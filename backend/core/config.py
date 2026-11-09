"""Centralised application configuration for FactoryAssist AI.

All settings are read from the root ``.env`` file (falling back to the
defaults declared below), so nothing has to be hardcoded elsewhere in the
codebase. Import ``settings`` from this module wherever configuration is
needed.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is derived from this file's location, so the application works
# regardless of the directory it is launched from.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
ENV_FILE: Path = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "FactoryAssist AI"
    app_version: str = "1.0.0"
    debug: bool = True

    # --- Google Gemini ---
    # The key is intentionally optional: the application must start (and report
    # its status) without it, and AI features raise a clear error until it is set.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 1024
    gemini_timeout_seconds: int = 60

    # --- Storage locations ---
    chroma_persist_directory: Path = Path("vector_store/chroma_db")
    active_documents_directory: Path = Path("documents/active")
    archived_documents_directory: Path = Path("documents/archived")
    sample_questions_directory: Path = Path("documents/sample_questions")
    processed_data_directory: Path = Path("data/processed")

    # --- Text chunking (characters) ---
    chunk_size: int = 900
    chunk_overlap: int = 150

    # --- Embeddings and vector retrieval ---
    embedding_batch_size: int = 24
    embedding_dimensions: int | None = None
    chroma_active_collection: str = "factoryassist_active_documents"
    retrieval_top_k: int = 5
    retrieval_min_similarity: float = 0.30

    # --- API limits ---
    max_question_length: int = 1000

    # --- Frontend ---
    frontend_directory: Path = Path("frontend")

    # --- Server ---
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    @field_validator(
        "chroma_persist_directory",
        "active_documents_directory",
        "archived_documents_directory",
        "sample_questions_directory",
        "processed_data_directory",
        "frontend_directory",
        mode="after",
    )
    @classmethod
    def _resolve_against_project_root(cls, value: Path) -> Path:
        """Turn relative paths from ``.env`` into absolute project paths."""
        if value.is_absolute():
            return value
        return (PROJECT_ROOT / value).resolve()

    @property
    def is_gemini_configured(self) -> bool:
        """Whether a Gemini API key is present, without exposing its value."""
        return bool(self.gemini_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()


settings: Settings = get_settings()
