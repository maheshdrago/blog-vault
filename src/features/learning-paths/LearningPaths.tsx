import { useEffect, useMemo, useState } from 'react';

import type { LearningPath } from '../../shared/api/readerApi';

interface LearningPathsProps {
  activePathSlug?: string;
  paths: LearningPath[];
  selectedPostSlug?: string;
  onOpenLesson: (pathSlug: string, articleSlug: string) => void;
  onSelectPath: (pathSlug: string) => void;
}

const SECTION_ICONS: Record<string, string> = {
  book: '◇', core: '▣', patterns: '⌘', technology: 'ϟ', advanced: '◉', compass: '⌾',
};

export function LearningPaths({ activePathSlug, paths, selectedPostSlug,
  onOpenLesson, onSelectPath }: LearningPathsProps) {
  const activePath = paths.find((path) => path.slug === activePathSlug) ?? paths[0];
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (activePath && activePath.slug !== activePathSlug) onSelectPath(activePath.slug);
  }, [activePath, activePathSlug, onSelectPath]);

  const lessonCount = useMemo(() => activePath?.sections.reduce(
    (total, section) => total + section.lessons.length, 0,
  ) ?? 0, [activePath]);

  if (!activePath) return <div className="path-empty"><strong>No learning paths yet.</strong>
    <span>Create one through MCP, then organize articles into categories.</span></div>;

  const toggleSection = (sectionId: string) => setCollapsed((current) => {
    const next = new Set(current);
    next.has(sectionId) ? next.delete(sectionId) : next.add(sectionId);
    return next;
  });

  return <div className="learning-paths">
    <header className="path-summary">
      {paths.length > 1 ? <select value={activePath.slug}
        onChange={(event) => onSelectPath(event.target.value)} aria-label="Learning path">
        {paths.map((path) => <option key={path.pathId} value={path.slug}>{path.title}</option>)}
      </select> : <h2>{activePath.title}</h2>}
      <p>{activePath.description}</p>
      <div className="path-progress-meta"><span>{activePath.completedLessons} of {lessonCount} complete</span>
        <strong>{activePath.progressPercent}%</strong></div>
      <div className="path-progress"><i style={{ width: `${activePath.progressPercent}%` }} /></div>
    </header>
    <div className="path-section-list">{activePath.sections.map((section) => {
      const isCollapsed = collapsed.has(section.sectionId);
      return <section className="path-section" key={section.sectionId}>
        <button className="path-section-heading" onClick={() => toggleSection(section.sectionId)}
          aria-expanded={!isCollapsed}>
          <span className="path-section-icon">{SECTION_ICONS[section.icon] ?? '◇'}</span>
          <strong>{section.title}</strong><span className="path-chevron">⌄</span>
        </button>
        {!isCollapsed && <div className="path-lessons">{section.lessons.map((lesson) =>
          <button key={lesson.lessonId} disabled={lesson.isLocked}
            className={selectedPostSlug === lesson.article.slug ? 'active' : ''}
            onClick={() => onOpenLesson(activePath.slug, lesson.article.slug)}>
            <span className={`lesson-state ${lesson.isCompleted ? 'complete' : ''}`}>
              {lesson.isCompleted ? '✓' : lesson.progressPercent > 0 ? '◐' : '○'}</span>
            <span className="lesson-title">{lesson.article.title}</span>
            {lesson.isLocked && <span className="lesson-lock" aria-label="Complete prior required lessons">▣</span>}
          </button>)}</div>}
      </section>;
    })}</div>
  </div>;
}
