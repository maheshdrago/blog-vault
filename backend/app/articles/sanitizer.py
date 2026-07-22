"""Shared normalization helpers for stored article content."""

import bleach

from .content_policy import (
    ALLOWED_HTML_PROTOCOLS,
    ALLOWED_HTML_TAGS,
    mutable_html_attributes,
)


def sanitize_article_html(html: str) -> str:
    """Return semantic article HTML permitted by the shared content policy."""
    return bleach.clean(
        html,
        tags=ALLOWED_HTML_TAGS,
        attributes=mutable_html_attributes(),
        protocols=ALLOWED_HTML_PROTOCOLS,
        strip=True,
    ).strip()
