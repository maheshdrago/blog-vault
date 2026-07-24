"""Database-backed Model Context Protocol resources and authoring tools."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from ..articles.authoring_policy import (
    ARTICLE_CONTRACT_VERSION,
    ARTICLE_THEME_FALLBACKS,
    REQUIRED_ARTICLE_THEME_TOKENS,
    build_authoring_prompt,
)
from ..articles.repository import ArticleRepository
from ..config import settings
from ..database import database_session
from ..learning_paths.repository import LearningPathRepository
from ..models import (
    ArticleReviewReplyInput,
    ArticleWorkflowStatus,
    InteractivePostInput,
    LearningPathInput,
    LearningPathLessonInput,
    LearningPathSectionInput,
    PostInput,
)
from ..review.repository import ReviewRepository
from ..security import current_mcp_reader_id
from ..telemetry import trace_observation, update_current_observation
from .auth import token_verifier

# FastMCP defaults its bind host to 127.0.0.1, which auto-enables DNS-rebinding
# protection allowing only localhost. Behind Render/Vercel the Host header is the
# public domain, so the deployed host must be allow-listed explicitly or every
# request is rejected with "Invalid Host header" (421).
_mcp_resource_host = urlsplit(settings.mcp_resource_url).netloc
_mcp_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        _mcp_resource_host,
        f"{_mcp_resource_host}:*",
        "127.0.0.1:*",
        "localhost:*",
        "[::1]:*",
    ],
    allowed_origins=[
        *settings.allowed_origins,
        *settings.auth_allowed_origins,
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ],
)

mcp = FastMCP(
    "Blog Vault",
    instructions=(
        "Blog Vault is an HTML-first personal blog. You author for one signed-in "
        "owner; every draft goes to human review, and you can never approve, "
        "publish, or delete.\n\n"
        "AUTHORING WORKFLOW — follow this whenever the user asks you to write, "
        "draft, create, or update an article, however casually they phrase it. "
        "Do not skip steps just because the request was short.\n"
        "1. FIRST call get_article_authoring_brief. It returns the binding v2 "
        "contract, the exact theme-token values, and the research gate. Read it "
        "before writing anything.\n"
        "2. Research the topic on the live web; use at least three primary "
        "sources and keep a claim-to-source record.\n"
        "3. Produce an INTERACTIVE article by default via "
        "create_interactive_article_draft. Never return Markdown or a plain "
        "prose draft — the blog renders HTML and validates every submission. The "
        'experience_html must be a complete, self-contained document: <html '
        'data-article-contract="v2">, [data-theme="light"] and '
        '[data-theme="dark"] blocks defining all 22 --article-* tokens at the '
        "brief's exact values, var(--article-*) for every other color (no raw "
        "hex), prefers-reduced-motion support, at least two <h2> sections, no "
        "external scripts/stylesheets/fonts, and two or three genuinely useful "
        "interactive figures. Text must be useful before interaction.\n"
        "4. Submit with submit_article_for_review. For an update, first fetch "
        "the complete current post and submit a complete same-slug replacement; "
        "the last published snapshot stays privately readable while it is "
        "reviewed.\n"
        "When a reviewer requests changes, fetch the review context, implement "
        "every open comment, and reply to each with what changed."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=_mcp_transport_security,
    token_verifier=token_verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.mcp_oauth_issuer),
        resource_server_url=AnyHttpUrl(settings.mcp_resource_url),
        required_scopes=[],
    ),
)


@asynccontextmanager
async def _repository() -> AsyncIterator[ArticleRepository]:
    """Yield a repository scoped to the credential owner's private vault."""
    async with database_session() as session:
        yield ArticleRepository(session, current_mcp_reader_id())


