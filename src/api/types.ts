/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Global Tickers and Coins
export type AssetTicker = 'BTC/USDT' | 'ETH/USDT' | 'SOL/USDT' | 'BNB/USDT' | 'XRP/USDT' | 'ADA/USDT' | 'AVAX/USDT' | 'LINK/USDT';

export interface MarketTicker {
  symbol: AssetTicker;
  name: string;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  sparkline: number[];
}

export interface DashboardStats {
  portfolioValue: number;
  portfolioChange24h: number;
  portfolioChangePercent24h: number;
  totalUnrealizedPnL: number;
  activeTradesCount: number;
  winRate: number;
  gasPriceGwei: number;
}

export type TradingMode = 'scalping' | 'intraday';
export type BackendDirection = 'buy' | 'sell';
export type BackendGrade = 'A+' | 'A' | 'B+' | 'B';
export type BackendTimeframe = 'M1' | 'M5' | 'M15' | 'H1';
export type ScanOutcome = 'actionable' | 'rejected' | 'skipped' | 'failed';

export interface ScanMetrics { current_price:number|null; ema20:number|null; ema50:number|null; rsi14:number|null; trend_gap_pct:number|null; }
export interface ScannerResult { symbol:string; outcome:ScanOutcome; mode:TradingMode; timeframe:BackendTimeframe|null; direction:BackendDirection|null; grade:BackendGrade|null; strategy:string|null; reason:string|null; rejection_reason:string|null; failure_reason:string|null; metrics:ScanMetrics|null; }
export interface ScanCounts { total:number; actionable:number; rejected:number; skipped:number; failed:number; }
export interface CanonicalScanData { mode:TradingMode; timeframe:BackendTimeframe|null; counts:ScanCounts; results:ScannerResult[]; }
export interface ScanRequestPayload { mode?:TradingMode; symbols?:string[]; timeframe?:BackendTimeframe; direction?:BackendDirection; grade?:BackendGrade; }
export interface TradingSignal { signal_id:string; symbol:string; direction:BackendDirection; grade:BackendGrade; mode:TradingMode; timeframe:BackendTimeframe; status:string; strategy:string|null; reason:string|null; entry_price:number|null; current_price:number|null; }
export interface CanonicalSignalsData { filters:{mode:TradingMode; grade:BackendGrade|null; symbol:string|null; timeframe:BackendTimeframe|null}; signals:TradingSignal[]; }

export interface ChartCandle { open_time:number; open:number; high:number; low:number; close:number; volume:number|null; turnover:number|null; }
export interface ChartIndicatorContext { ema20:number|null; ema50:number|null; ema200:number|null; rsi:number|null; macd:number|null; macd_signal:number|null; }
export interface ChartContextData { symbol:string; mode:TradingMode; timeframe:BackendTimeframe; chart_status:'pending_data'|'context_ready'; candles:ChartCandle[]; last_price:number|null; indicator_context:ChartIndicatorContext; fetched_at:string|null; }
export interface Candlestick { time:string; open:number; high:number; low:number; close:number; volume:number; }

export type TradeDirection = 'LONG' | 'SHORT';
export interface ActiveTrade { id:string; symbol:AssetTicker; direction:TradeDirection; entryPrice:number; currentPrice:number; sizeTokens:number; sizeUsd:number; leverage:number; margin:number; unrealizedPnL:number; unrealizedPnLPercent:number; realizedPnL:number; stopLoss:number; takeProfit:number; trailingStopEnabled:boolean; timestamp:string; }
export type JournalOutcome = 'WIN' | 'LOSS' | 'BREAKEVEN' | 'OPEN';
export interface JournalEntry { id:string; timestamp:string; symbol:string; direction:TradeDirection; outcome:JournalOutcome; entryPrice:number; exitPrice:number|null; positionSizeUsd:number; netPnL:number; returnPercent:number; strategy:string; notes:string; screenshotUrl?:string; }

export interface ModeRiskSettings { max_risk_per_trade_pct:number; max_trades_per_day:number; max_daily_loss:number; max_concurrent_trades:number; session_start_utc:string|null; session_end_utc:string|null; }
export interface ControlCenterSettings { system:{system_mode:'demo'}; strategy:{active_strategy_mode:TradingMode; allowed_signal_grades:BackendGrade[]}; risk:{daily_max_loss:number; daily_max_trades:number; risk_per_trade_pct:number; max_open_positions:number; scalping:ModeRiskSettings; intraday:ModeRiskSettings}; notifications:{telegram:boolean; email:boolean; chime:boolean; toast:boolean}; engine_control:{scalping_engine_enabled:boolean; intraday_engine_enabled:boolean}; execution_control:{auto_trade_enabled:boolean; emergency_stop:boolean}; }
export interface SettingsUpdatePayload { scalping?:Partial<ModeRiskSettings>; intraday?:Partial<ModeRiskSettings>; scalping_engine_enabled?:boolean; intraday_engine_enabled?:boolean; auto_trade_enabled?:boolean; emergency_stop?:boolean; active_strategy_mode?:TradingMode; }
export interface EngineControlState { scalping_engine_enabled:boolean; intraday_engine_enabled:boolean; auto_trade_enabled:boolean; emergency_stop:boolean; }

