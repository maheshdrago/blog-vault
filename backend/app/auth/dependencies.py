"""FastAPI identity dependencies and authorization boundaries."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from ..database import DatabaseSession
from .jwt_verifier import AccessTokenError, jwt_verifier
from .models import AppRole, AssuranceLevel, AuthenticatedPrincipal
from .repository import AuthRepository, SessionRejectedError


def bearer_token(authorization: str | None) -> str:
    """Extract a strict Bearer credential without accepting alternate schemes."""
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def require_principal(
    session: DatabaseSession,
    authorization: str | None = Header(default=None),
) -> AuthenticatedPrincipal:
    """Verify a Supabase JWT and enforce application-session state."""
    try:
        claims = await jwt_verifier.verify(bearer_token(authorization))
        return await AuthRepository(session).authenticate(claims)
    except (AccessTokenError, SessionRejectedError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


Principal = Annotated[AuthenticatedPrincipal, Depends(require_principal)]


def require_role(
    principal: AuthenticatedPrincipal,
    role: AppRole,
    *,
    require_aal2: bool = False,
) -> None:
    """Enforce application-owned role and optional MFA assurance."""
    if principal.role is not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have permission for that action.",
        )
    if require_aal2 and principal.assurance_level is not AssuranceLevel.AAL2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication is required for this action.",
        )
