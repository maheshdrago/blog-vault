import type { ReaderGroup } from '../../shared/api/readerApi';
import { Icon } from '../../shared/components/Icons';
import type { BlogPost } from '../../shared/types';

interface PreviewProps {
  error?: string;
  isLoading: boolean;
  isFavorite: boolean;
  isSaved: boolean;
  groups: ReaderGroup[];
  groupId: string | null;
  post: BlogPost | null;
  onRead: () => void;
  onGroupChange: (groupId: string | null) => void;
  onToggleFavorite: () => void;
  onToggleSaved: () => void;
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', {
    month: 'short', day: 'numeric', year: 'numeric',
  }).format(new Date(`${value}T12:00:00`));
}

export function Preview({ error, groupId, groups, isFavorite, isLoading, isSaved,
  post, onGroupChange, onRead, onToggleFavorite, onToggleSaved }: PreviewProps) {
  if (error) {
    return <section className="preview preview-state"><div className="load-error">
      <span className="eyebrow">ARCHIVE UNAVAILABLE</span><h2>We couldn’t open the notes.</h2>
      <p>{error}</p><button className="secondary" onClick={() => window.location.reload()}>Try again</button>
    </div></section>;
  }
  if (isLoading) {
    return <section className="preview preview-loading" aria-label="Loading post">
      <div className="skeleton skeleton-top" />
      <div className="skeleton skeleton-meta" /><div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-copy" />
    </section>;
  }
  if (!post) {
    return <section className="preview preview-state"><div className="load-error">No notes yet.</div></section>;
  }
  return (
    <section className="preview" aria-live="polite">
      <div className="preview-actions"><span className="eyebrow">SELECTED FIELDNOTE</span>
        <div className="post-actions"><button className={`icon-button favorite ${isFavorite ? 'saved' : ''}`}
          onClick={onToggleFavorite} aria-label="Favorite post"><Icon name="heart" /></button>
        <button className={`icon-button save ${isSaved ? 'saved' : ''}`}
          onClick={onToggleSaved} aria-label="Bookmark post"><Icon name="bookmark" /></button></div>
      </div>
      <article className="preview-copy">
        <div className="preview-type"><span>{(post.tags[0] ?? 'fieldnote').toUpperCase()}</span>
          <span>READ / {String(post.readingTime).padStart(2, '0')} MIN</span></div>
        <div className="meta"><span>{formatDate(post.date)}</span><i /><span>{post.tags.length} topics</span></div>
        <h2>{post.title}</h2><p>{post.description}</p>
        <div className="preview-footer">
          <div className="preview-organize"><div className="tag-row">{post.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>
            <label className="group-picker"><Icon name="folder" size={14} />
              <select value={groupId ?? ''} onChange={(event) => onGroupChange(event.target.value || null)}
                aria-label="Move post to group"><option value="">Ungrouped</option>
                {groups.map((group) => <option value={group.groupId} key={group.groupId}>{group.name}</option>)}</select>
            </label></div>
          <button className="primary" onClick={onRead}><span>Enter reading mode</span>
            <Icon name="arrow" size={18} /></button>
        </div>
      </article>
    </section>
  );
}
