import { useCallback, useEffect, useMemo, useState } from 'react';

import type { Theme } from '../../shared/types';
import { ReviewComments, type ReviewAnchor } from './ReviewComments';
import { reviewApi, ReviewApiError } from './reviewApi';
import {
  ReviewPreview,
  type ReviewMode,
  type ReviewViewport,
} from './ReviewPreview';
import type {
  ReviewCommentDraft,
  ReviewContext,
  ReviewQueueItem,
} from './types';

const ADMIN_TOKEN_KEY = 'blog-vault-review-token';

function collectAnchors(context: ReviewContext): ReviewAnchor[] {
  const parser = new DOMParser();
  const reading = parser.parseFromString(context.article.post.html, 'text/html');
  const sections: ReviewAnchor[] = [...reading.querySelectorAll('h2[id],h3[id]')]
    .map((heading) => ({
      type: 'section',
      value: heading.id,
      label: `Section · ${heading.textContent?.trim() || heading.id}`,
    }));
  if (!context.article.experienceHtml) return sections;
  const experience = parser.parseFromString(context.article.experienceHtml, 'text/html');
  const figures: ReviewAnchor[] = [...experience.querySelectorAll('[data-article-figure]')]
    .flatMap((figure) => {
      const value = figure.getAttribute('data-article-figure');
      return value ? [{ type: 'figure', value, label: `Figure · ${value}` }] : [];
    });
  return [...sections, ...figures];
}

