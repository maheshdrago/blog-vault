# Fieldnotes / Blog Vault

An HTML-first personal blog with Git as the content database, React on Vercel, and a private FastAPI + MCP authoring service on Render.

## Architecture

```text
posts/published/*.html ── GitHub ── Vercel build ── static reader
                              ▲
                              │ branch + pull request
LLM ── authenticated MCP ── Render/FastAPI

Browser preferences ── FastAPI ── Supabase PostgreSQL
```

Blog content and user state deliberately use different persistence:

- Git stores versioned HTML posts and images.
- PostgreSQL stores reader preferences, favorites, bookmarks, progress, and
  personal post groups.
- Render's filesystem is never treated as durable storage.
- MCP can create a branch and pull request. It cannot merge or delete content.

## Local development

Requirements: Node.js 22+, Python 3.12+, and `uv`.

```bash
npm install
uv sync
cp .env.example .env
```

Set a PostgreSQL connection, GitHub credentials, and MCP access token in `.env`, then run:

```bash
uv run alembic upgrade head
uv run uvicorn backend.app.main:app --reload --port 8000
npm run dev
```

The frontend is at `http://localhost:5173`, REST documentation is at `http://localhost:8000/docs`, and MCP Streamable HTTP is at `http://localhost:8000/mcp/`.

The frontend uses `VITE_API_URL`, defaulting locally to `http://localhost:8000/api/v1`.

## Posts

Published posts are semantic HTML files under `posts/published`. `npm run content:build` validates their metadata and produces `public/content/posts.json`; the Vercel build runs this automatically.

Each file contains metadata followed by an HTML **fragment**, not a complete page.
React owns the application shell and route for every post. The unified in-app
reader keeps progress, bookmarks, favorites, groups, typography,
previous/next navigation, and the generated table of contents available for
imported and hand-written articles alike.

Standalone HTML pages can be normalized into the same safe article format with:

```bash
uv run python -m scripts.import_html_article article.html \
  --title "Article title" \
  --slug article-title \
  --date 2026-07-17 \
  --description "Short archive description." \
  --tags "systems,architecture"
```

The importer keeps semantic prose, code, lists, links, images, and tables while
removing page-level CSS, JavaScript, navigation, and interactive demos from the
distraction-free reading representation. For a trusted, manually reviewed animated page,
preserve an additional in-app experience with:

```bash
uv run python -m scripts.import_html_article article.html \
  --title "Article title" \
  --slug article-title \
  --date 2026-07-17 \
  --description "Short archive description." \
  --tags "systems,architecture" \
  --experience-output public/experiences
```

Interactive experiences never replace the React route. The reader fetches them,
injects a restrictive Content Security Policy and progress bridge, then renders
them in an iframe sandbox that permits scripts but not same-origin access,
forms, popups, or top-level navigation. Readers can switch between Interactive
and Reading/Explore views without leaving Blog Vault. Experience sources are deployed as
plain-text assets, so navigating to one directly cannot open a second website.
The shared HTML whitelist lives in
`backend/app/content_policy.py` and is also used when MCP serializes a proposed
post.

MCP reads current content through the GitHub API. `create_post_pull_request` sanitizes and validates a post, creates a branch, commits the HTML file, and opens a pull request. Merging the pull request triggers only the frontend workflow.

For new researched writing, MCP exposes:

- `draft_researched_article`, an MCP prompt primitive containing the canonical
  research, editorial, semantic HTML, animation, accessibility, and theme rules.
- `get_article_authoring_brief`, the same contract as a tool for clients that do
  not expose MCP prompts.
- `create_interactive_post_pull_request`, which requires at least three checked
  sources from independent hosts and commits the Reading HTML and interactive
  source together in one reviewable pull request.

Interactive publication validation requires complete light and dark definitions
for semantic tokens covering page, surfaces, text, borders, accents, code, and
status colors. It also requires reduced-motion behavior and rejects forms,
iframes, embedded objects, external scripts, and external stylesheets. Blog
Vault generates the index from `h2`/`h3` headings and passes the current app
theme into the sandbox, so article generators should not create their own index
or theme switcher. New experiences declare
`<html data-article-contract="v1" data-theme="light">`; the version marker keeps
future host changes explicit instead of silently breaking older articles.

The GitHub credential should be a fine-grained token limited to this repository with:

