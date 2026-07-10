import {
  CanonicalActiveTrade,
  CanonicalActiveTradesData,
  CanonicalClosedTrade,
  CanonicalDashboardData,
  CanonicalJournalData,
  DateTimeRange,
  JournalSummaryMetric,
} from './types';
import { apiRequest } from './client';

const COLD_START_TIMEOUT_MS = 75_000;
const RETRY_DELAY_MS = 2_000;

function appPath(path: string): string {
  return `/api${path.startsWith('/') ? path : `/${path}`}`;
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

async function resilientGet<T>(path: string): Promise<T> {
  try {
    return await apiRequest<T>(path, { method: 'GET', timeoutMs: COLD_START_TIMEOUT_MS });
  } catch (firstError) {
    await new Promise((resolve) => window.setTimeout(resolve, RETRY_DELAY_MS));
    try {
      return await apiRequest<T>(path, { method: 'GET', timeoutMs: COLD_START_TIMEOUT_MS });
    } catch {
      throw firstError;
    }
  }
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
  const pnlValues = trades.map((trade) => trade.realized_pnl).filter((value): value is number => value !== null);
  const wins = pnlValues.filter((value) => value > 0).length;
  const losses = pnlValues.filter((value) => value < 0).length;
  const decided = wins + losses;
  const rrValues = trades.map((trade) => trade.risk_reward).filter((value): value is number => value !== null);
  return {
    total_trades: trades.length,
    wins,
    losses,
    win_rate: decided ? (wins / decided) * 100 : null,
    realized_pnl: pnlValues.length ? pnlValues.reduce((sum, value) => sum + value, 0) : null,
    average_risk_reward: rrValues.length ? rrValues.reduce((sum, value) => sum + value, 0) / rrValues.length : null,
  };
}

export async function fetchDashboardSummary(range?: DateTimeRange): Promise<CanonicalDashboardData> {
  const raw: any = await resilientGet<any>(`${appPath('/dashboard-summary')}${buildRangeQuery(range)}`);
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
      opened_trades_today: Number(today.opened_trades_today || 0),
      active_trades_now: Number(today.active_trades_now ?? today.total_open_trades ?? 0),
      total_open_trades: Number(today.total_open_trades || 0),
      scalping_open_trades: Number(today.scalping_open_trades || 0),
      intraday_open_trades: Number(today.intraday_open_trades || 0),
      unknown_open_trades: Number(today.unknown_open_trades || 0),
      closed_trades_today: Number(today.closed_trades_today || 0),
      wins_today: Number(today.wins_today || 0),
      losses_today: Number(today.losses_today || 0),
      breakeven_today: Number(today.breakeven_today || 0),
      win_rate_today: numberOrNull(today.win_rate_today),
      loss_rate_today: numberOrNull(today.loss_rate_today),
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
  const raw: any = await resilientGet<any>(`${appPath('/active-trades')}${buildRangeQuery(range)}`);
  const source = Array.isArray(raw.active_trades)
    ? raw.active_trades
    : [...(raw.scalping_trades || []), ...(raw.intraday_trades || []), ...(raw.unknown_trades || [])];
  const active = source.map(activeTrade);
  return {
    today_summary: {
      total_open_trades: Number(raw.today_summary?.total_open_trades ?? active.length),
      scalping_open_trades: Number(raw.today_summary?.scalping_open_trades ?? active.filter((trade) => trade.mode === 'scalping').length),
      intraday_open_trades: Number(raw.today_summary?.intraday_open_trades ?? active.filter((trade) => trade.mode === 'intraday').length),
      unknown_open_trades: Number(raw.today_summary?.unknown_open_trades ?? active.filter((trade) => !trade.mode).length),
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
  const raw: any = await resilientGet<any>(`${appPath('/closed-trades')}${buildRangeQuery(range)}`);
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
