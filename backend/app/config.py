"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Blog Vault service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BLOG_",
        extra="ignore",
    )

    project_root: Path = Path(__file__).resolve().parents[2]
    allowed_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr | None = None
    mcp_access_token: SecretStr | None = None
    admin_access_token: SecretStr | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://us.cloud.langfuse.com"
    langfuse_environment: str = Field(
        default="development",
        pattern=r"^[a-z0-9_-]{1,40}$",
    )
    langfuse_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def langfuse_configured(self) -> bool:
        """Return whether both required Langfuse credentials are available."""
        return (
            self.langfuse_public_key is not None
            and self.langfuse_secret_key is not None
        )

    @field_validator("langfuse_environment")
    @classmethod
    def validate_langfuse_environment(cls, value: str) -> str:
        """Reject the namespace reserved by Langfuse itself."""
        if value.startswith("langfuse"):
            raise ValueError("Langfuse environment cannot start with 'langfuse'.")
        return value


settings = Settings()
