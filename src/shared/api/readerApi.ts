import { resolveApiPath } from './config';
import type { PostSummary } from '../types';

export interface ReadingState {
  readerId: string;
  postSlug: string;
  isFavorite: boolean;
  isBookmarked: boolean;
  progressPercent: number;
  groupId: string | null;
  updatedAt: string;
  lastReadAt: string | null;
}

export interface ReaderGroup {
  groupId: string;
  readerId: string;
  name: string;
  color: string;
  createdAt: string;
  updatedAt: string;
}

export interface ReaderPreferences {
  readerId: string;
  theme: 'dark' | 'light' | 'system';
  fontScale: number;
  fontFamily: 'serif' | 'sans';
  lineHeight: number;
  contentWidth: number;
  updatedAt: string;
}

export interface LearningPathLesson {
  lessonId: string;
  article: PostSummary;
  sortOrder: number;
  isRequired: boolean;
  progressPercent: number;
  isCompleted: boolean;
  isLocked: boolean;
}

export interface LearningPathSection {
  sectionId: string;
  title: string;
  icon: string;
  sortOrder: number;
  lessons: LearningPathLesson[];
}

export interface LearningPath {
  pathId: string;
  slug: string;
  title: string;
  description: string;
  icon: string;
  sortOrder: number;
  completedLessons: number;
  totalLessons: number;
  progressPercent: number;
  sections: LearningPathSection[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiPath(path), {
    ...init,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) throw new Error(`Reader API failed with status ${response.status}.`);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getReaderId(): string {
  const existing = localStorage.getItem('readerId');
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem('readerId', created);
  return created;
}

export const readerApi = {
  getPreferences: (readerId: string): Promise<ReaderPreferences> =>
    request(`/readers/${readerId}/preferences`),
  updatePreferences: (readerId: string,
    values: Pick<ReaderPreferences, 'theme' | 'fontScale' | 'fontFamily' | 'lineHeight' | 'contentWidth'>): Promise<ReaderPreferences> =>
    request(`/readers/${readerId}/preferences`, {
      method: 'PUT', body: JSON.stringify(values),
    }),
  listReadingStates: (readerId: string): Promise<ReadingState[]> =>
    request(`/readers/${readerId}/reading-states`),
  listLearningPaths: (readerId: string): Promise<LearningPath[]> =>
    request(`/readers/${readerId}/learning-paths`),
  listGroups: (readerId: string): Promise<ReaderGroup[]> =>
    request(`/readers/${readerId}/groups`),
  createGroup: (readerId: string, name: string, color: string): Promise<ReaderGroup> =>
    request(`/readers/${readerId}/groups`, {
      method: 'POST', body: JSON.stringify({ name, color }),
    }),
  deleteGroup: (readerId: string, groupId: string): Promise<void> =>
    request(`/readers/${readerId}/groups/${groupId}`, { method: 'DELETE' }),
  updateReadingState: (
    readerId: string,
    postSlug: string,
    state: Pick<ReadingState, 'isFavorite' | 'isBookmarked' | 'progressPercent' | 'groupId'>,
  ): Promise<ReadingState> => request(`/readers/${readerId}/reading-states/${postSlug}`, {
    method: 'PUT', body: JSON.stringify(state),
  }),
};
