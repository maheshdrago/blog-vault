import { useEffect, useMemo, useState } from 'react';

import {
  ApiError,
  authApi,
  type OAuthAuthorizationDetails,
} from '../../shared/api/authApi';
import { useAuth } from './AuthContext';

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const scopeLabels: Record<string, string> = {
  openid: 'Confirm your Blog Vault identity',
  email: 'See the email attached to your account',
  profile: 'See your profile name and avatar',
  phone: 'See the phone number attached to your account',
};

function clientHost(uri: string): string | null {
  try {
    return new URL(uri).host;
  } catch {
    return null;
  }
}

export function OAuthConsentPage() {
  const { status, user } = useAuth();
  const authorizationId = useMemo(
    () => new URLSearchParams(window.location.search).get('authorization_id') ?? '',
    [],
  );
  const [details, setDetails] = useState<OAuthAuthorizationDetails>();
  const [error, setError] = useState<string>();
  const [decision, setDecision] = useState<'approve' | 'deny'>();

  useEffect(() => {
    if (!uuidPattern.test(authorizationId)) {
      setError('This authorization request is missing or invalid.');
      return;
    }
    if (status === 'signed-out') {
      const returnTo = `/oauth/consent?authorization_id=${authorizationId}`;
      window.location.assign(`/auth?returnTo=${encodeURIComponent(returnTo)}`);
      return;
    }
    if (status !== 'authenticated') return;
    let active = true;
    void authApi.getOAuthAuthorizationDetails(authorizationId).then((response) => {
      if (!active) return;
      if ('redirectUrl' in response) {
        window.location.assign(response.redirectUrl);
        return;
      }
      setDetails(response);
    }).catch((caught) => {
      if (!active) return;
      setError(caught instanceof ApiError ? caught.message :
        'The authorization request could not be loaded.');
    });
    return () => { active = false; };
  }, [authorizationId, status]);

  const decide = async (nextDecision: 'approve' | 'deny') => {
    setDecision(nextDecision);
    setError(undefined);
    try {
      const response = await authApi.decideOAuthAuthorization(
        authorizationId,
        nextDecision,
      );
      window.location.assign(response.redirectUrl);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message :
        'Your authorization decision could not be completed.');
      setDecision(undefined);
    }
  };

  const scopes = details?.scope.split(/\s+/).filter(Boolean) ?? [];
  const host = details ? clientHost(details.client.uri) : null;
  const clientInitial = details?.client.name.trim().charAt(0).toUpperCase() || 'A';

  return (
    <main className="oauth-consent-shell">
      <header className="oauth-consent-brand">
        <a className="auth-brand" href="/" aria-label="Return to Blog Vault">
          <span className="auth-brand-mark" aria-hidden="true">B</span>
          <span>BLOG VAULT</span>
        </a>
        {user && <span>Signed in as {user.email ?? user.displayName ?? 'reader'}</span>}
      </header>

      <section className="oauth-consent-card" aria-busy={!details && !error}>
        {!details && !error ? (
          <div className="oauth-consent-loading">
            <span className="auth-loading-indicator" />
            <p>{status === 'signed-out' ? 'Taking you to sign in…' :
              'Verifying the connector request…'}</p>
          </div>
        ) : error ? (
          <div className="oauth-consent-error">
            <span className="eyebrow">CONNECTION STOPPED</span>
            <h1>We couldn’t verify this request.</h1>
            <p role="alert">{error}</p>
            <a className="auth-primary-link" href="/account">Return to your account</a>
          </div>
        ) : details && (
          <>
            <div className="oauth-consent-clients" aria-hidden="true">
              <span className="auth-brand-mark">B</span>
              <i />
              <span className="oauth-client-mark">{clientInitial}</span>
            </div>
            <span className="eyebrow">CONNECT AN AI CLIENT</span>
            <h1>Allow {details.client.name} to use your Blog Vault?</h1>
            <p className="oauth-consent-intro">
              This gives the connector access to MCP tools and resources as you.
              It can read your private library and create or update drafts for
              human review. It cannot publish or delete articles.
            </p>

            <div className="oauth-permission-panel">
              <strong>Requested access</strong>
              <ul>
                <li><span>✓</span><p><b>Read your private vault</b>
                  <small>Articles, learning paths, tags, and review context.</small></p></li>
                <li><span>✓</span><p><b>Prepare content changes</b>
                  <small>Create and update drafts that still require your approval.</small></p></li>
                {scopes.map((scope) => (
                  <li key={scope}><span>✓</span><p><b>{scopeLabels[scope] ?? scope}</b>
                    <small>OAuth scope: {scope}</small></p></li>
                ))}
              </ul>
            </div>

            <dl className="oauth-client-details">
              <div><dt>Client</dt><dd>{details.client.name}</dd></div>
              {host && <div><dt>Website</dt><dd>{host}</dd></div>}
              <div><dt>Signed in</dt><dd>{details.user.email}</dd></div>
            </dl>

            <p className="oauth-consent-warning">
              Only continue if you initiated this connection in a client you trust.
              You can disconnect it later from your Blog Vault Account page.
            </p>

            <div className="oauth-consent-actions">
              <button className="oauth-deny" disabled={decision !== undefined}
                onClick={() => void decide('deny')}>
                {decision === 'deny' ? 'Denying…' : 'Deny'}
              </button>
              <button className="auth-submit" disabled={decision !== undefined}
                onClick={() => void decide('approve')}>
                {decision === 'approve' ? 'Connecting…' : 'Allow connection'}
              </button>
            </div>
          </>
        )}
      </section>

      <p className="oauth-consent-footnote">
        Authorization codes and refresh tokens are issued by Supabase Auth.
        Blog Vault never shares your password with the connector.
      </p>
    </main>
  );
}
