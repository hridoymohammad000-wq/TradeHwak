export interface Signal {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT" | "BUY" | "SELL";
  grade: "A+" | "A" | "B+" | "REJECTED" | "WAITING" | "UNKNOWN" | string;
  trend1H: string;
  setup15M: string;
  entry5M: string;
  entryPrice: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  riskReward?: number | null;
  score?: number | null;
  reason: string;
  status: string;
  createdAt: string;
  updatedAt?: string;
}

export interface Trade {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT" | "BUY" | "SELL";
  grade?: string;
  entryPrice: number;
  currentPrice?: number;
  exitPrice?: number;
  quantity?: number;
  size?: number;
  pnl?: number; // legacy or generic
  grossPnl?: number;
  fees?: number;
  netPnl?: number;
  pnlPercentage?: number;
  status: "OPEN" | "CLOSED" | string;
  result?: "WIN" | "LOSS" | "BREAKEVEN" | "UNKNOWN" | string;
  reason?: string;
  openTime: string;
  closeTime?: string;
  tp?: number;
  sl?: number;
}

export interface PerformanceStats {
  totalTrades: number;
  winRate: number;
  totalPnl: number;
  dailyPnl: number;
  accountBalance: number;
  drawdown: number;
}

export interface Settings {
  riskPerTrade?: number;
  maxDailyLoss?: number;
  defaultLeverage?: number;
  maxOpenPositions?: number;
  dailyMaxTrades?: number;
  allowedSignalGrades?: string[];
  telegramStatus?: string;
  emailStatus?: string;
}

export interface BotStatus {
  isRunning: boolean;
  isDemo: boolean;
  backendStatus: "ONLINE" | "OFFLINE" | "ERROR";
  bybitStatus: "CONNECTED" | "DISCONNECTED" | "ERROR";
}

export interface DashboardData {
  stats: PerformanceStats;
  recentSignals: Signal[];
  activeTrades: Trade[];
}