export function ReviewDashboard() {
  const [token, setToken] = useState(() => sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? '');
  const [tokenDraft, setTokenDraft] = useState(token);
  const [isAuthenticated, setAuthenticated] = useState(false);
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [context, setContext] = useState<ReviewContext>();
  const [mode, setMode] = useState<ReviewMode>('reading');
  const [viewport, setViewport] = useState<ReviewViewport>('desktop');
  const [theme, setTheme] = useState<Theme>('dark');
  const [isBusy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const loadQueue = useCallback(async (credential: string) => {
    const items = await reviewApi.listQueue(credential);
    setQueue(items);
    setAuthenticated(true);
    sessionStorage.setItem(ADMIN_TOKEN_KEY, credential);
    setToken(credential);
    setSelectedId((current) => current && items.some((item) => item.articleId === current)
      ? current : items[0]?.articleId);
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadQueue(token).catch((loadError: unknown) => {
      sessionStorage.removeItem(ADMIN_TOKEN_KEY);
      setAuthenticated(false);
      setError(loadError instanceof Error ? loadError.message : 'Authentication failed.');
    });
  }, [loadQueue, token]);

  const loadContext = useCallback(async (articleId: string) => {
    setBusy(true);
    setError(undefined);
    try {
      setContext(await reviewApi.getContext(token, articleId));
    } catch (loadError) {
      if (loadError instanceof ReviewApiError && loadError.status === 401) {
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
        setAuthenticated(false);
      }
      setError(loadError instanceof Error ? loadError.message : 'Review could not be loaded.');
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated && selectedId) void loadContext(selectedId);
    if (!selectedId) setContext(undefined);
  }, [isAuthenticated, loadContext, selectedId]);

  const refresh = async () => {
    if (!selectedId) return;
    const [nextContext] = await Promise.all([
      reviewApi.getContext(token, selectedId),
      loadQueue(token),
    ]);
    setContext(nextContext);
  };

  const runAction = async (action: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setError(undefined);
    try {
      await action();
      after?.();
      await loadQueue(token);
      if (selectedId && !after) setContext(await reviewApi.getContext(token, selectedId));
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Review action failed.');
    } finally {
      setBusy(false);
    }
  };

  const anchors = useMemo(() => context ? collectAnchors(context) : [], [context]);
  const rootComments = context?.comments.filter((comment) => !comment.parentCommentId) ?? [];
  const unresolvedCount = rootComments
    .filter((comment) => comment.status !== 'resolved').length;

  if (!isAuthenticated) {
    return <main className="review-login-shell"><section className="review-login-card">
      <a href="/" className="review-wordmark">BLOG VAULT</a>
      <span className="review-kicker">PRIVATE WORKSPACE</span>
      <h1>Human review</h1>
      <p>Inspect working drafts, compare the safe snapshot, and control publication.</p>
      <form onSubmit={(event) => {
        event.preventDefault();
        setError(undefined);
        void loadQueue(tokenDraft).catch((loginError: unknown) => {
          setError(loginError instanceof Error ? loginError.message : 'Authentication failed.');
        });
      }}><label>Admin access token<input type="password" autoComplete="current-password"
          value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} /></label>
        {error && <p className="review-error">{error}</p>}
        <button type="submit" disabled={!tokenDraft}>Open review queue</button></form>
      <small>The token is retained only for this browser tab.</small>
    </section></main>;
  }

  return <main className="review-shell">
    <header className="review-topbar"><div><a href="/" className="review-wordmark">BLOG VAULT</a>
      <span>/ REVIEW</span></div><div className="review-topbar-actions">
        <span>{queue.filter((item) => item.status !== 'published').length} active</span><button onClick={() => {
          sessionStorage.removeItem(ADMIN_TOKEN_KEY);
          setToken(''); setTokenDraft(''); setAuthenticated(false);
        }}>Lock workspace</button></div></header>
    <aside className="review-queue"><div className="review-queue-heading">
      <span className="review-kicker">VERIFICATION</span><h1>Review queue</h1></div>
      <div className="review-queue-list">{queue.map((item) =>
        <button className={item.articleId === selectedId ? 'active' : ''}
          key={item.articleId} onClick={() => setSelectedId(item.articleId)}>
          <div><span className={`review-status ${item.status}`}>{item.status.replace('_', ' ')}</span>
            <span>{item.status === 'published' ? 'rollback available' : 'working copy'}</span></div><strong>{item.title}</strong>
          <p>{item.description}</p><small>{item.openComments} open · {item.addressedComments} addressed</small>
        </button>)}</div>
      {queue.length === 0 && <div className="review-queue-empty">Nothing needs attention.</div>}
    </aside>
    <section className="review-workspace">
      {context ? <>
        <header className="review-document-header"><div><span className="review-kicker">
          {context.article.slug} · WORKING ARTICLE</span>
          <h2>{context.article.post.title}</h2></div>
          <div className="review-document-actions">
            {context.article.status === 'in_review' && <>
              <button className="review-action-danger" disabled={isBusy || unresolvedCount === 0}
                onClick={() => void runAction(() => reviewApi.requestChanges(token, context.article.articleId))}>
                Request changes</button>
              <button className="review-action-primary" disabled={isBusy || unresolvedCount > 0}
                onClick={() => void runAction(() => reviewApi.approve(token, context.article.articleId))}>
                Approve</button></>}
            {context.article.status === 'changes_requested' &&
              <button onClick={() => void navigator.clipboard.writeText(
                `Pick up the requested changes for Blog Vault article ${context.article.slug}.`,
              )}>Copy Claude instruction</button>}
            {context.publishedSnapshot && context.article.status !== 'published' &&
              <button className="review-action-danger" disabled={isBusy}
                onClick={() => window.confirm('Discard this working draft and restore the published snapshot?') &&
                  void runAction(
                    () => reviewApi.discardDraft(token, context.article.articleId),
                    () => setSelectedId(undefined),
                  )}>Discard draft</button>}
            {context.article.status === 'approved' &&
              <button className="review-action-primary" disabled={isBusy}
                onClick={() => void runAction(
                  () => reviewApi.publish(token, context.article.articleId),
                  () => setSelectedId(undefined),
                )}>Publish</button>}
            {context.article.status === 'published' && context.publishedSnapshot &&
              <button className="review-action-danger" disabled={isBusy}
                onClick={() => window.confirm('Roll back to the previous published snapshot?') &&
                  void runAction(() => reviewApi.rollback(token, context.article.articleId))}>
                Roll back publication</button>}
          </div></header>
        <nav className="review-preview-toolbar" aria-label="Preview controls">
          <div>{(['reading', 'explore', 'compare'] as ReviewMode[]).map((item) =>
            <button className={mode === item ? 'active' : ''} key={item}
              disabled={item === 'explore' && !context.article.experienceHtml}
              onClick={() => setMode(item)}>{item}</button>)}</div>
          <div>{(['desktop', 'tablet', 'mobile'] as ReviewViewport[]).map((item) =>
            <button className={viewport === item ? 'active' : ''} key={item}
              disabled={mode === 'compare'} onClick={() => setViewport(item)}>{item}</button>)}</div>
          <div>{(['light', 'dark'] as Theme[]).map((item) =>
            <button className={theme === item ? 'active' : ''} key={item}
              onClick={() => setTheme(item)}>{item}</button>)}</div>
        </nav>
        {error && <div className="review-error-banner">{error}</div>}
        <div className="review-preview-stage"><ReviewPreview current={context.article}
          snapshot={context.publishedSnapshot} mode={mode} theme={theme} viewport={viewport} /></div>
      </> : <div className="review-empty">Select an article to begin review.</div>}
    </section>
    {context && <ReviewComments anchors={anchors} comments={context.comments}
      canComment={context.article.status !== 'approved' && context.article.status !== 'published'} isSaving={isBusy}
      onAdd={async (values: ReviewCommentDraft) => {
        setError(undefined);
        setBusy(true);
        try { await reviewApi.addComment(token, context.article.articleId, values); await refresh(); }
        catch (actionError) {
          setError(actionError instanceof Error ? actionError.message : 'Comment could not be saved.');
        }
        finally { setBusy(false); }
      }} onResolve={async (commentId, resolved) => {
        setError(undefined);
        setBusy(true);
        try { await reviewApi.resolveComment(token, commentId, resolved); await refresh(); }
        catch (actionError) {
          setError(actionError instanceof Error ? actionError.message : 'Comment could not be updated.');
        }
        finally { setBusy(false); }
      }} />}
  </main>;
}
