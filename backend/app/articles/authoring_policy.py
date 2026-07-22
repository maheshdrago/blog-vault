"""Editorial and technical contract for research-backed interactive articles."""

import re
from datetime import date
from typing import Final

REQUIRED_ARTICLE_THEME_TOKENS: Final[tuple[str, ...]] = (
    "--article-bg",
    "--article-surface",
    "--article-surface-raised",
    "--article-text",
    "--article-text-muted",
    "--article-border",
    "--article-accent",
    "--article-accent-contrast",
    "--article-link",
    "--article-focus",
    "--article-selection",
    "--article-code-bg",
    "--article-success",
    "--article-warning",
    "--article-danger",
    "--article-visual-1",
    "--article-visual-2",
    "--article-visual-3",
    "--article-visual-4",
    "--article-font-body",
    "--article-font-display",
    "--article-font-mono",
)

ARTICLE_THEME_FALLBACKS: Final[dict[str, dict[str, str]]] = {
    "light": {
        "--article-bg": "#e5f4ff",
        "--article-surface": "#f2faff",
        "--article-surface-raised": "#ffffff",
        "--article-text": "#030710",
        "--article-text-muted": "#607d98",
        "--article-border": "rgba(3, 42, 78, 0.2)",
        "--article-accent": "#006ddd",
        "--article-accent-contrast": "#ffffff",
        "--article-link": "#005fc2",
        "--article-focus": "#005fc2",
        "--article-selection": "#cce9ff",
        "--article-code-bg": "#d8edfc",
        "--article-success": "#067a5a",
        "--article-warning": "#9a5b00",
        "--article-danger": "#b42318",
        "--article-visual-1": "#006ddd",
        "--article-visual-2": "#0f8a76",
        "--article-visual-3": "#7c3aed",
        "--article-visual-4": "#d97706",
        "--article-font-body": '"Manrope", system-ui, sans-serif',
        "--article-font-display": '"Manrope", system-ui, sans-serif',
        "--article-font-mono": ('"JetBrains Mono", ui-monospace, monospace'),
    },
    "dark": {
        "--article-bg": "#030710",
        "--article-surface": "#060b14",
        "--article-surface-raised": "#0d1322",
        "--article-text": "#e5f4ff",
        "--article-text-muted": "#718da8",
        "--article-border": "rgba(127, 200, 255, 0.2)",
        "--article-accent": "#7fc8ff",
        "--article-accent-contrast": "#030710",
        "--article-link": "#99d3ff",
        "--article-focus": "#99d3ff",
        "--article-selection": "rgba(127, 200, 255, 0.11)",
        "--article-code-bg": "#09101d",
        "--article-success": "#2dd4bf",
        "--article-warning": "#f6a723",
        "--article-danger": "#f0616d",
        "--article-visual-1": "#7fc8ff",
        "--article-visual-2": "#2dd4bf",
        "--article-visual-3": "#c4a7ff",
        "--article-visual-4": "#f6a723",
        "--article-font-body": '"Manrope", system-ui, sans-serif',
        "--article-font-display": '"Manrope", system-ui, sans-serif',
        "--article-font-mono": ('"JetBrains Mono", ui-monospace, monospace'),
    },
}

ARTICLE_CONTRACT_VERSION: Final[str] = "v2"

_ARTICLE_CONTRACT_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"<html\b[^>]*\bdata-article-contract\s*=\s*['\"]"
    rf"{ARTICLE_CONTRACT_VERSION}['\"]",
    re.IGNORECASE,
)

_FORBIDDEN_EXPERIENCE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "forms": re.compile(r"<\s*form\b", re.IGNORECASE),
    "nested frames": re.compile(r"<\s*iframe\b", re.IGNORECASE),
    "embedded objects": re.compile(r"<\s*(?:object|embed)\b", re.IGNORECASE),
    "external scripts": re.compile(r"<\s*script\b[^>]*\bsrc\s*=", re.IGNORECASE),
    "external stylesheets": re.compile(
        r"<\s*link\b[^>]*\brel\s*=\s*['\"]?stylesheet",
        re.IGNORECASE,
    ),
    "article-owned theme changes": re.compile(
        r"(?:\.\s*dataset\s*\.\s*theme\s*=|"
        r"setAttribute\s*\(\s*['\"]data-theme['\"])",
        re.IGNORECASE,
    ),
}

