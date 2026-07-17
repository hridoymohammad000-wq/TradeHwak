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
  PerformanceFilters,
  CanonicalActiveTrade,
  CanonicalClosedTrade,
  JournalSummaryMetric,
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

function appPath(path: string): string {
  return `/api${path.startsWith('/') ? path : `/${path}`}`;
}

async function parseApiEnvelope<T>(response: Response): Promise<ApiEnvelope<T>> {
  const rawBody = await response.text();
  if (!rawBody) {
    return { success: response.ok, message: response.statusText || 'Request completed.', data: null };
  }

  try {
    return JSON.parse(rawBody) as ApiEnvelope<T>;
  } catch {
    throw new ApiError('Backend returned an invalid JSON response.', response.status, 'parse');
  }
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError('VITE_API_BASE_URL is not configured.', 0, 'configuration');
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
      if (!options.suppressUnauthorizedEvent) unauthorizedHandler?.();
      throw new ApiError(envelope.message || 'Unauthorized.', response.status, 'unauthorized');
    }
    if (!response.ok || envelope.success === false) {
      throw new ApiError(
        envelope.message || `Backend request failed with status ${response.status}.`,
        response.status,
        'backend',
      );
    }
    if (envelope.data == null) {
      throw new ApiError(envelope.message || 'Backend returned no data.', response.status, 'backend');
    }
    return envelope.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
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
    method: 'POST', body: { access_token: accessToken }, suppressUnauthorizedEvent: true,
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
  const params = new URLSearchParams({ start_time: range.start, end_time: range.end });
  return `?${params.toString()}`;
}

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function activeTrade(raw: any, index: number): CanonicalActiveTrade {
  return {
    trade_id: raw.trade_id || raw.order_id || raw.signal_id || `${raw.symbol || 'trade'}-${raw.opened_at || index}`,
    order_id: raw.order_id ?? null,
    signal_id: raw.signal_id ?? null,
    symbol: String(raw.symbol || 'Unknown'),
    mode: raw.mode ?? null,
    direction: raw.direction,
    qty: raw.qty ?? null,
    entry_price: numberOrNull(raw.entry_price),
    current_price: numberOrNull(raw.current_price),
    stop_loss: numberOrNull(raw.stop_loss),
    take_profit: numberOrNull(raw.take_profit),
    notional: numberOrNull(raw.notional),
    planned_risk_usdt: numberOrNull(raw.planned_risk_usdt),
    risk_distance: numberOrNull(raw.risk_distance),
    risk_pct_of_entry: numberOrNull(raw.risk_pct_of_entry),
    risk_reward: numberOrNull(raw.risk_reward),
    pnl: numberOrNull(raw.pnl),
    status: String(raw.status || 'unknown'),
    timeframe: raw.timeframe ?? null,
    opened_at: raw.opened_at ?? null,
  };
}

function closedTrade(raw: any, index: number): CanonicalClosedTrade {
  return {
    trade_id: raw.trade_id || raw.order_id || raw.signal_id || `${raw.symbol || 'trade'}-${raw.closed_time || index}`,
    order_id: raw.order_id ?? null,
    signal_id: raw.signal_id ?? null,
    symbol: String(raw.symbol || 'Unknown'),
    mode: raw.mode ?? null,
    direction: raw.direction,
    qty: raw.qty ?? null,
    entry_price: numberOrNull(raw.entry_price),
    exit_price: numberOrNull(raw.exit_price),
    stop_loss: numberOrNull(raw.stop_loss),
    take_profit: numberOrNull(raw.take_profit),
    notional: numberOrNull(raw.notional),
    planned_risk_usdt: numberOrNull(raw.planned_risk_usdt),
    risk_distance: numberOrNull(raw.risk_distance),
    risk_pct_of_entry: numberOrNull(raw.risk_pct_of_entry),
    realized_pnl: numberOrNull(raw.realized_pnl),
    pnl_multiple_of_risk: numberOrNull(raw.pnl_multiple_of_risk),
    stop_slippage_usdt: numberOrNull(raw.stop_slippage_usdt),
    risk_reward: numberOrNull(raw.risk_reward),
    result: raw.result ?? null,
    status: String(raw.status || 'unknown'),
    close_reason: raw.close_reason ?? null,
    exit_analysis: raw.exit_analysis ?? null,
    operator_summary: raw.operator_summary ?? null,
    timeframe: raw.timeframe ?? null,
    opened_at: raw.opened_at ?? null,
    closed_time: raw.closed_time ?? null,
  };
}

