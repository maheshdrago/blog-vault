import { useState, type FormEvent } from 'react';

import type { LearningPath, ReaderGroup, ReadingState } from '../../shared/api/readerApi';
import { Icon } from '../../shared/components/Icons';
import { DEFAULT_GROUP_COLOR } from '../../shared/designTokens';
import type { PostSummary, SortOrder } from '../../shared/types';
import { LearningPaths } from '../learning-paths/LearningPaths';

export type LibraryFilter = 'all' | 'bookmarked' | 'favorites' | 'progress' |
  'completed' | `group:${string}`;
export type LibraryMode = 'archive' | 'paths' | 'library';

interface LibraryProps {
  isOpen: boolean;
  groups: ReaderGroup[];
  mode: LibraryMode;
  paths: LearningPath[];
  activePathSlug?: string;
  filter: LibraryFilter;
  posts: PostSummary[];
  readingStates: Map<string, ReadingState>;
  query: string;
  selectedSlug?: string;
  sort: SortOrder;
  onQueryChange: (query: string) => void;
  onClose: () => void;
  onCreateGroup: (name: string, color: string) => Promise<void>;
  onDeleteGroup: (groupId: string) => Promise<void>;
  onFilterChange: (filter: LibraryFilter) => void;
  onModeChange: (mode: LibraryMode) => void;
  onOpenLesson: (pathSlug: string, articleSlug: string) => void;
  onSelectPath: (pathSlug: string) => void;
  onSelect: (slug: string) => void;
  onSortChange: (sort: SortOrder) => void;
}

function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })
    .format(new Date(`${value}T12:00:00`));
}

export function Library(props: LibraryProps) {
  const { activePathSlug, filter, groups, isOpen, mode, paths, posts, query, readingStates, selectedSlug,
    sort, onClose, onCreateGroup, onDeleteGroup, onFilterChange, onModeChange,
    onOpenLesson, onQueryChange, onSelect, onSelectPath, onSortChange } = props;
  const [isCreatingGroup, setCreatingGroup] = useState(false);
  const [groupName, setGroupName] = useState('');

  const submitGroup = async (event: FormEvent) => {
    event.preventDefault();
    if (!groupName.trim()) return;
    await onCreateGroup(groupName.trim(), DEFAULT_GROUP_COLOR);
    setGroupName('');
    setCreatingGroup(false);
  };
  return (
    <section className={`library ${isOpen ? 'mobile-open' : ''}`}>
      <header className="library-header">
        <div><span className="eyebrow">PERSONAL ARCHIVE</span><h1>Posts</h1></div>
        <div className="library-header-actions"><span className="post-count">{posts.length} notes</span>
          <button className="icon-button library-close" onClick={onClose}
            aria-label="Close posts"><Icon name="close" size={18} /></button></div>
      </header>
      <div className="library-tabs" role="tablist" aria-label="Post collection">
        <button className={mode === 'archive' ? 'active' : ''}
          onClick={() => onModeChange('archive')} role="tab">Archive</button>
        <button className={mode === 'paths' ? 'active' : ''}
          onClick={() => onModeChange('paths')} role="tab">Paths</button>
        <button className={mode === 'library' ? 'active' : ''}
          onClick={() => onModeChange('library')} role="tab">My library</button>
      </div>
      {mode === 'library' && <div className="collection-nav">
        <button className={filter === 'all' ? 'active' : ''}
          onClick={() => onFilterChange('all')}>All saved</button>
        <button className={filter === 'bookmarked' ? 'active' : ''}
          onClick={() => onFilterChange('bookmarked')}>Bookmarks</button>
        <button className={filter === 'favorites' ? 'active' : ''}
          onClick={() => onFilterChange('favorites')}>Favorites</button>
        <button className={filter === 'progress' ? 'active' : ''}
          onClick={() => onFilterChange('progress')}>Continue</button>
        <button className={filter === 'completed' ? 'active' : ''}
          onClick={() => onFilterChange('completed')}>Finished</button>
      </div>}
      {mode === 'library' && <div className="groups-section">
        <div className="groups-heading"><span>GROUPS</span>
          <button className="mini-icon" onClick={() => setCreatingGroup(!isCreatingGroup)}
            aria-label="Create group"><Icon name="plus" size={14} /></button></div>
        {isCreatingGroup && <form className="group-form" onSubmit={(event) => void submitGroup(event)}>
          <input value={groupName} onChange={(event) => setGroupName(event.target.value)}
            maxLength={50} placeholder="Group name" autoFocus />
          <button type="submit">Add</button>
        </form>}
        <div className="group-list">{groups.map((group) =>
          <div className={`group-row ${filter === `group:${group.groupId}` ? 'active' : ''}`}
            key={group.groupId}>
            <button className="group-button" onClick={() => onFilterChange(`group:${group.groupId}`)}>
              <i style={{ background: group.color }} /><span>{group.name}</span>
            </button>
            <button className="group-delete" onClick={() => void onDeleteGroup(group.groupId)}
              aria-label={`Delete ${group.name}`}><Icon name="trash" size={12} /></button>
          </div>)}</div>
      </div>}
      {mode === 'paths' && <LearningPaths paths={paths} activePathSlug={activePathSlug}
        selectedPostSlug={selectedSlug} onOpenLesson={onOpenLesson}
        onSelectPath={onSelectPath} />}
      {mode !== 'paths' && <>
      <label className="search"><Icon name="search" size={17} />
        <input type="search" value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search the archive…" aria-label="Search posts" /><kbd>⌘K</kbd>
      </label>
      <div className="sort-row"><span>Sort by</span>
        <select value={sort}
          onChange={(event) => onSortChange(event.target.value as SortOrder)}
          aria-label="Sort posts">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="title">Title A–Z</option>
        </select>
      </div>
      <div className="post-list">
        {posts.length === 0 ?
          <div className="empty">No notes found.<small>Try another word or topic.</small></div> :
          posts.map((post) => {
            const readingState = readingStates.get(post.slug);
            return (
            <button key={post.slug}
              className={`post-item ${selectedSlug === post.slug ? 'selected' : ''}`}
              onClick={() => onSelect(post.slug)}>
              <span className="post-dot" /><span className="post-item-body">
                <span className="post-item-top"><strong>{post.title}</strong>
                  <time>{formatShortDate(post.date)}</time></span>
                <span>{post.description}</span>
                {readingState && <span className="post-state-row">
                  <span>{readingState.isBookmarked && <Icon name="bookmark" size={11} />}
                    {readingState.isFavorite && <Icon name="heart" size={11} />}</span>
                  {readingState.progressPercent > 0 && <span className="mini-progress">
                    <i style={{ width: `${readingState.progressPercent}%` }} /></span>}
                </span>}
              </span>
            </button>
          )})}
      </div>
      </>}
      <footer className="library-footer">
        <a className="new-post" href="mailto:?subject=New%20blog%20idea">+ &nbsp;Capture an idea</a>
        <span>Supabase-backed archive</span>
      </footer>
    </section>
  );
}
