import { getRequest, postRequest } from './client';
import type {
  ActiveTradesData,
  BybitConfigStatusData,
  BybitConnectionStatusData,
  BybitMarketSnapshotData,
  BybitMarketTestData,
  ChartContextData,
  ClosedTradesData,
  DashboardSummaryData,
  EngineControlPayload,
  EngineControlState,
  HealthData,
  ManualTradeData,
  ManualTradePayload,
  ModeData,
  ScanData,
  ScanRequestPayload,
  SettingsUpdatePayload,
  SettingsViewData,
  SignalGrade,
  SignalsData,
  Timeframe,
  TradingMode,
  WorkflowStatusData,
} from './types';

export const backendApi = {
  getHealth(signal?: AbortSignal) {
    return getRequest<HealthData>('/health', { signal });
  },
  getBybitConfigStatus(signal?: AbortSignal) {
    return getRequest<BybitConfigStatusData>('/bybit/config-status', { signal });
  },
  getBybitConnection(signal?: AbortSignal) {
    return getRequest<BybitConnectionStatusData>('/bybit/connection', { signal });
  },
  testBybitConnection(signal?: AbortSignal) {
    return postRequest<BybitConnectionStatusData>('/bybit/test-connection', { signal });
  },
  getBybitMarketTest(symbol: string, signal?: AbortSignal) {
    return getRequest<BybitMarketTestData>('/market/test', {
      query: { symbol },
      signal,
    });
  },
  getBybitMarketSnapshot(symbol: string, signal?: AbortSignal) {
    return getRequest<BybitMarketSnapshotData>('/market/snapshot', {
      query: { symbol },
      signal,
    });
  },
  getMode(signal?: AbortSignal) {
    return getRequest<ModeData>('/mode', { signal });
  },
  getDashboardSummary(signal?: AbortSignal) {
    return getRequest<DashboardSummaryData>('/dashboard-summary', { signal });
  },
  getSettingsView(signal?: AbortSignal) {
    return getRequest<SettingsViewData>('/settings/view', { signal });
  },
  updateSettings(body: SettingsUpdatePayload, signal?: AbortSignal) {
    return postRequest<SettingsViewData>('/settings', { body, signal });
  },
  updateEngineControl(body: EngineControlPayload, signal?: AbortSignal) {
    return postRequest<EngineControlState>('/engine/control', { body, signal });
  },
  getActiveTrades(signal?: AbortSignal) {
    return getRequest<ActiveTradesData>('/active-trades', { signal });
  },
  getClosedTrades(signal?: AbortSignal) {
    return getRequest<ClosedTradesData>('/closed-trades', { signal });
  },
  executeManualTrade(body: ManualTradePayload, signal?: AbortSignal) {
    return postRequest<ManualTradeData>('/trade/manual', { body, signal });
  },
  scanMarket(body: ScanRequestPayload, signal?: AbortSignal) {
    return postRequest<ScanData>('/scan', { body, signal });
  },
  getSignals(
    query: {
      mode?: TradingMode;
      grade?: SignalGrade;
      symbol?: string;
      timeframe?: Timeframe;
    },
    signal?: AbortSignal,
  ) {
    return getRequest<SignalsData>('/signals', { query, signal });
  },
  getChartContext(
    query: {
      symbol: string;
      mode: TradingMode;
      timeframe?: Timeframe;
    },
    signal?: AbortSignal,
  ) {
    return getRequest<ChartContextData>('/chart-context', { query, signal });
  },
  getWorkflowStatus(signal?: AbortSignal) {
    return getRequest<WorkflowStatusData>('/workflow/status', { signal });
  },
};
