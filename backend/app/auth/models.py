"""Typed request, response, and principal models for authentication."""

import re
from datetime import datetime
from enum import StrEnum
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from pydantic import Field, field_validator

from ..models import ApiModel

# Supabase issues opaque OAuth authorization identifiers (base32-style tokens),
# not UUIDs. Accept URL-safe tokens (UUID strings still match this shape).
OAUTH_AUTHORIZATION_ID_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"
_OAUTH_AUTHORIZATION_ID = re.compile(OAUTH_AUTHORIZATION_ID_PATTERN)


class AppRole(StrEnum):
    """Server-owned application authorization roles."""

    READER = "reader"
    ADMIN = "admin"


class AssuranceLevel(StrEnum):
    """Supabase authenticator assurance levels."""

    AAL1 = "aal1"
    AAL2 = "aal2"


class AuthenticatedPrincipal:
    """Verified request identity resolved to an application profile."""

    def __init__(
        self,
        *,
        auth_user_id: UUID,
        reader_id: UUID,
        session_id: UUID,
        role: AppRole,
        assurance_level: AssuranceLevel,
        email: str | None,
    ) -> None:
        self.auth_user_id = auth_user_id
        self.reader_id = reader_id
        self.session_id = session_id
        self.role = role
        self.assurance_level = assurance_level
        self.email = email


class EmailInput(ApiModel):
    """Normalized email supplied to a provider-owned identity operation."""

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Apply a conservative email shape check without storing the value."""
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@"):
            raise ValueError("Enter a valid email address.")
        return normalized


class SignInInput(EmailInput):
    """Existing credentials forwarded only to Supabase Auth."""

    password: str = Field(min_length=1, max_length=1_024)


def is_safe_auth_return_path(value: str) -> bool:
    """Return whether a post-authentication path stays inside Blog Vault."""
    if value in {"/", "/account", "/auth?mode=update"}:
        return True
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path != "/oauth/consent"
    ):
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {"authorization_id"} or len(query["authorization_id"]) != 1:
        return False
    return _OAUTH_AUTHORIZATION_ID.match(query["authorization_id"][0]) is not None


def validate_auth_return_path(value: str) -> str:
    """Validate an application-owned post-authentication destination."""
    if not is_safe_auth_return_path(value):
        raise ValueError("Unsupported authentication return path.")
    return value


class SignUpInput(EmailInput):
    """New account credentials subject to the application password floor."""

    password: str = Field(min_length=8, max_length=1_024)
    display_name: str | None = Field(default=None, max_length=80)
    return_to: str = Field(default="/", max_length=200)

    @field_validator("return_to")
    @classmethod
    def allow_safe_return_path(cls, value: str) -> str:
        """Accept only application-owned post-verification destinations."""
        return validate_auth_return_path(value)


class OAuthProvider(StrEnum):
    """OAuth providers intentionally enabled by the UI."""

    GOOGLE = "google"
    GITHUB = "github"


class OAuthStartInput(ApiModel):
    """Start an allowlisted OAuth PKCE flow."""

    provider: OAuthProvider
    return_to: str = Field(default="/", max_length=200)

    @field_validator("return_to")
    @classmethod
    def allow_safe_return_path(cls, value: str) -> str:
        """Accept only application-owned post-authentication destinations."""
        return validate_auth_return_path(value)


class AuthUser(ApiModel):
    """Safe account data returned to the browser."""

    auth_user_id: UUID
    reader_id: UUID
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    role: AppRole
    assurance_level: AssuranceLevel


class AuthSessionResponse(ApiModel):
    """Memory-only access credentials plus safe account details."""

    access_token: str | None = None
    expires_in: int | None = Field(default=None, ge=1)
    expires_at: int | None = None
    user: AuthUser | None = None
    verification_required: bool = False
    message: str | None = None


class OAuthStartResponse(ApiModel):
    """Supabase authorization URL to which the browser should navigate."""

    authorization_url: str


class OAuthAuthorizationClient(ApiModel):
    """Safe client metadata displayed on the OAuth consent screen."""

    id: str
    name: str
    # Dynamically registered clients (e.g. Claude) may omit these, so Supabase
    # returns the authorization without them.
    uri: str | None = None
    logo_uri: str | None = None


class OAuthAuthorizationUser(ApiModel):
    """Identity summary Supabase binds to an authorization request."""

    id: UUID
    email: str


class OAuthAuthorizationDetails(ApiModel):
    """Validated details for a pending OAuth authorization request."""

    authorization_id: str
    redirect_uri: str
    client: OAuthAuthorizationClient
    user: OAuthAuthorizationUser
    scope: str


class OAuthRedirect(ApiModel):
    """Trusted provider redirect after an OAuth consent decision."""

    redirect_url: str


class OAuthConsentDecision(StrEnum):
    """Explicit decisions accepted by the authorization UI."""

    APPROVE = "approve"
    DENY = "deny"


class OAuthConsentInput(ApiModel):
    """One explicit authorization decision."""

    decision: OAuthConsentDecision


class OAuthGrant(ApiModel):
    """One OAuth client authorization owned by the current user."""

    client: OAuthAuthorizationClient
    scopes: list[str]
    granted_at: datetime


class UserSession(ApiModel):
    """Privacy-conscious device information shown to its owner."""

    session_id: UUID
    device_label: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    is_current: bool


class McpCredentialCreateInput(ApiModel):
    """Human-readable label for a new personal MCP credential."""

    label: str = Field(min_length=1, max_length=80)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        """Reject blank labels and discard surrounding whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Credential labels cannot be blank.")
        return normalized


class McpCredential(ApiModel):
    """Safe metadata for one revocable personal MCP credential."""

    credential_id: UUID
    label: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class McpCredentialCreated(McpCredential):
    """New MCP token returned exactly once at creation."""

    token: str


class PasswordResetInput(EmailInput):
    """Password recovery request with enumeration-safe response behavior."""


class PasswordUpdateInput(ApiModel):
    """New password for an authenticated recovery or account session."""

    password: str = Field(min_length=8, max_length=1_024)


class MessageResponse(ApiModel):
    """Generic non-sensitive operation result."""

    message: str
