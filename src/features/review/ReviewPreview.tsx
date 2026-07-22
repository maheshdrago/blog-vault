import { useEffect, useMemo, useRef } from 'react';

import {
  ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
  prepareArticleExperience,
} from '../reader/articleExperience';
import { resolveArticleThemeTokens } from '../reader/articleTheme';
import type { Theme } from '../../shared/types';
import type { ArticleDetail, ArticleSnapshot } from './types';

export type ReviewMode = 'reading' | 'explore' | 'compare';
export type ReviewViewport = 'desktop' | 'tablet' | 'mobile';

interface ReviewPreviewProps {
  current: ArticleDetail;
  snapshot?: ArticleSnapshot | null;
  mode: ReviewMode;
  theme: Theme;
  viewport: ReviewViewport;
}

type PreviewContent = Pick<ArticleDetail, 'post' | 'experienceHtml'>;

function readingDocument(content: PreviewContent, theme: Theme, label: string): string {
  return `<!doctype html><html lang="en" data-theme="${theme}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light;--paper:#e5f4ff;--surface:#fff;--text:#030710;--muted:#607d98;--line:rgba(3,42,78,.2);--accent:#005fc2}
:root[data-theme=dark]{color-scheme:dark;--paper:#030710;--surface:#0d1322;--text:#e5f4ff;--muted:#718da8;--line:rgba(127,200,255,.2);--accent:#99d3ff}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--text);font:18px/1.78 Georgia,serif}
article{width:min(760px,calc(100% - 40px));margin:0 auto;padding:64px 0 120px}h1,h2,h3{font-family:system-ui,sans-serif;line-height:1.1;letter-spacing:-.035em}h1{font-size:clamp(38px,7vw,72px);margin:0 0 24px}h2{font-size:34px;margin-top:64px}h3{font-size:24px;margin-top:42px}p,li{max-width:68ch}a{color:var(--accent)}blockquote,pre{padding:20px;border:1px solid var(--line);background:var(--surface);overflow:auto}img,video,canvas,svg{max-width:100%;height:auto}.meta{margin-bottom:48px;color:var(--muted);font:12px/1.5 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em}
</style></head><body><article><div class="meta">${escapeHtml(label)}</div><h1>${escapeHtml(content.post.title)}</h1>${content.post.html}</article></body></html>`;
}

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function PreviewFrame({ content, mode, theme, label, contentLabel }: {
  content: PreviewContent;
  mode: Exclude<ReviewMode, 'compare'>;
  theme: Theme;
  label: string;
  contentLabel: string;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const source = useMemo(() => {
    if (mode === 'explore' && content.experienceHtml) {
      return prepareArticleExperience(content.experienceHtml);
    }
    return readingDocument(content, theme, contentLabel);
  }, [content, contentLabel, mode, theme]);

  useEffect(() => {
    if (mode !== 'explore') return;
    frameRef.current?.contentWindow?.postMessage({
      source: ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
      type: 'theme',
      theme,
      tokens: resolveArticleThemeTokens(theme),
    }, '*');
  }, [mode, source, theme]);

  return <iframe ref={frameRef} title={label} srcDoc={source}
    sandbox={mode === 'explore' ? 'allow-scripts' : ''} referrerPolicy="no-referrer"
    onLoad={() => {
      if (mode === 'explore') {
        frameRef.current?.contentWindow?.postMessage({
          source: ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
          type: 'theme',
          theme,
          tokens: resolveArticleThemeTokens(theme),
        }, '*');
      }
    }} />;
}

export function ReviewPreview({ current, snapshot, mode, theme,
  viewport }: ReviewPreviewProps) {
  if (mode === 'compare') {
    return <div className="review-comparison">
      <section><header>Published snapshot</header>
        {snapshot ? <PreviewFrame content={snapshot} mode="reading" theme={theme}
          contentLabel="Published snapshot"
          label={`Published snapshot of ${current.post.title}`} /> :
          <div className="review-empty">This article has not been published yet.</div>}</section>
      <section><header>Working article</header>
        <PreviewFrame content={current} mode="reading" theme={theme}
          contentLabel="Working article"
          label={`Working copy of ${current.post.title}`} /></section>
    </div>;
  }
  if (mode === 'explore' && !current.experienceHtml) {
    return <div className="review-empty">This article has no Explore document.</div>;
  }
  return <div className={`review-device review-device-${viewport}`}>
    <PreviewFrame content={current} mode={mode} theme={theme}
      contentLabel="Working article"
      label={`${current.post.title} ${mode} preview`} />
  </div>;
}
