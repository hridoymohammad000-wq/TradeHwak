export type RuntimeMode = 'demo' | 'live';
export type TradingMode = 'scalping' | 'intraday';
export type Direction = 'buy' | 'sell';
export type SignalGrade = 'A+' | 'A' | 'B+' | 'B';
export type Timeframe = 'M1' | 'M5' | 'M15' | 'H1';
export type SystemStatus = 'pending_integration';
export type ChartStatus = 'pending_data' | 'context_ready';

export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface HealthData {
  status: string;
  app: string;
  phase: string;
  execution_enabled: boolean;
}

export interface ModeData {
  system_mode: RuntimeMode;
  available_system_modes: RuntimeMode[];
  active_strategy_mode: TradingMode;
  available_strategy_modes: TradingMode[];
}

export interface DashboardTodaySummary {
  total_open_trades: number;
  closed_trades_today: number;
}

export interface DashboardEvent {
  event_type: string;
  message: string;
  created_at: string | null;
}

export interface DashboardSummaryData {
  system_status: SystemStatus;
  system_mode: RuntimeMode;
  active_strategy_mode: TradingMode;
  scalping_engine_enabled: boolean;
  intraday_engine_enabled: boolean;
  auto_trade_enabled: boolean;
  emergency_stop: boolean;
  today_summary: DashboardTodaySummary;
  recent_events: DashboardEvent[];
}

export interface NotificationSettings {
  telegram: boolean;
  email: boolean;
  chime: boolean;
  toast: boolean;
}

export interface SystemSettingsSection {
  system_mode: RuntimeMode;
}

export interface StrategySettingsSection {
  active_strategy_mode: TradingMode;
  allowed_signal_grades: SignalGrade[];
}

export interface RiskSettingsSection {
  daily_max_loss: number;
  daily_max_trades: number;
  risk_per_trade_pct: number;
  max_open_positions: number;
}

export interface EngineControlSection {
  scalping_engine_enabled: boolean;
  intraday_engine_enabled: boolean;
}

export interface ExecutionControlSection {
  auto_trade_enabled: boolean;
  emergency_stop: boolean;
}

export interface SettingsViewData {
  system: SystemSettingsSection;
  strategy: StrategySettingsSection;
  risk: RiskSettingsSection;
  notifications: NotificationSettings;
  engine_control: EngineControlSection;
  execution_control: ExecutionControlSection;
}

export interface SettingsUpdatePayload {
  system_mode?: RuntimeMode;
  active_strategy_mode?: TradingMode;
  scalping_engine_enabled?: boolean;
  intraday_engine_enabled?: boolean;
  auto_trade_enabled?: boolean;
  emergency_stop?: boolean;
  daily_max_loss?: number;
  daily_max_trades?: number;
  risk_per_trade_pct?: number;
  max_open_positions?: number;
  allowed_signal_grades?: SignalGrade[];
  notifications?: Partial<NotificationSettings>;
}

export interface EngineControlPayload {
  scalping_engine_enabled?: boolean;
  intraday_engine_enabled?: boolean;
  auto_trade_enabled?: boolean;
  emergency_stop?: boolean;
}

export interface EngineControlState {
  scalping_engine_enabled: boolean;
  intraday_engine_enabled: boolean;
  auto_trade_enabled: boolean;
  emergency_stop: boolean;
}

export interface ActiveTradesTodaySummary {
  total_open_trades: number;
  scalping_open_trades: number;
  intraday_open_trades: number;
  closed_trades_today: number;
  system_mode: RuntimeMode;
}

export interface ActiveTradeRecord {
  symbol: string;
  mode: TradingMode;
  direction: Direction;
  qty: string | null;
  entry_price: number | null;
  current_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  notional: number | null;
  planned_risk_usdt: number | null;
  risk_reward: number | null;
  pnl: number | null;
  status: string;
  timeframe: Timeframe | null;
  opened_at: string | null;
}

