"""Tests for research-backed interactive article authoring policy."""

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.articles.authoring_policy import (
    ARTICLE_CONTRACT_VERSION,
    ARTICLE_THEME_FALLBACKS,
    REQUIRED_ARTICLE_THEME_TOKENS,
    build_authoring_prompt,
)
from backend.app.models import InteractivePostInput, ResearchSource


def theme_block(theme: str) -> str:
    """Build a complete theme block for validation fixtures."""
    declarations = ";".join(
        f"{token}: {ARTICLE_THEME_FALLBACKS[theme][token]}"
        for token in REQUIRED_ARTICLE_THEME_TOKENS
    )
    return f'html[data-theme="{theme}"] {{{declarations};}}'


def experience_html() -> str:
    """Return the smallest complete experience accepted by the policy."""
    filler = "A detailed accessible explanation. " * 20
    return f"""<!doctype html>
<html lang="en" data-article-contract="{ARTICLE_CONTRACT_VERSION}" data-theme="light">
<head><title>Quality validation fixture</title><style>
{theme_block("light")}
{theme_block("dark")}
body {{ background: var(--article-bg); color: var(--article-text); }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style></head><body><main>
<h1>Quality validation fixture</h1>
<h2 id="model">Mental model</h2><p>{filler}</p>
<h2 id="tradeoffs">Tradeoffs</h2><p>{filler}</p>
</main></body></html>"""


def research_sources() -> list[ResearchSource]:
    """Return independent, traceable research sources."""
    return [
        ResearchSource(
            publisher="Standards body",
            title="Primary specification",
            url="https://www.rfc-editor.org/rfc/rfc9110",
            claim_supported="Defines the relevant protocol semantics.",
        ),
        ResearchSource(
            publisher="Research lab",
            title="Original research",
            url="https://arxiv.org/abs/1706.03762",
            claim_supported="Provides the original technical method.",
        ),
        ResearchSource(
            publisher="Vendor documentation",
            title="Current implementation guide",
            url="https://developer.mozilla.org/en-US/docs/Web/HTTP",
            claim_supported="Documents current browser implementation behavior.",
        ),
    ]


def test_authoring_prompt_requires_browsing_and_purposeful_animation() -> None:
    """The MCP prompt should encode the non-negotiable editorial workflow."""
    prompt = build_authoring_prompt(
        "How browsers cache requests",
        "software engineers",
        interactive=True,
        user_instructions=("Use one shopping-cart request as the end-to-end example."),
    )

    assert "Browse the live internet" in prompt
    assert "at least three independent authoritative sources" in prompt
    assert "Do not animate decoration" in prompt
    assert "Blog Vault is the only theme owner" in prompt
    assert "Use one shopping-cart request" in prompt
    assert "what problem does it solve" in prompt
    assert "140–220 character summary" in prompt
    assert "3–6 lowercase" in prompt
    assert "--article-bg" in prompt
    assert "data-article-state-target" in prompt


def test_interactive_post_generates_canonical_experience_path() -> None:
    """Publication input should bind semantic and animated files to one slug."""
    draft = InteractivePostInput(
        title="A researched article",
        slug="a-researched-article",
        date=date(2026, 7, 20),
        description="A precise description of the researched article.",
        tags=["systems"],
        html="<h2>Mental model</h2><p>Semantic explanation.</p>",
        experience_html=experience_html(),
        research_sources=research_sources(),
    )

    assert draft.to_post_input().experience == (
        "/posts/a-researched-article/experience"
    )


def test_interactive_post_rejects_incomplete_dark_theme() -> None:
    """Every required token must be configurable in both themes."""
    invalid_experience = experience_html().replace(
        theme_block("dark"),
        theme_block("dark").replace("--article-danger: #f0616d;", ""),
    )

    with pytest.raises(ValidationError, match="dark theme is missing"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )


def test_interactive_post_rejects_missing_contract_version() -> None:
    """Experiences must opt into the versioned host integration contract."""
    invalid_experience = experience_html().replace(
        f' data-article-contract="{ARTICLE_CONTRACT_VERSION}"', ""
    )

    with pytest.raises(ValidationError, match="data-article-contract"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )


def test_interactive_post_rejects_custom_base_palette() -> None:
    """The host palette must remain consistent across article experiences."""
    invalid_experience = experience_html().replace(
        "--article-bg: #030710;",
        "--article-bg: #101512;",
    )

    with pytest.raises(ValidationError, match="fallback values"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )


def test_interactive_post_rejects_article_owned_theme_changes() -> None:
    """Only the host application may change the active article theme."""
    invalid_experience = experience_html().replace(
        "</body>",
        "<script>document.documentElement.dataset.theme = 'dark';</script></body>",
    )

    with pytest.raises(ValidationError, match="article-owned theme changes"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )


def test_interactive_post_rejects_raw_component_colors() -> None:
    """Components must use semantic colors so both host themes remain legible."""
    invalid_experience = experience_html().replace(
        "body { background: var(--article-bg); color: var(--article-text); }",
        "body { background: var(--article-bg); color: var(--article-text); }"
        ".callout { background: var(--article-text); color: #fff; }",
    )

    with pytest.raises(ValidationError, match="raw color literals"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )


def test_interactive_post_rejects_low_contrast_token_pair() -> None:
    """Semantic tokens still cannot be paired into unreadable components."""
    invalid_experience = experience_html().replace(
        "body { background: var(--article-bg); color: var(--article-text); }",
        "body { background: var(--article-bg); color: var(--article-text); }"
        ".callout { background: var(--article-bg); color: var(--article-bg); }",
    )

    with pytest.raises(ValidationError, match="insufficient light contrast"):
        InteractivePostInput(
            title="A researched article",
            slug="a-researched-article",
            date=date(2026, 7, 20),
            description="A precise description of the researched article.",
            tags=["systems"],
            html="<h2>Mental model</h2><p>Semantic explanation.</p>",
            experience_html=invalid_experience,
            research_sources=research_sources(),
        )
