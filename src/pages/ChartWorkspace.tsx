import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
} from 'lightweight-charts';
import { Activity, AlertTriangle, BarChart3, LineChart, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';
import { fetchChartContext, ApiError } from '../api/client';
import { AssetTicker, BackendTimeframe, ChartContextData, TradingMode } from '../api/types';
import { useApp } from '../context/AppContext';

const symbols: AssetTicker[] = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT'];
const framesByMode: Record<TradingMode, BackendTimeframe[]> = {
  scalping: ['M1', 'M5'],
  intraday: ['M15', 'H1'],
};

function formatMetric(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return 'N/A';
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function ChartWorkspace() {
  const { selectedSymbol, setSelectedSymbol, dashboardData } = useApp();
  const activeMode = dashboardData?.active_strategy_mode ?? 'scalping';
  const [mode, setMode] = useState<TradingMode>(activeMode);
  const [timeframe, setTimeframe] = useState<BackendTimeframe>(activeMode === 'scalping' ? 'M5' : 'M15');
  const [data, setData] = useState<ChartContextData | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'empty' | 'unauthorized' | 'disconnected' | 'timeout' | 'error'>('loading');
  const [error, setError] = useState('');
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volume = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema20 = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50 = useRef<ISeriesApi<'Line'> | null>(null);
  const ema200 = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    setMode(activeMode);
    setTimeframe(activeMode === 'scalping' ? 'M5' : 'M15');
  }, [activeMode]);

  const allowedFrames = framesByMode[mode];

  const load = async () => {
    setState('loading');
    setError('');
    try {
      const result = await fetchChartContext(selectedSymbol.replace('/', ''), mode, timeframe);
      setData(result);
      setState(result.candles.length > 0 ? 'ready' : 'empty');
    } catch (requestError) {
      setData(null);
      setError(requestError instanceof Error ? requestError.message : 'Chart request failed');
      if (requestError instanceof ApiError) {
        setState(
          requestError.kind === 'unauthorized'
            ? 'unauthorized'
            : requestError.kind === 'timeout'
              ? 'timeout'
              : requestError.kind === 'network' || requestError.kind === 'configuration'
                ? 'disconnected'
                : 'error',
        );
      } else {
        setState('error');
      }
    }
  };

  useEffect(() => { void load(); }, [selectedSymbol, mode, timeframe]);

  useEffect(() => {
    if (!container.current) return;
    const instance = createChart(container.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#080c14' },
        textColor: '#94a3b8',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: 'rgba(30,41,59,.34)' },
        horzLines: { color: 'rgba(30,41,59,.34)' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.08, bottom: 0.24 } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#1e293b', rightOffset: 5 },
      autoSize: true,
    });

    chart.current = instance;
    candles.current = instance.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#f43f5e',
      wickUpColor: '#22c55e',
      wickDownColor: '#f43f5e',
      borderVisible: false,
    });
    ema20.current = instance.addSeries(LineSeries, { color: '#22d3ee', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    ema50.current = instance.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    ema200.current = instance.addSeries(LineSeries, { color: '#a78bfa', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    volume.current = instance.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
    });
    instance.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    return () => {
      instance.remove();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    if (!data || !candles.current || !volume.current || data.candles.length === 0) return;
    const rows = data.candles.map((item) => ({
      time: Math.floor(item.open_time / 1000) as never,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));
    candles.current.setData(rows);
    volume.current.setData(data.candles.map((item) => ({
      time: Math.floor(item.open_time / 1000) as never,
      value: item.volume ?? 0,
      color: item.close >= item.open ? 'rgba(34,197,94,.42)' : 'rgba(244,63,94,.42)',
    })));

    const lastTime = rows.at(-1)?.time;
    if (lastTime) {
      const indicators = data.indicator_context;
      const points = (value: number | null | undefined) => value == null ? [] : [
        { time: rows[0].time, value },
        { time: lastTime, value },
      ];
      ema20.current?.setData(points(indicators.ema20));
      ema50.current?.setData(points(indicators.ema50));
      ema200.current?.setData(points(indicators.ema200));
    }
    chart.current?.timeScale().fitContent();
  }, [data]);

  const statusText = {
    loading: 'Loading real chart data…',
    empty: 'Real closed candles are unavailable from the canonical backend.',
    unauthorized: 'Unauthorized session.',
    disconnected: 'Backend disconnected.',
    timeout: 'Chart request timed out.',
    error: 'Backend error.',
    ready: '',
  }[state];

  const trend = useMemo(() => {
    const indicators = data?.indicator_context;
    if (!indicators?.ema20 || !indicators?.ema50) return 'Neutral';
    return indicators.ema20 > indicators.ema50 ? 'Bullish' : 'Bearish';
  }, [data]);

  const rsiLabel = useMemo(() => {
    const rsi = data?.indicator_context.rsi;
    if (rsi == null) return 'N/A';
    if (rsi >= 70) return 'Overbought';
    if (rsi <= 30) return 'Oversold';
    return 'Balanced';
  }, [data]);

  const onModeChange = (nextMode: TradingMode) => {
    setMode(nextMode);
    setTimeframe(nextMode === 'scalping' ? 'M5' : 'M15');
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 to-slate-900/70 p-5 shadow-lg shadow-black/10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="rounded-lg bg-emerald-500/10 p-2"><LineChart className="h-5 w-5 text-emerald-400" /></div>
              <div>
                <h1 className="text-xl font-black text-white">Chart Workspace</h1>
                <p className="text-xs text-slate-400">Closed-candle market structure with deterministic indicators.</p>
              </div>
            </div>
          </div>
          <button onClick={() => void load()} disabled={state === 'loading'} className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-white transition hover:border-emerald-500/50 disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${state === 'loading' ? 'animate-spin' : ''}`} />Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Last close</div><div className="mt-2 text-xl font-black text-white">{formatMetric(data?.last_price, 8)}</div></div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Trend</div><div className={`mt-2 flex items-center gap-2 text-xl font-black ${trend === 'Bullish' ? 'text-emerald-400' : trend === 'Bearish' ? 'text-rose-400' : 'text-slate-300'}`}>{trend === 'Bullish' ? <TrendingUp size={20} /> : trend === 'Bearish' ? <TrendingDown size={20} /> : <Activity size={20} />}{trend}</div></div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">RSI state</div><div className="mt-2 text-xl font-black text-white">{rsiLabel}</div></div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Context</div><div className="mt-2 text-xl font-black capitalize text-white">{mode} · {timeframe}</div></div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-xl shadow-black/10">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 bg-slate-900/95 p-3">
          <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value as AssetTicker)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-white">
            {symbols.map((symbol) => <option key={symbol}>{symbol}</option>)}
          </select>
          <select value={mode} onChange={(event) => onModeChange(event.target.value as TradingMode)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-white">
            <option value="scalping">Scalping</option><option value="intraday">Intraday</option>
          </select>
          <div className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950 p-1">
            {allowedFrames.map((frame) => (
              <button key={frame} onClick={() => setTimeframe(frame)} className={`rounded-md px-3 py-1.5 text-xs font-bold transition ${timeframe === frame ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-white'}`}>{frame}</button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-4 text-[11px] text-slate-400">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-cyan-400" />EMA20</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" />EMA50</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-violet-400" />EMA200</span>
          </div>
        </div>

        {state !== 'ready' && (
          <div className="flex h-[440px] flex-col items-center justify-center px-6 text-center text-sm text-slate-400">
            {state === 'empty' && <AlertTriangle className="mb-3 h-7 w-7 text-amber-400" />}
            <span>{statusText}</span>
            {error && <span className="mt-2 text-rose-400">{error}</span>}
          </div>
        )}
        <div ref={container} className={state === 'ready' ? 'h-[440px]' : 'hidden'} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[
          ['EMA20', data?.indicator_context.ema20, 'text-cyan-300'],
          ['EMA50', data?.indicator_context.ema50, 'text-amber-300'],
          ['EMA200', data?.indicator_context.ema200, 'text-violet-300'],
          ['RSI', data?.indicator_context.rsi, 'text-white'],
          ['MACD', data?.indicator_context.macd, 'text-white'],
          ['Signal', data?.indicator_context.macd_signal, 'text-white'],
        ].map(([label, metric, className]) => (
          <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</div><BarChart3 className="h-3.5 w-3.5 text-slate-600" /></div>
            <div className={`mt-2 text-sm font-black ${className}`}>{state === 'ready' ? formatMetric(metric as number | null | undefined, 8) : 'N/A'}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