export interface ClosedTradeRecord {
  symbol: string;
  mode: TradingMode;
  direction: Direction;
  qty: string | null;
  entry_price: number | null;
  exit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  notional: number | null;
  planned_risk_usdt: number | null;
  realized_pnl: number | null;
  risk_reward: number | null;
  result: string | null;
  status: string;
  close_reason: string | null;
  exit_analysis: string | null;
  timeframe: Timeframe | null;
  closed_time: string | null;
}

export interface ActiveTradesData {
  today_summary: ActiveTradesTodaySummary;
  scalping_trades: ActiveTradeRecord[];
  intraday_trades: ActiveTradeRecord[];
}

export interface ClosedTradesData {
  closed_trades: ClosedTradeRecord[];
}

export interface ManualTradePayload {
  symbol: string;
  direction: Direction;
  mode: TradingMode;
  timeframe?: Timeframe;
  stop_loss?: number;
  take_profit?: number;
}

export interface ManualTradeData {
  status: string;
  order_id: string | null;
  symbol: string;
  side: string;
  qty: string;
  market_price: number;
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  notional: number;
}

export interface BackendConnectionInfo {
  baseUrl: string;
  host: string;
  port: string;
}

export interface BybitConfigStatusData {
  environment: string;
  base_url: string;
  api_key_configured: boolean;
  api_secret_configured: boolean;
  configured: boolean;
}

export interface BybitConnectionStatusData {
  code: string;
  status: string;
  detail: string;
  equity: string | null;
  available_balance: string | null;
  fetched_at: string | null;
}

export interface BybitMarketServiceStatus {
  status: string;
  code: string | null;
  detail: string | null;
  count: number | null;
}

export interface BybitMarketTestData {
  symbol: string;
  tested_at: string;
  all_passed: boolean;
  services: Record<string, BybitMarketServiceStatus>;
}

export interface BybitMarketSnapshotData {
  symbol: string;
  last_price: number | null;
  mark_price: number | null;
  index_price: number | null;
  price_change_percent_24h: number | null;
  volume_24h: number | null;
  turnover_24h: number | null;
  best_bid_price: number | null;
  best_ask_price: number | null;
  spread: number | null;
  spread_percent: number | null;
  fetched_at: string | null;
}

export interface ScanRequestPayload {
  mode?: TradingMode;
  symbols?: string[];
  timeframe?: Timeframe;
  direction?: Direction;
  grade?: SignalGrade;
}

export interface ScanResult {
  symbol: string;
  mode: TradingMode;
  timeframe: Timeframe | null;
  direction: Direction | null;
  grade: SignalGrade | null;
  reason: string | null;
}

export interface ScanData {
  mode: TradingMode;
  timeframe: Timeframe | null;
  results: ScanResult[];
}

export interface SignalItem {
  signal_id: string;
  symbol: string;
  direction: Direction;
  grade: SignalGrade;
  mode: TradingMode;
  timeframe: Timeframe;
  status: string;
  entry_price: number | null;
  current_price: number | null;
}

export interface SignalFilters {
  mode: TradingMode;
  grade: SignalGrade | null;
  symbol: string | null;
  timeframe: Timeframe | null;
}

export interface SignalsData {
  filters: SignalFilters;
  signals: SignalItem[];
}

export interface IndicatorContext {
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
  rsi: number | null;
}

export interface ChartContextData {
  symbol: string;
  mode: TradingMode;
  timeframe: Timeframe | null;
  chart_status: ChartStatus;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward: number | null;
  indicator_context: IndicatorContext;
}

export interface WorkflowSignalSnapshot {
  symbol: string;
  direction: string;
  grade: string;
  timeframe: string;
  reason: string;
}

export interface WorkflowOrderSnapshot {
  symbol: string;
  side: string;
  qty: string;
  order_id: string | null;
  status: string;
}

export interface WorkflowStatusData {
  backend_health: string;
  selected_mode: TradingMode;
  scanner_status: string;
  signal_status: string;
  execution_status: string;
  auto_trade_enabled: boolean;
  bybit_connection_code: string;
  active_trade_count: number;
  daily_trade_count: number;
  candidate_signal: WorkflowSignalSnapshot | null;
  last_order: WorkflowOrderSnapshot | null;
  last_reject_reason: string | null;
  last_cycle_at: string | null;
}