export type CanonicalTradingMode = 'scalping' | 'intraday' | null;
export type CanonicalTradeDirection = 'buy' | 'sell';
export type DataRequestState = 'idle' | 'loading' | 'ready' | 'empty' | 'unauthorized' | 'disconnected' | 'backend_error';

export interface CanonicalActiveTrade { trade_id:string; order_id:string|null; signal_id:string|null; symbol:string; mode:CanonicalTradingMode; direction:CanonicalTradeDirection; qty:string|null; entry_price:number|null; current_price:number|null; stop_loss:number|null; take_profit:number|null; notional:number|null; planned_risk_usdt:number|null; risk_distance:number|null; risk_pct_of_entry:number|null; risk_reward:number|null; pnl:number|null; status:string; timeframe:string|null; opened_at:string|null; }
export interface CanonicalClosedTrade { trade_id:string; order_id:string|null; signal_id:string|null; symbol:string; mode:CanonicalTradingMode; direction:CanonicalTradeDirection; qty:string|null; entry_price:number|null; exit_price:number|null; stop_loss:number|null; take_profit:number|null; notional:number|null; planned_risk_usdt:number|null; risk_distance:number|null; risk_pct_of_entry:number|null; realized_pnl:number|null; pnl_multiple_of_risk:number|null; stop_slippage_usdt:number|null; risk_reward:number|null; result:string|null; status:string; close_reason:string|null; exit_analysis:string|null; operator_summary:string|null; timeframe:string|null; opened_at:string|null; closed_time:string|null; }

export interface CanonicalTodaySummary { total_open_trades:number; scalping_open_trades:number; intraday_open_trades:number; unknown_open_trades:number; closed_trades_today:number; system_mode:'demo'; }
export interface CanonicalActiveTradesData { today_summary:CanonicalTodaySummary; active_trades:CanonicalActiveTrade[]; scalping_trades:CanonicalActiveTrade[]; intraday_trades:CanonicalActiveTrade[]; unknown_trades:CanonicalActiveTrade[]; range_start:string|null; range_end:string|null; }
export interface JournalSummaryMetric { total_trades:number; wins:number; losses:number; win_rate:number|null; realized_pnl:number|null; average_risk_reward:number|null; }
export interface JournalSummaries { scalping:JournalSummaryMetric; intraday:JournalSummaryMetric; unknown:JournalSummaryMetric; combined:JournalSummaryMetric; }
export interface CanonicalJournalData { closed_trades:CanonicalClosedTrade[]; summaries:JournalSummaries; range_start:string|null; range_end:string|null; }

export interface DashboardAccountSummary { status:'connected'|'not_configured'|'unavailable'|string; equity:number|null; available_balance:number|null; }
export interface CanonicalDashboardTodaySummary {
  // These newer aggregate fields are optional while older backend payloads are
  // still supported. The always-present counters below remain authoritative.
  opened_trades_today?:number;
  active_trades_now?:number;
  total_open_trades:number;
  scalping_open_trades:number;
  intraday_open_trades:number;
  unknown_open_trades:number;
  closed_trades_today:number;
  wins_today:number;
  losses_today:number;
  breakeven_today?:number;
  win_rate_today:number|null;
  loss_rate_today?:number|null;
  unrealized_pnl:number|null;
  realized_pnl_today:number|null;
  average_risk_reward_today:number|null;
}
export interface DashboardEventRecord { event_type:string; message:string; created_at:string|null; }
export interface CanonicalDashboardData { system_status:string; system_mode:'demo'; active_strategy_mode:'scalping'|'intraday'; scalping_engine_enabled:boolean; intraday_engine_enabled:boolean; auto_trade_enabled:boolean; emergency_stop:boolean; account:DashboardAccountSummary; today_summary:CanonicalDashboardTodaySummary; recent_events:DashboardEventRecord[]; range_start:string|null; range_end:string|null; }
export interface DateTimeRange { start:string; end:string; }

export interface PerformanceSummaryMetric { total_trades:number; wins:number; losses:number; breakeven:number; realized_pnl:number|null; average_realized_pnl:number|null; win_rate:number|null; average_risk_reward:number|null; best_trade:number|null; worst_trade:number|null; stop_loss_hit_count:number; take_profit_hit_count:number; manual_close_count:number; emergency_stop_count:number; }
export interface PerformanceAnalysisData { trades:CanonicalClosedTrade[]; summaries:{scalping:PerformanceSummaryMetric; intraday:PerformanceSummaryMetric; unknown:PerformanceSummaryMetric; combined:PerformanceSummaryMetric}; strategies:string[]; statuses:string[]; exit_reasons:string[]; range_start:string|null; range_end:string|null; }
export interface PerformanceFilters { start?:string; end?:string; mode?:'scalping'|'intraday'|'unknown'; strategy?:string; status?:string; exitReason?:string; }
