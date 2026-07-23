"""Privacy-conscious Langfuse tracing for MCP publication operations."""

import re
from collections.abc import Callable
from typing import Any, Final, Literal, TypeVar

from langfuse import Langfuse, observe

from .config import settings

ObservationType = Literal["chain", "retriever", "tool"]

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
_REDACTED: Final[str] = "[REDACTED]"
_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "content",
        "cookie",
        "csrf_token",
        "database_url",
        "experience_html",
        "github_token",
        "html",
        "password",
        "access_token",
        "refresh_token",
        "secret",
        "secret_key",
        "source",
        "token",
    }
)
_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_-]+"),
    re.compile(r"\b(?:sk-lf|pk-lf)-[A-Za-z0-9_-]+"),
)


def mask_trace_data(data: Any, **_: Any) -> Any:
    """Recursively redact credentials and large authored content from traces."""
    if isinstance(data, dict):
        return {
            str(key): (
                _REDACTED
                if str(key).casefold() in _SENSITIVE_KEYS
                else mask_trace_data(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [mask_trace_data(value) for value in data]
    if isinstance(data, str):
        masked = data
        for pattern in _SECRET_PATTERNS:
            masked = pattern.sub(_REDACTED, masked)
        return masked
    return data


def _create_client() -> Langfuse | None:
    """Create one disabled-by-default client from validated application settings."""
    if not settings.langfuse_configured:
        return None
    assert settings.langfuse_public_key is not None
    assert settings.langfuse_secret_key is not None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        environment=settings.langfuse_environment,
        sample_rate=settings.langfuse_sample_rate,
        mask=mask_trace_data,
    )


_client = _create_client()


def trace_observation(
    name: str,
    *,
    as_type: ObservationType = "tool",
) -> Callable[[_CallableT], _CallableT]:
    """Trace a function without automatically recording arguments or results."""
    if _client is None:
        return lambda function: function
    decorator = observe(
        name=name,
        as_type=as_type,
        capture_input=False,
        capture_output=False,
    )
    return decorator


def update_current_observation(
    *,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Attach a deliberately small, non-sensitive payload to the current span."""
    if _client is None:
        return
    _client.update_current_span(
        input=input,
        output=output,
        metadata=metadata,
    )


def shutdown_telemetry() -> None:
    """Flush queued traces and stop Langfuse background workers."""
    if _client is not None:
        _client.shutdown()
