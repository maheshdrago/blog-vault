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
    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_algorithms: list[str] = ["ES256", "RS256"]
    auth_allowed_origins: list[str] = ["http://localhost:5173"]
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = Field(default="lax", pattern=r"^(lax|strict)$")
    auth_idle_days: int = Field(default=30, ge=1, le=365)
    auth_absolute_days: int = Field(default=90, ge=1, le=365)
    auth_callback_url: str | None = None
    mcp_resource_url: str = "http://localhost:8000/mcp/"
    mcp_oauth_issuer_url: str | None = None
    mcp_oauth_audience: str = "authenticated"
    ip_hmac_secret: SecretStr | None = None
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

    @property
    def auth_configured(self) -> bool:
        """Return whether the identity provider can service auth requests."""
        return (
            self.supabase_url is not None and self.supabase_publishable_key is not None
        )

    @property
    def auth_issuer(self) -> str | None:
        """Return the explicit or conventional Supabase Auth JWT issuer."""
        if self.supabase_jwt_issuer is not None:
            return self.supabase_jwt_issuer.rstrip("/")
        if self.supabase_url is None:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def mcp_oauth_issuer(self) -> str:
        """Return the OAuth issuer advertised by the MCP resource server."""
        return (
            self.mcp_oauth_issuer_url.rstrip("/")
            if self.mcp_oauth_issuer_url is not None
            else self.auth_issuer or "http://localhost:8000"
        )

    @field_validator("langfuse_environment")
    @classmethod
    def validate_langfuse_environment(cls, value: str) -> str:
        """Reject the namespace reserved by Langfuse itself."""
        if value.startswith("langfuse"):
            raise ValueError("Langfuse environment cannot start with 'langfuse'.")
        return value

    @field_validator("allowed_origins", "auth_allowed_origins")
    @classmethod
    def require_exact_origins(cls, values: list[str]) -> list[str]:
        """Reject wildcard origins because browser credentials are enabled."""
        normalized = [value.rstrip("/") for value in values]
        if not normalized or "*" in normalized:
            raise ValueError("Credentialed browser access requires exact origins.")
        return normalized

    @field_validator("mcp_resource_url")
    @classmethod
    def normalize_mcp_resource_url(cls, value: str) -> str:
        """Require one absolute, canonical MCP resource URL."""
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Public service URLs must be absolute HTTP(S) URLs.")
        return f"{normalized.rstrip('/')}/"

    @field_validator("mcp_oauth_issuer_url")
    @classmethod
    def normalize_optional_issuer(cls, value: str | None) -> str | None:
        """Normalize an explicitly configured OAuth authorization server issuer."""
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("The OAuth issuer must be an absolute HTTP(S) URL.")
        return normalized


settings = Settings()
