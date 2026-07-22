import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
  loadArticleExperience,
} from './articleExperience';
import { resolveArticleThemeTokens } from './articleTheme';
import type { Theme } from '../../shared/types';

interface InteractiveArticleProps {
  initialProgress: number;
  path: string;
  theme: Theme;
  title: string;
  onProgress: (progress: number) => void;
  onUseReadMode: () => void;
}

interface ExperienceMessage {
  progress?: number;
  source?: string;
  type?: string;
}

export function InteractiveArticle({ initialProgress, path, theme, title, onProgress,
  onUseReadMode }: InteractiveArticleProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [documentSource, setDocumentSource] = useState('');
  const [error, setError] = useState<string>();

  const publishTheme = useCallback(() => {
    frameRef.current?.contentWindow?.postMessage({
      source: ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
      type: 'theme',
      theme,
      tokens: resolveArticleThemeTokens(theme),
    }, '*');
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();
    setDocumentSource('');
    setError(undefined);
    void loadArticleExperience(path, controller.signal)
      .then(setDocumentSource)
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(loadError instanceof Error ? loadError.message : 'The interactive article could not be loaded.');
        }
      });
    return () => controller.abort();
  }, [path]);

  useEffect(() => {
    const receiveMessage = (event: MessageEvent<ExperienceMessage>) => {
      if (event.source !== frameRef.current?.contentWindow ||
        event.data?.source !== ARTICLE_EXPERIENCE_MESSAGE_SOURCE) return;
      if (event.data.type === 'ready') {
        frameRef.current?.contentWindow?.postMessage({
          source: ARTICLE_EXPERIENCE_MESSAGE_SOURCE,
          type: 'restore',
          progress: initialProgress,
        }, '*');
        publishTheme();
      }
      if (event.data.type === 'progress' && Number.isFinite(event.data.progress)) {
        onProgress(Math.min(100, Math.max(0, event.data.progress ?? 0)));
      }
    };
    window.addEventListener('message', receiveMessage);
    return () => window.removeEventListener('message', receiveMessage);
  }, [initialProgress, onProgress, publishTheme]);

  useEffect(() => {
    publishTheme();
  }, [documentSource, publishTheme]);

  if (error) {
    return <div className="experience-state"><span className="eyebrow">INTERACTIVE VIEW UNAVAILABLE</span>
      <p>{error}</p><button className="secondary" onClick={onUseReadMode}>Open reading view</button></div>;
  }
  if (!documentSource) {
    return <div className="experience-state"><span className="eyebrow">LOADING INTERACTIVE ARTICLE</span></div>;
  }
  return <div className="experience-pane">
    <iframe ref={frameRef} title={`${title} — interactive article`} srcDoc={documentSource}
      sandbox="allow-scripts" referrerPolicy="no-referrer" />
  </div>;
}
