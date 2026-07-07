import React, { useEffect, useState } from 'react';
import { AlertTriangle, BellRing, Eye, LoaderCircle, Search, SlidersHorizontal } from 'lucide-react';
import { backendApi } from '../../api/services';
import type { Direction, SignalGrade, SignalItem, Timeframe, TradingMode } from '../../api/types';
import type { BackendStatus } from '../../App';
import { Badge, Button, EmptyState, PageHeader, SectionHeader } from '../UIFoundation';

const modeOptions: Array<{ label: string; value: TradingMode }> = [
  { label: 'Scalping', value: 'scalping' },
  { label: 'Intraday', value: 'intraday' },
];

const directionOptions: Array<{ label: string; value: Direction }> = [
  { label: 'buy', value: 'buy' },
  { label: 'sell', value: 'sell' },
];

const gradeOptions: Array<{ label: string; value: SignalGrade }> = [
  { label: 'A+', value: 'A+' },
  { label: 'A', value: 'A' },
  { label: 'B+', value: 'B+' },
  { label: 'B', value: 'B' },
];

const timeframeOptions: Array<{ label: string; value: Timeframe }> = [
  { label: 'M1', value: 'M1' },
  { label: 'M5', value: 'M5' },
  { label: 'M15', value: 'M15' },
  { label: 'H1', value: 'H1' },
];

function formatPrice(value: number | null) {
  return value === null ? 'Pending Data' : value.toFixed(4);
}

function getModeBadgeVariant(mode: TradingMode) {
  return mode === 'scalping' ? 'purple' : 'blue';
}

