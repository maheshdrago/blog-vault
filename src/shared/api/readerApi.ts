import { authenticatedFetch } from './authApi';
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

async function authenticatedRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const requestInit: RequestInit = {
    ...init,
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
  };
  const response = await authenticatedFetch(path, requestInit);
  if (!response.ok) throw new Error(`Reader API failed with status ${response.status}.`);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const readerApi = {
  getPreferences: (): Promise<ReaderPreferences> =>
    authenticatedRequest('/me/preferences'),
  updatePreferences: (_readerId: string,
    values: Pick<ReaderPreferences,
    'theme' | 'fontScale' | 'fontFamily' | 'lineHeight' | 'contentWidth'>): Promise<ReaderPreferences> =>
    authenticatedRequest('/me/preferences', {
      method: 'PUT', body: JSON.stringify(values),
    }),
  listReadingStates: (): Promise<ReadingState[]> =>
    authenticatedRequest('/me/reading-states'),
  listLearningPaths: (): Promise<LearningPath[]> =>
    authenticatedRequest('/me/learning-paths'),
  listGroups: (): Promise<ReaderGroup[]> =>
    authenticatedRequest('/me/groups'),
  createGroup: (_readerId: string, name: string, color: string): Promise<ReaderGroup> =>
    authenticatedRequest('/me/groups', {
      method: 'POST', body: JSON.stringify({ name, color }),
    }),
  deleteGroup: (_readerId: string, groupId: string): Promise<void> =>
    authenticatedRequest(`/me/groups/${groupId}`, { method: 'DELETE' }),
  updateReadingState: (
    _readerId: string,
    postSlug: string,
    state: Pick<ReadingState, 'isFavorite' | 'isBookmarked' | 'progressPercent' | 'groupId'>,
  ): Promise<ReadingState> =>
    authenticatedRequest(`/me/reading-states/${postSlug}`, {
      method: 'PUT', body: JSON.stringify(state),
    }),
};
