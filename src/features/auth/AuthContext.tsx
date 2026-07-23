import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { authApi, type AuthSessionResponse, type AuthUser } from '../../shared/api/authApi';

type AuthStatus = 'bootstrapping' | 'signed-out' | 'authenticated' | 'offline';

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  signIn: (email: string, password: string) => Promise<AuthSessionResponse>;
  signUp: (email: string, password: string,
    displayName: string, returnTo?: string) => Promise<AuthSessionResponse>;
  signOut: () => Promise<void>;
  startOAuth: (provider: 'google' | 'github', returnTo?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('bootstrapping');
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let active = true;
    const handleExpired = () => {
      if (!active) return;
      setUser(null);
      setStatus('signed-out');
    };
    window.addEventListener('blog-vault:auth-expired', handleExpired);
    void authApi.bootstrap().then((session) => {
      if (!active) return;
      setUser(session?.user ?? null);
      setStatus(session?.user ? 'authenticated' : 'signed-out');
    }).catch(() => {
      if (active) setStatus('offline');
    });
    return () => {
      active = false;
      window.removeEventListener('blog-vault:auth-expired', handleExpired);
    };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    signIn: async (email, password) => {
      const session = await authApi.signIn(email, password);
      setUser(session.user);
      setStatus(session.user ? 'authenticated' : 'signed-out');
      return session;
    },
    signUp: async (email, password, displayName, returnTo) => {
      const session = await authApi.signUp(email, password, displayName, returnTo);
      setUser(session.user);
      setStatus(session.user ? 'authenticated' : 'signed-out');
      return session;
    },
    signOut: async () => {
      await authApi.signOut();
      setUser(null);
      setStatus('signed-out');
    },
    startOAuth: authApi.startOAuth,
  }), [status, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
