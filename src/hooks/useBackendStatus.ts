import { useState, useEffect, useCallback } from "react";
import { apiClient, ApiError } from "../lib/apiClient";
import { useAuth } from "../context/AuthContext";

export type BackendStatus = "Connected" | "Degraded" | "Offline" | "Unauthorized" | "Checking";

export function useBackendStatus() {
  const [status, setStatus] = useState<BackendStatus>("Checking");
  const { token, logout } = useAuth();

  const checkStatus = useCallback(async () => {
    setStatus("Checking");
    try {
      await apiClient.health();
      setStatus("Connected");
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          setStatus("Unauthorized");
          await logout();
        } else if (error.status === 403) {
          setStatus("Unauthorized");
        } else if (error.status === 408) {
          setStatus("Degraded");
        } else {
          setStatus("Offline");
        }
      } else {
        setStatus("Offline");
      }
    }
  }, [logout]);

  useEffect(() => {
    if (token) {
      checkStatus();
      const interval = setInterval(checkStatus, 30000);
      return () => clearInterval(interval);
    }
    setStatus("Unauthorized");
  }, [checkStatus, token]);

  return { status, checkStatus };
}
