/** Security boundary and messaging contract for animated article experiences. */

import { INTERACTIVE_EXPERIENCE_PATH_PATTERN } from './contentPolicy';
import { ARTICLE_THEME_TOKEN_NAMES } from './articleTheme';
import { authenticatedFetch } from '../../shared/api/authApi';

export const ARTICLE_EXPERIENCE_MESSAGE_SOURCE = 'blog-vault-article-experience';

const CONTENT_SECURITY_POLICY = [
  "default-src 'none'",
  "script-src 'unsafe-inline'",
  "style-src 'unsafe-inline'",
  'img-src data: blob:',
  'font-src data:',
  'media-src data: blob:',
  "connect-src 'none'",
  "object-src 'none'",
  "frame-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
].join('; ');

const RESPONSIVE_COMPATIBILITY_STYLES = `<style data-blog-vault-boundary>
/* Existing articles predate the versioned semantic-token contract. These aliases let
   their custom diagrams follow dark mode without altering animation behavior. */
html[data-theme='dark']:not([data-article-contract]) {
  color-scheme: dark;
  --paper: #030710;
  --paper-2: #0d1322;
  --bg: #030710;
  --surface: #0d1322;
  --panel: #060b14;
  --panel-2: #0d1322;
  --navy: #060b14;
  --navy-2: #0d1322;
  --navy-3: #161f34;
  --ink: #e5f4ff;
  --ink-soft: #b2deff;
  --ink-faint: #718da8;
  --muted: #718da8;
  --faint: #607d98;
  --hair: rgba(127, 200, 255, .16);
  --hair-dark: #2f4b68;
  --hair-dk: #2f4b68;
  --line: rgba(127, 200, 255, .16);
  --line-navy: #2f4b68;
  --head: #7fc8ff;
  --head-soft: #161f34;
  --data: #99d3ff;
  --data-soft: #161f34;
  --old: #99d3ff;
  --old-soft: #161f34;
  --new: #2dd4bf;
  --new-soft: #10352f;
  --add: #2dd4bf;
  --add-soft: #10352f;
  --pass: #2dd4bf;
  --pass-soft: #10352f;
  --del: #f0616d;
  --del-soft: #3a171d;
  --stop: #f0616d;
  --stop-soft: #3a171d;
  --danger: #f0616d;
  --danger-soft: #3a171d;
  --edit: #f6a723;
  --edit-soft: #3b2b0c;
  --warn: #f6a723;
  --warn-soft: #3b2b0c;
}
html[data-theme='dark']:not([data-article-contract]) :is(
  .widget,
  .note:not(.warn):not(.data):not(.pass),
  .cmp-card,
  .stk-btn:not(.on),
  .btn:not(.primary):not(.accent):not(.warnbtn),
  .dl.ctx,
  .hashin,
  .cmt,
  .tool,
  .tier,
  .phase-btn:not(.active),
  .fact,
  .navbtns button,
  .steps-hint button
) {
  background: #0d1322 !important;
  border-color: rgba(127, 200, 255, .16) !important;
}
html[data-theme='dark']:not([data-article-contract]) :is(
  .lead,
  .pull,
  .dl.ctx,
  .tool p,
  .strat-card p,
  .cmp-card p
) {
  color: #b2deff !important;
}
html[data-theme='dark']:not([data-article-contract]) .noderect {
  fill: #0d1322 !important;
}
html, body {
  width: 100% !important;
  max-width: 100% !important;
  overflow-x: hidden !important;
}
body > *, main, header, footer, section, article {
  max-width: 100%;
}
img, video, canvas {
  max-width: 100%;
  height: auto;
}
pre, table, .widget, .panel, .railstage, .stage {
  max-width: 100%;
  overflow-x: auto;
}
[data-blog-vault-index] {
  position: fixed;
  z-index: 2147483000;
  top: 18px;
  right: 18px;
  width: min(220px, calc(100vw - 36px));
  overflow: hidden;
  border: 1px solid var(--article-border, rgba(127, 200, 255, .24));
  border-radius: 6px;
  background: color-mix(in srgb, var(--article-surface, #0d1322) 92%, transparent);
  box-shadow: 0 18px 55px rgba(0, 0, 0, .18);
  color: var(--article-text, #e5f4ff);
  font: 500 11px/1.45 var(--article-font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  backdrop-filter: blur(14px);
}
html[data-theme='light']:not([data-article-contract]) [data-blog-vault-index] {
  --article-surface: #f2faff;
  --article-text: #030710;
  --article-text-muted: #607d98;
  --article-border: rgba(3, 42, 78, .2);
  --article-accent: #006ddd;
}
html[data-theme='dark']:not([data-article-contract]) [data-blog-vault-index] {
  --article-surface: #0d1322;
  --article-text: #e5f4ff;
  --article-text-muted: #718da8;
  --article-border: rgba(127, 200, 255, .2);
  --article-accent: #7fc8ff;
}
[data-blog-vault-index] > button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  letter-spacing: .1em;
  text-transform: uppercase;
  cursor: pointer;
}
[data-blog-vault-index] > button span { color: var(--article-accent); }
[data-blog-vault-index] ol {
  display: grid;
  gap: 1px;
  max-height: min(62vh, 560px);
  margin: 0;
  padding: 4px 9px 10px;
  overflow-y: auto;
  list-style: none;
}
[data-blog-vault-index] li { margin: 0; padding: 0; }
[data-blog-vault-index] a {
  display: block;
  padding: 6px 7px;
  border-left: 1px solid var(--article-border);
  color: var(--article-text-muted, #718da8);
  text-decoration: none;
}
[data-blog-vault-index] li[data-level='3'] a { padding-left: 17px; font-size: 10px; }
[data-blog-vault-index] a[aria-current='true'] {
  border-left-color: var(--article-accent);
  color: var(--article-text);
}
[data-blog-vault-index].is-collapsed ol { display: none; }
@media (max-width: 980px) {
  [data-blog-vault-index] { width: auto; max-width: calc(100vw - 36px); }
  [data-blog-vault-index] ol { display: none; width: min(300px, calc(100vw - 36px)); }
  [data-blog-vault-index].is-open ol { display: grid; }
}
</style>`;