function summaryFor(trades: CanonicalClosedTrade[]): JournalSummaryMetric {
  const wins = trades.filter((trade) => trade.result === 'win').length;
  const losses = trades.filter((trade) => trade.result === 'loss').length;
  const pnlValues = trades.map((trade) => trade.realized_pnl).filter((value): value is number => value !== null);
  const rrValues = trades.map((trade) => trade.risk_reward).filter((value): value is number => value !== null);
  return {
    total_trades: trades.length,
    wins,
    losses,
    win_rate: trades.length ? (wins / trades.length) * 100 : null,
    realized_pnl: pnlValues.length ? pnlValues.reduce((sum, value) => sum + value, 0) : null,
    average_risk_reward: rrValues.length ? rrValues.reduce((sum, value) => sum + value, 0) / rrValues.length : null,
  };
}

export async function fetchDashboardSummary(range?: DateTimeRange): Promise<CanonicalDashboardData> {
  const raw: any = await apiRequest<any>(`${appPath('/dashboard-summary')}${buildRangeQuery(range)}`, { method: 'GET' });
  const today = raw.today_summary || {};
  return {
    system_status: String(raw.system_status || 'unknown'),
    system_mode: raw.system_mode || 'demo',
    active_strategy_mode: raw.active_strategy_mode || 'scalping',
    scalping_engine_enabled: Boolean(raw.scalping_engine_enabled),
    intraday_engine_enabled: Boolean(raw.intraday_engine_enabled),
    auto_trade_enabled: Boolean(raw.auto_trade_enabled),
    emergency_stop: Boolean(raw.emergency_stop),
    account: raw.account || { status: 'unavailable', equity: null, available_balance: null },
    today_summary: {
      total_open_trades: Number(today.total_open_trades || 0),
      scalping_open_trades: Number(today.scalping_open_trades || 0),
      intraday_open_trades: Number(today.intraday_open_trades || 0),
      unknown_open_trades: Number(today.unknown_open_trades || 0),
      closed_trades_today: Number(today.closed_trades_today || 0),
      wins_today: Number(today.wins_today || 0),
      losses_today: Number(today.losses_today || 0),
      win_rate_today: numberOrNull(today.win_rate_today),
      unrealized_pnl: numberOrNull(today.unrealized_pnl),
      realized_pnl_today: numberOrNull(today.realized_pnl_today),
      average_risk_reward_today: numberOrNull(today.average_risk_reward_today),
    },
    recent_events: Array.isArray(raw.recent_events) ? raw.recent_events : [],
    range_start: raw.range_start ?? range?.start ?? null,
    range_end: raw.range_end ?? range?.end ?? null,
  };
}

export async function fetchCanonicalActiveTrades(range?: DateTimeRange): Promise<CanonicalActiveTradesData> {
  const raw: any = await apiRequest<any>(`${appPath('/active-trades')}${buildRangeQuery(range)}`, { method: 'GET' });
  const source = Array.isArray(raw.active_trades)
    ? raw.active_trades
    : [...(raw.scalping_trades || []), ...(raw.intraday_trades || []), ...(raw.unknown_trades || [])];
  const active = source.map(activeTrade);
  return {
    today_summary: {
      total_open_trades: Number(raw.today_summary?.total_open_trades ?? active.length),
      scalping_open_trades: Number(raw.today_summary?.scalping_open_trades ?? active.filter((t) => t.mode === 'scalping').length),
      intraday_open_trades: Number(raw.today_summary?.intraday_open_trades ?? active.filter((t) => t.mode === 'intraday').length),
      unknown_open_trades: Number(raw.today_summary?.unknown_open_trades ?? active.filter((t) => !t.mode).length),
      closed_trades_today: Number(raw.today_summary?.closed_trades_today || 0),
      system_mode: raw.today_summary?.system_mode || 'demo',
    },
    active_trades: active,
    scalping_trades: active.filter((trade) => trade.mode === 'scalping'),
    intraday_trades: active.filter((trade) => trade.mode === 'intraday'),
    unknown_trades: active.filter((trade) => !trade.mode),
    range_start: raw.range_start ?? range?.start ?? null,
    range_end: raw.range_end ?? range?.end ?? null,
  };
}

export async function fetchCanonicalJournal(range?: DateTimeRange): Promise<CanonicalJournalData> {
  const raw: any = await apiRequest<any>(`${appPath('/closed-trades')}${buildRangeQuery(range)}`, { method: 'GET' });
  const trades = (raw.closed_trades || []).map(closedTrade);
  const scalping = trades.filter((trade) => trade.mode === 'scalping');
  const intraday = trades.filter((trade) => trade.mode === 'intraday');
  const unknown = trades.filter((trade) => !trade.mode);
  return {
    closed_trades: trades,
    summaries: raw.summaries || {
      scalping: summaryFor(scalping),
      intraday: summaryFor(intraday),
      unknown: summaryFor(unknown),
      combined: summaryFor(trades),
    },
    range_start: raw.range_start ?? range?.start ?? null,
    range_end: raw.range_end ?? range?.end ?? null,
  };
}