- Contents: read and write
- Pull requests: read and write
- Metadata: read

For stronger rotation and short-lived credentials, replace the token with a GitHub App installation token later.

## Langfuse observability

Langfuse tracing is optional and disabled unless both project keys are configured.
Create a Langfuse project, copy its API keys, and use the base URL matching the
project's data region:

```text
BLOG_LANGFUSE_PUBLIC_KEY=pk-lf-...
BLOG_LANGFUSE_SECRET_KEY=sk-lf-...
BLOG_LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
BLOG_LANGFUSE_ENVIRONMENT=development
BLOG_LANGFUSE_SAMPLE_RATE=1.0
```

The health endpoint reports `telemetryConfigured`. MCP prompts, resources, and
tools are traced without automatic argument/result capture. GitHub API calls are
nested below the invoking MCP operation and record only method, route, and status.
Article HTML, interactive source, authorization values, tokens, and passwords are
redacted before export. The FastAPI lifespan flushes queued observations during
graceful shutdown.

Start with a sample rate of `1.0` while testing. For higher traffic, reduce read
trace volume while retaining publication and error visibility. Langfuse observes
the server-side MCP workflow; browsing and model calls performed by an external
MCP client are visible only if that client exports its own traces.

## Supabase PostgreSQL

Create a free Supabase project and copy its connection string into `BLOG_DATABASE_URL`, using the async SQLAlchemy driver:

```text
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/postgres
```

Apply schema migrations:

```bash
uv run alembic upgrade head
```

The initial identity is an anonymous UUID generated by the browser. It is sufficient for low-risk preferences on one browser. Add Supabase Auth before supporting private accounts or cross-device identity.

The frontend's **My library** view includes bookmark, favorite, continue-reading,
finished, and custom-group filters. A post can belong to one personal group at a
time. Deleting a group preserves its posts and moves them back to Ungrouped.

## Reader experience

The default route is a dashboard rather than an automatically selected post. It
surfaces the featured note, recent writing, library totals, and up to three
in-progress posts ordered by their latest reading activity. Post hashes remain
supported as intentional deep links.

- `Cmd/Ctrl + K` opens a searchable command palette for posts, groups, the
  library, and theme switching.
- Reading mode provides a generated table of contents for `h2` and `h3`
  headings, resumable scroll progress, and previous/next navigation.
- Trusted animated posts open in the semantic Read view and offer a sandboxed
  Explore view for purposeful animations. Both retain Blog Vault's reading-state
  controls, generated index, and color-theme selection.
- Reader typography controls persist typeface, text size, line height, and
  content width to Supabase.
- A compact rail indicator reports saving, saved, or offline state. Local theme
  and bookmark data remain available if the free backend is sleeping.

## Deployment

### Vercel

Create a Vercel project for this repository and set:

- `VITE_API_URL=https://YOUR-RENDER-SERVICE.onrender.com/api/v1`

Disable Vercel's automatic Git deployment because `.github/workflows/frontend.yml` owns deployment. Add these GitHub Actions secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

The workflow runs only for frontend configuration, `src`, `public`, or published-post changes.

### Render

Create the service using `render.yaml`, then configure these secret environment variables:

- `BLOG_DATABASE_URL`
- `BLOG_GITHUB_TOKEN`
- `BLOG_GITHUB_REPOSITORY`, formatted as `owner/repository`
- `BLOG_MCP_ACCESS_TOKEN`
- `BLOG_ALLOWED_ORIGINS`, formatted as `["https://your-blog.vercel.app"]`

Create a Render deploy hook and add it to GitHub Actions as `RENDER_DEPLOY_HOOK_URL`. Render auto-deploy is disabled; `.github/workflows/backend.yml` triggers the hook only after backend checks pass and only for backend-related changes.

MCP clients must send:

```text
Authorization: Bearer YOUR_BLOG_MCP_ACCESS_TOKEN
```

## CI/CD paths

| Change | Frontend/Vercel | Backend/Render |
|---|---:|---:|
| `posts/published/**` | Yes | No |
| `src/**`, `public/**` | Yes | No |
| `backend/**`, `migrations/**` | No | Yes |
| `pyproject.toml`, `uv.lock` | No | Yes |
| Documentation only | No | No |

## Quality checks

```bash
npm run build
uv run ruff check backend migrations
uv run mypy backend
uv run pytest
```
