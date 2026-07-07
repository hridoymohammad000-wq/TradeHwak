import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowDownUp, LoaderCircle, TrendingUp } from 'lucide-react';
import { backendApi } from '../../api/services';
import type { BybitMarketSnapshotData, ChartContextData, Timeframe, TradingMode } from '../../api/types';
import type { BackendStatus } from '../../App';
import { Badge, Button, EmptyState, PageHeader } from '../UIFoundation';

const timeframeOptions: Array<{ label: string; value: Timeframe }> = [
  { label: 'M1', value: 'M1' },
  { label: 'M5', value: 'M5' },
  { label: 'M15', value: 'M15' },
  { label: 'H1', value: 'H1' },
];

const modeOptions: Array<{ label: string; value: TradingMode }> = [
  { label: 'SCALPING', value: 'scalping' },
  { label: 'INTRADAY', value: 'intraday' },
];

function formatValue(value: number | null) {
  return value === null ? 'No Data' : value.toFixed(4);
}

export function ChartPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const [symbolInput, setSymbolInput] = useState('BTCUSDT');
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [mode, setMode] = useState<TradingMode>('scalping');
  const [timeframe, setTimeframe] = useState<Timeframe>('M15');
  const [chartContext, setChartContext] = useState<ChartContextData | null>(null);
  const [marketSnapshot, setMarketSnapshot] = useState<BybitMarketSnapshotData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [executionMessage, setExecutionMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadChartContext() {
      if (backendStatus !== 'healthy') {
        setChartContext(null);
        setMarketSnapshot(null);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        return;
      }
      try {
        setIsLoading(true);
        setError(null);
        setExecutionMessage(null);
        const [contextResponse, marketResponse] = await Promise.all([
          backendApi.getChartContext(
            {
              symbol: selectedSymbol,
              mode,
              timeframe,
            },
            controller.signal,
          ),
          backendApi.getBybitMarketSnapshot(selectedSymbol, controller.signal),
        ]);
        setChartContext(contextResponse.data);
        setMarketSnapshot(marketResponse.data);
      } catch (loadError) {
        setChartContext(null);
        setMarketSnapshot(null);
        setError(loadError instanceof Error ? loadError.message : 'Failed to load chart context');
      } finally {
        setIsLoading(false);
      }
    }

    void loadChartContext();
    return () => controller.abort();
  }, [backendStatus, mode, selectedSymbol, timeframe]);

  const indicatorSummary = useMemo(() => {
    if (!chartContext) {
      return [];
    }
    return [
      { label: 'EMA20', value: chartContext.indicator_context.ema20 },
      { label: 'EMA50', value: chartContext.indicator_context.ema50 },
      { label: 'EMA200', value: chartContext.indicator_context.ema200 },
      { label: 'RSI', value: chartContext.indicator_context.rsi },
    ];
  }, [chartContext]);

  const isPendingData = !chartContext || chartContext.chart_status === 'pending_data';
  const formatSnapshotValue = (value: number | null, digits = 4) =>
    value === null ? 'No Data' : value.toFixed(digits);

  const commitSelectedSymbol = () => {
    const nextSymbol = symbolInput.trim().toUpperCase();
    if (nextSymbol) {
      setSelectedSymbol(nextSymbol);
    }
  };

  async function handleManualTrade(direction: 'buy' | 'sell') {
    if (backendStatus !== 'healthy') {
      setError('Backend unavailable');
      return;
    }
    try {
      setIsExecuting(true);
      setError(null);
      setExecutionMessage(null);
      const response = await backendApi.executeManualTrade({
        symbol: selectedSymbol,
        direction,
        mode,
        timeframe,
      });
      setExecutionMessage(
        `${response.data.side} submitted: ${response.data.symbol} | Qty ${response.data.qty} | Order ${response.data.order_id || 'accepted'}`,
      );
    } catch (tradeError) {
      setError(tradeError instanceof Error ? tradeError.message : 'Failed to submit manual trade');
    } finally {
      setIsExecuting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Charting & Execution Workspace"
        description="Visual technical analysis combined with manual trade dispatch capabilities."
      />

      <div className="bg-slate-900/60 border border-slate-800/80 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 uppercase font-bold">Symbol:</span>
            <input
              value={symbolInput}
              onChange={(event) => setSymbolInput(event.target.value.toUpperCase())}
              onBlur={commitSelectedSymbol}
              className="px-3 py-1.5 w-32 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="hidden md:block h-6 w-px bg-slate-800"></div>

          <div className="flex items-center gap-2">
            <span className="text-slate-500 uppercase font-bold">Strategy:</span>
            <select
              className="px-3 py-1.5 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none focus:border-indigo-500"
              value={mode}
              onChange={(event) => setMode(event.target.value as TradingMode)}
            >
              {modeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="hidden md:block h-6 w-px bg-slate-800"></div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 uppercase font-bold mr-1">Interval:</span>
            <select
              className="px-3 py-1.5 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none focus:border-indigo-500"
              value={timeframe}
              onChange={(event) => setTimeframe(event.target.value as Timeframe)}
            >
              {timeframeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="gray">{chartContext?.chart_status || 'pending_data'}</Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={commitSelectedSymbol}
            disabled={isLoading}
            className="font-mono"
          >
            {isLoading ? <LoaderCircle size={14} className="animate-spin" /> : 'Reload'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-rose-900/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-300 font-sans flex items-center gap-2">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {executionMessage && (
        <div className="rounded border border-emerald-900/30 bg-emerald-950/10 px-4 py-3 text-sm text-emerald-300 font-sans">
          {executionMessage}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 flex flex-col justify-between bg-slate-950/60 border border-slate-800 rounded-lg p-5 min-h-[500px] relative overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 mb-4 font-mono gap-2">
            <div className="flex items-center gap-3">
              <span className="text-base font-bold text-slate-100 uppercase">
                {chartContext ? `${chartContext.symbol} Context` : 'No Chart Context Loaded'}
              </span>
            </div>

            <div className="text-xs text-slate-500 flex items-center gap-1.5 font-mono font-bold uppercase">
              <span className={`inline-block w-2 h-2 rounded-full ${isLoading ? 'bg-amber-500' : error ? 'bg-rose-500' : isPendingData ? 'bg-slate-700' : 'bg-emerald-500'}`}></span>
              {isLoading ? 'Loading' : error ? 'Unavailable' : isPendingData ? 'Pending Data' : 'Context Ready'}
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center items-center relative border border-dashed border-slate-800/60 p-4 rounded bg-slate-900/20">
            {isLoading ? (
              <EmptyState
                title="Loading chart context"
                description="Fetching backend chart state."
                icon={<LoaderCircle size={24} className="animate-spin" />}
                className="border-none bg-transparent"
              />
            ) : isPendingData ? (
              <div className="text-center p-6 space-y-4">
                <TrendingUp size={48} className="mx-auto text-slate-600" />
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider font-mono">Chart Workspace Placeholder</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto font-sans leading-relaxed">
                  Waiting for backend integration. No live price action, technical indicators, or real market data is available in the current foundation phase.
                </p>
              </div>
            ) : (
              <div className="w-full max-w-2xl space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {indicatorSummary.map((indicator) => (
                    <div key={indicator.label} className="rounded border border-slate-800 bg-slate-950/30 p-3">
                      <p className="text-[10px] uppercase text-slate-500 font-mono font-bold">{indicator.label}</p>
                      <p className="mt-2 text-sm text-slate-200 font-mono">{formatValue(indicator.value)}</p>
                    </div>
                  ))}
                </div>
                <div className="rounded border border-slate-800 bg-slate-950/30 p-4 text-xs font-mono space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Last Price</span>
                    <span className="text-slate-200 uppercase">{formatSnapshotValue(marketSnapshot?.last_price ?? null)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Bid / Ask</span>
                    <span className="text-slate-200 uppercase">
                      {formatSnapshotValue(marketSnapshot?.best_bid_price ?? null)} / {formatSnapshotValue(marketSnapshot?.best_ask_price ?? null)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Spread</span>
                    <span className="text-slate-200 uppercase">
                      {marketSnapshot?.spread_percent !== null && marketSnapshot?.spread_percent !== undefined
                        ? `${marketSnapshot.spread_percent.toFixed(4)}%`
                        : 'No Data'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Mode</span>
                    <span className="text-slate-200 uppercase">{chartContext?.mode}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Timeframe</span>
                    <span className="text-slate-200 uppercase">{chartContext?.timeframe || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 uppercase">Chart Status</span>
                    <span className="text-slate-200 uppercase">{chartContext?.chart_status}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-between items-center mt-4 pt-3 border-t border-slate-800 text-[10px] font-mono text-slate-500 uppercase font-bold">
            <span>Data Source: Backend Context</span>
            <span>Market Status: {chartContext?.chart_status || 'Unknown'}</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div className="space-y-5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono pb-2 border-b border-slate-800 flex items-center gap-2">
              <ArrowDownUp size={16} className="text-indigo-400" />
              Manual Trade Setup
            </h3>

            <div className="space-y-4 font-mono text-xs">
              <div>
                <label className="block text-[11px] text-slate-500 uppercase mb-1 font-bold">Entry Price (USDT)</label>
                <input
                  type="text"
                  value={formatValue(chartContext?.entry_price ?? null)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded font-bold focus:outline-none"
                  readOnly
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 uppercase mb-1 font-bold">Stop Loss (SL)</label>
                <input
                  type="text"
                  value={formatValue(chartContext?.stop_loss ?? null)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded font-bold focus:outline-none"
                  readOnly
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 uppercase mb-1 font-bold">Take Profit (TP)</label>
                <input
                  type="text"
                  value={formatValue(chartContext?.take_profit ?? null)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded font-bold focus:outline-none"
                  readOnly
                />
              </div>
              <div className="pt-3 border-t border-slate-800/50 space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500 font-bold uppercase">Risk/Reward</span>
                  <span className="text-slate-300 font-bold uppercase">{formatValue(chartContext?.risk_reward ?? null)}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500 font-bold uppercase">Mark Price</span>
                  <span className="text-slate-300 font-bold uppercase">{formatSnapshotValue(marketSnapshot?.mark_price ?? null)}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500 font-bold uppercase">24H Change</span>
                  <span className="text-slate-300 font-bold uppercase">
                    {marketSnapshot?.price_change_percent_24h !== null && marketSnapshot?.price_change_percent_24h !== undefined
                      ? `${(marketSnapshot.price_change_percent_24h * 100).toFixed(2)}%`
                      : 'No Data'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-800 space-y-3">
            <Button
              variant="outline"
              className="w-full py-2.5 font-mono font-bold uppercase tracking-wider text-xs"
              disabled={isLoading || isExecuting || !marketSnapshot}
              onClick={() => {
                void handleManualTrade('buy');
              }}
            >
              {isExecuting ? <LoaderCircle size={14} className="animate-spin" /> : null}
              Execute Long
            </Button>
            <Button
              variant="outline"
              className="w-full py-2.5 font-mono font-bold uppercase tracking-wider text-xs"
              disabled={isLoading || isExecuting || !marketSnapshot}
              onClick={() => {
                void handleManualTrade('sell');
              }}
            >
              {isExecuting ? <LoaderCircle size={14} className="animate-spin" /> : null}
              Execute Short
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
