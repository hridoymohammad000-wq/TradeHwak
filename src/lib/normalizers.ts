import { DashboardData, Signal, Trade, PerformanceStats, Settings } from "../types";

function unwrap(raw: any): any {
  return raw?.data ?? raw ?? {};
}

function firstArray(raw: any, keys: string[]): any[] {
  if (Array.isArray(raw)) return raw;
  const data = unwrap(raw);
  if (Array.isArray(data)) return data;
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
    if (Array.isArray(raw?.[key])) return raw[key];
  }
  return [];
}

function numberOrNull(...values: any[]): number | null {
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function numberOrZero(...values: any[]): number {
  return numberOrNull(...values) ?? 0;
}

function text(...values: any[]): string {
  for (const value of values) {
    if (value !== null && value !== undefined && String(value).trim() !== "") return String(value);
  }
  return "N/A";
}

function normalizeDirection(value: any): Signal["direction"] {
  const raw = String(value || "").toUpperCase();
  if (["BUY", "LONG"].includes(raw)) return "BUY";
  if (["SELL", "SHORT"].includes(raw)) return "SELL";
  return "BUY";
}

export function normalizeDashboardData(raw: any): DashboardData {
  const data = unwrap(raw);
  const stats = data.stats || data.performance || data.today_summary || data.summary || {};
  const recentSignals = normalizeSignals(data.recentSignals || data.recent_signals || data.signals || []);
  const activeTrades = normalizeTrades(data.activeTrades || data.active_trades || data.intraday_trades || []);

  return {
    stats: {
      totalTrades: numberOrZero(stats.totalTrades, stats.total_trades, stats.closed_trades_today),
      winRate: numberOrZero(stats.winRate, stats.win_rate),
      totalPnl: numberOrZero(stats.totalPnl, stats.total_pnl, stats.net_pnl, stats.realized_pnl),
      dailyPnl: numberOrZero(stats.dailyPnl, stats.daily_pnl, stats.net_pnl_today, stats.realized_pnl_today),
      accountBalance: numberOrZero(stats.accountBalance, stats.account_balance),
      drawdown: numberOrZero(stats.drawdown, stats.max_drawdown, stats.daily_loss_usage_pct),
    },
    recentSignals,
    activeTrades,
  };
}

export function normalizeSignals(raw: any): Signal[] {
  const signals = firstArray(raw, [
    "signals",
    "items",
    "results",
    "candidates",
    "actionable_signals",
    "scan_results",
    "a_plus_signals",
    "a_signals",
  ]);

  return signals.map((s, index) => {
    const metrics = s.metrics || {};
    return {
      id: text(s.id, s.signal_id, `${s.symbol || "signal"}-${s.created_at || s.updated_at || index}`),
      symbol: text(s.symbol, s.ticker, "UNKNOWN"),
      direction: normalizeDirection(s.direction || s.side),
      grade: text(s.grade, s.signal_grade, s.rating, "UNKNOWN"),
      trend1H: text(s.trend1H, s.trend_1h, metrics.trend_direction, metrics.trend_timeframe_minutes ? "Aligned" : "N/A"),
      setup15M: text(s.setup15M, s.setup_15m, s.setup, metrics.setup_timeframe_minutes ? "Matched" : "N/A"),
      entry5M: text(s.entry5M, s.entry_5m, s.entry, metrics.entry_timeframe_minutes ? "Confirmed" : "N/A"),
      entryPrice: numberOrNull(s.entryPrice, s.entry_price, s.current_price),
      stopLoss: numberOrNull(s.stopLoss, s.stop_loss, s.sl),
      takeProfit: numberOrNull(s.takeProfit, s.take_profit, s.tp),
      riskReward: numberOrNull(s.riskReward, s.risk_reward, s.rr),
      score: numberOrNull(s.score, s.final_score, metrics.final_score),
      reason: text(s.reason, s.detail, s.message),
      status: text(s.status, s.outcome, "UNKNOWN"),
      createdAt: text(s.createdAt, s.created_at, s.timestamp, "N/A"),
      updatedAt: text(s.updatedAt, s.updated_at, s.timestamp, "N/A"),
    };
  });
}

export function normalizeTrades(raw: any): Trade[] {
  const data = unwrap(raw);
  const trades = Array.isArray(raw)
    ? raw
    : [
        ...firstArray(data, ["intraday_trades", "active_trades", "closed_trades", "trades"]),
        ...firstArray(data, ["scalping_trades"]),
      ];

  return trades.map((t, index) => ({
    id: text(t.id, t.trade_id, t.client_order_id, `${t.symbol || "trade"}-${t.open_time || t.closed_time || index}`),
    symbol: text(t.symbol, t.ticker, "UNKNOWN"),
    direction: normalizeDirection(t.direction || t.side),
    grade: text(t.grade, t.signal_grade, "UNKNOWN"),
    entryPrice: numberOrZero(t.entryPrice, t.entry_price, t.avg_entry_price),
    currentPrice: numberOrZero(t.currentPrice, t.current_price, t.mark_price),
    exitPrice: numberOrZero(t.exitPrice, t.exit_price, t.avg_exit_price),
    quantity: numberOrZero(t.quantity, t.qty, t.size),
    grossPnl: numberOrZero(t.grossPnl, t.gross_pnl, t.pnl, t.realized_pnl),
    fees: numberOrNull(t.fees, t.total_fees, t.commission),
    netPnl: numberOrZero(t.netPnl, t.net_pnl, t.pnl_after_fees, t.pnl),
    status: text(t.status, t.state, "UNKNOWN"),
    result: text(t.result, t.outcome, "UNKNOWN"),
    reason: text(t.reason, t.close_reason, t.exit_reason),
    openTime: text(t.openTime, t.open_time, t.created_at, "N/A"),
    closeTime: t.closeTime || t.close_time || t.closed_at || undefined,
    tp: numberOrNull(t.tp, t.take_profit) ?? undefined,
    sl: numberOrNull(t.sl, t.stop_loss) ?? undefined,
  }));
}

export function normalizePerformance(raw: any): PerformanceStats | null {
  const data = unwrap(raw);
  const source = data.stats || data.performance || data.summary || data;
  if (!source || Object.keys(source).length === 0) return null;
  return {
    totalTrades: numberOrZero(source.totalTrades, source.total_trades),
    winRate: numberOrZero(source.winRate, source.win_rate),
    totalPnl: numberOrZero(source.totalPnl, source.total_pnl, source.net_pnl),
    dailyPnl: numberOrZero(source.dailyPnl, source.daily_pnl, source.net_pnl_today),
    accountBalance: numberOrZero(source.accountBalance, source.account_balance),
    drawdown: numberOrZero(source.drawdown, source.max_drawdown),
  };
}

export function normalizeSettings(raw: any): Settings {
  const data = unwrap(raw);
  const risk = data.risk || data.risk_settings || data;
  const notifications = data.notifications || {};
  return {
    riskPerTrade: numberOrNull(risk.riskPerTrade, risk.risk_per_trade_pct) ?? undefined,
    maxDailyLoss: numberOrNull(risk.maxDailyLoss, risk.daily_max_loss) ?? undefined,
    defaultLeverage: numberOrNull(risk.defaultLeverage, risk.default_leverage) ?? undefined,
    maxOpenPositions: numberOrNull(risk.maxOpenPositions, risk.max_open_positions) ?? undefined,
    dailyMaxTrades: numberOrNull(risk.dailyMaxTrades, risk.daily_max_trades) ?? undefined,
    allowedSignalGrades: data.allowedSignalGrades || data.allowed_signal_grades || data.strategy?.allowed_signal_grades,
    telegramStatus: notifications.telegram === true ? "Enabled" : notifications.telegram === false ? "Disabled" : undefined,
    emailStatus: notifications.email === true ? "Enabled" : notifications.email === false ? "Disabled" : undefined,
  };
}
