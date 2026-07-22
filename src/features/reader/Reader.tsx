import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

import { InteractiveArticle } from './InteractiveArticle';
import { formatDate } from './Preview';
import type { ReaderGroup, ReaderPreferences } from '../../shared/api/readerApi';
import { Icon } from '../../shared/components/Icons';
import type { BlogPost, PostSummary, Theme } from '../../shared/types';

interface ReaderProps {
  initialProgress: number;
  isOpen: boolean;
  isFavorite: boolean;
  isSaved: boolean;
  groups: ReaderGroup[];
  groupId: string | null;
  preferences: ReaderPreferences;
  pathTitle?: string;
  next?: PostSummary;
  post: BlogPost | null;
  previous?: PostSummary;
  theme: Theme;
  onClose: () => void;
  onGroupChange: (groupId: string | null) => void;
  onNavigate: (slug: string) => void;
  onToggleSaved: () => void;
  onToggleFavorite: () => void;
  onProgress: (progress: number) => void;
  onPreferencesChange: (preferences: ReaderPreferences) => void;
}

type ReaderMode = 'read' | 'interactive';

export function Reader(props: ReaderProps) {
  const { groupId, groups, initialProgress, isFavorite, isOpen, isSaved, next, pathTitle, post, preferences, theme,
    previous, onClose, onGroupChange, onNavigate, onPreferencesChange, onProgress, onToggleFavorite,
    onToggleSaved } = props;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [progress, setProgress] = useState(0);
  const [activeHeading, setActiveHeading] = useState('');
  const [showAppearance, setShowAppearance] = useState(false);
  const [readerMode, setReaderMode] = useState<ReaderMode>('read');

  const article = useMemo(() => {
    if (!post) return { html: '', headings: [] as { id: string; text: string; level: number }[] };
    const documentNode = new DOMParser().parseFromString(post.html, 'text/html');
    const headings = [...documentNode.querySelectorAll('h2, h3')].map((heading, index) => {
      const id = `${heading.textContent?.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section'}-${index}`;
      heading.id = id;
      return { id, text: heading.textContent ?? 'Section', level: Number(heading.tagName[1]) };
    });
    return { html: documentNode.body.innerHTML, headings };
  }, [post]);

  useEffect(() => {
    setReaderMode('read');
    setShowAppearance(false);
  }, [post?.experience, post?.slug]);

  useEffect(() => {
    if (!isOpen) return;
    setProgress(initialProgress);
    const frame = window.requestAnimationFrame(() => {
      const element = scrollRef.current;
      if (!element) return;
      const available = element.scrollHeight - element.clientHeight;
      element.scrollTo({ top: available * (initialProgress / 100) });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [initialProgress, isOpen, post?.slug]);

  const updateProgress = () => {
    const element = scrollRef.current;
    if (!element) return;
    const available = element.scrollHeight - element.clientHeight;
    const nextProgress = available > 0 ?
      Math.min(100, (element.scrollTop / available) * 100) : 100;
    setProgress(nextProgress);
    onProgress(Math.round(nextProgress));
    const headings = [...element.querySelectorAll<HTMLElement>('[data-article-content] h2, [data-article-content] h3')];
    const current = headings.filter((heading) => heading.offsetTop <= element.scrollTop + 230).at(-1);
    if (current) setActiveHeading(current.id);
  };

  const updateExperienceProgress = (nextProgress: number) => {
    setProgress(nextProgress);
    onProgress(Math.round(nextProgress));
  };

  if (!post) return null;
  const readerStyle = {
    '--reader-width': `${preferences.contentWidth}px`,
    '--reader-scale': preferences.fontScale / 100,
    '--reader-leading': preferences.lineHeight / 100,
    '--reader-font': preferences.fontFamily === 'serif' ? "'Newsreader', Georgia, serif" : "'Manrope', system-ui, sans-serif",
  } as CSSProperties;
  return (
    <section className={`reader ${isOpen ? 'open' : ''}`} aria-hidden={!isOpen}
      style={readerStyle}>
      <div className="reading-progress" style={{ transform: `scaleX(${progress / 100})` }} />
      {post.experience && <div className="reader-view-switcher" role="group"
        aria-label="Article view">
        <button className={readerMode === 'read' ? 'active' : ''}
          onClick={() => { setReaderMode('read'); setShowAppearance(false); }}
          aria-pressed={readerMode === 'read'} title="Calm, accessible reading view">
          Read</button>
        <button className={readerMode === 'interactive' ? 'active' : ''}
          onClick={() => { setReaderMode('interactive'); setShowAppearance(false); }}
          aria-pressed={readerMode === 'interactive'} title="Explore animated explanations">
          Explore</button>
      </div>}
      <aside className="reader-tools">
        <button className="icon-button" onClick={onClose} aria-label="Close reader"><Icon name="close" /></button>
        <span className="reader-line" />
        <button className={`icon-button favorite ${isFavorite ? 'saved' : ''}`}
          onClick={onToggleFavorite} aria-label="Favorite post"><Icon name="heart" /></button>
        <button className={`icon-button save ${isSaved ? 'saved' : ''}`}
          onClick={onToggleSaved} aria-label="Save post"><Icon name="bookmark" /></button>
        <button className={`appearance-button ${showAppearance ? 'active' : ''}`}
          onClick={() => setShowAppearance(!showAppearance)} aria-label="Display settings"
          title="Display settings"><Icon name={theme === 'dark' ? 'moon' : 'sun'} /></button>
        <label className="reader-group-picker" title="Move to group"><Icon name="folder" size={17} />
          <select value={groupId ?? ''} onChange={(event) => onGroupChange(event.target.value || null)}
            aria-label="Move post to group"><option value="">Ungrouped</option>
            {groups.map((group) => <option value={group.groupId} key={group.groupId}>{group.name}</option>)}</select>
        </label>
      </aside>
      {showAppearance && <aside className="appearance-panel" aria-label="Display settings">
        <span>COLOR THEME</span><div className="appearance-options theme-options">
          {(['light', 'dark'] as const).map((nextTheme) => <button key={nextTheme}
            className={theme === nextTheme ? 'active' : ''}
            onClick={() => onPreferencesChange({ ...preferences, theme: nextTheme })}>
            <Icon name={nextTheme === 'light' ? 'sun' : 'moon'} size={14} />
            {nextTheme === 'light' ? 'Light' : 'Dark'}</button>)}</div>
        {readerMode === 'read' ? <>
          <div><span>TEXT SIZE</span><strong>{preferences.fontScale}%</strong></div>
          <input type="range" min="80" max="150" step="5" value={preferences.fontScale}
            onChange={(event) => onPreferencesChange({ ...preferences, fontScale: Number(event.target.value) })} />
          <div><span>LINE HEIGHT</span><strong>{preferences.lineHeight}%</strong></div>
          <input type="range" min="140" max="220" step="10" value={preferences.lineHeight}
            onChange={(event) => onPreferencesChange({ ...preferences, lineHeight: Number(event.target.value) })} />
          <span>TYPEFACE</span><div className="appearance-options">
            <button className={preferences.fontFamily === 'serif' ? 'active' : ''}
              onClick={() => onPreferencesChange({ ...preferences, fontFamily: 'serif' })}>Serif</button>
            <button className={preferences.fontFamily === 'sans' ? 'active' : ''}
              onClick={() => onPreferencesChange({ ...preferences, fontFamily: 'sans' })}>Sans</button></div>
          <span>PAGE WIDTH</span><div className="appearance-options">
            {[640, 760, 880].map((width) => <button key={width}
              className={preferences.contentWidth === width ? 'active' : ''}
              onClick={() => onPreferencesChange({ ...preferences, contentWidth: width })}>{width === 640 ? 'Narrow' : width === 760 ? 'Default' : 'Wide'}</button>)}</div>
        </> : <p className="appearance-note">Explore keeps each diagram's authored typography.
          Its colors still follow the theme selected above.</p>}
      </aside>}
      {readerMode === 'interactive' && post.experience && isOpen ?
        <InteractiveArticle initialProgress={initialProgress} path={post.experience}
          theme={theme} title={post.title} onProgress={updateExperienceProgress}
          onUseReadMode={() => setReaderMode('read')} /> :
      <div className="reader-scroll" ref={scrollRef} onScroll={updateProgress}><article className="article">
        <div className="article-kicker"><span>FIELDNOTE · {(post.tags[0] ?? 'NOTE').toUpperCase()}</span><time>{formatDate(post.date)}</time></div>
        <h1>{post.title}</h1><p className="article-dek">{post.description}</p>
        <div data-article-content dangerouslySetInnerHTML={{ __html: article.html }} />
      </article>{article.headings.length > 0 && <nav className="article-toc" aria-label="Table of contents">
        <span>IN THIS NOTE</span>{article.headings.map((heading) => <button key={heading.id}
          className={`${heading.level === 3 ? 'nested' : ''} ${activeHeading === heading.id ? 'active' : ''}`}
          onClick={() => scrollRef.current?.querySelector(`#${heading.id}`)?.scrollIntoView({ behavior: 'smooth' })}>{heading.text}</button>)}</nav>}</div>}
      <footer className="reader-footer">
        <button disabled={!previous} onClick={() => previous && onNavigate(previous.slug)}>← <span>{previous?.title ?? 'Previous'}</span></button>
        <span>{pathTitle ? `${pathTitle} · ` : ''}{readerMode === 'interactive' ? 'Explore' : 'Read'} · {Math.round(progress)}% · {post.readingTime} min read</span>
        <button disabled={!next} onClick={() => next && onNavigate(next.slug)}><span>{next?.title ?? 'Next'}</span> →</button>
      </footer>
    </section>
  );
}
