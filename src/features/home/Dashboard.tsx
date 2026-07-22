import type { LearningPath, ReaderGroup, ReadingState } from '../../shared/api/readerApi';
import { Icon } from '../../shared/components/Icons';
import type { PostSummary } from '../../shared/types';
import { formatDate } from '../reader/Preview';

interface DashboardProps {
  groups: ReaderGroup[];
  learningPaths: LearningPath[];
  posts: PostSummary[];
  readingStates: Map<string, ReadingState>;
  onBrowse: () => void;
  onOpen: (slug: string) => void;
  onOpenLibrary: () => void;
  onOpenPath: (pathSlug: string) => void;
}

export function Dashboard({ groups, learningPaths, posts, readingStates, onBrowse, onOpen,
  onOpenLibrary, onOpenPath }: DashboardProps) {
  const featured = posts.find((post) => post.featured) ?? posts[0];
  const continuing = posts.filter((post) => {
    const progress = readingStates.get(post.slug)?.progressPercent ?? 0;
    return progress > 0 && progress < 100;
  }).sort((left, right) => {
    const leftDate = readingStates.get(left.slug)?.lastReadAt ?? '';
    const rightDate = readingStates.get(right.slug)?.lastReadAt ?? '';
    return rightDate.localeCompare(leftDate);
  });
  const savedCount = [...readingStates.values()].filter((state) =>
    state.isBookmarked).length;
  const finishedCount = [...readingStates.values()].filter((state) =>
    state.progressPercent === 100).length;
  const inProgressCount = [...readingStates.values()].filter((state) =>
    state.progressPercent > 0 && state.progressPercent < 100).length;

  return <section className="dashboard">
    <header className="dashboard-header">
      <div className="dashboard-intro"><span className="eyebrow">YOUR READING ROOM</span>
        <h1>Good ideas,<br />kept within reach.</h1>
        <p>A quiet archive of essays, experiments, and notes worth returning to.</p>
        <button className="secondary dashboard-browse" onClick={onBrowse}>Browse all notes <Icon name="arrow" size={15} /></button></div>
      <dl className="dashboard-overview" aria-label="Archive overview">
        <div><dt>Published</dt><dd>{String(posts.length).padStart(2, '0')}</dd></div>
        <div><dt>In progress</dt><dd>{String(inProgressCount).padStart(2, '0')}</dd></div>
        <div><dt>Collections</dt><dd>{String(groups.length).padStart(2, '0')}</dd></div>
      </dl>
    </header>

    {continuing.length > 0 && <section className="dashboard-section continue-section">
      <div className="section-heading"><div><span className="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h2>Continue reading</h2></div>
        <button onClick={onOpenLibrary}>View library</button></div>
      <div className="continue-grid">{continuing.slice(0, 3).map((post, index) => {
        const progress = readingStates.get(post.slug)?.progressPercent ?? 0;
        return <button className="continue-card" key={post.slug} onClick={() => onOpen(post.slug)}>
          <span className="continue-card-index">{String(index + 1).padStart(2, '0')}</span>
          <span className="continue-card-copy"><strong>{post.title}</strong>
            <span>{progress}% read</span><i><b style={{ width: `${progress}%` }} /></i></span></button>;
      })}</div>
    </section>}

    {learningPaths.length > 0 && <section className="dashboard-section path-dashboard-section">
      <div className="section-heading"><div><span className="eyebrow">CURATED CURRICULA</span>
        <h2>Learning paths</h2></div></div>
      <div className="path-card-grid">{learningPaths.map((path, index) =>
        <button className="path-card" key={path.pathId} onClick={() => onOpenPath(path.slug)}>
          <span className="path-card-index">{String(index + 1).padStart(2, '0')}</span>
          <strong>{path.title}</strong><p>{path.description}</p>
          <span className="path-card-progress"><i style={{ width: `${path.progressPercent}%` }} /></span>
          <small>{path.completedLessons}/{path.totalLessons} complete · {path.progressPercent}%</small>
        </button>)}</div>
    </section>}

    {featured && <section className="dashboard-section featured-section">
      <div className="section-heading"><div><span className="eyebrow">EDITOR’S PICK</span><h2>Featured fieldnote</h2></div></div>
      <article className="featured-card">
        <div className="featured-card-index"><span>01</span><small>FEATURED<br />FIELDNOTE</small></div>
        <div className="featured-card-copy"><div className="meta"><span>{formatDate(featured.date)}</span><i /><span>{featured.readingTime} min read</span></div>
          <h3>{featured.title}</h3><p>{featured.description}</p>
          <button className="primary" onClick={() => onOpen(featured.slug)}>Preview note <Icon name="arrow" size={17} /></button></div>
      </article>
    </section>}

    <section className="dashboard-section dashboard-lower">
      <div className="recent-block"><div className="section-heading"><div><span className="eyebrow">LATEST FROM THE ARCHIVE</span><h2>Recent notes</h2></div></div>
        <div className="recent-list">{posts.slice(0, 4).map((post, index) =>
          <button key={post.slug} onClick={() => onOpen(post.slug)}><span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{post.title}</strong><time>{formatDate(post.date)}</time><Icon name="arrow" size={14} /></button>)}</div></div>
      <aside className="library-summary"><span className="eyebrow">MY LIBRARY</span><h2>Your collection</h2>
        <div className="summary-stats"><div><strong>{savedCount}</strong><span>Bookmarks</span></div><div><strong>{finishedCount}</strong><span>Finished</span></div><div><strong>{groups.length}</strong><span>Groups</span></div></div>
        <button className="secondary" onClick={onOpenLibrary}>Open my library</button></aside>
    </section>
  </section>;
}
