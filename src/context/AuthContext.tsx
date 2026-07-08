import React, {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  ApiError,
  AuthenticatedSession,
  BackendConnectionStatus,
  checkBackendHealth,
  getAuthenticatedSession,
  loginWithAccessToken,
  logoutAuthenticatedSession,
  setUnauthorizedHandler,
} from '../api/client';

type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  authState: AuthState;
  connectionStatus: BackendConnectionStatus;
  sessionExpiresAt: string | null;
  errorMessage: string | null;
  login: (accessToken: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function connectionStatusFromError(error: unknown): BackendConnectionStatus {
  if (!(error instanceof ApiError)) {
    return 'backend_error';
  }
  if (error.kind === 'unauthorized') {
    return 'unauthorized';
  }
  if (['network', 'timeout', 'configuration'].includes(error.kind)) {
    return 'disconnected';
  }
  return 'backend_error';
}

function messageFromError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return 'Unexpected backend error.';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>('checking');
  const [connectionStatus, setConnectionStatus] = useState<BackendConnectionStatus>('connecting');
  const [sessionExpiresAt, setSessionExpiresAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const markUnauthorized = useCallback(() => {
    setAuthState('unauthenticated');
    setConnectionStatus('unauthorized');
    setSessionExpiresAt(null);
    window.location.hash = '#login';
  }, []);

  const applyValidSession = useCallback((session: AuthenticatedSession) => {
    setAuthState('authenticated');
    setConnectionStatus('connected');
    setSessionExpiresAt(session.expires_at);
    setErrorMessage(null);
    if (window.location.hash === '#login' || !window.location.hash) {
      window.location.hash = '#dashboard';
    }
  }, []);

  const verifyBackendAndSession = useCallback(async () => {
    setConnectionStatus('connecting');
    setErrorMessage(null);
    try {
      const health = await checkBackendHealth();
      if (health.status.toLowerCase() !== 'healthy') {
        throw new ApiError('Backend health check did not report healthy.', 502, 'backend');
      }
      const session = await getAuthenticatedSession();
      applyValidSession(session);
    } catch (error) {
      const nextStatus = connectionStatusFromError(error);
      setConnectionStatus(nextStatus);
      setErrorMessage(messageFromError(error));
      if (nextStatus === 'unauthorized') {
        markUnauthorized();
      } else {
        setAuthState('unauthenticated');
      }
    }
  }, [applyValidSession, markUnauthorized]);

  useEffect(() => {
    setUnauthorizedHandler(markUnauthorized);
    void verifyBackendAndSession();
    return () => setUnauthorizedHandler(null);
  }, [markUnauthorized, verifyBackendAndSession]);

  useEffect(() => {
    if (authState !== 'authenticated') {
      return;
    }
    const intervalId = window.setInterval(() => {
      void verifyBackendAndSession();
    }, 30_000);
    return () => window.clearInterval(intervalId);
  }, [authState, verifyBackendAndSession]);

  useEffect(() => {
    if (!sessionExpiresAt || authState !== 'authenticated') {
      return;
    }
    const remainingMs = new Date(sessionExpiresAt).getTime() - Date.now();
    if (remainingMs <= 0) {
      markUnauthorized();
      return;
    }
    const timeoutId = window.setTimeout(markUnauthorized, remainingMs);
    return () => window.clearTimeout(timeoutId);
  }, [authState, markUnauthorized, sessionExpiresAt]);

  const login = useCallback(async (accessToken: string): Promise<boolean> => {
    setConnectionStatus('connecting');
    setErrorMessage(null);
    try {
      const health = await checkBackendHealth();
      if (health.status.toLowerCase() !== 'healthy') {
        throw new ApiError('Backend health check did not report healthy.', 502, 'backend');
      }
      const session = await loginWithAccessToken(accessToken);
      applyValidSession(session);
      return true;
    } catch (error) {
      const nextStatus = connectionStatusFromError(error);
      setAuthState('unauthenticated');
      setConnectionStatus(nextStatus);
      setSessionExpiresAt(null);
      setErrorMessage(messageFromError(error));
      return false;
    }
  }, [applyValidSession]);

  const logout = useCallback(async () => {
    setErrorMessage(null);
    try {
      await logoutAuthenticatedSession();
    } catch (error) {
      setErrorMessage(messageFromError(error));
    } finally {
      setAuthState('unauthenticated');
      setConnectionStatus('unauthorized');
      setSessionExpiresAt(null);
      window.location.hash = '#login';
    }
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    authState,
    connectionStatus,
    sessionExpiresAt,
    errorMessage,
    login,
    logout,
  }), [authState, connectionStatus, errorMessage, login, logout, sessionExpiresAt]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
