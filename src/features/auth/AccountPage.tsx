import { useCallback, useEffect, useState } from 'react';

import {
  authApi,
  type DeviceSession,
  type McpCredential,
  type OAuthGrant,
} from '../../shared/api/authApi';
import { MCP_URL } from '../../shared/api/config';
import { useAuth } from './AuthContext';

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })
    .format(new Date(value));
}

export function AccountPage() {
  const { status, user, signOut } = useAuth();
  const [sessions, setSessions] = useState<DeviceSession[]>([]);
  const [mcpCredentials, setMcpCredentials] = useState<McpCredential[]>([]);
  const [oauthGrants, setOauthGrants] = useState<OAuthGrant[]>([]);
  const [mcpLabel, setMcpLabel] = useState('My LLM');
  const [newMcpToken, setNewMcpToken] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const [nextSessions, nextCredentials, nextGrants] = await Promise.all([
        authApi.listSessions(),
        authApi.listMcpCredentials(),
        authApi.listOAuthGrants(),
      ]);
      setSessions(nextSessions);
      setMcpCredentials(nextCredentials);
      setOauthGrants(nextGrants);
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Sessions could not be loaded.'); }
  }, []);

  const createMcpCredential = async () => {
    setBusy(true);
    setError(undefined);
    try {
      const credential = await authApi.createMcpCredential(mcpLabel);
      setNewMcpToken(credential.token);
      setMcpLabel('My LLM');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'MCP credential could not be created.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { if (user) void load(); }, [load, user]);

  if (status === 'bootstrapping') return <main className="auth-shell auth-state-shell"><p>Restoring session…</p></main>;
  if (!user) return <main className="auth-shell auth-state-shell"><section className="auth-card">
    <a className="auth-wordmark" href="/">BLOG VAULT</a><h1>Sign in required</h1>
    <p>Sign in to manage synced reading data and device sessions.</p>
    <a className="auth-primary-link" href="/auth">Sign in</a>
  </section></main>;

  return <main className="account-shell"><header className="account-header">
    <div><a className="auth-wordmark" href="/">BLOG VAULT</a><span>/ ACCOUNT</span></div>
    <nav><a href="/review">Review drafts</a><a href="/">Back to reading</a></nav></header>
    <section className="account-profile"><div className="account-avatar">
      {(user.displayName || user.email || 'R').slice(0, 1).toUpperCase()}</div>
      <div><span className="eyebrow">SIGNED IN</span><h1>{user.displayName || 'Reader'}</h1>
        <p>{user.email}</p><span className="account-role">{user.role}</span></div>
      <button onClick={() => void signOut().then(() => window.location.assign('/'))
        .catch((caught: unknown) => setError(caught instanceof Error ? caught.message :
          'Sign out could not be completed.'))}>Sign out</button>
    </section>
    <section className="session-panel"><header><div><span className="eyebrow">SECURITY</span>
      <h2>Your devices</h2><p>Review and revoke browsers connected to your library.</p></div>
      <button disabled={busy} onClick={() => { setBusy(true); void authApi.revokeOtherSessions()
        .then(load).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Could not revoke sessions.'))
        .finally(() => setBusy(false)); }}>Sign out other devices</button></header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="session-list">{sessions.map((session) => <article key={session.sessionId}>
        <div><strong>{session.deviceLabel}</strong>{session.isCurrent && <span>This device</span>}
          {session.revokedAt && <span className="revoked">Revoked</span>}
          <p>Last active {formatDate(session.lastSeenAt)}</p><small>Signed in {formatDate(session.createdAt)}</small></div>
        {!session.isCurrent && !session.revokedAt && <button onClick={() => void authApi
          .revokeSession(session.sessionId).then(load)}>Revoke</button>}</article>)}</div>
    </section>
    <section className="session-panel mcp-panel"><header><div>
      <span className="eyebrow">LLM ACCESS</span>
      <h2>Connect an AI client</h2>
      <p>OAuth-capable clients open a secure browser consent flow. They never
        receive your Blog Vault password.</p>
    </div></header>
      <div className="mcp-oauth-card">
        <div><strong>Recommended · OAuth 2.1</strong>
          <p>In Claude or ChatGPT, add a custom MCP connector and enter this URL.
            Blog Vault will ask you to approve the connection.</p></div>
        <code>{MCP_URL}</code>
        <button onClick={() => void navigator.clipboard.writeText(MCP_URL)}>
          Copy URL</button>
      </div>
      {oauthGrants.length > 0 && <div className="oauth-grant-list">
        <span>Authorized connectors</span>
        {oauthGrants.map((grant) => <article key={grant.client.id}>
          <div><strong>{grant.client.name}</strong>
            <p>{grant.scopes.length > 0 ? grant.scopes.join(' · ') :
              'Private vault access'}</p>
            <small>Authorized {formatDate(grant.grantedAt)}</small></div>
          <button disabled={busy} onClick={() => {
            setBusy(true);
            void authApi.revokeOAuthGrant(grant.client.id)
              .then(load)
              .catch((caught: unknown) => setError(caught instanceof Error ?
                caught.message : 'Connector access could not be revoked.'))
              .finally(() => setBusy(false));
          }}>Disconnect</button>
        </article>)}
      </div>}
      <div className="mcp-manual-heading">
        <span>Manual access tokens</span>
        <p>Use these only for Claude Code, CI, or clients without browser OAuth.</p>
      </div>
      <div className="mcp-create-row">
        <label htmlFor="mcp-label">Credential label</label>
        <div><input id="mcp-label" value={mcpLabel} maxLength={80}
          onChange={(event) => setMcpLabel(event.target.value)}
          placeholder="Claude Desktop" />
        <button disabled={busy || !mcpLabel.trim()}
          onClick={() => void createMcpCredential()}>Create credential</button></div>
      </div>
      {newMcpToken && <aside className="mcp-token-once" role="status">
        <strong>Copy this token now</strong>
        <p>It is shown only once. Blog Vault stores only a cryptographic hash.</p>
        <code>{newMcpToken}</code>
        <button onClick={() => void navigator.clipboard.writeText(newMcpToken)}>
          Copy token</button>
      </aside>}
      <div className="session-list">{mcpCredentials.map((credential) =>
        <article key={credential.credentialId}>
          <div><strong>{credential.label}</strong>
            {credential.revokedAt && <span className="revoked">Revoked</span>}
            <p>{credential.lastUsedAt ?
              `Last used ${formatDate(credential.lastUsedAt)}` : 'Never used'}</p>
            <small>Created {formatDate(credential.createdAt)}</small></div>
          {!credential.revokedAt && <button onClick={() => {
            setBusy(true);
            void authApi.revokeMcpCredential(credential.credentialId)
              .then(load)
              .catch((caught: unknown) => setError(
                caught instanceof Error ? caught.message : 'Credential could not be revoked.',
              ))
              .finally(() => setBusy(false));
          }}>Revoke</button>}
        </article>)}</div>
    </section>
  </main>;
}
