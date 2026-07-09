import React, { useEffect, useMemo, useState } from 'react';
import { BarChart3, RefreshCw, Filter, Target, AlertTriangle } from 'lucide-react';
import { ApiError, fetchCanonicalJournal } from '../api/client';
import { CanonicalClosedTrade, DateTimeRange, JournalSummaryMetric } from '../api/types';

function localDayRange(): DateTimeRange {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function formatNumber(value: number | null, digits = 2): string {
  return value == null ? 'N/A' : value.toFixed(digits);
}

function MetricCard({ title, metric }: { title: string; metric: JournalSummaryMetric }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="text-xs uppercase tracking-wider text-slate-400 font-bold mb-3">{title}</div>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>Total <b className="text-white float-right">{metric.total_trades}</b></div>
        <div>Win Rate <b className="text-white float-right">{metric.win_rate == null ? 'N/A' : `${formatNumber(metric.win_rate)}%`}</b></div>
        <div>Wins / Losses <b className="text-white float-right">{metric.wins}/{metric.losses}</b></div>
        <div>Realized PnL <b className={metric.realized_pnl != null && metric.realized_pnl < 0 ? 'text-rose-400 float-right' : 'text-emerald-400 float-right'}>{formatNumber(metric.realized_pnl)}</b></div>
        <div>Average R:R <b className="text-white float-right">{formatNumber(metric.average_risk_reward)}</b></div>
      </div>
    </div>
  );
}

export default function PerformanceStrategy() {
  const initialRange = useMemo(localDayRange, []);
  const [range, setRange] = useState<DateTimeRange>(initialRange);
  const [trades, setTrades] = useState<CanonicalClosedTrade[]>([]);
  const [summaries, setSummaries] = useState<{
    scalping: JournalSummaryMetric;
    intraday: JournalSummaryMetric;
    unknown: JournalSummaryMetric;
    combined: JournalSummaryMetric;
  } | null>(null);
  const [mode, setMode] = useState<'all' | 'scalping' | 'intraday' | 'unknown'>('all');
  const [state, setState] = useState<'loading' | 'ready' | 'empty' | 'error' | 'unauthorized'>('loading');
  const [error, setError] = useState('');

  const load = async () => {
    setState('loading');
    setError('');
    try {
      const data = await fetchCanonicalJournal(range);
      setTrades(data.closed_trades);
      setSummaries(data.summaries);
      setState(data.closed_trades.length ? 'ready' : 'empty');
    } catch (requestError) {
      setTrades([]);
      setSummaries(null);
      setError(requestError instanceof Error ? requestError.message : 'Backend request failed.');
      setState(requestError instanceof ApiError && requestError.kind === 'unauthorized' ? 'unauthorized' : 'error');
    }
  };

  useEffect(() => { void load(); }, []);

  const filteredTrades = trades.filter((trade) => {
    if (mode === 'all') return true;
    if (mode === 'unknown') return trade.mode == null;
    return trade.mode === mode;
  });

  return (
    <main className="flex-1 overflow-y-auto bg-slate-950 p-4 md:p-6">
      <div className="max-w-[1600px] mx-auto space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2"><BarChart3 className="text-emerald-400" />Performance & Strategy</h1>
            <p className="text-xs text-slate-400 mt-1">Derived only from the same persisted closed trades used by Operator Journal.</p>
          </div>
          <button onClick={() => void load()} className="px-3 py-2 rounded-lg bg-emerald-500 text-slate-950 text-xs font-bold flex items-center gap-2"><RefreshCw className="h-4 w-4" />Refresh</button>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            type="datetime-local"
            className="bg-slate-950 border border-slate-700 rounded p-2 text-xs"
            onChange={(event) => setRange((current) => ({ ...current, start: event.target.value ? new Date(event.target.value).toISOString() : initialRange.start }))}
          />
          <input
            type="datetime-local"
            className="bg-slate-950 border border-slate-700 rounded p-2 text-xs"
            onChange={(event) => setRange((current) => ({ ...current, end: event.target.value ? new Date(event.target.value).toISOString() : initialRange.end }))}
          />
          <select className="bg-slate-950 border border-slate-700 rounded p-2 text-xs" value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
            <option value="all">All modes</option><option value="scalping">Scalping</option><option value="intraday">Intraday</option><option value="unknown">Unknown</option>
          </select>
          <button onClick={() => void load()} className="bg-slate-800 border border-slate-700 rounded p-2 text-xs font-bold flex items-center justify-center gap-2"><Filter className="h-4 w-4" />Apply range</button>
        </div>

        {state === 'loading' && <div className="p-10 text-center text-slate-400">Loading persisted performance data…</div>}
        {state === 'unauthorized' && <div className="p-10 text-center text-amber-400">Unauthorized session.</div>}
        {state === 'error' && <div className="p-10 text-center text-rose-400">{error}</div>}
        {state === 'empty' && <div className="p-10 text-center text-slate-400">No persisted closed trades match this range.</div>}

        {summaries && state === 'ready' && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <MetricCard title="Scalping" metric={summaries.scalping} />
              <MetricCard title="Intraday" metric={summaries.intraday} />
              <MetricCard title="Unknown" metric={summaries.unknown} />
              <MetricCard title="Combined" metric={summaries.combined} />
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800 font-bold text-sm flex items-center gap-2"><Target className="h-4 w-4 text-emerald-400" />Trade Outcome Analysis</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-950 text-slate-400"><tr>{['Trade', 'Mode', 'Status', 'Result', 'PnL', 'Exit reason', 'Analysis', 'Closed'].map((heading) => <th key={heading} className="text-left p-3">{heading}</th>)}</tr></thead>
                  <tbody>
                    {filteredTrades.map((trade) => (
                      <tr key={trade.trade_id} className="border-t border-slate-800">
                        <td className="p-3"><b>{trade.symbol}</b><div className="text-slate-500 font-mono">{trade.trade_id}</div></td>
                        <td className="p-3 capitalize">{trade.mode || 'Unknown'}</td>
                        <td className="p-3">{trade.status}</td>
                        <td className="p-3">{trade.result || 'N/A'}</td>
                        <td className="p-3">{formatNumber(trade.realized_pnl)}</td>
                        <td className="p-3">{trade.close_reason || 'N/A'}</td>
                        <td className="p-3 max-w-md text-slate-400">{trade.exit_analysis || trade.operator_summary || 'N/A'}</td>
                        <td className="p-3">{trade.closed_time ? new Date(trade.closed_time).toLocaleString() : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {filteredTrades.length === 0 && <div className="p-8 text-center text-slate-500">No trades match the selected mode.</div>}
            </div>

            <div className="text-[11px] text-slate-500 flex items-center gap-2"><AlertTriangle className="h-3.5 w-3.5" />Strategy-specific attribution remains N/A when strategy was not persisted. No retrospective explanation is generated.</div>
          </>
        )}
      </div>
    </main>
  );
}
