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
    """Slash-command form of the Blog Vault authoring brief.

    Returns the research-first, contract-v2 drafting prompt for a topic. During
    autonomous authoring prefer the get_article_authoring_brief tool (it also
    returns the theme tokens and research gate); use this prompt when a person
    wants to kick off a draft interactively.
    """
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
    """The canonical Blog Vault authoring contract, as a readable reference.

    The same editorial and interactive-HTML rules that get_article_authoring_brief
    returns, rendered with a placeholder topic. Read it to learn the house
    standard; call the tool to get a topic-specific brief before drafting.
    """
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
    """Get the binding authoring brief. Call this FIRST for any article request.

    Returns contract v2, the topic-specific writing prompt, the exact --article-*
    theme-token fallback values, the metadata rules, and the research gate. Read
    it before researching or drafting; the create/update tools validate against
    this same contract and reject anything that ignores it.
    """
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
    """JSON index of every published post (metadata only, no HTML bodies).

    Resource form of list_posts, for clients that browse resources. Read a full
    body with the get_post tool or the blog://posts/{slug} resource.
    """
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
    """One complete published post as JSON, including its HTML body.

    Resource form of get_post. Returns published content only; use the
    get_article_draft tool for the current working copy, which may differ.
    """
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
    """List published posts as lightweight metadata (no HTML bodies).

    Optionally filter by an exact tag. Use it to see what already exists before
    drafting, or before placing an article in a learning path. Fetch a full body
    with get_post.
    """
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
    """Full-text search across published titles, tags, descriptions, and bodies.

    Returns ranked published matches (metadata only). Use it to check for prior
    coverage and avoid duplicating an existing article before drafting a new one.
    """
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
    """Fetch one complete PUBLISHED post by slug, including its HTML body.

    Returns published content only. For the current working draft, which may
    differ from what is published, use get_article_draft instead.
    """
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
    """Replace an existing NON-interactive draft's working copy (uncommon).

    Prefer update_interactive_article_draft for reader-facing pieces. Fetch the
    current article with get_article_draft first, then submit a complete same-slug
    replacement; the last published snapshot stays privately readable while the
    new working copy is reviewed. post.html must be semantic contract-v2 HTML,
    never Markdown.
    """
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
    """Replace an existing interactive article with a complete new working copy.

    Fetch the current post with get_article_draft first (or
    get_article_review_context when addressing feedback), then submit a complete
    same-slug replacement. Same contract as create_interactive_article_draft: a
    self-contained contract-v2 experience_html with all 22 --article-* tokens at
    their exact values, prefers-reduced-motion, no external resources, and at
    least three research_sources. The last published snapshot stays privately
    readable while the update is reviewed.
    """
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
    """List your articles the reviewer sent back with changes requested.

    Start here when resuming review work. For each item, call
    get_article_review_context to read the open comments, revise the working
    article, reply to each comment, then resubmit for review.
    """
    async with database_session() as session:
        result = await ReviewRepository(session, current_mcp_reader_id()).list_queue(
            status=ArticleWorkflowStatus.CHANGES_REQUESTED
        )
    update_current_observation(output={"revisionRequestCount": len(result)})
    return [item.model_dump(mode="json", by_alias=True) for item in result]


@mcp.tool()
@trace_observation("mcp.tool.get_article_review_context")
async def get_article_review_context(slug: str) -> dict[str, Any]:
    """Fetch everything needed to act on review feedback for one slug.

    Returns the current working article, the published rollback snapshot, and
    every reviewer comment thread. Use it before revising: implement each open
    comment, reply with reply_to_article_review_comment, then resubmit.
    """
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
    """Reply to one reviewer comment, recording how it was addressed.

    Call after implementing that comment's change in the working article. Reply to
    every open comment before resubmitting so the reviewer sees what changed per
    item. Identify the comment by the comment_id from get_article_review_context.
    """
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
    """Submit the current working draft for human review — the publication gate.

    Pass the slug and the contentHash returned by the most recent create/update
    draft call (or by get_article_draft). The hash pins the exact content being
    reviewed, so resubmit after any edit. You cannot publish; a human approves
    from here.
    """
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
    """Fetch the complete current WORKING draft by slug, including its contentHash.

    Returns the working copy (which may differ from the published post) plus the
    contentHash that submit_article_for_review requires. Use it before updating or
    submitting so you work from the exact current content.
    """
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
    """List the owner's learning paths with their sections (categories).

    Inspect existing curricula and section titles before creating a path or
    placing an article, so new lessons land in the right section.
    """
    async with database_session() as session:
        paths = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).list_paths()
    update_current_observation(output={"pathCount": len(paths)})
    return [path.model_dump(mode="json", by_alias=True) for path in paths]


@mcp.tool()
@trace_observation("mcp.tool.create_learning_path")
async def create_learning_path(path: LearningPathInput) -> dict[str, Any]:
    """Create a new curated learning path (an ordered reading sequence).

    Add sections with add_learning_path_section, then place published articles
    into a section with add_article_to_learning_path. Check list_learning_paths
    first to avoid duplicating an existing path.
    """
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
    """Append a named section (category) to an existing learning path.

    Sections group a path's lessons; create the path first with
    create_learning_path. Add articles to a section with
    add_article_to_learning_path.
    """
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
    """Add a PUBLISHED article as a lesson in one section of a learning path.

    The article must already be published (draft or in-review articles cannot be
    placed) and the target section must exist. Identify the section by its exact
    title from list_learning_paths.
    """
    async with database_session() as session:
        result = await LearningPathRepository(
            session, current_mcp_reader_id()
        ).add_lesson(path_slug, section_title, lesson)
    update_current_observation(
        input={"pathSlug": path_slug, "articleSlug": lesson.article_slug}
    )
    return result.model_dump(mode="json", by_alias=True)