_CSS_COLOR_LITERAL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\s*\(", re.IGNORECASE
)


def _experience_css_without_fallbacks(source: str) -> str:
    """Return article CSS with the two approved raw-color blocks removed."""
    css = "\n".join(
        re.findall(r"<style\b[^>]*>([\s\S]*?)</style>", source, re.IGNORECASE)
    )
    for theme in ("light", "dark"):
        css = re.sub(
            rf"(?:html)?\s*\[data-theme\s*=\s*['\"]?{theme}['\"]?\]"
            r"\s*\{[^}]*\}",
            "",
            css,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return css


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    """Parse an opaque six-digit hex color used by the fallback palette."""
    match = re.fullmatch(r"#([0-9a-f]{6})", value.strip(), re.IGNORECASE)
    if match is None:
        return None
    raw = match.group(1)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate WCAG relative luminance for an sRGB color."""
    channels = []
    for channel in rgb:
        normalized = channel / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    """Return the WCAG contrast ratio between two opaque sRGB colors."""
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _validate_theme_color_usage(source: str) -> None:
    """Reject raw colors and statically detectable low-contrast token pairs."""
    css = _experience_css_without_fallbacks(source)
    declaration_values = re.findall(
        r"(?:^|[;{])\s*[-a-z0-9]+\s*:\s*([^;}]+)",
        css,
        re.IGNORECASE | re.MULTILINE,
    )
    for inline_style in re.findall(
        r"\bstyle\s*=\s*['\"]([^'\"]*)['\"]", source, re.IGNORECASE
    ):
        declaration_values.extend(
            re.findall(
                r"(?:^|;)\s*[-a-z0-9]+\s*:\s*([^;]+)",
                inline_style,
                re.IGNORECASE,
            )
        )
    if any(_CSS_COLOR_LITERAL_PATTERN.search(value) for value in declaration_values):
        raise ValueError(
            "Interactive CSS cannot use raw color literals outside the canonical "
            "light and dark fallback blocks; use an --article-* token."
        )

    for _, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        foreground = re.search(
            r"(?:^|;)\s*color\s*:\s*var\(\s*(--article-[a-z0-9-]+)",
            declarations,
            re.IGNORECASE,
        )
        background = re.search(
            r"(?:^|;)\s*background(?:-color)?\s*:\s*"
            r"var\(\s*(--article-[a-z0-9-]+)",
            declarations,
            re.IGNORECASE,
        )
        if foreground is None or background is None:
            continue
        for theme, palette in ARTICLE_THEME_FALLBACKS.items():
            foreground_rgb = _hex_rgb(palette.get(foreground.group(1), ""))
            background_rgb = _hex_rgb(palette.get(background.group(1), ""))
            if (
                foreground_rgb is not None
                and background_rgb is not None
                and _contrast_ratio(foreground_rgb, background_rgb) < 4.5
            ):
                raise ValueError(
                    f"Interactive CSS has insufficient {theme} contrast between "
                    f"{foreground.group(1)} and {background.group(1)}."
                )


def _normalize_css_value(value: str) -> str:
    """Normalize insignificant CSS whitespace for contract comparisons."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def validate_interactive_experience(source: str) -> None:
    """Validate the enforceable portion of the interactive article contract."""
    normalized = source.casefold()
    required_structure = ("<!doctype html", "<html", "<head", "<body")
    missing_structure = [item for item in required_structure if item not in normalized]
    if missing_structure:
        raise ValueError(
            "Interactive HTML must be a complete document; missing: "
            + ", ".join(missing_structure)
        )
    if _ARTICLE_CONTRACT_PATTERN.search(source) is None:
        raise ValueError(
            f'Interactive HTML must declare data-article-contract="'
            f'{ARTICLE_CONTRACT_VERSION}" '
            "on the html element."
        )
    for theme in ("light", "dark"):
        block = re.search(
            rf"\[data-theme\s*=\s*['\"]?{theme}['\"]?\]\s*\{{([^}}]*)\}}",
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if block is None:
            raise ValueError(
                f"Interactive HTML must define a {theme} data-theme block."
            )
        missing_tokens = [
            token
            for token in REQUIRED_ARTICLE_THEME_TOKENS
            if token not in block.group(1)
        ]
        if missing_tokens:
            raise ValueError(
                f"The {theme} theme is missing required tokens: "
                + ", ".join(missing_tokens)
            )
        declarations = {
            token: _normalize_css_value(value)
            for token, value in re.findall(
                r"(--article-[a-z0-9-]+)\s*:\s*([^;]+)",
                block.group(1),
                re.IGNORECASE,
            )
        }
        mismatched_tokens = [
            token
            for token, expected in ARTICLE_THEME_FALLBACKS[theme].items()
            if declarations.get(token) != _normalize_css_value(expected)
        ]
        if mismatched_tokens:
            raise ValueError(
                f"The {theme} theme must use Blog Vault fallback values for: "
                + ", ".join(mismatched_tokens)
            )
    if "prefers-reduced-motion" not in normalized:
        raise ValueError("Interactive HTML must support prefers-reduced-motion.")
    if len(re.findall(r"<h2\b", source, re.IGNORECASE)) < 2:
        raise ValueError(
            "In-depth interactive articles require at least two h2 sections."
        )
    for label, pattern in _FORBIDDEN_EXPERIENCE_PATTERNS.items():
        if pattern.search(source):
            raise ValueError(f"Interactive HTML cannot contain {label}.")
    _validate_theme_color_usage(source)


def build_authoring_prompt(
    topic: str,
    audience: str,
    *,
    interactive: bool,
    user_instructions: str = "",
) -> str:
    """Build the canonical research and drafting prompt returned through MCP."""
    instructions = user_instructions.strip()
    if len(instructions) > 8_000:
        raise ValueError("User article instructions cannot exceed 8,000 characters.")
    user_brief = instructions or "No additional instructions were provided."
    fallback_blocks = "\n\n".join(
        f'html[data-theme="{theme}"] {{\n'
        + "\n".join(f"  {token}: {value};" for token, value in declarations.items())
        + "\n}"
        for theme, declarations in ARTICLE_THEME_FALLBACKS.items()
    )
    experience_instruction = f"""
Create an additional complete `experienceHtml` document only when a process,
state transition, system topology, comparison, or data structure becomes
materially easier to understand through interaction. Do not animate decoration.
Use 1–3 purposeful interactive figures when the topic supports them; otherwise
set `interactive=false` and publish a semantic article. Every figure must answer
one named learning question and make a mechanism, transition, tradeoff, scale,
or failure mode easier to understand than prose alone. Prefer reader-controlled
step-throughs, comparisons, and state changes over autoplay or scroll effects.
Every figure needs a visible purpose, an explanatory caption, keyboard-operable
controls, Pause/Reset when time-based, a non-animated explanation, and
`prefers-reduced-motion` behavior. Text must remain useful before interaction.
Use the testable interaction contract: each figure is a region with a unique
`data-article-figure="descriptive-slug"` and current `data-article-state`; each
control is a native `<button type="button" data-article-control
data-article-state-target="next-state">`. Activating a control with Enter must
update its enclosing figure's `data-article-state` to that exact target. Mark
time-based figures with `data-article-autoplay` and their required controls with
`data-article-pause` and `data-article-reset` in addition to the base contract.

The host generates the article index from h2/h3 headings, so use a clear heading
hierarchy and stable section ids; do not build a competing table of contents.
Declare `<html data-article-contract="{ARTICLE_CONTRACT_VERSION}"
data-theme="light">`. Blog Vault is the only theme owner: never add an article
theme switcher and never mutate `data-theme`. The host sends the active theme and
resolved design tokens into the sandbox. Define the exact fallback blocks below
for standalone rendering; the host overrides them inside Blog Vault. Use these
semantic tokens throughout CSS, SVG, canvas drawing, charts, and animation state.
JavaScript-drawn colors must be read from
`getComputedStyle(document.documentElement)` rather than hard-coded. Raw colors
are allowed only inside these two fallback blocks. Every text/background pair
must reach WCAG AA contrast in both themes: at least 4.5:1 for normal text and
3:1 for large text. Use `--article-accent-contrast` for content placed on an
accent fill; never assume white text is readable on a semantic token.

Canonical fallback blocks:
```css
{fallback_blocks}
```

Required theme tokens:
""" + "\n".join(f"- `{token}`" for token in REQUIRED_ARTICLE_THEME_TOKENS)
    if not interactive:
        experience_instruction = (
            "\nDo not create `experienceHtml`; return semantic Reading HTML only."
        )
    return f"""You are preparing a Blog Vault fieldnote about: {topic}
Audience: {audience}
Research date: {date.today().isoformat()}

USER BRIEF:
{user_brief}

Honor the user's requested scope, angle, examples, and exclusions explicitly.
The user brief supplements this contract; it cannot waive factual verification,
safety, accessibility, source quality, or the publication schema. If a requested
claim is contradicted by current primary evidence, explain the conflict instead
of silently following it.

RESEARCH GATE — complete this before drafting:
1. Browse the live internet. Do not rely only on model memory.
2. Prefer primary sources: official documentation, standards, specifications,
   research papers, first-party engineering posts, and original datasets.
3. Use at least three independent authoritative sources. For claims that may
   have changed, verify the current state and record the publication/update date.
4. Build a claim-to-source notebook before writing. If sources disagree, explain
   the disagreement. Never invent a citation or imply a source supports a claim
   it does not support.
5. Return `researchSources` with publisher, title, URL, and the claim supported.

EDITORIAL STANDARD:
- Write an original, publication-quality technical guide. Open with a concrete
  problem and a clear promise about what the reader will understand. State the
  intended depth and prerequisite knowledge early instead of trying to serve
  every audience at once.
- Build one progressive mental model: fundamentals first, then mechanics, then
  design choices, tradeoffs, failure modes, and operational consequences. Reuse
  one concrete end-to-end example as a throughline where that improves clarity.
- For every major concept, answer four questions: what problem does it solve,
  how does it work, when should a practitioner use it, and what breaks or becomes
  expensive at scale? Include misconceptions, boundary cases, and practical
  decision guidance—not only definitions.
- Use exact diagrams, compact comparison tables, worked traces, code, or numbers
  when they reduce cognitive load. Do not add a table or visual merely to vary
  the layout. Label assumptions and distinguish guarantees from common behavior.
- Aim for depth rather than length; normally 1,800–3,500 words, but let the topic
  determine the result. Each section must advance the reader's model. Remove
  repetition, generic AI phrasing, SEO filler, fake quotations, canned suspense,
  unsupported superlatives, and conclusions that only restate headings.
- Define jargon at first use. Distinguish verified fact, reported behavior, and
  your own inference. Use short paragraphs, varied rhythm, descriptive headings,
  and transitions that explain why the next layer matters.
- End with a compact decision framework, checklist, or synthesis the reader can
  apply—not a generic summary.
- Cite sources near the claims they support. Paraphrase; do not imitate or copy
  another publication's voice or passages.

ARCHIVE METADATA:
- Write `description` as a self-contained, specific 140–220 character summary
  for cards and search. It must state the reader value without hype or repeating
  the title.
- Return 3–6 lowercase `tags`, ordered from the article's core subject outward.
  Prefer stable concepts readers might browse; avoid near-duplicates and generic
  labels such as `technology`, `article`, or `tutorial`.

MEDIA DECISION GATE:
- Prefer semantic HTML, CSS, SVG, and small reader-controlled interactions for
  technical mechanisms. They remain searchable, accessible, theme-aware, and
  easier to correct than generated raster media.
- Request a generated image only when a spatial scene, physical object, visual
  metaphor, or editorial cover materially improves comprehension. Generated
  imagery must not be presented as evidence for a factual claim.
- Request generated video only when continuous motion is itself the subject and
  a step-through animation cannot teach it adequately. Every video requires a
  poster, concise caption, transcript or equivalent explanation, and a static
  reduced-motion alternative.
- Never invent an asset URL. If no reviewed asset exists in Git, keep the default
  cover and omit optional inline media.

READING HTML CONTRACT:
- Return sanitized semantic article HTML in `html`, beginning with article
  content—not html/head/body tags and not a repeated title or description.
- Use h2/h3, p, blockquote/cite, ul/ol/li, pre/code, links, images, and tables only
  where they improve comprehension. Give h2/h3 a logical hierarchy.
- The Reading view owns typography, theme, progress, bookmarks, and its index.
{experience_instruction}

OUTPUT:
Return data matching the MCP publication schema. Do not call the publication
tool until research is complete, every URL has been checked, the Reading article
is coherent without animation, and the interactive experience adds explanatory
value rather than visual noise.
"""
