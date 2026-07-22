/** Canonical mapping from the application palette to article theme tokens. */

import type { Theme } from '../../shared/types';

export const ARTICLE_THEME_TOKEN_NAMES = [
  '--article-bg',
  '--article-surface',
  '--article-surface-raised',
  '--article-text',
  '--article-text-muted',
  '--article-border',
  '--article-accent',
  '--article-accent-contrast',
  '--article-link',
  '--article-focus',
  '--article-selection',
  '--article-code-bg',
  '--article-success',
  '--article-warning',
  '--article-danger',
  '--article-visual-1',
  '--article-visual-2',
  '--article-visual-3',
  '--article-visual-4',
  '--article-font-body',
  '--article-font-display',
  '--article-font-mono',
] as const;

export type ArticleThemeToken = typeof ARTICLE_THEME_TOKEN_NAMES[number];
export type ArticleThemeTokens = Record<ArticleThemeToken, string>;

const APPLICATION_TOKEN_BY_ARTICLE_TOKEN: Record<ArticleThemeToken, string> = {
  '--article-bg': '--canvas',
  '--article-surface': '--chrome',
  '--article-surface-raised': '--chrome-raised',
  '--article-text': '--ink',
  '--article-text-muted': '--muted',
  '--article-border': '--hairline-strong',
  '--article-accent': '--accent',
  '--article-accent-contrast': '--accent-contrast',
  '--article-link': '--accent-bright',
  '--article-focus': '--accent-bright',
  '--article-selection': '--accent-wash',
  '--article-code-bg': '--canvas-deep',
  '--article-success': '--status-success',
  '--article-warning': '--status-warning',
  '--article-danger': '--status-danger',
  '--article-visual-1': '--visual-1',
  '--article-visual-2': '--visual-2',
  '--article-visual-3': '--visual-3',
  '--article-visual-4': '--visual-4',
  '--article-font-body': '--font-ui',
  '--article-font-display': '--font-ui',
  '--article-font-mono': '--font-mono',
};

export function resolveArticleThemeTokens(theme: Theme): ArticleThemeTokens {
  const root = document.documentElement;
  if (root.dataset.theme !== theme) root.dataset.theme = theme;
  const styles = getComputedStyle(root);
  return Object.fromEntries(ARTICLE_THEME_TOKEN_NAMES.map((articleToken) => {
    const applicationToken = APPLICATION_TOKEN_BY_ARTICLE_TOKEN[articleToken];
    const value = styles.getPropertyValue(applicationToken).trim();
    if (!value) throw new Error(`Missing application theme token: ${applicationToken}`);
    return [articleToken, value];
  })) as ArticleThemeTokens;
}