@mcp.prompt()
@trace_observation("mcp.prompt.draft_researched_article", as_type="chain")
def draft_researched_article(
    topic: str,
    audience: str = "technically curious readers",
    interactive: bool = True,
    user_instructions: str = "",
) -> str:
    """Return the required research-first Blog Vault drafting prompt."""
    prompt = build_authoring_prompt(
        topic,
        audience,
        interactive=interactive,
        user_instructions=user_instructions,
    )
    update_current_observation(
        input={
            "interactive": interactive,
            "topicCharacters": len(topic),
            "audienceCharacters": len(audience),
            "userInstructionCharacters": len(user_instructions),
        },
        output={"promptCharacters": len(prompt)},
    )
    return prompt


@mcp.resource("blog://authoring-guide")
@trace_observation("mcp.resource.authoring_guide", as_type="retriever")
def authoring_guide() -> str:
    """Expose the canonical editorial and interactive-article contract."""
    guide = build_authoring_prompt(
        "[replace with the article topic]",
        "technically curious readers",
        interactive=True,
    )
    update_current_observation(output={"guideCharacters": len(guide)})
    return guide


@mcp.tool()
@trace_observation("mcp.tool.get_article_authoring_brief")
def get_article_authoring_brief(
    topic: str,
    audience: str = "technically curious readers",
    interactive: bool = True,
    user_instructions: str = "",
) -> dict[str, Any]:
    """Get the publication prompt before browsing, researching, or drafting."""
    result = {
        "contractVersion": ARTICLE_CONTRACT_VERSION,
        "prompt": build_authoring_prompt(
            topic,
            audience,
            interactive=interactive,
            user_instructions=user_instructions,
        ),
        "requiredThemeTokens": list(REQUIRED_ARTICLE_THEME_TOKENS),
        "themeFallbacks": ARTICLE_THEME_FALLBACKS,
        "minimumResearchSources": 3,
        "metadataContract": {
            "description": "A specific 140–220 character UI summary.",
            "tags": "Three to six lowercase, stable subject tags.",
        },
        "mediaPolicy": (
            "Prefer native interactive diagrams. Use generated images only when "
            "they improve comprehension and video only when continuous motion is "
            "the subject; never invent an unreviewed asset URL."
        ),
        "indexOwner": "Blog Vault generates the index from h2/h3 headings.",
        "nextStep": (
            "Browse current authoritative sources and build a claim-to-source "
            "record before drafting."
        ),
    }
    update_current_observation(
        input={
            "interactive": interactive,
            "topicCharacters": len(topic),
            "audienceCharacters": len(audience),
            "userInstructionCharacters": len(user_instructions),
        },
        output={
            "contractVersion": ARTICLE_CONTRACT_VERSION,
            "themeTokenCount": len(REQUIRED_ARTICLE_THEME_TOKENS),
            "minimumResearchSources": 3,
        },
    )
    return result


@mcp.resource("blog://posts")
@trace_observation("mcp.resource.published_index", as_type="retriever")
async def published_index() -> str:
    """Return the published database-backed blog index as JSON."""
    async with _repository() as repository:
        posts = await repository.list_published()
    result = json.dumps(
        [post.model_dump(mode="json", by_alias=True) for post in posts],
        indent=2,
    )
    update_current_observation(output={"postCount": len(posts)})
    return result


@mcp.resource("blog://posts/{slug}")
@trace_observation("mcp.resource.published_post", as_type="retriever")
async def published_post(slug: str) -> str:
    """Return a complete published post from the database as JSON."""
    async with _repository() as repository:
        post = await repository.get_published(slug)
    update_current_observation(
        input={"slug": slug},
        output={"readingTime": post.reading_time},
    )
    return post.model_dump_json(by_alias=True, indent=2)


@mcp.tool()
@trace_observation("mcp.tool.list_posts")
async def list_posts(tag: str | None = None) -> list[dict[str, Any]]:
    """List published database articles without complete HTML bodies."""
    async with _repository() as repository:
        posts = await repository.list_published()
    if tag:
        posts = [post for post in posts if tag.lower() in post.tags]
    update_current_observation(
        input={"tagFilterPresent": tag is not None},
        output={"postCount": len(posts)},
    )
    return [post.model_dump(mode="json", by_alias=True) for post in posts]


