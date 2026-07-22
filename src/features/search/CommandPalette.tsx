import { useEffect, useMemo, useRef, useState } from 'react';

import type { ReaderGroup } from '../../shared/api/readerApi';
import { Icon } from '../../shared/components/Icons';
import type { PostSummary } from '../../shared/types';

interface CommandPaletteProps {
  groups: ReaderGroup[];
  isOpen: boolean;
  posts: PostSummary[];
  onClose: () => void;
  onOpenGroup: (groupId: string) => void;
  onOpenLibrary: () => void;
  onOpenPost: (slug: string) => void;
  onToggleTheme: () => void;
}

export function CommandPalette({ groups, isOpen, posts, onClose, onOpenGroup,
  onOpenLibrary, onOpenPost, onToggleTheme }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (isOpen) window.setTimeout(() => inputRef.current?.focus(), 50);
    else setQuery('');
  }, [isOpen]);
  const matches = useMemo(() => posts.filter((post) =>
    [post.title, post.description, ...post.tags].join(' ').toLowerCase()
      .includes(query.toLowerCase())).slice(0, 6), [posts, query]);
  if (!isOpen) return null;
  return <div className="command-backdrop" onMouseDown={onClose}>
    <div className="command-palette" role="dialog" aria-modal="true"
      aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
      <label className="command-search"><Icon name="search" size={19} />
        <input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Search notes or choose an action…" /><kbd>ESC</kbd></label>
      {!query && <div className="command-section"><span>QUICK ACTIONS</span>
        <button onClick={onOpenLibrary}><Icon name="folder" size={17} /><strong>Open my library</strong><small>Bookmarks, favorites, and progress</small></button>
        <button onClick={onToggleTheme}><Icon name="moon" size={17} /><strong>Toggle appearance</strong><small>Switch light and dark mode</small></button></div>}
      {groups.length > 0 && !query && <div className="command-section"><span>GROUPS</span>
        {groups.slice(0, 4).map((group) => <button key={group.groupId}
          onClick={() => onOpenGroup(group.groupId)}><i style={{ background: group.color }} />
          <strong>{group.name}</strong></button>)}</div>}
      <div className="command-section"><span>{query ? 'SEARCH RESULTS' : 'RECENT NOTES'}</span>
        {matches.map((post) => <button key={post.slug} onClick={() => onOpenPost(post.slug)}>
          <Icon name="doc" size={16} /><strong>{post.title}</strong><small>{post.readingTime} min</small></button>)}
        {matches.length === 0 && <p>No notes match “{query}”.</p>}</div>
    </div>
  </div>;
}