const EXPERIENCE_BRIDGE = `<script>
(() => {
  const source = '${ARTICLE_EXPERIENCE_MESSAGE_SOURCE}';
  const allowedThemeTokens = new Set(${JSON.stringify(ARTICLE_THEME_TOKEN_NAMES)});
  let scheduled = false;
  let contrastScheduled = false;

  const parseColor = (value) => {
    const match = value.match(/rgba?\(([^)]+)\)/i);
    if (!match) return null;
    const channels = match[1].replace('/', ' ').split(/[\s,]+/)
      .filter(Boolean).map(Number);
    if (channels.length < 3 || channels.slice(0, 3).some(Number.isNaN)) return null;
    return { rgb: channels.slice(0, 3), alpha: Number.isFinite(channels[3]) ? channels[3] : 1 };
  };

  const luminance = (rgb) => {
    const channels = rgb.map((channel) => {
      const value = channel / 255;
      return value <= .04045 ? value / 12.92 : Math.pow((value + .055) / 1.055, 2.4);
    });
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
  };

  const contrastRatio = (first, second) => {
    const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
    return (values[0] + .05) / (values[1] + .05);
  };

  const effectiveBackground = (element) => {
    let current = element;
    while (current) {
      const styles = getComputedStyle(current);
      if (styles.backgroundImage !== 'none') return null;
      const background = parseColor(styles.backgroundColor);
      if (background && background.alpha >= .95) return background.rgb;
      current = current.parentElement;
    }
    return document.documentElement.dataset.theme === 'dark' ? [3, 7, 16] : [229, 244, 255];
  };

  const clearContrastCorrections = () => {
    document.querySelectorAll('[data-blog-vault-contrast]').forEach((element) => {
      const original = element.getAttribute('data-blog-vault-original-color') || '';
      if (original) element.style.color = original;
      else element.style.removeProperty('color');
      element.removeAttribute('data-blog-vault-contrast');
      element.removeAttribute('data-blog-vault-original-color');
    });
  };

  const enforceReadableContrast = () => {
    contrastScheduled = false;
    document.querySelectorAll('body, body *').forEach((element) => {
      if (element.hasAttribute('data-blog-vault-contrast')) return;
      const hasDirectText = Array.from(element.childNodes).some((node) =>
        node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim()));
      if (!hasDirectText) return;
      const foreground = parseColor(getComputedStyle(element).color);
      const background = effectiveBackground(element);
      if (!foreground || !background || contrastRatio(foreground.rgb, background) >= 4.5) return;
      const dark = [3, 7, 16];
      const light = [242, 250, 255];
      const replacement = contrastRatio(dark, background) >= contrastRatio(light, background) ?
        '#030710' : '#f2faff';
      element.setAttribute('data-blog-vault-original-color', element.style.color || '');
      element.setAttribute('data-blog-vault-contrast', 'corrected');
      element.style.setProperty('color', replacement, 'important');
    });
  };

  const scheduleContrastCheck = () => {
    if (contrastScheduled) return;
    contrastScheduled = true;
    requestAnimationFrame(enforceReadableContrast);
  };

  const buildIndex = () => {
    if (document.querySelector('[data-blog-vault-index], [data-article-index]')) return;
    const headings = Array.from(document.querySelectorAll('main h2, main h3, article h2, article h3'));
    if (headings.length < 2) return;
    const usedIds = new Set(Array.from(document.querySelectorAll('[id]')).map((node) => node.id));
    headings.forEach((heading, index) => {
      if (heading.id) return;
      const base = (heading.textContent || 'section')
        .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section';
      let id = base;
      let suffix = index;
      while (usedIds.has(id)) id = base + '-' + (++suffix);
      heading.id = id;
      usedIds.add(id);
    });

    const navigation = document.createElement('nav');
    navigation.dataset.blogVaultIndex = '';
    navigation.setAttribute('aria-label', 'Article index');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.innerHTML = 'Index <span aria-hidden="true">+</span>';
    const compact = matchMedia('(max-width: 980px)');
    toggle.setAttribute('aria-expanded', String(!compact.matches));
    const list = document.createElement('ol');
    headings.forEach((heading) => {
      const item = document.createElement('li');
      item.dataset.level = heading.tagName.slice(1);
      const link = document.createElement('a');
      link.href = '#' + heading.id;
      link.textContent = heading.textContent || 'Section';
      link.addEventListener('click', (event) => {
        event.preventDefault();
        heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
        navigation.classList.remove('is-open');
      });
      item.append(link);
      list.append(item);
    });
    toggle.addEventListener('click', () => {
      if (compact.matches) {
        navigation.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', String(navigation.classList.contains('is-open')));
      } else {
        navigation.classList.toggle('is-collapsed');
        toggle.setAttribute('aria-expanded', String(!navigation.classList.contains('is-collapsed')));
      }
    });
    navigation.append(toggle, list);
    document.body.append(navigation);

    if ('IntersectionObserver' in window) {
      const links = new Map(Array.from(list.querySelectorAll('a')).map((link) => [link.hash.slice(1), link]));
      const observer = new IntersectionObserver((entries) => {
        const active = entries.find((entry) => entry.isIntersecting);
        if (!active) return;
        links.forEach((link) => link.removeAttribute('aria-current'));
        links.get(active.target.id)?.setAttribute('aria-current', 'true');
      }, { rootMargin: '-15% 0px -72% 0px' });
      headings.forEach((heading) => observer.observe(heading));
    }
  };

  const publishProgress = () => {
    scheduled = false;
    const root = document.scrollingElement || document.documentElement;
    const available = Math.max(0, root.scrollHeight - root.clientHeight);
    const progress = available > 0 ? (root.scrollTop / available) * 100 : 100;
    parent.postMessage({ source, type: 'progress', progress }, '*');
  };

  const scheduleProgress = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(publishProgress);
  };

  addEventListener('scroll', scheduleProgress, { passive: true });
  addEventListener('resize', () => {
    scheduleProgress();
    scheduleContrastCheck();
  }, { passive: true });
  addEventListener('message', (event) => {
    if (event.source !== parent || event.data?.source !== source) return;
    if (event.data?.type === 'theme' && ['light', 'dark'].includes(event.data.theme)) {
      const root = document.documentElement;
      root.dataset.theme = event.data.theme;
      root.style.colorScheme = event.data.theme;
      if (event.data.tokens && typeof event.data.tokens === 'object') {
        Object.entries(event.data.tokens).forEach(([token, value]) => {
          if (allowedThemeTokens.has(token) && typeof value === 'string' && value.length <= 200) {
            root.style.setProperty(token, value);
          }
        });
      }
      clearContrastCorrections();
      scheduleContrastCheck();
    }
    if (event.data?.type === 'restore') {
      const root = document.scrollingElement || document.documentElement;
      const available = Math.max(0, root.scrollHeight - root.clientHeight);
      const progress = Math.min(100, Math.max(0, Number(event.data.progress) || 0));
      scrollTo({ top: available * (progress / 100), behavior: 'instant' });
      scheduleProgress();
    }
  });

  if ('ResizeObserver' in window) {
    new ResizeObserver(scheduleProgress).observe(document.documentElement);
  }
  if ('MutationObserver' in window) {
    new MutationObserver(scheduleContrastCheck).observe(document.body, {
      childList: true,
      subtree: true,
    });
  }
  addEventListener('load', () => {
    buildIndex();
    parent.postMessage({ source, type: 'ready' }, '*');
    scheduleProgress();
    scheduleContrastCheck();
  });
})();
</script>`;

export function prepareArticleExperience(source: string): string {
  const policy = `<meta http-equiv="Content-Security-Policy" content="${CONTENT_SECURITY_POLICY}">`;
  const boundary = `${policy}${RESPONSIVE_COMPATIBILITY_STYLES}`;
  const withPolicy = /<head(?:\s[^>]*)?>/i.test(source) ?
    source.replace(/<head(?:\s[^>]*)?>/i, (head) => `${head}${boundary}`) :
    `${boundary}${source}`;
  return /<\/body>/i.test(withPolicy) ?
    withPolicy.replace(/<\/body>/i, `${EXPERIENCE_BRIDGE}</body>`) :
    `${withPolicy}${EXPERIENCE_BRIDGE}`;
}

export async function loadArticleExperience(
  path: string,
  signal: AbortSignal,
): Promise<string> {
  if (!INTERACTIVE_EXPERIENCE_PATH_PATTERN.test(path)) {
    throw new Error('Invalid interactive article path.');
  }
  const response = await authenticatedFetch(`/me${path}`, {
    headers: { Accept: 'text/plain' },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Interactive article failed to load (${response.status}).`);
  }
  return prepareArticleExperience(await response.text());
}