@mcp.tool()
@trace_observation("mcp.tool.search_posts")
async def search_posts(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search published titles, tags, descriptions, and HTML bodies."""
    async with _repository() as repository:
        matches = await repository.search_published(query, limit)
    update_current_observation(
        input={"queryCharacters": len(query), "limit": limit},
        output={"matchCount": len(matches)},
    )
    return [post.model_dump(mode="json", by_alias=True) for post in matches]


@mcp.tool()
@trace_observation("mcp.tool.get_post")
async def get_post(slug: str) -> dict[str, Any]:
    """Fetch one complete published post from Supabase PostgreSQL."""
    async with _repository() as repository:
        post = await repository.get_published(slug)
    update_current_observation(
        input={"slug": slug},
        output={"readingTime": post.reading_time},
    )
    return post.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.create_article_draft")
async def create_article_draft(
    post: PostInput, revision_notes: str = ""
) -> dict[str, Any]:
    """Create a NON-interactive article draft (uncommon).

    Prefer create_interactive_article_draft for reader-facing pieces. Call
    get_article_authoring_brief first; post.html must be semantic, contract-v2
    HTML using --article-* tokens, never Markdown.
    """
    async with _repository() as repository:
        result = await repository.create_draft(post, revision_notes or None)
    update_current_observation(
        input={"slug": post.slug, "interactive": post.experience is not None},
        output={"articleId": str(result.article_id), "status": result.status},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.create_interactive_article_draft")
async def create_interactive_article_draft(
    post: InteractivePostInput, revision_notes: str = ""
) -> dict[str, Any]:
    """Store a researched, contract-v2 interactive article as one working draft.

    PREREQUISITE: call get_article_authoring_brief first and follow contract v2.
    post.experience_html must be a complete, self-contained HTML document —
    <html data-article-contract="v2">, light and dark [data-theme] blocks
    defining all 22 --article-* tokens at the brief's exact fallback values,
    var(--article-*) for every other color (no raw hex), prefers-reduced-motion,
    at least two <h2> sections, no external scripts/stylesheets/fonts, and at
    least three research_sources. Submissions are validated and rejected on any
    violation. Never submit Markdown.
    """
    async with _repository() as repository:
        result = await repository.create_draft(post, revision_notes or None)
    update_current_observation(
        input={
            "slug": post.slug,
            "researchSourceCount": len(post.research_sources),
        },
        output={"articleId": str(result.article_id), "status": result.status},
    )
    response = result.model_dump(mode="json", by_alias=True)
    response["reviewStatus"] = "draft"
    response["nextStep"] = (
        "Call submit_article_for_review with this slug and contentHash so the reviewer "
        "can inspect Reading and Explore modes before publication."
    )
    return response


@mcp.tool()
@trace_observation("mcp.tool.update_article_draft")
async def update_article_draft(
    post: PostInput, revision_notes: str = ""
) -> dict[str, Any]:
    """Replace the working copy while retaining one safe published snapshot."""
    async with _repository() as repository:
        result = await repository.update_draft(post, revision_notes or None)
    update_current_observation(
        input={"slug": post.slug, "interactive": False},
        output={"articleId": str(result.article_id), "status": result.status},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.update_interactive_article_draft")
async def update_interactive_article_draft(
    post: InteractivePostInput, revision_notes: str = ""
) -> dict[str, Any]:
    """Store complete researched Reading/Explore replacement documents."""
    async with _repository() as repository:
        result = await repository.update_draft(post, revision_notes or None)
    update_current_observation(
        input={
            "slug": post.slug,
            "researchSourceCount": len(post.research_sources),
        },
        output={"articleId": str(result.article_id), "status": result.status},
    )
    response = result.model_dump(mode="json", by_alias=True)
    response["reviewStatus"] = "draft"
    response["nextStep"] = (
        "Call submit_article_for_review with this slug and contentHash so the reviewer "
        "can compare it with the published snapshot."
    )
    return response


@mcp.tool()
@trace_observation("mcp.tool.list_article_revision_requests")
async def list_article_revision_requests() -> list[dict[str, Any]]:
    """List working articles returned with unresolved human feedback."""
    async with database_session() as session:
        result = await ReviewRepository(session, current_mcp_reader_id()).list_queue(
            status=ArticleWorkflowStatus.CHANGES_REQUESTED
        )
    update_current_observation(output={"revisionRequestCount": len(result)})
    return [item.model_dump(mode="json", by_alias=True) for item in result]


@mcp.tool()
@trace_observation("mcp.tool.get_article_review_context")
async def get_article_review_context(slug: str) -> dict[str, Any]:
    """Fetch the working article, rollback snapshot, and feedback threads."""
    async with database_session() as session:
        owner = current_mcp_reader_id()
        article = await ArticleRepository(session, owner).get_article_by_slug(slug)
        result = await ReviewRepository(session, owner).get_context(article.article_id)
    update_current_observation(
        input={"slug": slug},
        output={"commentCount": len(result.comments)},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.reply_to_article_review_comment")
async def reply_to_article_review_comment(
    comment_id: UUID, body: str
) -> dict[str, Any]:
    """Explain how human feedback was implemented and mark it addressed."""
    values = ArticleReviewReplyInput(body=body)
    async with database_session() as session:
        result = await ReviewRepository(
            session, current_mcp_reader_id()
        ).reply_as_assistant(comment_id, values)
    update_current_observation(
        input={"commentId": str(comment_id)},
        output={"status": result.status},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.submit_article_for_review")
async def submit_article_for_review(slug: str, content_hash: str) -> dict[str, Any]:
    """Submit the exact working content hash for human review."""
    async with _repository() as repository:
        result = await repository.submit_for_review(slug, content_hash)
    update_current_observation(
        input={"slug": slug, "contentHash": content_hash},
        output={"status": result.status},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.get_article_draft")
async def get_article_draft(slug: str) -> dict[str, Any]:
    """Fetch the complete current working article by slug."""
    async with _repository() as repository:
        result = await repository.get_article_by_slug(slug)
    update_current_observation(
        input={"slug": slug},
        output={"status": result.status, "slug": result.slug},
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.list_learning_paths")
async def list_learning_paths() -> list[dict[str, Any]]:
    """Inspect current curricula and categories before placing a new article."""
    async with database_session() as session:
        paths = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).list_paths()
    update_current_observation(output={"pathCount": len(paths)})
    return [path.model_dump(mode="json", by_alias=True) for path in paths]


@mcp.tool()
@trace_observation("mcp.tool.create_learning_path")
async def create_learning_path(path: LearningPathInput) -> dict[str, Any]:
    """Create a new curated learning sequence."""
    async with database_session() as session:
        result = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).create_path(path)
    update_current_observation(
        input={"slug": path.slug}, output={"pathId": str(result.path_id)}
    )
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.add_learning_path_section")
async def add_learning_path_section(
    path_slug: str, section: LearningPathSectionInput
) -> dict[str, Any]:
    """Append a named category to an existing curriculum."""
    async with database_session() as session:
        result = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).add_section(path_slug, section)
    return result.model_dump(mode="json", by_alias=True)


@mcp.tool()
@trace_observation("mcp.tool.add_article_to_learning_path")
async def add_article_to_learning_path(
    path_slug: str,
    section_title: str,
    lesson: LearningPathLessonInput,
) -> dict[str, Any]:
    """Append a published article to one path category."""
    async with database_session() as session:
        result = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).add_lesson(path_slug, section_title, lesson)
    update_current_observation(
        input={"pathSlug": path_slug, "articleSlug": lesson.article_slug}
    )
    return result.model_dump(mode="json", by_alias=True)
