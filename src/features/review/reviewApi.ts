import { resolveApiPath } from '../../shared/api/config';
import type {
  ReviewComment,
  ReviewCommentDraft,
  ReviewContext,
  ReviewQueueItem,
} from './types';

export class ReviewApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(resolveApiPath(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Review request failed.' })) as {
      detail?: string;
    };
    throw new ReviewApiError(payload.detail ?? 'Review request failed.', response.status);
  }
  return response.json() as Promise<T>;
}

export const reviewApi = {
  listQueue: (token: string): Promise<ReviewQueueItem[]> =>
    request('/admin/reviews?includePublished=true', token),
  getContext: (token: string, articleId: string): Promise<ReviewContext> =>
    request(`/admin/reviews/${articleId}`, token),
  addComment: (
    token: string,
    articleId: string,
    values: ReviewCommentDraft,
  ): Promise<ReviewComment> => request(`/admin/reviews/${articleId}/comments`, token, {
    method: 'POST',
    body: JSON.stringify(values),
  }),
  resolveComment: (
    token: string,
    commentId: string,
    resolved: boolean,
  ): Promise<ReviewComment> => request(
    `/admin/reviews/comments/${commentId}/resolution`,
    token,
    { method: 'PUT', body: JSON.stringify({ resolved }) },
  ),
  requestChanges: (token: string, articleId: string): Promise<ReviewContext> =>
    request(`/admin/reviews/${articleId}/request-changes`, token, { method: 'POST' }),
  approve: (token: string, articleId: string): Promise<ReviewContext> =>
    request(`/admin/reviews/${articleId}/approve`, token, { method: 'POST' }),
  publish: (token: string, articleId: string): Promise<unknown> =>
    request(`/admin/reviews/${articleId}/publish`, token, { method: 'POST' }),
  discardDraft: (token: string, articleId: string): Promise<unknown> =>
    request(`/admin/reviews/${articleId}/discard-draft`, token, { method: 'POST' }),
  rollback: (token: string, articleId: string): Promise<unknown> =>
    request(`/admin/reviews/${articleId}/rollback`, token, { method: 'POST' }),
};