export async function runBackendScan(payload: ScanRequestPayload = {}): Promise<CanonicalScanData> {
  const raw: any = await apiRequest<any>(appPath('/scan'), { method: 'POST', body: payload });
  const results = (raw.results || []).map((item: any) => ({
    symbol: item.symbol,
    outcome: item.outcome || (item.grade === 'A+' || item.grade === 'A' ? 'actionable' : 'rejected'),
    mode: item.mode || raw.mode,
    timeframe: item.timeframe ?? raw.timeframe ?? null,
    direction: item.direction ?? null,
    grade: item.grade ?? null,
    strategy: item.strategy ?? null,
    reason: item.reason ?? null,
    rejection_reason: item.rejection_reason ?? null,
    failure_reason: item.failure_reason ?? null,
    metrics: item.metrics ?? null,
  }));
  const counts = results.reduce((acc: any, item: any) => {
    acc.total += 1;
    acc[item.outcome] += 1;
    return acc;
  }, { total: 0, actionable: 0, rejected: 0, skipped: 0, failed: 0 });
  return { mode: raw.mode, timeframe: raw.timeframe ?? null, counts: raw.counts || counts, results };
}

export async function fetchBackendSignals(filters: {
  mode?: TradingMode; grade?: BackendGrade; symbol?: string; timeframe?: BackendTimeframe;
} = {}): Promise<CanonicalSignalsData> {
  const params = new URLSearchParams();
  if (filters.mode) params.set('mode', filters.mode);
  if (filters.grade) params.set('grade', filters.grade);
  if (filters.symbol) params.set('symbol', filters.symbol);
  if (filters.timeframe) params.set('timeframe', filters.timeframe);
  const raw: any = await apiRequest<any>(`${appPath('/signals')}${params.size ? `?${params}` : ''}`, { method: 'GET' });
  return {
    filters: raw.filters,
    signals: (raw.signals || []).map((signal: any) => ({ ...signal, strategy: signal.strategy ?? null, reason: signal.reason ?? null })),
  };
}

export async function fetchChartContext(symbol: string, mode: TradingMode, timeframe: BackendTimeframe, limit = 300): Promise<ChartContextData> {
  const params = new URLSearchParams({ symbol, mode, timeframe, limit: String(limit) });
  const raw: any = await apiRequest<any>(`${appPath('/chart-context')}?${params}`, { method: 'GET' });
  const candles = Array.isArray(raw.candles) ? raw.candles : [];
  const lastCandle = candles[candles.length - 1];
  return {
    symbol: raw.symbol,
    mode: raw.mode,
    timeframe: raw.timeframe,
    chart_status: candles.length ? 'context_ready' : 'pending_data',
    candles,
    last_price: lastCandle ? numberOrNull(lastCandle.close) : null,
    indicator_context: candles.length ? raw.indicator_context : {
      ema20: null, ema50: null, ema200: null, rsi: null, macd: null, macd_signal: null,
    },
    fetched_at: raw.fetched_at ?? null,
  };
}

export function fetchControlSettings(): Promise<ControlCenterSettings> {
  return apiRequest<ControlCenterSettings>(appPath('/settings'), { method: 'GET' });
}
export function saveControlSettings(payload: SettingsUpdatePayload): Promise<ControlCenterSettings> {
  return apiRequest<ControlCenterSettings>(appPath('/settings'), { method: 'POST', body: payload });
}
export function updateEngineControls(payload: Partial<EngineControlState>): Promise<EngineControlState> {
  return apiRequest<EngineControlState>(appPath('/engine/control'), { method: 'POST', body: payload });
}

export function fetchPerformanceAnalysis(filters: PerformanceFilters = {}): Promise<PerformanceAnalysisData> {
  const params = new URLSearchParams();
  if (filters.start) params.set('start_time', filters.start);
  if (filters.end) params.set('end_time', filters.end);
  if (filters.mode) params.set('mode', filters.mode);
  if (filters.strategy) params.set('strategy', filters.strategy);
  if (filters.status) params.set('status', filters.status);
  if (filters.exitReason) params.set('exit_reason', filters.exitReason);
  const query = params.toString();
  return apiRequest<PerformanceAnalysisData>(`${appPath('/performance-analysis')}${query ? `?${query}` : ''}`, { method: 'GET' });
}

// Legacy exports retained for existing UI-only helpers.
export type { MarketTicker, DashboardStats };
