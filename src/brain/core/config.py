"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import os

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file at import time
load_dotenv(override=True)


class VaultConfig(BaseSettings):
    """Obsidian vault configuration."""

    path: Path = Field(default=Path("D:/obsdn/Personal"))
    watch_interval: float = 1.0
    ignore_patterns: list[str] = Field(
        default_factory=lambda: [".obsidian/*", ".trash/*", "*.excalidraw.md"]
    )


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    sqlite_path: Path = Field(default=Path("./data/brain.db"))
    chroma_path: Path = Field(default=Path("./data/chroma"))


class EmbeddingsConfig(BaseSettings):
    """Embeddings configuration."""

    provider: str = "openai"
    model: str = "text-embedding-3-small"
    batch_size: int = 100
    cache_enabled: bool = True


class ClaudeConfig(BaseSettings):
    """Claude API configuration."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7


class RetrievalConfig(BaseSettings):
    """Retrieval configuration."""

    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    max_results: int = 20
    link_expansion_hops: int = 1


class ChunkingConfig(BaseSettings):
    """Chunking configuration."""

    strategy: str = "semantic"
    max_chunk_size: int = 512
    overlap: int = 50


class SchedulerConfig(BaseSettings):
    """Scheduler configuration."""

    briefing_time: str = "07:00"
    reminder_check_interval: int = 15
    timezone: str = "UTC"


class ApiConfig(BaseSettings):
    """API configuration."""

    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


class N8nConfig(BaseSettings):
    """N8n webhook configuration."""

    enabled: bool = True
    webhook_url: str = ""


class NotificationsConfig(BaseSettings):
    """Notifications configuration."""

    enabled: bool = True
    desktop: bool = True
    n8n: N8nConfig = Field(default_factory=N8nConfig)


class AppConfig(BaseSettings):
    """Application configuration."""

    name: str = "Personal Brain"
    debug: bool = False
    log_level: str = "INFO"


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="BRAIN_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

    # API keys (read directly from env, no prefix)
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    n8n_webhook_url: str = Field(default="")


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_config(config_path: Path | None = None) -> Config:
    """Get configuration instance (cached)."""
    if config_path is None:
        config_path = Path("config/default.yaml")

    yaml_config = load_yaml_config(config_path)

    # Manually inject API keys from environment (without BRAIN_ prefix)
    yaml_config["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
    yaml_config["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")
    yaml_config["n8n_webhook_url"] = os.getenv("N8N_WEBHOOK_URL", "")

    return Config(**yaml_config)
