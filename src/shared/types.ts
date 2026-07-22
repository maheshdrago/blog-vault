export interface BlogPost {
  title: string;
  slug: string;
  date: string;
  description: string;
  tags: string[];
  cover: string;
  experience?: string;
  featured: boolean;
  readingTime: number;
  html: string;
}

export type PostSummary = Omit<BlogPost, 'html'>;
export type SortOrder = 'newest' | 'oldest' | 'title';
export type Theme = 'dark' | 'light';
