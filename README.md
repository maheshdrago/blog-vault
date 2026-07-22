# Blog Vault

A personal publishing system with a React reader, FastAPI REST API, private MCP
authoring server, Supabase PostgreSQL storage, and Langfuse tracing.

## Architecture

```text
React / Vercel ── REST reads ─────────────┐
                                          ▼
LLM ── authenticated MCP ── FastAPI ── Supabase PostgreSQL
             │                    │         ├─ working articles + safe snapshots
             │                    │         └─ preferences + reading state
             └─ creates drafts ───┘

Human reviewer ── review dashboard ── comments / approves / publishes
```

Git stores application code and database migrations. Article bodies, interactive
documents, metadata, research records, drafts, and rollback snapshots live in
Supabase. Render's filesystem is not used as durable storage.

## Local development

Requirements: Node.js 22+, Python 3.12+, and `uv`.

```bash
npm install
uv sync
cp .env.example .env
uv run alembic upgrade head
```

Run the services in separate terminals:

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
npm run dev
```

- Frontend: `http://localhost:5173`
- REST/OpenAPI: `http://localhost:8000/docs`
- MCP Streamable HTTP: `http://localhost:8000/mcp/`

The frontend uses `VITE_API_URL`, which defaults to
`http://localhost:8000/api/v1`.

## Article storage and publication

`articles` holds each stable slug and its one current working copy:

- title, date, UI summary, tags, cover, and featured state;
- sanitized semantic Reading HTML;
- optional sandboxed interactive HTML;
- research sources and revision notes;
- draft, review, approved, published, or archived workflow status.

`article_snapshots` holds at most one previous published copy per article. Before
MCP edits a published article, the current public content is copied into that
snapshot. Readers receive the working copy only while it is published; during
drafting and review they continue receiving the snapshot. Publishing retains the
snapshot for one-step rollback. There is no permanent version history. The
semantic HTML whitelist is centralized in `backend/app/articles/content_policy.py`.

MCP exposes publication-quality authoring instructions and these content tools:

- `list_posts`, `search_posts`, and `get_post` browse published content.
- `create_article_draft` and `create_interactive_article_draft` create a working
  article.
- `update_article_draft` and `update_interactive_article_draft` replace that
  working copy after preserving the current publication as the snapshot.
- `get_article_draft` retrieves the complete working copy by slug.
- `list_article_revision_requests` shows articles returned by a reviewer.
- `get_article_review_context` returns the working article, public snapshot, and
  durable feedback threads an assistant needs to revise it.
- `reply_to_article_review_comment` records how a requested change was handled.
- `submit_article_for_review` moves a draft into the human review queue.

MCP cannot approve, publish, discard, roll back, or delete. Interactive
drafts require at least three checked sources from independent hosts. The
authoring brief keeps client-supplied instructions while enforcing research,
editorial, accessibility, theme, reduced-motion, and sandbox contracts.
Human review, rather than browser automation on the free Render instance, is the
mandatory publication gate.

### Human review

Set `BLOG_ADMIN_ACCESS_TOKEN` to a secret different from
`BLOG_MCP_ACCESS_TOKEN`, then open `http://localhost:5173/review`. The token is
kept in `sessionStorage`, so closing the tab clears it. The dashboard provides:

- a queue of submitted, changes-requested, approved, and rollback-ready articles;
- Reading and Explore previews in light/dark and desktop/tablet/mobile modes;
- a published-snapshot/working-copy comparison;
- section- and figure-anchored feedback with assistant replies;
- explicit request-changes, approve, and publish actions.

The same endpoints are visible in `/docs` and require:

```text
Authorization: Bearer YOUR_BLOG_ADMIN_ACCESS_TOKEN
```

Typical lifecycle:

```text
draft -> in_review -> approved -> published
                 \-> changes_requested -> updated draft -> in_review
```

A reviewer must leave an unresolved comment before requesting changes. The LLM
updates the same working article and the current review cycle keeps its comments.
Submission freezes `contentHash`; approval fails if the article changes after it
was submitted. An assistant does not wake automatically: ask the MCP client to
pick up revision requests, update the working article, reply to each comment, and
submit the new hash.

Useful API checks:

```bash
curl -H "Authorization: Bearer $BLOG_ADMIN_ACCESS_TOKEN" \
  http://localhost:8000/api/v1/admin/reviews

curl -H "Authorization: Bearer $BLOG_ADMIN_ACCESS_TOKEN" \
  http://localhost:8000/api/v1/admin/reviews/ARTICLE_ID

curl -X POST -H "Authorization: Bearer $BLOG_ADMIN_ACCESS_TOKEN" \
  http://localhost:8000/api/v1/admin/reviews/ARTICLE_ID/approve
```

Publication is a separate authenticated action after approval. The same protected
API provides `discard-draft` and `rollback`; neither action is exposed through MCP.

## Interactive articles

The React route remains in control of navigation, reader state, theme, progress,
and mode switching. FastAPI returns the stored interactive document as inert
plain text. The browser injects a restrictive Content Security Policy and then
renders it in an iframe sandbox that permits inline scripts but denies
same-origin access, network connections, forms, popups, and top-level
navigation.

Blog Vault generates an index from `h2`/`h3` headings and passes app-owned theme
tokens into the sandbox. New documents use
`<html data-article-contract="v2" data-theme="light">` and implement reduced
motion.

## Reader state

Supabase also stores anonymous-browser preferences, bookmarks, favorites,
progress, last-read time, and custom groups. The frontend includes dashboard,
library filters, searchable command palette, generated contents index,
previous/next navigation, typography controls, Reading/Explore modes, and local
fallback state while a free backend wakes up.

## Learning paths

`learning_paths`, `learning_path_sections`, and `learning_path_lessons` define
ordered curricula independently from personal groups and free-form article tags.
The UI presents collapsible categories, sequential locks, aggregate completion,
and path-aware previous/next lesson navigation. Completion is derived from the
existing `reading_states.progress_percent`; paths do not duplicate reader state.

MCP can inspect paths, create a curriculum, append categories, and place existing
published articles with `list_learning_paths`, `create_learning_path`,
`add_learning_path_section`, and `add_article_to_learning_path`. The initial
curricula are idempotently defined in `backend/scripts/seed_learning_paths.py`.

## Langfuse

Tracing is enabled when both Langfuse keys are present. MCP prompts, resources,
and tools are traced without automatic content capture; article bodies,
interactive source, credentials, and passwords are redacted.

## Deployment

Vercel needs:

```text
VITE_API_URL=https://YOUR-RENDER-SERVICE.onrender.com/api/v1
```

Render needs:

```text
BLOG_DATABASE_URL
BLOG_MCP_ACCESS_TOKEN
BLOG_ADMIN_ACCESS_TOKEN
BLOG_ALLOWED_ORIGINS=["https://your-blog.vercel.app"]
```

Langfuse variables are optional. `render.yaml` runs `alembic upgrade head` before
starting FastAPI. GitHub Actions deploys Vercel only for frontend paths and
triggers Render only for backend, migration, or Python dependency paths.

## Project layout

```text
src/
  app/                 React entry point and global shell
  features/            home, library, reader, review, and search
  shared/              API clients, shared components, tokens, and types
backend/app/
  api/                 REST transport
  articles/            authoring policy, sanitization, and persistence
  mcp/                 private MCP transport and tools
  readers/             preferences, groups, and reading state
  review/              comments and publication state machine
migrations/            Alembic schema history
infra/docker/          production API image
```

## Quality checks

```bash
npm run build
uv run ruff check backend migrations
uv run mypy backend
uv run pytest
```
