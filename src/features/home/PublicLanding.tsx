import { useState } from 'react';

import { Icon } from '../../shared/components/Icons';
import type { Theme } from '../../shared/types';

const previewNotes = [
  { title: 'Networking essentials', detail: '12 min · 68% read', active: true },
  { title: 'Designing load balancers', detail: '9 min · Not started' },
  { title: 'Safe database migrations', detail: '14 min · Saved' },
];

export function PublicLanding() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    localStorage.setItem('theme', nextTheme);
  };

  return (
    <main className="public-home">
      <nav className="public-nav" aria-label="Public navigation">
        <a className="public-brand" href="/" aria-label="Blog Vault home">
          <span><Icon name="logo" size={18} /></span>
          <strong>Blog Vault</strong>
        </a>
        <div>
          <button className="public-theme" onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />
          </button>
          <a className="public-sign-in" href="/auth">Sign in</a>
          <a className="public-nav-cta" href="/auth?mode=sign-up">Create your vault</a>
        </div>
      </nav>

      <section className="public-hero">
        <div className="public-hero-copy">
          <span className="eyebrow">YOUR PRIVATE READING DESK</span>
          <h1>Turn good articles into lasting understanding.</h1>
          <p>
            Read deeply, organize ideas into learning paths, and let an AI
            research and prepare new drafts without giving up human review.
          </p>
          <div className="public-hero-actions">
            <a className="public-primary" href="/auth?mode=sign-up">
              Start a private vault <Icon name="arrow" size={16} />
            </a>
            <a className="public-secondary" href="#how-it-works">See how it works</a>
          </div>
          <small>No public feed. No advertising. Your library belongs to your account.</small>
        </div>

        <div className="public-product-window" aria-label="Blog Vault product preview">
          <div className="public-window-bar">
            <span className="window-lights" aria-hidden="true"><i /><i /><i /></span>
            <span>Blog Vault · Reading desk</span>
            <span className="window-status"><i /> Synced</span>
          </div>
          <div className="public-window-body">
            <aside className="public-preview-sidebar">
              <div className="public-preview-title">
                <span>Library</span><small>18 notes</small>
              </div>
              <div className="public-preview-segment">
                <span className="active">Archive</span><span>Paths</span><span>Saved</span>
              </div>
              <div className="public-preview-search">
                <Icon name="search" size={13} /><span>Search your notes</span><kbd>⌘K</kbd>
              </div>
              <div className="public-preview-notes">
                {previewNotes.map((note) => (
                  <article className={note.active ? 'active' : ''} key={note.title}>
                    <i /><div><strong>{note.title}</strong><small>{note.detail}</small></div>
                  </article>
                ))}
              </div>
              <div className="public-preview-path">
                <span>ACTIVE PATH</span><strong>System design foundations</strong>
                <i><b /></i><small>3 of 8 lessons complete</small>
              </div>
            </aside>
            <section className="public-preview-reader">
              <header><span>CORE CONCEPTS · LESSON 01</span><div>
                <Icon name="bookmark" size={15} /><span>8 min left</span>
              </div></header>
              <div className="public-preview-article">
                <span className="eyebrow">NETWORKING</span>
                <h2>What actually happens when services talk?</h2>
                <p>
                  Follow a request across DNS, transport, routing, and the
                  application boundary—then see where latency and failure enter.
                </p>
                <div className="public-request-flow">
                  <span>Client</span><i>→</i><span>DNS</span><i>→</i>
                  <span>Gateway</span><i>→</i><span>Service</span>
                </div>
                <div className="public-preview-callout">
                  <span>01</span>
                  <p><strong>Start with the boundary.</strong>
                    Every network hop changes what can fail and what you can observe.</p>
                </div>
              </div>
              <footer><span><i /> 68% complete</span>
                <span className="public-preview-continue">Continue reading
                  <Icon name="arrow" size={14} /></span></footer>
            </section>
          </div>
        </div>
      </section>

      <section className="public-utility" id="how-it-works">
        <article><span>01</span><Icon name="doc" size={20} />
          <h2>Read without losing the thread</h2>
          <p>Focused reading, bookmarks, progress, preferences, and a useful archive.</p>
        </article>
        <article><span>02</span><Icon name="logo" size={20} />
          <h2>Learn in a deliberate order</h2>
          <p>Curated paths connect fundamentals to advanced topics with clear next steps.</p>
        </article>
        <article><span>03</span><Icon name="folder" size={20} />
          <h2>Research with AI, publish yourself</h2>
          <p>MCP clients prepare sourced drafts. Comments and human approval remain the gate.</p>
        </article>
      </section>

      <footer className="public-footer">
        <span>Blog Vault</span>
        <p>Private by default · Supabase-backed · OAuth-secured MCP</p>
        <a href="/auth">Open your vault</a>
      </footer>
    </main>
  );
}
