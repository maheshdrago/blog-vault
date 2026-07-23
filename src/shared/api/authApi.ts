import { resolveApiPath } from './config';

export type AppRole = 'reader' | 'admin';
export type AssuranceLevel = 'aal1' | 'aal2';

export interface AuthUser {
  authUserId: string;
  readerId: string;
  email: string | null;
  displayName: string | null;
  avatarUrl: string | null;
  role: AppRole;
  assuranceLevel: AssuranceLevel;
}

export interface AuthSessionResponse {
  accessToken: string | null;
  expiresIn: number | null;
  expiresAt: number | null;
  user: AuthUser | null;
  verificationRequired: boolean;
  message: string | null;
}

export interface DeviceSession {
  sessionId: string;
  deviceLabel: string;
  createdAt: string;
  lastSeenAt: string;
  expiresAt: string;
  revokedAt: string | null;
  isCurrent: boolean;
}

export interface McpCredential {
  credentialId: string;
  label: string;
  createdAt: string;
  lastUsedAt: string | null;
  revokedAt: string | null;
}

export interface McpCredentialCreated extends McpCredential {
  token: string;
}

export interface OAuthAuthorizationClient {
  id: string;
  name: string;
  uri: string;
  logoUri: string;
}

export interface OAuthAuthorizationDetails {
  authorizationId: string;
  redirectUri: string;
  client: OAuthAuthorizationClient;
  user: { id: string; email: string };
  scope: string;
}

export interface OAuthRedirect {
  redirectUrl: string;
}

export type OAuthAuthorizationResponse = OAuthAuthorizationDetails | OAuthRedirect;

export interface OAuthGrant {
  client: OAuthAuthorizationClient;
  scopes: string[];
  grantedAt: string;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

let accessToken: string | null = null;
let authenticatedSession = false;
let refreshPromise: Promise<AuthSessionResponse | null> | null = null;

function cookieValue(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split('; ').find((cookie) => cookie.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'The request failed.' })) as {
      detail?: string;
    };
    throw new ApiError(payload.detail ?? 'The request failed.', response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function refreshAccessToken(): Promise<AuthSessionResponse | null> {
  if (refreshPromise) return refreshPromise;
  const csrfToken = cookieValue('blog_csrf');
  if (!csrfToken) return null;
  refreshPromise = fetch(resolveApiPath('/auth/refresh'), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken },
  }).then(async (response) => {
    if (!response.ok) {
      accessToken = null;
      authenticatedSession = false;
      window.dispatchEvent(new CustomEvent('blog-vault:auth-expired'));
      return null;
    }
    const session = await response.json() as AuthSessionResponse;
    accessToken = session.accessToken;
    authenticatedSession = session.user !== null;
    return session;
  }).catch(() => null).finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

export function hasAuthenticatedSession(): boolean {
  return authenticatedSession;
}

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<Response> {
  if (!accessToken) await refreshAccessToken();
  const headers = new Headers(init.headers);
  headers.set('Accept', headers.get('Accept') ?? 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(resolveApiPath(path), {
    ...init,
    credentials: 'same-origin',
    headers,
  });
  if (response.status !== 401 || !retry || !accessToken) return response;
  accessToken = null;
  const refreshed = await refreshAccessToken();
  if (!refreshed?.accessToken) return response;
  return authenticatedFetch(path, init, false);
}

async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiPath(path), {
    ...init,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });
  return parseResponse<T>(response);
}

export const authApi = {
  bootstrap: refreshAccessToken,
  signIn: async (email: string, password: string): Promise<AuthSessionResponse> => {
    const session = await authRequest<AuthSessionResponse>('/auth/sign-in', {
      method: 'POST', body: JSON.stringify({ email, password }),
    });
    accessToken = session.accessToken;
    authenticatedSession = session.user !== null;
    return session;
  },
  signUp: async (email: string, password: string,
    displayName: string, returnTo = '/'): Promise<AuthSessionResponse> => {
    const session = await authRequest<AuthSessionResponse>('/auth/sign-up', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        displayName: displayName || null,
        returnTo,
      }),
    });
    accessToken = session.accessToken;
    authenticatedSession = session.user !== null;
    return session;
  },
  startOAuth: async (provider: 'google' | 'github', returnTo = '/'): Promise<void> => {
    const result = await authRequest<{ authorizationUrl: string }>('/auth/oauth/start', {
      method: 'POST', body: JSON.stringify({ provider, returnTo }),
    });
    window.location.assign(result.authorizationUrl);
  },
  signOut: async (): Promise<void> => {
    const csrfToken = cookieValue('blog_csrf');
    await parseResponse(await authenticatedFetch('/auth/sign-out', {
      method: 'POST', headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
    }));
    accessToken = null;
    authenticatedSession = false;
  },
  requestPasswordReset: (email: string): Promise<{ message: string }> =>
    authRequest('/auth/password-reset', {
      method: 'POST', body: JSON.stringify({ email }),
    }),
  updatePassword: async (password: string): Promise<{ message: string }> =>
    parseResponse(await authenticatedFetch('/auth/update-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })),
  listSessions: async (): Promise<DeviceSession[]> =>
    parseResponse(await authenticatedFetch('/auth/sessions')),
  revokeSession: async (sessionId: string): Promise<void> => {
    await parseResponse(await authenticatedFetch(`/auth/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    }));
  },
  revokeOtherSessions: async (): Promise<void> => {
    await parseResponse(await authenticatedFetch('/auth/sessions', { method: 'DELETE' }));
  },
  listMcpCredentials: async (): Promise<McpCredential[]> =>
    parseResponse(await authenticatedFetch('/me/mcp-credentials')),
  createMcpCredential: async (label: string): Promise<McpCredentialCreated> =>
    parseResponse(await authenticatedFetch('/me/mcp-credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    })),
  revokeMcpCredential: async (credentialId: string): Promise<void> => {
    await parseResponse(await authenticatedFetch(
      `/me/mcp-credentials/${encodeURIComponent(credentialId)}`,
      { method: 'DELETE' },
    ));
  },
  getOAuthAuthorizationDetails: async (
    authorizationId: string,
  ): Promise<OAuthAuthorizationResponse> =>
    parseResponse(await authenticatedFetch(
      `/auth/oauth/authorizations/${encodeURIComponent(authorizationId)}`,
    )),
  decideOAuthAuthorization: async (
    authorizationId: string,
    decision: 'approve' | 'deny',
  ): Promise<OAuthRedirect> =>
    parseResponse(await authenticatedFetch(
      `/auth/oauth/authorizations/${encodeURIComponent(authorizationId)}/consent`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision }),
      },
    )),
  listOAuthGrants: async (): Promise<OAuthGrant[]> =>
    parseResponse(await authenticatedFetch('/auth/oauth/grants')),
  revokeOAuthGrant: async (clientId: string): Promise<void> => {
    await parseResponse(await authenticatedFetch(
      `/auth/oauth/grants/${encodeURIComponent(clientId)}`,
      { method: 'DELETE' },
    ));
  },
};
