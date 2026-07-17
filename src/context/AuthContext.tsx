import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { config } from "../lib/config";
import { apiClient } from "../lib/apiClient";

interface AuthContextType {
  token: string | null;
  checkingSession: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(config.tokenKey));
  const [checkingSession, setCheckingSession] = useState(true);

  const markSessionActive = () => {
    localStorage.setItem(config.tokenKey, "session-active");
    setToken("session-active");
  };

  const clearSessionState = () => {
    localStorage.removeItem(config.tokenKey);
    setToken(null);
  };

  const refreshSession = async () => {
    try {
      await apiClient.session();
      markSessionActive();
      return true;
    } catch {
      clearSessionState();
      return false;
    }
  };

  const login = async (accessToken: string) => {
    await apiClient.login(accessToken);
    markSessionActive();
  };

  const logout = async () => {
    try {
      await apiClient.logout();
    } catch {
      // Local logout should still work if backend is unreachable.
    } finally {
      clearSessionState();
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      await refreshSession();
      if (mounted) setCheckingSession(false);
    })();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <AuthContext.Provider value={{ token, checkingSession, login, logout, refreshSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
