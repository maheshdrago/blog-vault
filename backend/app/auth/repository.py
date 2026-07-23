"""Persistence and ownership rules for authenticated profiles and sessions."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..tables import (
    ArticleTable,
    LearningPathTable,
    ReaderProfileTable,
    SecurityEventTable,
    UserSessionTable,
)
from .jwt_verifier import VerifiedClaims
from .models import AppRole, AuthenticatedPrincipal, AuthUser, UserSession
from .provider import ProviderUser


class SessionRejectedError(RuntimeError):
    """Raised when an application session is unknown, expired, or revoked."""


def hash_csrf_token(token: str) -> str:
    """Hash a high-entropy CSRF value before database persistence."""
    return sha256(token.encode()).hexdigest()


class AuthRepository:
    """Resolve provider identities into Blog Vault-owned authorization data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_profile(self, user: ProviderUser) -> ReaderProfileTable:
        """Load or create the stable application profile for an identity."""
        profile = await self._session.scalar(
            select(ReaderProfileTable).where(
                ReaderProfileTable.auth_user_id == UUID(user.user_id)
            )
        )
        metadata = user.metadata
        display_name = (
            metadata.get("display_name")
            or metadata.get("full_name")
            or metadata.get("name")
        )
        avatar_url = metadata.get("avatar_url") or metadata.get("picture")
        if profile is None:
            profile = ReaderProfileTable(
                reader_id=uuid4(),
                auth_user_id=UUID(user.user_id),
                display_name=str(display_name)[:80] if display_name else None,
                avatar_url=str(avatar_url)[:500] if avatar_url else None,
                app_role=AppRole.READER.value,
            )
            self._session.add(profile)
            await self._session.flush()
            await self._claim_unowned_vault(profile.reader_id)
        else:
            if display_name and not profile.display_name:
                profile.display_name = str(display_name)[:80]
            if avatar_url and not profile.avatar_url:
                profile.avatar_url = str(avatar_url)[:500]
        return profile

    async def _claim_unowned_vault(self, reader_id: UUID) -> None:
        """Atomically assign all legacy content to the first created profile."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('blog-vault-bootstrap'))")
        )
        existing_owner = await self._session.scalar(
            select(ArticleTable.owner_reader_id).where(
                ArticleTable.owner_reader_id.is_not(None)
            )
        )
        if existing_owner is not None:
            return
        await self._session.execute(
            update(ArticleTable)
            .where(ArticleTable.owner_reader_id.is_(None))
            .values(owner_reader_id=reader_id)
        )
        await self._session.execute(
            update(LearningPathTable)
            .where(LearningPathTable.owner_reader_id.is_(None))
            .values(owner_reader_id=reader_id)
        )

    async def register_session(
        self,
        *,
        claims: VerifiedClaims,
        user: ProviderUser,
        csrf_token: str,
        user_agent: str | None,
    ) -> tuple[ReaderProfileTable, UserSessionTable]:
        """Create or restore an application session after provider authentication."""
        profile = await self.ensure_profile(user)
        now = datetime.now(UTC)
        row = await self._session.get(UserSessionTable, claims.session_id)
        expires_at = now + timedelta(days=settings.auth_absolute_days)
        if row is None:
            row = UserSessionTable(
                session_id=claims.session_id,
                auth_user_id=claims.auth_user_id,
                reader_id=profile.reader_id,
                user_agent=self._clean_user_agent(user_agent),
                device_label=self._device_label(user_agent),
                expires_at=expires_at,
                csrf_token_hash=hash_csrf_token(csrf_token),
            )
            self._session.add(row)
        else:
            if row.auth_user_id != claims.auth_user_id:
                raise SessionRejectedError("Session ownership is inconsistent.")
            row.last_seen_at = now
            row.revoked_at = None
            row.revoked_reason = None
            row.csrf_token_hash = hash_csrf_token(csrf_token)
        await self.record_event(
            auth_user_id=claims.auth_user_id,
            session_id=claims.session_id,
            event_type="sign_in_succeeded",
        )
        await self._session.flush()
        return profile, row

    async def authenticate(self, claims: VerifiedClaims) -> AuthenticatedPrincipal:
        """Enforce immediate application-session revocation and expiry."""
        row = await self._session.get(UserSessionTable, claims.session_id)
        now = datetime.now(UTC)
        if row is None or row.auth_user_id != claims.auth_user_id:
            raise SessionRejectedError("The application session is not active.")
        last_seen = self._aware(row.last_seen_at)
        if row.revoked_at is not None or self._aware(row.expires_at) <= now:
            raise SessionRejectedError("The application session has expired.")
        if last_seen + timedelta(days=settings.auth_idle_days) <= now:
            row.revoked_at = now
            row.revoked_reason = "idle_expired"
            raise SessionRejectedError("The application session has expired.")
        profile = await self._session.get(ReaderProfileTable, row.reader_id)
        if profile is None or profile.auth_user_id != claims.auth_user_id:
            raise SessionRejectedError("The reader profile is unavailable.")
        if last_seen + timedelta(minutes=5) <= now:
            row.last_seen_at = now
        return AuthenticatedPrincipal(
            auth_user_id=claims.auth_user_id,
            reader_id=profile.reader_id,
            session_id=claims.session_id,
            role=AppRole(profile.app_role),
            assurance_level=claims.assurance_level,
            email=claims.email,
        )

    async def verify_csrf(self, session_id: UUID, token: str) -> bool:
        """Compare a request CSRF token with its session-bound hash."""
        row = await self._session.get(UserSessionTable, session_id)
        return row is not None and row.csrf_token_hash == hash_csrf_token(token)

    async def rotate_csrf(self, session_id: UUID, token: str) -> None:
        """Bind a fresh browser CSRF value to a successfully rotated session."""
        row = await self._session.get(UserSessionTable, session_id)
        if row is None:
            raise SessionRejectedError("The application session is not active.")
        row.csrf_token_hash = hash_csrf_token(token)
        row.last_seen_at = datetime.now(UTC)
        await self.record_event(
            auth_user_id=row.auth_user_id,
            session_id=row.session_id,
            event_type="session_refreshed",
        )

    async def auth_user(self, principal: AuthenticatedPrincipal) -> AuthUser:
        """Return safe profile fields for the current identity."""
        profile = await self._session.get(ReaderProfileTable, principal.reader_id)
        if profile is None:
            raise SessionRejectedError("The reader profile is unavailable.")
        return AuthUser(
            auth_user_id=principal.auth_user_id,
            reader_id=principal.reader_id,
            email=principal.email,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            role=principal.role,
            assurance_level=principal.assurance_level,
        )

    async def list_sessions(
        self, principal: AuthenticatedPrincipal
    ) -> list[UserSession]:
        """List only the current user's devices."""
        rows = await self._session.scalars(
            select(UserSessionTable)
            .where(UserSessionTable.auth_user_id == principal.auth_user_id)
            .order_by(UserSessionTable.last_seen_at.desc())
        )
        return [
            UserSession(
                session_id=row.session_id,
                device_label=row.device_label or "Unknown browser",
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
                is_current=row.session_id == principal.session_id,
            )
            for row in rows
        ]

    async def revoke_session(
        self, principal: AuthenticatedPrincipal, session_id: UUID
    ) -> bool:
        """Revoke one session only when it belongs to the caller."""
        row = await self._session.get(UserSessionTable, session_id)
        if row is None or row.auth_user_id != principal.auth_user_id:
            return False
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            row.revoked_reason = "user_revoked"
            await self.record_event(
                auth_user_id=principal.auth_user_id,
                session_id=session_id,
                event_type="session_revoked",
            )
        return True

    async def revoke_other_sessions(self, principal: AuthenticatedPrincipal) -> int:
        """Revoke every device except the one making the request."""
        rows = list(
            await self._session.scalars(
                select(UserSessionTable).where(
                    UserSessionTable.auth_user_id == principal.auth_user_id,
                    UserSessionTable.session_id != principal.session_id,
                    UserSessionTable.revoked_at.is_(None),
                )
            )
        )
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
            row.revoked_reason = "user_revoked"
        return len(rows)

    async def record_event(
        self,
        *,
        auth_user_id: UUID,
        session_id: UUID | None,
        event_type: str,
    ) -> None:
        """Persist a bounded event without credentials or direct identifiers."""
        self._session.add(
            SecurityEventTable(
                auth_user_id=auth_user_id,
                session_id=session_id,
                event_type=event_type,
                event_metadata={},
            )
        )

    @staticmethod
    def _clean_user_agent(value: str | None) -> str | None:
        if value is None:
            return None
        return "".join(character for character in value if character.isprintable())[
            :512
        ]

    @staticmethod
    def _device_label(value: str | None) -> str:
        user_agent = (value or "").lower()
        browser = next(
            (
                label
                for marker, label in (
                    ("firefox", "Firefox"),
                    ("edg/", "Edge"),
                    ("chrome", "Chrome"),
                    ("safari", "Safari"),
                )
                if marker in user_agent
            ),
            "Browser",
        )
        platform = next(
            (
                label
                for marker, label in (
                    ("iphone", "iPhone"),
                    ("android", "Android"),
                    ("mac os", "macOS"),
                    ("windows", "Windows"),
                    ("linux", "Linux"),
                )
                if marker in user_agent
            ),
            "device",
        )
        return f"{browser} on {platform}"

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
