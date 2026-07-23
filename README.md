# Blog Vault

A signup-only personal publishing system with a React reader, FastAPI API,
private MCP authoring server, Supabase Auth/PostgreSQL, and Langfuse tracing.

## Architecture

```text
Browser ── same-origin /api/* ── Vercel proxy ── FastAPI ── Supabase
   │                                      │          ├─ Auth
   ├─ private reader + review UI          │          └─ private vault rows
   └─ access JWT in memory                └─ refresh token in HttpOnly cookie

MCP client ── Supabase OAuth or personal token ── FastAPI MCP ── one user's vault
```

Git stores application code and migrations. Article bodies, interactive
documents, metadata, research records, learning paths, drafts, and the single
rollback snapshot live in Supabase. Render's filesystem is not durable storage.

Every product surface requires an account except health and authentication
endpoints. Articles are not public. FastAPI derives vault ownership from a
verified identity or personal MCP credential; clients never submit an owner ID.

## Authentication and ownership

Registration, email/password sign-in, Google/GitHub OAuth, recovery, session
refresh, and device revocation use Supabase Auth through FastAPI as a backend for
frontend:

```text
Browser ── /api/v1/auth/* ── Vercel proxy ── FastAPI ── Supabase Auth
                     access JWT: memory only
                     refresh token: Secure HttpOnly same-site cookie
```

Authenticated browser APIs are under `/api/v1/me/*`. The React application
waits for session bootstrap and renders no vault data while signed out.

`articles` and `learning_paths` carry `owner_reader_id`. Reader preferences,
groups, progress, bookmarks, favorites, reviews, and MCP credentials are also
scoped to that reader. Slugs are unique within a vault, not globally.

For the existing installation, the first successfully created account claims
all legacy unowned articles and learning paths atomically. Later accounts begin
with empty vaults. This bootstrap is protected by a PostgreSQL advisory
transaction lock, so concurrent signups cannot both claim the content.

See [the authentication architecture](docs/authentication-and-session-architecture.md)
for the trust boundaries, schema, and request flows.

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

Vite proxies `/api/*` to FastAPI, matching production's same-origin request
shape.

## Article storage and review

`articles` stores one mutable working copy per owner and slug:

- title, date, summary, tags, cover, and featured state;
- sanitized semantic Reading HTML;
- optional sandboxed interactive Explore HTML;
- research sources and revision notes;
- draft, review, approved, published, or archived workflow status.

Here, `published` means visible in the owner's reader; it never means anonymous
or internet-public.

`article_snapshots` stores at most one last-known-good copy per article. When an
LLM edits a published article, the safe copy remains readable during review.
Publishing retains the prior copy for one-step rollback. There is no permanent
version history.

The owner reviews drafts at `/review`:

- compare the working article with its rollback snapshot;
- preview Reading and Explore modes across themes and viewport sizes;
- leave section- or figure-anchored comments;
- request changes, approve, publish, discard, or roll back.

Lifecycle:

```text
draft -> in_review -> approved -> published
                 \-> changes_requested -> updated draft -> in_review
```

Approval is bound to a frozen content hash and fails after an unreviewed change.
MCP cannot approve, publish, discard, roll back, or delete.

Authenticated review endpoints use the current vault:

```text
GET  /api/v1/me/reviews
GET  /api/v1/me/reviews/{article_id}
POST /api/v1/me/reviews/{article_id}/approve
```

## MCP

OAuth-capable clients such as Claude and ChatGPT connect with the MCP URL only:

```text
https://YOUR_RENDER_SERVICE.onrender.com/mcp/
```

The endpoint advertises RFC 9728 protected-resource metadata. The client
discovers Supabase OAuth, dynamically registers when enabled, opens Blog Vault's
`/oauth/consent` screen, and receives its own access and refresh tokens after
the user approves. FastAPI accepts only signed OAuth JWTs containing the
OAuth-only `client_id` claim and maps `sub` to one reader profile.

For Claude Code, CI, or clients without browser OAuth, create a personal MCP
credential on `/account`. Its plaintext is displayed once and the database
stores only a SHA-256 digest. Credentials can be named, audited by last use, and
revoked independently.

Configure a client with:

```text
URL: https://YOUR_RENDER_SERVICE.onrender.com/mcp/
Authorization: Bearer bv_mcp_...
```

