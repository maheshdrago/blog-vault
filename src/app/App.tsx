import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Dashboard } from '../features/home/Dashboard';
import { Library, type LibraryFilter, type LibraryMode } from '../features/library/Library';
import { Preview } from '../features/reader/Preview';
import { Reader } from '../features/reader/Reader';
import { CommandPalette } from '../features/search/CommandPalette';
import { blogApi } from '../shared/api/blogApi';
import { getReaderId, readerApi, type LearningPath, type ReaderGroup, type ReaderPreferences,
  type ReadingState } from '../shared/api/readerApi';
import { Icon } from '../shared/components/Icons';
import { SyncStatus, type SyncState } from '../shared/components/SyncStatus';
import type { BlogPost, PostSummary, SortOrder, Theme } from '../shared/types';

export function App() {
  const [posts, setPosts] = useState<PostSummary[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [selectedPost, setSelectedPost] = useState<BlogPost | null>(null);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortOrder>('newest');
  const [isLibraryOpen, setLibraryOpen] = useState(false);
  const [isCommandOpen, setCommandOpen] = useState(false);
  const [libraryMode, setLibraryMode] = useState<LibraryMode>('archive');
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>('all');
  const [isReaderOpen, setReaderOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(() =>
    (localStorage.getItem('theme') as Theme) || 'dark');
  const [saved, setSaved] = useState<Set<string>>(() =>
    new Set(JSON.parse(localStorage.getItem('savedPosts') || '[]') as string[]));
  const [readingStates, setReadingStates] = useState<Map<string, ReadingState>>(new Map());
  const [groups, setGroups] = useState<ReaderGroup[]>([]);
  const [learningPaths, setLearningPaths] = useState<LearningPath[]>([]);
  const [activePathSlug, setActivePathSlug] = useState<string | undefined>(() =>
    localStorage.getItem('activeLearningPath') ?? undefined);
  const [readerId] = useState(getReaderId);
  const [preferences, setPreferences] = useState<ReaderPreferences>({
    readerId,
    theme,
    fontScale: 100,
    fontFamily: 'serif',
    lineHeight: 180,
    contentWidth: 760,
    updatedAt: new Date().toISOString(),
  });
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const progressTimer = useRef<number | undefined>(undefined);
  const preferenceTimer = useRef<number | undefined>(undefined);

  const selectPost = useCallback(async (slug: string, openReader = false) => {
    try {
      const post = await blogApi.getPost(slug);
      setSelectedPost(post);
      setLibraryOpen(false);
      setReaderOpen(openReader);
      window.history.replaceState(null, '', `#${slug}${openReader ? '/read' : ''}`);
    } catch {
      setLoadError('The post index could not be loaded. Please refresh and try again.');
    }
  }, []);

  useEffect(() => {
    blogApi.listPosts().then((items) => {
      setPosts(items);
      const [linkedPost, view] = window.location.hash.slice(1).split('/');
      if (linkedPost) void selectPost(linkedPost, view === 'read');
    }).catch(() => setLoadError('The archive could not be loaded. Please refresh and try again.'))
      .finally(() => setLoading(false));
  }, [selectPost]);

  useEffect(() => {
    Promise.all([
      readerApi.getPreferences(readerId),
      readerApi.listReadingStates(readerId),
      readerApi.listGroups(readerId),
      readerApi.listLearningPaths(readerId),
    ]).then(([preferences, states, readerGroups, paths]) => {
      if (preferences.theme !== 'system') setTheme(preferences.theme);
      setPreferences(preferences);
      setSaved(new Set(states.filter((state) => state.isBookmarked).map((state) => state.postSlug)));
      setReadingStates(new Map(states.map((state) => [state.postSlug, state])));
      setGroups(readerGroups);
      setLearningPaths(paths);
      setActivePathSlug((current) => current && paths.some((path) => path.slug === current)
        ? current : paths[0]?.slug);
      setSyncState('saved');
    }).catch(() => {
      // Local storage remains an offline fallback when the free API is asleep.
      setSyncState('offline');
    });
  }, [readerId]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault(); setCommandOpen(true);
      }
      if (event.key === 'Escape') {
        setReaderOpen(false);
        setCommandOpen(false);
        if (selectedPost) {
          window.history.replaceState(null, '', `#${selectedPost.slug}`);
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      window.clearTimeout(progressTimer.current);
      window.clearTimeout(preferenceTimer.current);
    };
  }, [selectedPost]);

  const visiblePosts = useMemo(() => {
    const needle = query.toLowerCase();
    return posts.filter((post) => {
      const state = readingStates.get(post.slug);
      const matchesQuery = [post.title, post.description, ...post.tags]
        .join(' ').toLowerCase().includes(needle);
      if (!matchesQuery || libraryMode === 'archive') return matchesQuery;
      if (libraryFilter === 'bookmarked') return state?.isBookmarked ?? false;
      if (libraryFilter === 'favorites') return state?.isFavorite ?? false;
      if (libraryFilter === 'progress') return Boolean(state && state.progressPercent > 0 && state.progressPercent < 100);
      if (libraryFilter === 'completed') return state?.progressPercent === 100;
      if (libraryFilter.startsWith('group:')) return state?.groupId === libraryFilter.slice(6);
      return Boolean(state && (state.isBookmarked || state.isFavorite ||
        state.progressPercent > 0 || state.groupId));
    })
      .sort((a, b) => sort === 'oldest' ? a.date.localeCompare(b.date) :
        sort === 'title' ? a.title.localeCompare(b.title) : b.date.localeCompare(a.date));
  }, [libraryFilter, libraryMode, posts, query, readingStates, sort]);

  const selectedIndex = posts.findIndex((post) => post.slug === selectedPost?.slug);
  const selectedState = selectedPost ? readingStates.get(selectedPost.slug) : undefined;
  const activeLearningPath = learningPaths.find((path) => path.slug === activePathSlug);
  const pathLessons = activeLearningPath?.sections.flatMap((section) => section.lessons) ?? [];
  const pathLessonIndex = pathLessons.findIndex(
    (lesson) => lesson.article.slug === selectedPost?.slug,
  );

  const updatePostState = (slug: string, patch: Partial<ReadingState>) => {
    setReadingStates((current) => {
      const existing = current.get(slug);
      const nextState: ReadingState = {
        readerId,
        postSlug: slug,
        isFavorite: false,
        isBookmarked: false,
        progressPercent: 0,
        groupId: null,
        lastReadAt: null,
        updatedAt: new Date().toISOString(),
        ...existing,
        ...patch,
      };
      const next = new Map(current).set(slug, nextState);
      void readerApi.updateReadingState(readerId, slug, {
        isBookmarked: nextState.isBookmarked,
        isFavorite: nextState.isFavorite,
        progressPercent: nextState.progressPercent,
        groupId: nextState.groupId,
      }).then(async () => {
        setLearningPaths(await readerApi.listLearningPaths(readerId));
        setSyncState('saved');
      }).catch(() => setSyncState('offline'));
      setSyncState('saving');
      return next;
    });
  };

  const toggleSaved = () => {
    if (!selectedPost) return;
    const next = new Set(saved);
    next.has(selectedPost.slug) ? next.delete(selectedPost.slug) : next.add(selectedPost.slug);
    setSaved(next);
    localStorage.setItem('savedPosts', JSON.stringify([...next]));
    updatePostState(selectedPost.slug, { isBookmarked: next.has(selectedPost.slug) });
  };

  const toggleFavorite = () => {
    if (selectedPost) updatePostState(selectedPost.slug, {
      isFavorite: !selectedState?.isFavorite,
    });
  };

  const moveToGroup = (groupId: string | null) => {
    if (selectedPost) updatePostState(selectedPost.slug, { groupId });
  };

  const saveProgress = (progress: number) => {
    if (!selectedPost) return;
    window.clearTimeout(progressTimer.current);
    progressTimer.current = window.setTimeout(() => {
      const normalized = progress >= 96 ? 100 : Math.max(progress, selectedState?.progressPercent ?? 0);
      updatePostState(selectedPost.slug, { progressPercent: normalized });
    }, 700);
  };

  const createGroup = async (name: string, color: string) => {
    setSyncState('saving');
    const group = await readerApi.createGroup(readerId, name, color);
    setGroups((current) => [...current, group]);
    setLibraryFilter(`group:${group.groupId}`);
    setSyncState('saved');
  };

  const deleteGroup = async (groupId: string) => {
    setSyncState('saving');
    await readerApi.deleteGroup(readerId, groupId);
    setGroups((current) => current.filter((group) => group.groupId !== groupId));
    setReadingStates((current) => new Map([...current].map(([slug, state]) =>
      [slug, state.groupId === groupId ? { ...state, groupId: null } : state])));
    if (libraryFilter === `group:${groupId}`) setLibraryFilter('all');
    setSyncState('saved');
  };

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    updatePreferences({ ...preferences, theme: nextTheme });
  };

  const updatePreferences = (next: ReaderPreferences) => {
    setPreferences(next);
    if (next.theme !== 'system') setTheme(next.theme);
    setSyncState('saving');
    window.clearTimeout(preferenceTimer.current);
    preferenceTimer.current = window.setTimeout(() => {
      void readerApi.updatePreferences(readerId, next)
        .then((savedPreferences) => {
          setPreferences(savedPreferences);
          setSyncState('saved');
        })
        .catch(() => setSyncState('offline'));
    }, 400);
  };

  const openLibrary = (filter: LibraryFilter = 'all') => {
    setLibraryMode('library'); setLibraryFilter(filter); setLibraryOpen(true);
  };

  const selectLearningPath = useCallback((slug: string) => {
    setActivePathSlug(slug);
    localStorage.setItem('activeLearningPath', slug);
  }, []);

  const openLearningPath = () => {
    setLibraryMode('paths');
    setLibraryOpen(true);
  };

  const goHome = () => {
    setSelectedPost(null); setReaderOpen(false); setLibraryOpen(false);
    window.history.replaceState(null, '', window.location.pathname);
  };

  return <>
    <div className="mobile-bar">
      <button className="icon-button" onClick={() => setLibraryOpen(true)} aria-label="Open posts"><Icon name="menu" /></button>
      <button className="mobile-title" onClick={goHome}>Fieldnotes</button>
      <button className="icon-button" onClick={() => setCommandOpen(true)} aria-label="Search"><Icon name="search" /></button>
    </div>
    <button className={`drawer-backdrop ${isLibraryOpen ? 'visible' : ''}`}
      onClick={() => setLibraryOpen(false)} aria-label="Close post drawer" />
    <main className="app-shell">
      <aside className="rail"><div className="brand-mark"><Icon name="logo" size={25} /></div>
        <nav aria-label="Primary"><button className={`rail-button ${libraryMode === 'archive' && !selectedPost ? 'active' : ''}`}
          onClick={() => { setLibraryMode('archive'); goHome(); }} aria-label="Home"><Icon name="doc" /></button>
          <button className={`rail-button ${libraryMode === 'library' ? 'active' : ''}`}
            onClick={() => { setLibraryMode('library'); setLibraryOpen(true); }}
            aria-label="My library"><Icon name="folder" /></button>
          <button className={`rail-button ${libraryMode === 'paths' ? 'active' : ''}`}
            onClick={openLearningPath} aria-label="Learning paths"><Icon name="logo" /></button>
          <button className="rail-button" onClick={toggleTheme}
            aria-label="Toggle color theme"><Icon name={theme === 'dark' ? 'moon' : 'sun'} /></button></nav>
        <SyncStatus state={syncState} /><a className="avatar" href="/review"
          aria-label="Open private review workspace">M</a></aside>
      <Library filter={libraryFilter} groups={groups} isOpen={isLibraryOpen}
        paths={learningPaths} activePathSlug={activePathSlug}
        mode={libraryMode} posts={visiblePosts} query={query} readingStates={readingStates}
        selectedSlug={selectedPost?.slug} sort={sort} onClose={() => setLibraryOpen(false)}
        onCreateGroup={createGroup} onDeleteGroup={deleteGroup} onFilterChange={setLibraryFilter}
        onModeChange={setLibraryMode} onQueryChange={setQuery}
        onOpenLesson={(pathSlug, articleSlug) => {
          selectLearningPath(pathSlug); void selectPost(articleSlug);
        }} onSelectPath={selectLearningPath}
        onSelect={(slug) => void selectPost(slug)} onSortChange={setSort} />
      {selectedPost ? <Preview post={selectedPost} error={loadError} isLoading={isLoading}
        groups={groups} groupId={selectedState?.groupId ?? null}
        isFavorite={selectedState?.isFavorite ?? false}
        isSaved={selectedPost ? saved.has(selectedPost.slug) : false}
        onGroupChange={moveToGroup} onRead={() => {
          setReaderOpen(true);
          window.history.replaceState(null, '', `#${selectedPost.slug}/read`);
        }}
        onToggleFavorite={toggleFavorite} onToggleSaved={toggleSaved} /> :
        <Dashboard groups={groups} learningPaths={learningPaths} posts={posts} readingStates={readingStates}
          onBrowse={() => { setLibraryMode('archive'); setLibraryOpen(true); }}
          onOpen={(slug) => void selectPost(slug)} onOpenLibrary={() => openLibrary()}
          onOpenPath={(slug) => { selectLearningPath(slug); openLearningPath(); }} />}
    </main>
    <Reader groups={groups} groupId={selectedState?.groupId ?? null}
      initialProgress={selectedState?.progressPercent ?? 0}
      isFavorite={selectedState?.isFavorite ?? false} isOpen={isReaderOpen}
      isSaved={selectedPost ? saved.has(selectedPost.slug) : false}
      post={selectedPost} preferences={preferences} theme={theme}
      pathTitle={pathLessonIndex >= 0 ? activeLearningPath?.title : undefined}
      previous={pathLessonIndex >= 0 ? pathLessons[pathLessonIndex - 1]?.article :
        posts[selectedIndex - 1]} next={(() => {
        const nextLesson = pathLessonIndex >= 0 ? pathLessons[pathLessonIndex + 1] : undefined;
        return nextLesson && !nextLesson.isLocked ? nextLesson.article :
          pathLessonIndex >= 0 ? undefined : posts[selectedIndex + 1];
      })()}
      onClose={() => {
        setReaderOpen(false);
        if (selectedPost) window.history.replaceState(null, '', `#${selectedPost.slug}`);
      }} onGroupChange={moveToGroup}
      onNavigate={(slug) => void selectPost(slug, true)} onPreferencesChange={updatePreferences}
      onProgress={saveProgress}
      onToggleFavorite={toggleFavorite} onToggleSaved={toggleSaved} />
    <CommandPalette groups={groups} isOpen={isCommandOpen} posts={posts}
      onClose={() => setCommandOpen(false)} onOpenGroup={(groupId) => {
        setCommandOpen(false); openLibrary(`group:${groupId}`);
      }} onOpenLibrary={() => { setCommandOpen(false); openLibrary(); }}
      onOpenPost={(slug) => { setCommandOpen(false); void selectPost(slug); }}
      onToggleTheme={() => { toggleTheme(); setCommandOpen(false); }} />
  </>;
}
