import { useCallback, useEffect, useMemo, useState } from 'react';

import type { Theme } from '../../shared/types';
import { useAuth } from '../auth/AuthContext';
import { ReviewComments, type ReviewAnchor } from './ReviewComments';
import { reviewApi } from './reviewApi';
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
  const { status: authStatus, user, signOut } = useAuth();
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [context, setContext] = useState<ReviewContext>();
  const [mode, setMode] = useState<ReviewMode>('reading');
  const [viewport, setViewport] = useState<ReviewViewport>('desktop');
  const [theme, setTheme] = useState<Theme>('dark');
  const [isBusy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const loadQueue = useCallback(async () => {
    const items = await reviewApi.listQueue();
    setQueue(items);
    setSelectedId((current) => current && items.some((item) => item.articleId === current)
      ? current : items[0]?.articleId);
  }, []);

  useEffect(() => {
    if (!user) return;
    void loadQueue().catch((loadError: unknown) => {
      setError(loadError instanceof Error ? loadError.message : 'Authentication failed.');
    });
  }, [loadQueue, user]);

  const loadContext = useCallback(async (articleId: string) => {
    setBusy(true);
    setError(undefined);
    try {
      setContext(await reviewApi.getContext(articleId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Review could not be loaded.');
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (user && selectedId) void loadContext(selectedId);
    if (!selectedId) setContext(undefined);
  }, [loadContext, selectedId, user]);

  const refresh = async () => {
    if (!selectedId) return;
    const [nextContext] = await Promise.all([
      reviewApi.getContext(selectedId),
      loadQueue(),
    ]);
    setContext(nextContext);
  };

  const runAction = async (action: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setError(undefined);
    try {
      await action();
      after?.();
      await loadQueue();
      if (selectedId && !after) setContext(await reviewApi.getContext(selectedId));
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

  if (authStatus === 'bootstrapping') {
    return <main className="review-login-shell"><p>Restoring session…</p></main>;
  }
  if (!user) {
    return <main className="review-login-shell"><section className="review-login-card">
      <a href="/" className="review-wordmark">BLOG VAULT</a>
      <span className="review-kicker">PRIVATE WORKSPACE</span>
      <h1>Human review</h1>
      <p>Inspect working drafts, compare the safe snapshot, and control publication.</p>
      <a className="auth-primary-link" href="/auth">Sign in</a>
    </section></main>;
  }
  return <main className="review-shell">
    <header className="review-topbar"><div><a href="/" className="review-wordmark">BLOG VAULT</a>
      <span>/ REVIEW</span></div><div className="review-topbar-actions">
        <span>{queue.filter((item) => item.status !== 'published').length} active</span><button onClick={() => {
          void signOut().then(() => window.location.assign('/')).catch(
            (caught: unknown) => setError(caught instanceof Error ? caught.message :
              'Sign out could not be completed.'),
          );
        }}>Sign out</button></div></header>
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
                onClick={() => void runAction(() => reviewApi.requestChanges(context.article.articleId))}>
                Request changes</button>
              <button className="review-action-primary" disabled={isBusy || unresolvedCount > 0}
                onClick={() => void runAction(() => reviewApi.approve(context.article.articleId))}>
                Approve</button></>}
            {context.article.status === 'changes_requested' &&
              <button onClick={() => void navigator.clipboard.writeText(
                `Pick up the requested changes for Blog Vault article ${context.article.slug}.`,
              )}>Copy Claude instruction</button>}
            {context.publishedSnapshot && context.article.status !== 'published' &&
              <button className="review-action-danger" disabled={isBusy}
                onClick={() => window.confirm('Discard this working draft and restore the published snapshot?') &&
                  void runAction(
                    () => reviewApi.discardDraft(context.article.articleId),
                    () => setSelectedId(undefined),
                  )}>Discard draft</button>}
            {context.article.status === 'approved' &&
              <button className="review-action-primary" disabled={isBusy}
                onClick={() => void runAction(
                  () => reviewApi.publish(context.article.articleId),
                  () => setSelectedId(undefined),
                )}>Publish</button>}
            {context.article.status === 'published' && context.publishedSnapshot &&
              <button className="review-action-danger" disabled={isBusy}
                onClick={() => window.confirm('Roll back to the previous published snapshot?') &&
                  void runAction(() => reviewApi.rollback(context.article.articleId))}>
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
        try { await reviewApi.addComment(context.article.articleId, values); await refresh(); }
        catch (actionError) {
          setError(actionError instanceof Error ? actionError.message : 'Comment could not be saved.');
        }
        finally { setBusy(false); }
      }} onResolve={async (commentId, resolved) => {
        setError(undefined);
        setBusy(true);
        try { await reviewApi.resolveComment(commentId, resolved); await refresh(); }
        catch (actionError) {
          setError(actionError instanceof Error ? actionError.message : 'Comment could not be updated.');
        }
        finally { setBusy(false); }
      }} />}
  </main>;
}
