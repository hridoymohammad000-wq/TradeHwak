/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  MarketTicker,
  DashboardStats,
  CanonicalScanData,
  CanonicalSignalsData,
  ScanRequestPayload,
  TradingMode,
  BackendGrade,
  BackendTimeframe,
  ControlCenterSettings,
  SettingsUpdatePayload,
  EngineControlState,
  ChartContextData,
  CanonicalDashboardData,
  CanonicalActiveTradesData,
  CanonicalJournalData,
  DateTimeRange,
  PerformanceAnalysisData,
  PerformanceFilters
} from './types';


export type BackendConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'unauthorized'
  | 'backend_error';

export type ApiErrorKind =
  | 'configuration'
  | 'timeout'
  | 'network'
  | 'unauthorized'
  | 'backend'
  | 'parse';

export interface BackendHealth {
  status: string;
  app: string;
  phase: string;
  execution_enabled: boolean;
}

export interface AuthenticatedSession {
  authenticated: boolean;
  expires_at: string;
}

interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data: T | null;
}

interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  timeoutMs?: number;
  suppressUnauthorizedEvent?: boolean;
}

const REQUEST_TIMEOUT_MS = 10_000;
const configuredBaseUrl = (import.meta.env?.VITE_API_BASE_URL as string | undefined)?.trim();
const API_BASE_URL = configuredBaseUrl?.replace(/\/+$/, '') || '';
let unauthorizedHandler: (() => void) | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;

  constructor(message: string, status: number, kind: ApiErrorKind) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
  }
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function getBackendBaseUrl(): string | null {
  return API_BASE_URL || null;
}

async function parseApiEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const rawBody = await response.text();
  if (!rawBody) {
    return { success: response.ok, message: response.statusText || 'Request completed.', data: null };
  }

  try {
    return JSON.parse(rawBody) as ApiEnvelope<T>;
  } catch {
    throw new ApiError(
      'Backend returned an invalid JSON response.',
      response.status,
      'parse'
    );
  }
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(
      'VITE_API_BASE_URL is not configured.',
      0,
      'configuration'
    );
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      body,
      headers,
      credentials: 'include',
      cache: 'no-store',
      signal: controller.signal,
    });
    const envelope = await parseApiEnvelope<T>(response);

    if (response.status === 401) {
      if (!options.suppressUnauthorizedEvent) {
        unauthorizedHandler?.();
      }
      throw new ApiError(
        envelope.message || 'Unauthorized.',
        response.status,
        'unauthorized'
      );
    }

    if (!response.ok || envelope.success === false) {
      throw new ApiError(
        envelope.message || `Backend request failed with status ${response.status}.`,
        response.status,
        'backend'
      );
    }

    return envelope.data as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Backend request timed out.', 0, 'timeout');
    }
    throw new ApiError('Unable to reach the backend.', 0, 'network');
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function checkBackendHealth(): Promise<BackendHealth> {
  return apiRequest<BackendHealth>('/health', { method: 'GET' });
}

export function loginWithAccessToken(accessToken: string): Promise<AuthenticatedSession> {
  return apiRequest<AuthenticatedSession>('/auth/login', {
    method: 'POST',
    body: { access_token: accessToken },
    suppressUnauthorizedEvent: true,
  });
}

export function getAuthenticatedSession(): Promise<AuthenticatedSession> {
  return apiRequest<AuthenticatedSession>('/auth/session', { method: 'GET' });
}

export function logoutAuthenticatedSession(): Promise<null> {
  return apiRequest<null>('/auth/logout', { method: 'POST' });
}

function buildRangeQuery(range?: DateTimeRange): string {
  if (!range) return '';
  const params = new URLSearchParams({
    start_time: range.start,
    end_time: range.end,
  });
  return `?${params.toString()}`;
}

export function fetchDashboardSummary(range?: DateTimeRange): Promise<CanonicalDashboardData> {
  return apiRequest<CanonicalDashboardData>(`/dashboard-summary${buildRangeQuery(range)}`, { method: 'GET' });
}

export function fetchCanonicalActiveTrades(range?: DateTimeRange): Promise<CanonicalActiveTradesData> {
  return apiRequest<CanonicalActiveTradesData>(`/active-trades${buildRangeQuery(range)}`, { method: 'GET' });
}

export function fetchCanonicalJournal(range?: DateTimeRange): Promise<CanonicalJournalData> {
  return apiRequest<CanonicalJournalData>(`/closed-trades${buildRangeQuery(range)}`, { method: 'GET' });
}

export function runBackendScan(payload: ScanRequestPayload = {}): Promise<CanonicalScanData> {
  return apiRequest<CanonicalScanData>('/scan', { method: 'POST', body: payload });
}

export function fetchBackendSignals(filters: {
  mode?: TradingMode;
  grade?: BackendGrade;
  symbol?: string;
  timeframe?: BackendTimeframe;
} = {}): Promise<CanonicalSignalsData> {
  const params = new URLSearchParams();
  if (filters.mode) params.set('mode', filters.mode);
  if (filters.grade) params.set('grade', filters.grade);
  if (filters.symbol) params.set('symbol', filters.symbol);
  if (filters.timeframe) params.set('timeframe', filters.timeframe);
  const query = params.toString();
  return apiRequest<CanonicalSignalsData>(`/signals${query ? `?${query}` : ''}`, { method: 'GET' });
}


export function fetchChartContext(symbol:string, mode:TradingMode, timeframe:BackendTimeframe, limit=300):Promise<ChartContextData> {
 const params=new URLSearchParams({symbol,mode,timeframe,limit:String(limit)});
 return apiRequest<ChartContextData>(`/chart-context?${params.toString()}`,{method:'GET'});
}
export function fetchControlSettings():Promise<ControlCenterSettings>{ return apiRequest<ControlCenterSettings>('/settings',{method:'GET'}); }
export function saveControlSettings(payload:SettingsUpdatePayload):Promise<ControlCenterSettings>{ return apiRequest<ControlCenterSettings>('/settings',{method:'POST',body:payload}); }
export function updateEngineControls(payload:Partial<EngineControlState>):Promise<EngineControlState>{ return apiRequest<EngineControlState>('/engine/control',{method:'POST',body:payload}); }

export function fetchPerformanceAnalysis(filters: PerformanceFilters = {}): Promise<PerformanceAnalysisData> {
  const params = new URLSearchParams();
  if (filters.start) params.set('start_time', filters.start);
  if (filters.end) params.set('end_time', filters.end);
  if (filters.mode) params.set('mode', filters.mode);
  if (filters.strategy) params.set('strategy', filters.strategy);
  if (filters.status) params.set('status', filters.status);
  if (filters.exitReason) params.set('exit_reason', filters.exitReason);
  const query = params.toString();
  return apiRequest<PerformanceAnalysisData>(`/performance-analysis${query ? `?${query}` : ''}`, { method: 'GET' });
}