The token resolves to exactly one `reader_id`. MCP tools and resources therefore
cannot list, read, create, update, review, or categorize another user's content.

Important tools include:

- `list_posts`, `search_posts`, and `get_post`;
- `create_article_draft` and `create_interactive_article_draft`;
- `update_article_draft` and `update_interactive_article_draft`;
- `get_article_draft`, `submit_article_for_review`, and revision tools;
- learning-path inspection and editing tools.

The authoring prompt adds quality, research, theme-token, accessibility,
reduced-motion, and sandbox requirements without replacing the user's own
instructions.

## Interactive articles

FastAPI returns stored interactive documents as inert plain text. React injects
a restrictive Content Security Policy and renders them inside a sandboxed iframe
that allows inline article scripts but denies same-origin access, network
connections, forms, popups, and top-level navigation.

The app owns navigation, theme, progress, typography, and Reading/Explore mode.
It generates a contents index from `h2`/`h3`, supplies semantic theme tokens, and
requires reduced-motion behavior.

## Learning paths and reader state

Each private vault can organize articles into ordered learning paths with
collapsible sections, sequential locks, aggregate progress, and previous/next
lesson navigation. Completion derives from the same private reading state used
for bookmarks, favorites, custom groups, and last-read position.

The idempotent seed script targets the oldest authenticated account:

```bash
uv run python -m backend.scripts.seed_learning_paths
```

Create an account first.

## Deployment

Vercel is the browser-facing gateway. `vercel.json` forwards `/api/*` to Render
before the React SPA fallback, so auth cookies remain first-party from the
browser's perspective.

Both hosts remain connected to the `main` branch, while GitHub Actions owns
validation. The path-filtered frontend and backend workflows test only the
affected application. Configure Vercel's production Deployment Check to require
the `Frontend / validate` GitHub check; Render uses
`autoDeployTrigger: checksPass` and waits for successful GitHub checks before
deploying. This avoids platform deployment tokens and duplicate deploy jobs in
GitHub Actions.

Frontend:

```text
VITE_API_URL=/api/v1
VITE_MCP_URL=https://blog-vault-api.onrender.com/mcp/
```

Render:

```text
BLOG_DATABASE_URL
BLOG_SUPABASE_URL
BLOG_SUPABASE_PUBLISHABLE_KEY
BLOG_SUPABASE_JWT_ISSUER
BLOG_MCP_RESOURCE_URL=https://blog-vault-api.onrender.com/mcp/
BLOG_MCP_OAUTH_ISSUER_URL=https://PROJECT_REF.supabase.co/auth/v1
BLOG_MCP_OAUTH_AUDIENCE=authenticated
BLOG_AUTH_ALLOWED_ORIGINS=["https://your-blog.vercel.app"]
BLOG_AUTH_CALLBACK_URL=https://your-blog.vercel.app/api/v1/auth/callback
BLOG_AUTH_COOKIE_SECURE=true
BLOG_ALLOWED_ORIGINS=["https://your-blog.vercel.app"]
```

Personal MCP credentials are database records created by users; there is no
shared MCP environment secret.

In Supabase, use an asymmetric JWT signing key, add the exact callback URL to
Auth redirect URLs, and configure the enabled identity providers. Then enable
Authentication → OAuth Server, set Authorization Path to `/oauth/consent`, and
enable Dynamic Client Registration for automatic MCP connector setup. The
Supabase Site URL must be the Vercel origin. Keep email confirmation enabled and
use custom SMTP before relying on production email. `render.yaml` runs
`alembic upgrade head` before FastAPI starts.

Supabase OAuth access tokens use the audience `authenticated` by default, which
matches the default backend setting. For stricter resource-bound JWTs, configure
a Supabase Custom Access Token Hook to set OAuth-token `aud` to the exact
`BLOG_MCP_RESOURCE_URL`, then change `BLOG_MCP_OAUTH_AUDIENCE` to that URL.

Langfuse variables are optional. Article bodies and credentials are excluded
from automatic trace capture.

## Project layout

```text
src/
  app/                 React entry point and private shell
  features/auth/       registration, sign-in, account, and sessions
  features/            home, library, reader, review, and search
  shared/              API clients, components, tokens, and types
backend/app/
  api/                 health and authenticated REST transport
  auth/                Supabase BFF, JWT verification, and MCP credentials
  articles/            authoring policy, sanitization, and persistence
  mcp/                 owner-scoped MCP tools and resources
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
