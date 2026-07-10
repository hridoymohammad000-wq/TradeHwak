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
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Crosshair,
  Expand,
  Eye,
  LineChart,
  Lock,
  Magnet,
  MousePointer2,
  Pencil,
  RefreshCw,
  Ruler,
  Search,
  Settings,
  Trash2,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
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

function emaSeries(values: number[], period: number): Array<number | null> {
  const result: Array<number | null> = Array(values.length).fill(null);
  if (values.length < period) return result;
  const multiplier = 2 / (period + 1);
  let current = values.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period - 1] = current;
  for (let index = period; index < values.length; index += 1) {
    current = (values[index] - current) * multiplier + current;
    result[index] = current;
  }
  return result;
}

function rsiSeries(values: number[], period = 14): Array<number | null> {
  const result: Array<number | null> = Array(values.length).fill(null);
  if (values.length <= period) return result;
  let gain = 0;
  let loss = 0;
  for (let index = 1; index <= period; index += 1) {
    const delta = values[index] - values[index - 1];
    gain += Math.max(delta, 0);
    loss += Math.abs(Math.min(delta, 0));
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  result[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let index = period + 1; index < values.length; index += 1) {
    const delta = values[index] - values[index - 1];
    avgGain = ((avgGain * (period - 1)) + Math.max(delta, 0)) / period;
    avgLoss = ((avgLoss * (period - 1)) + Math.abs(Math.min(delta, 0))) / period;
    result[index] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return result;
}

function macdSeries(values: number[]) {
  const fast = emaSeries(values, 12);
  const slow = emaSeries(values, 26);
  const macd: Array<number | null> = values.map((_, index) =>
    fast[index] != null && slow[index] != null ? (fast[index] as number) - (slow[index] as number) : null,
  );
  const compact = macd.filter((value): value is number => value != null);
  const compactSignal = emaSeries(compact, 9);
  const signal: Array<number | null> = Array(values.length).fill(null);
  let compactIndex = 0;
  macd.forEach((value, index) => {
    if (value != null) {
      signal[index] = compactSignal[compactIndex] ?? null;
      compactIndex += 1;
    }
  });
  const histogram = macd.map((value, index) => value != null && signal[index] != null ? value - (signal[index] as number) : null);
  return { macd, signal, histogram };
}

export default function ChartWorkspace() {
  const { selectedSymbol, setSelectedSymbol, dashboardData } = useApp();
  const activeMode = dashboardData?.active_strategy_mode ?? 'scalping';
  const [mode, setMode] = useState<TradingMode>(activeMode);
  const [timeframe, setTimeframe] = useState<BackendTimeframe>(activeMode === 'scalping' ? 'M5' : 'M15');
  const [data, setData] = useState<ChartContextData | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'empty' | 'unauthorized' | 'disconnected' | 'timeout' | 'error'>('loading');
  const [error, setError] = useState('');
  const [symbolSearch, setSymbolSearch] = useState('');

  const mainContainer = useRef<HTMLDivElement>(null);
  const rsiContainer = useRef<HTMLDivElement>(null);
  const macdContainer = useRef<HTMLDivElement>(null);
  const charts = useRef<IChartApi[]>([]);
  const candleSeries = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeries = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema20Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const ema200Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsi70Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const rsi30Ref = useRef<ISeriesApi<'Line'> | null>(null);
  const macdRef = useRef<ISeriesApi<'Line'> | null>(null);
  const signalRef = useRef<ISeriesApi<'Line'> | null>(null);
  const histogramRef = useRef<ISeriesApi<'Histogram'> | null>(null);

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
    if (!mainContainer.current || !rsiContainer.current || !macdContainer.current) return;
    const common = {
      layout: { background: { type: ColorType.Solid as const, color: '#080b10' }, textColor: '#94a3b8', attributionLogo: false },
      grid: { vertLines: { color: 'rgba(30,41,59,.30)' }, horzLines: { color: 'rgba(30,41,59,.30)' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#1e293b', rightOffset: 4 },
      autoSize: true,
    };

    const main = createChart(mainContainer.current, {
      ...common,
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.07, bottom: 0.22 } },
    });
    const rsi = createChart(rsiContainer.current, common);
    const macd = createChart(macdContainer.current, common);
    charts.current = [main, rsi, macd];

    candleSeries.current = main.addSeries(CandlestickSeries, {
      upColor: '#14b8a6', downColor: '#f43f5e', wickUpColor: '#14b8a6', wickDownColor: '#f43f5e', borderVisible: false,
    });
    ema20Ref.current = main.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    ema50Ref.current = main.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    ema200Ref.current = main.addSeries(LineSeries, { color: '#a78bfa', lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    volumeSeries.current = main.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false });
    main.priceScale('volume').applyOptions({ scaleMargins: { top: 0.80, bottom: 0 } });

    rsiRef.current = rsi.addSeries(LineSeries, { color: '#a78bfa', lineWidth: 2, priceLineVisible: false });
    rsi70Ref.current = rsi.addSeries(LineSeries, { color: 'rgba(148,163,184,.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    rsi30Ref.current = rsi.addSeries(LineSeries, { color: 'rgba(148,163,184,.55)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });

    macdRef.current = macd.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 2, priceLineVisible: false });
    signalRef.current = macd.addSeries(LineSeries, { color: '#f97316', lineWidth: 2, priceLineVisible: false });
    histogramRef.current = macd.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false });

    const sync = (source: IChartApi, targets: IChartApi[]) => {
      source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return;
        targets.forEach((target) => target.timeScale().setVisibleLogicalRange(range));
      });
    };
    sync(main, [rsi, macd]);
    sync(rsi, [main, macd]);
    sync(macd, [main, rsi]);

    return () => {
      charts.current.forEach((item) => item.remove());
      charts.current = [];
    };
  }, []);

  useEffect(() => {
    if (!data || data.candles.length === 0 || !candleSeries.current) return;
    const candles = data.candles;
    const times = candles.map((item) => Math.floor(item.open_time / 1000) as never);
    const closes = candles.map((item) => item.close);
    const ema20 = emaSeries(closes, 20);
    const ema50 = emaSeries(closes, 50);
    const ema200 = emaSeries(closes, 200);
    const rsi = rsiSeries(closes);
    const macd = macdSeries(closes);

    candleSeries.current.setData(candles.map((item, index) => ({ time: times[index], open: item.open, high: item.high, low: item.low, close: item.close })));
    volumeSeries.current?.setData(candles.map((item, index) => ({
      time: times[index], value: item.volume ?? 0, color: item.close >= item.open ? 'rgba(20,184,166,.50)' : 'rgba(244,63,94,.50)',
    })));

    const lineData = (values: Array<number | null>) => values.flatMap((value, index) => value == null ? [] : [{ time: times[index], value }]);
    ema20Ref.current?.setData(lineData(ema20));
    ema50Ref.current?.setData(lineData(ema50));
    ema200Ref.current?.setData(lineData(ema200));
    rsiRef.current?.setData(lineData(rsi));
    rsi70Ref.current?.setData(times.map((time) => ({ time, value: 70 })));
    rsi30Ref.current?.setData(times.map((time) => ({ time, value: 30 })));
    macdRef.current?.setData(lineData(macd.macd));
    signalRef.current?.setData(lineData(macd.signal));
    histogramRef.current?.setData(macd.histogram.flatMap((value, index) => value == null ? [] : [{
      time: times[index], value, color: value >= 0 ? 'rgba(45,212,191,.75)' : 'rgba(251,113,133,.75)',
    }]));

    charts.current.forEach((item) => item.timeScale().fitContent());
  }, [data]);

  const statusText = {
    loading: 'Loading real chart data…', empty: 'Real closed candles are unavailable from the canonical backend.', unauthorized: 'Unauthorized session.',
    disconnected: 'Backend disconnected.', timeout: 'Chart request timed out.', error: 'Backend error.', ready: '',
  }[state];

  const trend = useMemo(() => {
    const indicators = data?.indicator_context;
    if (!indicators?.ema20 || !indicators?.ema50) return 'Neutral';
    return indicators.ema20 > indicators.ema50 ? 'Bullish' : 'Bearish';
  }, [data]);

  const filteredSymbols = symbols.filter((symbol) => symbol.toLowerCase().includes(symbolSearch.toLowerCase()));

  const onModeChange = (nextMode: TradingMode) => {
    setMode(nextMode);
    setTimeframe(nextMode === 'scalping' ? 'M5' : 'M15');
  };

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-[#080b10] shadow-2xl shadow-black/30">
      <div className="flex min-h-[760px]">
        <aside className="hidden w-12 shrink-0 flex-col items-center gap-2 border-r border-slate-800 bg-[#0d1118] py-3 lg:flex">
          {[MousePointer2, Crosshair, Pencil, Ruler, Magnet, Lock, Eye, Trash2].map((Icon, index) => (
            <button key={index} className="rounded-md p-2 text-slate-500 transition hover:bg-slate-800 hover:text-white"><Icon size={17} /></button>
          ))}
        </aside>

        <section className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 bg-[#0d1118] p-2">
            <select value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value as AssetTicker)} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-white">
              {symbols.map((symbol) => <option key={symbol}>{symbol}</option>)}
            </select>
            <select value={mode} onChange={(event) => onModeChange(event.target.value as TradingMode)} className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-white">
              <option value="scalping">Scalping</option><option value="intraday">Intraday</option>
            </select>
            <div className="flex rounded border border-slate-700 bg-slate-950 p-1">
              {allowedFrames.map((frame) => <button key={frame} onClick={() => setTimeframe(frame)} className={`rounded px-3 py-1.5 text-xs font-bold ${timeframe === frame ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-white'}`}>{frame}</button>)}
            </div>
            <div className="hidden items-center gap-2 border-l border-slate-700 pl-3 text-xs text-slate-400 md:flex"><BarChart3 size={15} /> Indicators</div>
            <div className="ml-auto flex items-center gap-1">
              <button onClick={() => void load()} disabled={state === 'loading'} className="rounded p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><RefreshCw size={16} className={state === 'loading' ? 'animate-spin' : ''} /></button>
              <button className="rounded p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><Settings size={16} /></button>
              <button className="rounded p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><Expand size={16} /></button>
            </div>
          </div>

          {state !== 'ready' ? (
            <div className="flex h-[650px] flex-col items-center justify-center px-6 text-center text-sm text-slate-400">
              {state === 'empty' && <AlertTriangle className="mb-3 h-7 w-7 text-amber-400" />}
              <span>{statusText}</span>{error && <span className="mt-2 text-rose-400">{error}</span>}
            </div>
          ) : (
            <>
              <div className="relative border-b border-slate-800">
                <div className="absolute left-3 top-3 z-10 rounded bg-black/40 px-2 py-1 text-[11px] text-slate-300 backdrop-blur">
                  <b className="text-white">{selectedSymbol}</b> · {timeframe} · Close {formatMetric(data?.last_price, 8)}
                  <div className="mt-1 flex gap-3 text-[10px]"><span className="text-sky-400">EMA20</span><span className="text-amber-400">EMA50</span><span className="text-violet-400">EMA200</span></div>
                </div>
                <div ref={mainContainer} className="h-[390px]" />
              </div>
              <div className="relative border-b border-slate-800">
                <div className="absolute left-3 top-2 z-10 text-[11px] font-bold text-slate-400">RSI 14 <span className="ml-2 text-violet-300">{formatMetric(data?.indicator_context.rsi)}</span></div>
                <div ref={rsiContainer} className="h-[145px]" />
              </div>
              <div className="relative">
                <div className="absolute left-3 top-2 z-10 text-[11px] font-bold text-slate-400">MACD 12 26 9 <span className="ml-2 text-sky-300">{formatMetric(data?.indicator_context.macd)}</span> <span className="ml-2 text-orange-300">{formatMetric(data?.indicator_context.macd_signal)}</span></div>
                <div ref={macdContainer} className="h-[165px]" />
              </div>
            </>
          )}

          <div className="flex items-center gap-2 border-t border-slate-800 bg-[#0d1118] px-3 py-2 text-[11px] text-slate-500">
            <span className="font-bold text-white">{selectedSymbol}</span><span>•</span><span className={trend === 'Bullish' ? 'text-emerald-400' : trend === 'Bearish' ? 'text-rose-400' : ''}>{trend}</span><span>•</span><span>Closed candles only</span><span className="ml-auto">Bybit Demo market data</span>
          </div>
        </section>

        <aside className="hidden w-64 shrink-0 border-l border-slate-800 bg-[#0d1118] xl:block">
          <div className="border-b border-slate-800 p-3"><div className="mb-3 flex items-center justify-between"><span className="text-sm font-black text-white">Market List</span><Activity size={16} className="text-emerald-400" /></div><div className="relative"><Search size={14} className="absolute left-3 top-2.5 text-slate-600" /><input value={symbolSearch} onChange={(event) => setSymbolSearch(event.target.value)} placeholder="Search symbol" className="w-full rounded border border-slate-700 bg-slate-950 py-2 pl-8 pr-2 text-xs" /></div></div>
          <div className="divide-y divide-slate-800">
            {filteredSymbols.map((symbol) => (
              <button key={symbol} onClick={() => setSelectedSymbol(symbol)} className={`flex w-full items-center justify-between px-3 py-3 text-left transition hover:bg-slate-800/60 ${symbol === selectedSymbol ? 'bg-emerald-500/10' : ''}`}>
                <div><div className="text-xs font-bold text-white">{symbol}</div><div className="mt-1 text-[10px] uppercase text-slate-500">USDT perpetual</div></div>
                <div className="text-right"><div className="text-[10px] font-bold uppercase text-slate-500">{mode}</div>{symbol === selectedSymbol && <div className="mt-1 text-[10px] text-emerald-400">Selected</div>}</div>
              </button>
            ))}
          </div>
          <div className="border-t border-slate-800 p-3">
            <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Current context</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded bg-slate-950 p-2"><span className="text-slate-500">Last</span><div className="mt-1 font-bold text-white">{formatMetric(data?.last_price, 8)}</div></div>
              <div className="rounded bg-slate-950 p-2"><span className="text-slate-500">Trend</span><div className={`mt-1 font-bold ${trend === 'Bullish' ? 'text-emerald-400' : trend === 'Bearish' ? 'text-rose-400' : 'text-white'}`}>{trend}</div></div>
              <div className="rounded bg-slate-950 p-2"><span className="text-slate-500">RSI</span><div className="mt-1 font-bold text-white">{formatMetric(data?.indicator_context.rsi)}</div></div>
              <div className="rounded bg-slate-950 p-2"><span className="text-slate-500">MACD</span><div className="mt-1 font-bold text-white">{formatMetric(data?.indicator_context.macd)}</div></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