function renderSignalCard(signal: SignalItem) {
  return (
    <div
      key={signal.signal_id}
      className="bg-slate-900/40 border border-slate-800/80 rounded-lg p-5 flex flex-col justify-between"
    >
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-200 font-mono uppercase">{signal.symbol}</span>
            <Badge variant={getModeBadgeVariant(signal.mode)}>{signal.mode.toUpperCase()}</Badge>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="gray">{signal.direction}</Badge>
            <Badge variant="gray">{signal.grade}</Badge>
          </div>
        </div>
        <div className="space-y-2 border-y border-slate-800/50 py-3 my-3 text-xs font-mono">
          <div className="flex justify-between">
            <span className="text-slate-500">Entry Target</span>
            <span className="text-slate-300 font-semibold uppercase">{formatPrice(signal.entry_price)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Current Price</span>
            <span className="text-slate-300 font-semibold uppercase">{formatPrice(signal.current_price)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Timeframe</span>
            <span className="text-slate-300 font-semibold uppercase">{signal.timeframe}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Status</span>
            <span className="text-slate-300 font-semibold uppercase">{signal.status}</span>
          </div>
        </div>
      </div>
      <div className="mt-2">
        <Button variant="outline" size="sm" className="w-full text-xs font-mono gap-1.5 font-bold" disabled>
          <Eye size={14} />
          VIEW CHART (Disabled)
        </Button>
      </div>
    </div>
  );
}

export function SignalsPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const [symbol, setSymbol] = useState('');
  const [mode, setMode] = useState<TradingMode>('scalping');
  const [direction, setDirection] = useState<Direction | ''>('');
  const [grade, setGrade] = useState<SignalGrade | ''>('');
  const [timeframe, setTimeframe] = useState<Timeframe | ''>('');
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSignals() {
      if (backendStatus !== 'healthy') {
        setSignals([]);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        return;
      }
      try {
        setIsLoading(true);
        setError(null);
        const response = await backendApi.getSignals(
          {
            mode,
            grade: grade || undefined,
            symbol: symbol.trim().toUpperCase() || undefined,
            timeframe: timeframe || undefined,
          },
          controller.signal,
        );
        setSignals(response.data.signals);
      } catch (loadError) {
        setSignals([]);
        setError(loadError instanceof Error ? loadError.message : 'Failed to load signals');
      } finally {
        setIsLoading(false);
      }
    }

    void loadSignals();
    return () => controller.abort();
  }, [backendStatus, grade, mode, symbol, timeframe]);

  const filteredSignals = direction ? signals.filter((signal) => signal.direction === direction) : signals;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Execution Signals Feed"
        description="Incoming trigger events formulated by the strategy processing engines."
      />

      <div className="bg-slate-900/60 border border-slate-800/80 rounded-lg p-4 flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
          <div className="relative flex-1 sm:flex-none">
            <span className="absolute inset-y-0 left-3 flex items-center text-slate-500">
              <Search size={14} />
            </span>
            <input
              type="text"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              placeholder="Search Symbols..."
              className="pl-9 pr-4 py-2 w-full sm:w-48 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>
          <select
            className="px-3 py-2 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold font-mono flex-1 sm:flex-none focus:outline-none focus:border-indigo-500"
            value={mode}
            onChange={(event) => setMode(event.target.value as TradingMode)}
          >
            {modeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="px-3 py-2 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold font-mono flex-1 sm:flex-none focus:outline-none focus:border-indigo-500"
            value={direction}
            onChange={(event) => setDirection((event.target.value as Direction | '') || '')}
          >
            <option value="">Direction: All</option>
            {directionOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="px-3 py-2 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold font-mono flex-1 sm:flex-none focus:outline-none focus:border-indigo-500"
            value={grade}
            onChange={(event) => setGrade((event.target.value as SignalGrade | '') || '')}
          >
            <option value="">Grade: All</option>
            {gradeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="px-3 py-2 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold font-mono flex-1 sm:flex-none focus:outline-none focus:border-indigo-500"
            value={timeframe}
            onChange={(event) => setTimeframe((event.target.value as Timeframe | '') || '')}
          >
            <option value="">Timeframe: All</option>
            {timeframeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" disabled className="gap-1.5 py-2 flex-1 sm:flex-none">
            <SlidersHorizontal size={14} />
            Parameters
          </Button>
        </div>
        <div className="flex items-center gap-2 bg-slate-950/40 p-2 rounded border border-slate-800/50">
          {isLoading ? <LoaderCircle size={14} className="text-slate-500 animate-spin" /> : <BellRing size={14} className="text-slate-500" />}
          <span className="font-mono text-xs text-slate-500 font-bold uppercase tracking-wider">
            {isLoading ? 'Loading signals' : 'Alert dispatch standby'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          <SectionHeader title="Active Signals Queue" />

          {error && (
            <div className="rounded border border-rose-900/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-300 font-sans flex items-center gap-2">
              <AlertTriangle size={16} />
              {error}
            </div>
          )}

          {filteredSignals.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredSignals.map((signal) => renderSignalCard(signal))}
            </div>
          ) : (
            <EmptyState
              title={
                isLoading
                  ? 'Loading signals'
                  : error
                    ? 'Failed to load signals'
                    : 'No signals available'
              }
              description={
                isLoading
                  ? 'Fetching backend signal filters and queue state.'
                  : error
                    ? 'Backend unavailable'
                    : 'Waiting for backend integration'
              }
              icon={isLoading ? <LoaderCircle size={24} className="animate-spin" /> : error ? <AlertTriangle size={24} /> : <BellRing size={24} />}
            />
          )}
        </div>

        <div>
          <SectionHeader title="Workflow Settings" />
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-5 space-y-4">
            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-300 font-mono">Operator Routing</h4>
            <div className="space-y-3 font-sans text-xs text-slate-400 leading-relaxed">
              <p>
                Incoming signals are now loaded from the backend endpoint, but live values remain placeholder-safe until the backend provides richer signal details.
              </p>
              <ul className="list-disc pl-4 space-y-2 text-slate-500">
                <li>System filters use backend-aligned mode, grade, symbol, and timeframe values.</li>
                <li>Chart handoff remains intentionally disabled in Phase 2.</li>
              </ul>
              <p className="pt-3 border-t border-slate-800 text-[10.5px] text-slate-500 font-mono font-semibold">
                * No fake signal cards are generated when the backend queue is empty.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
