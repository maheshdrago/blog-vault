import type { BlogPost } from '../../shared/types';

export type ArticleWorkflowStatus =
  | 'draft'
  | 'in_review'
  | 'changes_requested'
  | 'approved'
  | 'published'
  | 'archived';

export type ReviewAnchorType = 'general' | 'section' | 'figure';
export type ReviewCommentStatus = 'open' | 'addressed' | 'resolved';

export interface ResearchSource {
  publisher: string;
  title: string;
  url: string;
  claimSupported: string;
}

export interface ArticleRecord {
  articleId: string;
  slug: string;
  status: ArticleWorkflowStatus;
  reviewCycleId?: string | null;
  submittedContentHash?: string | null;
  createdAt: string;
  updatedAt: string;
  publishedAt?: string | null;
}

export interface ArticleDetail extends ArticleRecord {
  post: BlogPost;
  experienceHtml?: string | null;
  contentHash: string;
  researchSources: ResearchSource[];
  revisionNotes?: string | null;
}

export interface ArticleSnapshot {
  articleId: string;
  slug: string;
  post: BlogPost;
  experienceHtml?: string | null;
  contentHash: string;
  researchSources: ResearchSource[];
  capturedAt: string;
  publishedAt: string;
}

export interface ReviewQueueItem extends ArticleRecord {
  title: string;
  description: string;
  openComments: number;
  addressedComments: number;
}

export interface ReviewComment {
  commentId: string;
  articleId: string;
  reviewCycleId: string;
  parentCommentId?: string | null;
  author: 'human' | 'assistant';
  body: string;
  anchorType: ReviewAnchorType;
  anchorValue?: string | null;
  status: ReviewCommentStatus;
  createdAt: string;
  resolvedAt?: string | null;
}

export interface ReviewContext {
  article: ArticleDetail;
  publishedSnapshot?: ArticleSnapshot | null;
  comments: ReviewComment[];
}

export interface ReviewCommentDraft {
  body: string;
  anchorType: ReviewAnchorType;
  anchorValue?: string;
}
