import type { BlogPost, PostSummary } from '../types';
import { resolveApiPath } from './config';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(resolveApiPath(path), {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Blog API request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const blogApi = {
  listPosts: async (): Promise<PostSummary[]> => {
    return request<PostSummary[]>('/posts');
  },
  getPost: async (slug: string): Promise<BlogPost> => {
    return request<BlogPost>(`/posts/${encodeURIComponent(slug)}`);
  },
};
