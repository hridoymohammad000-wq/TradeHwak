import { config } from "./config";
import { Signal, Trade, PerformanceStats, Settings, DashboardData } from "../types";

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(message: string, status: number, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = "ApiError";
  }
}

async function fetchWithTimeout(resource: RequestInfo, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = 10000 } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(resource, {
      ...options,
      signal: controller.signal,
      credentials: "include",
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

async function client<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const headers = new Headers(options.headers);

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const fetchOptions: RequestInit = {
    ...options,
    credentials: "include",
    headers,
  };

  try {
    const response = await fetchWithTimeout(url, fetchOptions);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;

    if (response.status === 401) {
      throw new ApiError(payload?.detail || "Unauthorized. Please login again.", response.status, payload);
    }
    if (response.status === 403) {
      throw new ApiError(
        payload?.detail || "Origin validation failed. Check backend CORS/FRONTEND_URL settings.",
        response.status,
        payload
      );
    }
    if (!response.ok) {
      throw new ApiError(payload?.detail || payload?.message || `API Error: ${response.statusText}`, response.status, payload);
    }

    return (payload ?? {}) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("Request timeout", 408);
    }
    throw new ApiError(error instanceof Error ? error.message : "Network error", 0);
  }
}

export const apiClient = {
  health: () => client<{ status?: string; data?: unknown }>("/health"),

  login: (accessToken: string) =>
    client<{ message?: string; data?: { expires_at?: string } }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ access_token: accessToken }),
    }),
  session: () => client<{ message?: string; data?: { expires_at?: string } }>("/auth/session"),
  logout: () => client<{ message?: string; data?: { logged_out?: boolean } }>("/auth/logout", { method: "POST" }),

  getDashboard: () => client<DashboardData | any>("/api/dashboard-summary"),
  getScanner: () => client<Signal[] | any>("/api/scan", { method: "POST" }),
  runScanner: () => client<{ success?: boolean; message?: string } | any>("/api/scan", { method: "POST" }),
  getSignals: () => client<Signal[] | any>("/api/signals"),
  getActiveTrades: () => client<Trade[] | any>("/api/active-trades"),
  getJournal: () => client<Trade[] | any>("/api/closed-trades"),
  getPerformance: () => client<PerformanceStats | any>("/api/performance"),
  getSettings: () => client<Settings | any>("/api/settings"),
  updateSettings: (payload: Partial<Settings>) =>
    client<Settings | any>("/api/settings", { method: "POST", body: JSON.stringify(payload) }),
  startBot: () => client<{ success?: boolean; message?: string } | any>("/api/bot/start", { method: "POST" }),
  stopBot: () => client<{ success?: boolean; message?: string } | any>("/api/bot/stop", { method: "POST" }),
  updateEngineControl: (payload: any) =>
    client<{ success?: boolean; message?: string } | any>("/api/engine/control", { method: "POST", body: JSON.stringify(payload) }),
};
