"""Shared policy for safe semantic blog HTML."""

from typing import Final

ALLOWED_HTML_TAGS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "blockquote",
        "br",
        "cite",
        "code",
        "em",
        "h2",
        "h3",
        "hr",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "strong",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)

ALLOWED_HTML_ATTRIBUTES: Final[dict[str, tuple[str, ...]]] = {
    "a": ("href", "title"),
    "img": ("src", "alt", "title"),
    "p": ("class",),
}

ALLOWED_HTML_PROTOCOLS: Final[frozenset[str]] = frozenset({"http", "https", "mailto"})

INTERACTIVE_EXPERIENCE_PATH_PATTERN: Final[str] = (
    r"^/posts/[a-z0-9]+(?:-[a-z0-9]+)*/experience$"
)


def mutable_html_attributes() -> dict[str, list[str]]:
    """Return the list-based attribute mapping expected by Bleach."""
    return {
        tag: list(attributes) for tag, attributes in ALLOWED_HTML_ATTRIBUTES.items()
    }
