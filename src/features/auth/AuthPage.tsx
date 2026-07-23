import { useState, type FormEvent } from 'react';

import { GitHubIcon, GoogleIcon } from '../../shared/components/Icons';
import { ApiError, authApi } from '../../shared/api/authApi';
import { useAuth } from './AuthContext';

type AuthMode = 'sign-in' | 'sign-up' | 'recovery' | 'update';
type OAuthProvider = 'google' | 'github';

const consentReturnPattern =
  /^\/oauth\/consent\?authorization_id=[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const authCopy: Record<AuthMode, { eyebrow: string; title: string; body: string }> = {
  'sign-in': {
    eyebrow: 'WELCOME BACK',
    title: 'Continue where you left off.',
    body: 'Your saved articles, progress, and learning paths are waiting.',
  },
  'sign-up': {
    eyebrow: 'CREATE YOUR LIBRARY',
    title: 'Make your reading compound.',
    body: 'Keep every useful idea organized and continue on any device.',
  },
  recovery: {
    eyebrow: 'ACCOUNT RECOVERY',
    title: 'Reset your password.',
    body: 'Enter your email and we’ll send recovery instructions if the account exists.',
  },
  update: {
    eyebrow: 'SECURE YOUR ACCOUNT',
    title: 'Choose a new password.',
    body: 'Use at least eight characters and a password you have not used elsewhere.',
  },
};

function AuthBrand() {
  return (
    <a className="auth-brand" href="/" aria-label="Return to Blog Vault">
      <span className="auth-brand-mark" aria-hidden="true">B</span>
      <span>BLOG VAULT</span>
    </a>
  );
}

export function AuthPage() {
  const { status, user, signIn, signUp, startOAuth } = useAuth();
  const searchParameters = new URLSearchParams(window.location.search);
  const requestedReturn = searchParameters.get('returnTo') ?? '/';
  const returnTo = consentReturnPattern.test(requestedReturn) ? requestedReturn : '/';
  const isConnectorFlow = returnTo.startsWith('/oauth/consent?');
  const [mode, setMode] = useState<AuthMode>(() =>
    searchParameters.get('mode') === 'update' ? 'update' :
      searchParameters.get('mode') === 'sign-up' ? 'sign-up' : 'sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();

  if (status === 'bootstrapping') {
    return (
      <main className="auth-shell auth-loading">
        <AuthBrand />
        <span className="auth-loading-indicator" />
        <p>Restoring your library…</p>
      </main>
    );
  }

  if (user && mode !== 'update') {
    return (
      <main className="auth-shell auth-state-shell">
        <section className="auth-card auth-state-card">
          <AuthBrand />
          <span className="auth-state-icon" aria-hidden="true">✓</span>
          <span className="eyebrow">SESSION RESTORED</span>
          <h1>{isConnectorFlow ? 'Continue connecting.' : 'You’re already signed in.'}</h1>
          <p>{isConnectorFlow ?
            'Review the requesting app before granting access to your vault.' :
            'Your reading state can follow you across devices.'}</p>
          <a className="auth-primary-link" href={isConnectorFlow ? returnTo : '/account'}>
            {isConnectorFlow ? 'Review connector access' : 'Open your account'}
          </a>
          <a className="auth-secondary-link" href="/">Return to the library</a>
        </section>
      </main>
    );
  }

  const copy = authCopy[mode];

  const changeMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError(undefined);
    setMessage(undefined);
    setPassword('');
  };

  const finishAuthentication = async () => {
    window.location.assign(returnTo);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(undefined); setMessage(undefined);
    try {
      if (mode === 'recovery') {
        setMessage((await authApi.requestPasswordReset(email)).message);
        return;
      }
      if (mode === 'update') {
        setMessage((await authApi.updatePassword(password)).message);
        setPassword('');
        return;
      }
      const result = mode === 'sign-up' ?
        await signUp(email, password, displayName, returnTo) :
        await signIn(email, password);
      if (result.verificationRequired) {
        setMessage(result.message ?? 'Check your email to verify the account.');
        return;
      }
      await finishAuthentication();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Authentication could not be completed.');
    } finally { setBusy(false); }
  };

  const startProvider = async (provider: OAuthProvider) => {
    setBusy(true);
    setError(undefined);
    try {
      await startOAuth(provider, returnTo);
    } catch (caught) {
      setError(
        caught instanceof ApiError ?
          caught.message :
          `Could not continue with ${provider === 'google' ? 'Google' : 'GitHub'}.`,
      );
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <div className="auth-layout">
        <aside className="auth-story">
          <AuthBrand />
          <div className="auth-story-copy">
            <span className="eyebrow">A READING SYSTEM, NOT A FEED</span>
            <h2>Keep the thread.<br />Build real understanding.</h2>
            <p>
              Blog Vault turns individual articles into an organized library
              you can return to, build on, and finish.
            </p>
            <ul className="auth-benefits">
              <li>
                <span>01</span>
                <div><strong>Resume anywhere</strong><small>Sync article and learning-path progress.</small></div>
              </li>
              <li>
                <span>02</span>
                <div><strong>Keep the useful parts</strong><small>Carry bookmarks, favorites, and groups across devices.</small></div>
              </li>
              <li>
                <span>03</span>
                <div><strong>Control every session</strong><small>Review and revoke signed-in devices from your account.</small></div>
              </li>
            </ul>
          </div>
          <p className="auth-story-note">
            Every article, learning path, review, and reading preference stays
            inside your signed-in vault.
          </p>
        </aside>

        <section className="auth-card auth-form-card">
          <div className="auth-mobile-brand"><AuthBrand /></div>
          {(mode === 'sign-in' || mode === 'sign-up') && (
            <div className="auth-mode-switch" aria-label="Authentication mode">
              <button className={mode === 'sign-in' ? 'active' : ''}
                aria-pressed={mode === 'sign-in'}
                onClick={() => changeMode('sign-in')}>Sign in</button>
              <button className={mode === 'sign-up' ? 'active' : ''}
                aria-pressed={mode === 'sign-up'}
                onClick={() => changeMode('sign-up')}>Create account</button>
            </div>
          )}

          <header className="auth-heading">
            <span className="eyebrow">{copy.eyebrow}</span>
            <h1>{copy.title}</h1>
            <p>{copy.body}</p>
          </header>

          {mode !== 'recovery' && mode !== 'update' && (
            <>
              <div className="oauth-grid">
                <button disabled={busy} onClick={() => void startProvider('google')}>
                  <GoogleIcon /><span>Continue with Google</span>
                </button>
                <button disabled={busy} onClick={() => void startProvider('github')}>
                  <GitHubIcon /><span>Continue with GitHub</span>
                </button>
              </div>
              <div className="auth-divider"><span>or continue with email</span></div>
            </>
          )}

          <form onSubmit={(event) => void submit(event)}>
            {mode === 'sign-up' && (
              <div className="auth-field">
                <label htmlFor="auth-name">Name <span>Optional</span></label>
                <input id="auth-name" value={displayName} maxLength={80}
                  autoComplete="name" placeholder="How should we address you?"
                  onChange={(event) => setDisplayName(event.target.value)} />
              </div>
            )}
            {mode !== 'update' && (
              <div className="auth-field">
                <label htmlFor="auth-email">Email address</label>
                <input id="auth-email" type="email" required value={email}
                  autoComplete="email" inputMode="email" placeholder="you@example.com"
                  onChange={(event) => setEmail(event.target.value)} />
              </div>
            )}
            {mode !== 'recovery' && (
              <div className="auth-field">
                <div className="auth-label-row">
                  <label htmlFor="auth-password">
                    {mode === 'update' ? 'New password' : 'Password'}
                  </label>
                  {mode === 'sign-in' && (
                    <button type="button" onClick={() => changeMode('recovery')}>
                      Forgot password?
                    </button>
                  )}
                </div>
                <input id="auth-password" type="password" required
                  minLength={mode === 'sign-in' ? 1 : 8} value={password}
                  autoComplete={mode === 'sign-up' || mode === 'update' ?
                    'new-password' : 'current-password'}
                  placeholder={mode === 'sign-in' ? 'Your password' : 'At least 8 characters'}
                  onChange={(event) => setPassword(event.target.value)} />
              </div>
            )}
            {error && <p className="auth-error" role="alert">{error}</p>}
            {message && <p className="auth-message" role="status">{message}</p>}
            <button className="auth-submit" disabled={busy} type="submit">
              {busy ? <><span className="auth-button-spinner" />Please wait</> :
                mode === 'sign-up' ? 'Create my account' :
                  mode === 'recovery' ? 'Send recovery email' :
                    mode === 'update' ? 'Update password' : 'Continue to my library'}
            </button>
          </form>

          <footer className="auth-footer">
            {mode === 'sign-in' ? (
              <p>New to Blog Vault? <button onClick={() => changeMode('sign-up')}>Create an account</button></p>
            ) : mode === 'sign-up' ? (
              <p>Already have an account? <button onClick={() => changeMode('sign-in')}>Sign in</button></p>
            ) : (
              <button className="auth-back" onClick={() => changeMode('sign-in')}>
                ← Back to sign in
              </button>
            )}
            <span>Your vault is available only after authentication.</span>
          </footer>
          <p className="auth-security-note">
            Protected by Supabase Auth. Blog Vault never stores your password.
          </p>
        </section>
      </div>
    </main>
  );
}
