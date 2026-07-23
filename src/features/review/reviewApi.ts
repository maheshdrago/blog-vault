import { authenticatedFetch } from '../../shared/api/authApi';
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
  init: RequestInit = {},
): Promise<T> {
  const response = await authenticatedFetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
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
  listQueue: (): Promise<ReviewQueueItem[]> =>
    request('/me/reviews?includePublished=true'),
  getContext: (articleId: string): Promise<ReviewContext> =>
    request(`/me/reviews/${articleId}`),
  addComment: (
    articleId: string,
    values: ReviewCommentDraft,
  ): Promise<ReviewComment> => request(`/me/reviews/${articleId}/comments`, {
    method: 'POST',
    body: JSON.stringify(values),
  }),
  resolveComment: (
    commentId: string,
    resolved: boolean,
  ): Promise<ReviewComment> => request(
    `/me/reviews/comments/${commentId}/resolution`,
    { method: 'PUT', body: JSON.stringify({ resolved }) },
  ),
  requestChanges: (articleId: string): Promise<ReviewContext> =>
    request(`/me/reviews/${articleId}/request-changes`, { method: 'POST' }),
  approve: (articleId: string): Promise<ReviewContext> =>
    request(`/me/reviews/${articleId}/approve`, { method: 'POST' }),
  publish: (articleId: string): Promise<unknown> =>
    request(`/me/reviews/${articleId}/publish`, { method: 'POST' }),
  discardDraft: (articleId: string): Promise<unknown> =>
    request(`/me/reviews/${articleId}/discard-draft`, { method: 'POST' }),
  rollback: (articleId: string): Promise<unknown> =>
    request(`/me/reviews/${articleId}/rollback`, { method: 'POST' }),
};
