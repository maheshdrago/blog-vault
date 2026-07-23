import type { BlogPost, PostSummary } from '../types';
import { authenticatedFetch } from './authApi';

async function request<T>(path: string): Promise<T> {
  const response = await authenticatedFetch(path);
  if (!response.ok) {
    throw new Error(`Blog API request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const blogApi = {
  listPosts: async (): Promise<PostSummary[]> => {
    return request<PostSummary[]>('/me/posts');
  },
  getPost: async (slug: string): Promise<BlogPost> => {
    return request<BlogPost>(`/me/posts/${encodeURIComponent(slug)}`);
  },
};
