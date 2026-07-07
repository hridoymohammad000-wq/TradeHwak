import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, LoaderCircle, Radar, Search, SlidersHorizontal } from 'lucide-react';
import { backendApi } from '../../api/services';
import type { Direction, ScanResult, SignalGrade, Timeframe, TradingMode } from '../../api/types';
import type { BackendStatus } from '../../App';
import { Button, EmptyState, PageHeader, SectionHeader, Table } from '../UIFoundation';

const timeframeOptions: Array<{ label: string; value: Timeframe }> = [
  { label: 'M1', value: 'M1' },
  { label: 'M5', value: 'M5' },
  { label: 'M15', value: 'M15' },
  { label: 'H1', value: 'H1' },
];

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

function parseSymbols(value: string) {
  return value
    .split(',')
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
}

function renderResultRows(results: ScanResult[]) {
  return results.map((result) => (
    <tr key={`${result.mode}-${result.symbol}-${result.timeframe || 'na'}-${result.direction || 'na'}`}>
      <td className="px-4 py-3 font-mono text-xs">{result.symbol}</td>
      <td className="px-4 py-3 font-mono text-xs uppercase">{result.mode}</td>
      <td className="px-4 py-3 text-slate-500">{result.timeframe || '-'}</td>
      <td className="px-4 py-3 font-mono text-xs uppercase">{result.direction || '-'}</td>
      <td className="px-4 py-3 font-mono text-xs">{result.grade || '-'}</td>
      <td className="px-4 py-3 text-slate-300">{result.reason || 'No reason provided'}</td>
      <td className="px-4 py-3 text-slate-500">Backend only</td>
    </tr>
  ));
}

export function ScannerPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const headers = ['Symbol', 'Mode', 'Timeframe', 'Direction', 'Grade', 'Status', 'Action'];
  const [symbolInput, setSymbolInput] = useState('');
  const [mode, setMode] = useState<TradingMode | ''>('');
  const [timeframe, setTimeframe] = useState<Timeframe | ''>('');
  const [direction, setDirection] = useState<Direction | ''>('');
  const [grade, setGrade] = useState<SignalGrade | ''>('');
  const [results, setResults] = useState<ScanResult[]>([]);
  const [appliedMode, setAppliedMode] = useState<TradingMode | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasScanned, setHasScanned] = useState(false);

  const helperText = useMemo(() => {
    if (error) {
      return error;
    }
    if (isLoading) {
      return 'Running backend scan...';
    }
    if (!hasScanned) {
      return 'Configure filters and run a backend scan.';
    }
    if (results.length === 0) {
      return 'Waiting for backend integration';
    }
    return `${results.length} scan result${results.length === 1 ? '' : 's'} loaded from backend.`;
  }, [error, hasScanned, isLoading, results.length]);

  useEffect(() => {
    if (backendStatus === 'healthy') {
      return;
    }
    setResults([]);
    setAppliedMode(null);
    setError(backendStatus === 'error' ? 'Backend unavailable' : null);
  }, [backendStatus]);

  async function handleScan() {
    if (backendStatus !== 'healthy') {
      setResults([]);
      setHasScanned(true);
      setError('Backend unavailable');
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      setHasScanned(true);

      const response = await backendApi.scanMarket({
        mode: mode || undefined,
        symbols: parseSymbols(symbolInput),
        timeframe: timeframe || undefined,
        direction: direction || undefined,
        grade: grade || undefined,
      });

      setResults(response.data.results);
      setAppliedMode(response.data.mode);
    } catch (scanError) {
      setResults([]);
      setError(scanError instanceof Error ? scanError.message : 'Failed to run scanner');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Market Scanner Workspace"
        description="Real-time multi-timeframe analysis for scalping and intraday setups."
      />

      <div className="bg-slate-900/60 border border-slate-800/80 rounded-lg p-4 flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
          <div className="relative flex-1 sm:flex-none">
            <span className="absolute inset-y-0 left-3 flex items-center text-slate-500">
              <Search size={14} />
            </span>
            <input
              type="text"
              value={symbolInput}
              onChange={(event) => setSymbolInput(event.target.value)}
              placeholder="BTCUSDT, ETHUSDT..."
              className="pl-9 pr-4 py-2 w-full sm:w-56 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>

          <select
            className="px-3 py-2 bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded font-bold font-mono flex-1 sm:flex-none focus:outline-none focus:border-indigo-500"
            value={mode}
            onChange={(event) => setMode((event.target.value as TradingMode | '') || '')}
          >
            <option value="">Mode: All</option>
            {modeOptions.map((option) => (
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

          <Button variant="outline" size="sm" className="gap-1.5 py-2 flex-1 sm:flex-none" disabled>
            <SlidersHorizontal size={14} />
            Filters
          </Button>
        </div>

        <div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleScan()}
            disabled={isLoading || backendStatus !== 'healthy'}
            className="gap-1.5 py-2 font-bold font-mono w-full sm:w-auto"
          >
            {isLoading ? <LoaderCircle size={14} className="animate-spin" /> : <Radar size={14} />}
            Run Scan
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <SectionHeader
          title="Live Scan Results"
          action={
            appliedMode ? (
              <span className="text-[10px] uppercase text-slate-500 font-mono font-bold">
                Effective Mode: {appliedMode}
              </span>
            ) : null
          }
        />

        {error && (
          <div className="rounded border border-rose-900/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-300 font-sans flex items-center gap-2">
            <AlertTriangle size={16} />
            {helperText}
          </div>
        )}

        <div className="w-full">
          <Table headers={headers}>
            {results.length > 0 ? (
              renderResultRows(results)
            ) : (
              <tr>
                <td colSpan={headers.length} className="text-center p-0">
                  <EmptyState
                    title={
                      isLoading
                        ? 'Loading scanner results'
                        : error
                          ? 'Failed to run scanner'
                          : hasScanned
                            ? 'No scan results available'
                            : 'Scanner ready'
                    }
                    description={helperText}
                    icon={
                      isLoading ? <LoaderCircle size={24} className="animate-spin" /> : error ? <AlertTriangle size={24} /> : <Radar size={24} />
                    }
                    className="border-none bg-transparent py-16"
                  />
                </td>
              </tr>
            )}
          </Table>
        </div>
      </div>
    </div>
  );
}
