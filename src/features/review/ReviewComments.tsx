import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';

import type {
  ReviewAnchorType,
  ReviewComment,
  ReviewCommentDraft,
} from './types';

export interface ReviewAnchor {
  type: Exclude<ReviewAnchorType, 'general'>;
  value: string;
  label: string;
}

interface ReviewCommentsProps {
  anchors: ReviewAnchor[];
  comments: ReviewComment[];
  canComment: boolean;
  isSaving: boolean;
  onAdd: (values: ReviewCommentDraft) => Promise<void>;
  onResolve: (commentId: string, resolved: boolean) => Promise<void>;
}

export function ReviewComments({ anchors, comments, canComment, isSaving,
  onAdd, onResolve }: ReviewCommentsProps) {
  const [body, setBody] = useState('');
  const [anchor, setAnchor] = useState('general:');
  const roots = comments.filter((comment) => !comment.parentCommentId);
  const replies = useMemo(() => new Map(roots.map((root) => [
    root.commentId,
    comments.filter((comment) => comment.parentCommentId === root.commentId),
  ])), [comments, roots]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!body.trim()) return;
    const separator = anchor.indexOf(':');
    const anchorType = anchor.slice(0, separator) as ReviewAnchorType;
    const anchorValue = anchor.slice(separator + 1) || undefined;
    await onAdd({ body, anchorType, anchorValue });
    setBody('');
  };

  return <aside className="review-comments">
    <header><div><span className="review-kicker">FEEDBACK</span>
      <h2>Review notes</h2></div><span>{roots.length}</span></header>
    <div className="review-thread-list">
      {roots.length === 0 && <div className="review-comments-empty">
        No comments yet. Approve directly, or leave concrete revision notes.
      </div>}
      {roots.map((comment) => <article className={`review-comment ${comment.status}`}
        key={comment.commentId}>
        <div className="review-comment-meta"><span>{comment.anchorType === 'general' ?
          'Whole article' : `${comment.anchorType}: ${comment.anchorValue}`}</span>
          <time>{new Date(comment.createdAt).toLocaleString()}</time></div>
        <p>{comment.body}</p>
        {(replies.get(comment.commentId) ?? []).map((reply) =>
          <div className="review-reply" key={reply.commentId}>
            <strong>Assistant response</strong><p>{reply.body}</p>
          </div>)}
        <button className="review-resolve" disabled={isSaving}
          onClick={() => void onResolve(
            comment.commentId,
            comment.status !== 'resolved',
          )}>{comment.status === 'resolved' ? 'Reopen' : 'Mark resolved'}</button>
      </article>)}
    </div>
    {canComment && <form className="review-comment-form" onSubmit={(event) => void submit(event)}>
      <label>Attach to<select value={anchor} onChange={(event) => setAnchor(event.target.value)}>
        <option value="general:">Whole article</option>
        {anchors.map((item) => <option key={`${item.type}:${item.value}`}
          value={`${item.type}:${item.value}`}>{item.label}</option>)}
      </select></label>
      <label>Comment<textarea value={body} maxLength={4000} rows={5}
        placeholder="Explain what should change and why…"
        onChange={(event) => setBody(event.target.value)} /></label>
      <button className="review-action-primary" type="submit"
        disabled={isSaving || !body.trim()}>Add comment</button>
    </form>}
  </aside>;
}
