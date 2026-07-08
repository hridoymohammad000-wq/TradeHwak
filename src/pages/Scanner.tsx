import React, { useMemo, useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, RefreshCw, Search, XCircle } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { ScanOutcome } from '../api/types';

const outcomeStyle: Record<ScanOutcome, string> = {
  actionable: 'text-emerald-400 border-emerald-900 bg-emerald-950/30',
  rejected: 'text-rose-400 border-rose-900 bg-rose-950/30',
  skipped: 'text-amber-400 border-amber-900 bg-amber-950/30',
  failed: 'text-red-400 border-red-900 bg-red-950/30',
};

function StatePanel({ title, detail }: { title: string; detail?: string | null }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-10 text-center">
      <AlertCircle className="mx-auto mb-3 text-slate-500" size={30} />
      <div className="font-bold text-slate-200">{title}</div>
      {detail && <div className="mt-2 text-sm text-slate-500">{detail}</div>}
    </div>
  );
}

export default function Scanner() {
  const { scannerResponse, scannerState, scannerError, runScanner } = useApp();
  const [mode, setMode] = useState<'scalping' | 'intraday'>('scalping');
  const [search, setSearch] = useState('');
  const [outcome, setOutcome] = useState<'all' | ScanOutcome>('all');

  const results = useMemo(() => {
    const items = scannerResponse?.results ?? [];
    return items.filter((item) => {
      const matchesSearch = !search || item.symbol.toLowerCase().includes(search.toLowerCase());
      const matchesOutcome = outcome === 'all' || item.outcome === outcome;
      return matchesSearch && matchesOutcome;
    });
  }, [scannerResponse, search, outcome]);

  const counts = scannerResponse?.counts;

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2"><Activity className="text-emerald-400" /> Market Scanner</h1>
          <p className="text-sm text-slate-500 mt-1">Canonical FastAPI scan results only</p>
        </div>
        <div className="flex gap-2">
          <select value={mode} onChange={(e) => setMode(e.target.value as 'scalping' | 'intraday')} className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm">
            <option value="scalping">Scalping</option>
            <option value="intraday">Intraday</option>
          </select>
          <button onClick={() => void runScanner({ mode })} disabled={scannerState === 'loading'} className="rounded-lg bg-emerald-500 px-4 py-2 font-bold text-slate-950 disabled:opacity-50 flex items-center gap-2">
            <RefreshCw size={16} className={scannerState === 'loading' ? 'animate-spin' : ''} /> {scannerState === 'loading' ? 'Scanning' : 'Run Scan'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          ['Total', counts?.total],
          ['Actionable', counts?.actionable],
          ['Rejected', counts?.rejected],
          ['Skipped', counts?.skipped],
          ['Failed', counts?.failed],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-1 text-2xl font-black text-white">{value ?? 'N/A'}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1"><Search size={16} className="absolute left-3 top-3 text-slate-500" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter symbol" className="w-full rounded-lg border border-slate-800 bg-slate-900 py-2.5 pl-9 pr-3 text-sm" /></div>
        <select value={outcome} onChange={(e) => setOutcome(e.target.value as 'all' | ScanOutcome)} className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2.5 text-sm">
          <option value="all">All outcomes</option><option value="actionable">Actionable</option><option value="rejected">Rejected</option><option value="skipped">Skipped</option><option value="failed">Failed</option>
        </select>
      </div>

      {scannerState === 'idle' && <StatePanel title="Scanner has not run yet" detail="Run a real backend scan to view results." />}
      {scannerState === 'loading' && <StatePanel title="Scanning backend market universe…" />}
      {scannerState === 'unauthorized' && <StatePanel title="Unauthorized" detail={scannerError} />}
      {scannerState === 'disconnected' && <StatePanel title="Backend disconnected or timed out" detail={scannerError} />}
      {scannerState === 'backend_error' && <StatePanel title="Backend error" detail={scannerError} />}
      {scannerState === 'empty' && <StatePanel title="No scan results returned" />}

      {(scannerState === 'ready' || scannerState === 'empty') && results.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {results.map((item) => {
            const reason = item.failure_reason || item.rejection_reason || item.reason;
            return (
              <div key={`${item.symbol}-${item.outcome}`} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div><div className="font-black text-white">{item.symbol}</div><div className="text-xs text-slate-500 mt-1">{item.mode} · {item.timeframe ?? 'N/A'} · {item.strategy ?? 'N/A'}</div></div>
                  <span className={`rounded-md border px-2 py-1 text-[11px] font-black uppercase ${outcomeStyle[item.outcome]}`}>{item.outcome}</span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg bg-slate-950 p-2"><span className="text-slate-500">Direction</span><div className="mt-1 font-bold text-slate-200">{item.direction?.toUpperCase() ?? 'N/A'}</div></div>
                  <div className="rounded-lg bg-slate-950 p-2"><span className="text-slate-500">Grade</span><div className="mt-1 font-bold text-slate-200">{item.grade ?? 'N/A'}</div></div>
                  <div className="rounded-lg bg-slate-950 p-2"><span className="text-slate-500">Price</span><div className="mt-1 font-bold text-slate-200">{item.metrics?.current_price ?? 'N/A'}</div></div>
                </div>
                {item.metrics && <div className="mt-3 text-xs text-slate-500">RSI 14: {item.metrics.rsi14 ?? 'N/A'} · EMA20: {item.metrics.ema20 ?? 'N/A'} · EMA50: {item.metrics.ema50 ?? 'N/A'} · Gap: {item.metrics.trend_gap_pct ?? 'N/A'}%</div>}
                <div className="mt-3 text-sm text-slate-300 leading-relaxed">{reason ?? 'No additional reason was returned by the backend.'}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
