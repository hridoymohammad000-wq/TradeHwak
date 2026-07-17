/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { useApp } from '../context/AppContext';
import { CanonicalClosedTrade, DateTimeRange, JournalSummaryMetric } from '../api/types';
import { formatMoney, formatNumber, formatPercent, formatRiskReward, formatTimestamp, modeLabel } from '../lib/tradeFormatting';
import {
  Activity,
  AlertTriangle,
  CalendarRange,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ShieldCheck,
  Target,
} from 'lucide-react';

function toLocalInput(iso: string): string {
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

function localRange(daysBack: number): DateTimeRange {
  const end = new Date();
  if (daysBack === 0) {
    const start = new Date(end);
    start.setHours(0, 0, 0, 0);
    const tomorrow = new Date(start);
    tomorrow.setDate(tomorrow.getDate() + 1);
    return { start: start.toISOString(), end: tomorrow.toISOString() };
  }
  const start = new Date(end);
  start.setDate(start.getDate() - daysBack);
  return { start: start.toISOString(), end: end.toISOString() };
}

function ModeBadge({ mode }: { mode: CanonicalClosedTrade['mode'] }) {
  const label = modeLabel(mode);
  const classes = label === 'Scalping'
    ? 'bg-teal-950/60 text-teal-400 border-teal-900/60'
    : label === 'Intraday'
      ? 'bg-indigo-950/60 text-indigo-400 border-indigo-900/60'
      : 'bg-slate-800 text-slate-300 border-slate-700';
  return <span className={`text-[9px] uppercase font-extrabold tracking-wider px-2 py-0.5 rounded border ${classes}`}>{label}</span>;
}

function SummaryCard({ label, summary, accent }: { label: string; summary: JournalSummaryMetric | undefined; accent: string }) {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-850 p-4 shadow-md">
      <div className={`text-[11px] uppercase tracking-wider font-extrabold ${accent}`}>{label}</div>
      <div className="grid grid-cols-2 gap-3 mt-4 text-xs font-mono">
        <div><span className="block text-[9px] uppercase text-slate-500">Trades</span><span className="text-lg font-extrabold text-white">{summary?.total_trades ?? 0}</span></div>
        <div><span className="block text-[9px] uppercase text-slate-500">Win Rate</span><span className="text-lg font-extrabold text-white">{formatPercent(summary?.win_rate ?? null)}</span></div>
        <div><span className="block text-[9px] uppercase text-slate-500">W / L</span><span className="font-bold text-emerald-400">{summary?.wins ?? 0}</span><span className="text-slate-600"> / </span><span className="font-bold text-rose-400">{summary?.losses ?? 0}</span></div>
        <div><span className="block text-[9px] uppercase text-slate-500">Realized</span><span className={`font-bold ${(summary?.realized_pnl ?? 0) < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{formatMoney(summary?.realized_pnl ?? null, true)}</span></div>
        <div className="col-span-2"><span className="block text-[9px] uppercase text-slate-500">Average R:R</span><span className="font-bold text-amber-400">{formatRiskReward(summary?.average_risk_reward ?? null)}</span></div>
      </div>
    </div>
  );
}

function LoadState({ state, error }: { state: string; error: string | null }) {
  if (state === 'ready' || state === 'empty') return null;
  const loading = state === 'loading' || state === 'idle';
  const message = loading
    ? 'Loading persisted journal records…'
    : state === 'unauthorized'
      ? 'Unauthorized session. Sign in again with the private access token.'
      : error || 'Canonical backend journal is unavailable.';
  return (
    <div className={`rounded-xl border p-4 flex items-start gap-3 text-sm ${loading ? 'bg-slate-900 border-slate-800 text-slate-300' : state === 'unauthorized' ? 'bg-amber-950/30 border-amber-900/50 text-amber-300' : 'bg-rose-950/30 border-rose-900/50 text-rose-300'}`}>
      {loading ? <Activity className="h-4 w-4 mt-0.5 animate-pulse" /> : <AlertTriangle className="h-4 w-4 mt-0.5" />}
      <span>{message}</span>
    </div>
  );
}

export default function OperatorJournal() {
  const {
    journalData,
    journalState,
    journalError,
    journalRange,
    setJournalRange,
    refreshJournal,
    refreshDashboard,
    refreshActiveTrades,
    showToast,
  } = useApp();

  const [startInput, setStartInput] = useState(() => toLocalInput(journalRange.start));
  const [endInput, setEndInput] = useState(() => toLocalInput(journalRange.end));
  const [modeFilter, setModeFilter] = useState<'all' | 'scalping' | 'intraday' | 'unknown'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const records = journalData?.closed_trades || [];
  const filtered = useMemo(() => records.filter((trade) => {
    if (modeFilter === 'all') return true;
    if (modeFilter === 'unknown') return trade.mode === null;
    return trade.mode === modeFilter;
  }), [records, modeFilter]);

  const summaries = journalData?.summaries;
  const reconciled = (summaries?.scalping.total_trades ?? 0)
    + (summaries?.intraday.total_trades ?? 0)
    + (summaries?.unknown.total_trades ?? 0)
    === (summaries?.combined.total_trades ?? 0);

  const applyRange = async (range: DateTimeRange) => {
    if (new Date(range.end).getTime() <= new Date(range.start).getTime()) {
      showToast('End date/time must be after start date/time.', 'error');
      return;
    }
    setJournalRange(range);
    setStartInput(toLocalInput(range.start));
    setEndInput(toLocalInput(range.end));
    await refreshJournal(range);
  };

  const applyCustomRange = async () => {
    try {
      await applyRange({ start: fromLocalInput(startInput), end: fromLocalInput(endInput) });
    } catch {
      showToast('Enter a valid start and end date/time.', 'error');
    }
  };

  const refresh = async () => {
    await Promise.all([refreshJournal(journalRange), refreshDashboard(), refreshActiveTrades()]);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Operator Journal</h1>
          <p className="text-xs text-slate-400">Backend-persisted closed trades with explicit Scalping, Intraday, and Unknown modes.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase font-mono px-2.5 py-1.5 bg-emerald-950/30 text-emerald-400 rounded border border-emerald-900/50 font-bold">Bybit Demo Only</span>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={journalState === 'loading'}
            className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-medium px-3 py-1.5 rounded border border-slate-700/60"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-emerald-400 ${journalState === 'loading' ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <LoadState state={journalState} error={journalError} />

      <section className="bg-slate-900 rounded-xl border border-slate-850 p-4 shadow-lg">
        <div className="flex items-center gap-2 mb-4">
          <CalendarRange className="h-4 w-4 text-indigo-400" />
          <span className="text-xs font-bold text-white">Date / Time Range</span>
          <span className="text-[10px] text-slate-500">Default: today</span>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <label className="text-[10px] uppercase font-bold text-slate-500">
            Start
            <input type="datetime-local" value={startInput} onChange={(event) => setStartInput(event.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono" />
          </label>
          <label className="text-[10px] uppercase font-bold text-slate-500">
            End
            <input type="datetime-local" value={endInput} onChange={(event) => setEndInput(event.target.value)} className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono" />
          </label>
          <button type="button" onClick={() => void applyCustomRange()} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-lg">Apply Range</button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <button onClick={() => void applyRange(localRange(0))} className="text-[10px] font-bold px-3 py-1.5 rounded border border-slate-700 bg-slate-800 text-slate-300">Today</button>
          <button onClick={() => void applyRange(localRange(7))} className="text-[10px] font-bold px-3 py-1.5 rounded border border-slate-700 bg-slate-800 text-slate-300">Last 7 Days</button>
          <button onClick={() => void applyRange(localRange(30))} className="text-[10px] font-bold px-3 py-1.5 rounded border border-slate-700 bg-slate-800 text-slate-300">Last 30 Days</button>
          <select value={modeFilter} onChange={(event) => setModeFilter(event.target.value as typeof modeFilter)} className="ml-auto text-[10px] font-bold px-3 py-1.5 rounded border border-slate-700 bg-slate-950 text-slate-300">
            <option value="all">All Modes</option>
            <option value="scalping">Scalping</option>
            <option value="intraday">Intraday</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard label="Scalping" summary={summaries?.scalping} accent="text-teal-400" />
        <SummaryCard label="Intraday" summary={summaries?.intraday} accent="text-indigo-400" />
        <SummaryCard label="Combined" summary={summaries?.combined} accent="text-emerald-400" />
        <SummaryCard label="Unknown Legacy" summary={summaries?.unknown} accent="text-slate-300" />
      </div>

      <div className={`rounded-lg border px-4 py-3 flex items-center gap-2 text-xs ${reconciled ? 'bg-emerald-950/20 border-emerald-900/40 text-emerald-300' : 'bg-rose-950/30 border-rose-900/50 text-rose-300'}`}>
        <ShieldCheck className="h-4 w-4" />
        Combined total {reconciled ? 'reconciles' : 'does not reconcile'} with Scalping + Intraday + Unknown records.
      </div>

      <section className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
        <div className="p-4 border-b border-slate-850 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white">Persisted Journal Records</h2>
            <p className="text-[11px] text-slate-500 mt-1">{filtered.length} record{filtered.length === 1 ? '' : 's'} in the selected backend range.</p>
          </div>
          <Target className="h-5 w-5 text-indigo-400" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1200px]">
            <thead>
              <tr className="border-b border-slate-850 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 bg-slate-950/40">
                <th className="py-3 px-4">Closed</th>
                <th className="py-3 px-4">Trade ID</th>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4 text-right">Entry</th>
                <th className="py-3 px-4 text-right">Exit</th>
                <th className="py-3 px-4 text-right">Notional</th>
                <th className="py-3 px-4 text-right">R:R</th>
                <th className="py-3 px-4 text-right">Realized PnL</th>
                <th className="py-3 px-4">Result</th>
                <th className="py-3 px-4 text-center">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {filtered.length > 0 ? filtered.map((trade) => {
                const open = expanded === trade.trade_id;
                return (
                  <React.Fragment key={trade.trade_id}>
                    <tr className="hover:bg-slate-850/30 text-xs font-mono text-slate-300">
                      <td className="py-4 px-4 text-slate-500 whitespace-nowrap">{formatTimestamp(trade.closed_time)}</td>
                      <td className="py-4 px-4 text-slate-500 max-w-[160px] truncate" title={trade.trade_id}>{trade.trade_id}</td>
                      <td className="py-4 px-4 font-extrabold text-white">{trade.symbol}</td>
                      <td className="py-4 px-4"><ModeBadge mode={trade.mode} /></td>
                      <td className={`py-4 px-4 font-bold uppercase ${trade.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}`}>{trade.direction}</td>
                      <td className="py-4 px-4 text-right">{formatNumber(trade.entry_price)}</td>
                      <td className="py-4 px-4 text-right">{formatNumber(trade.exit_price)}</td>
                      <td className="py-4 px-4 text-right">{formatMoney(trade.notional)}</td>
                      <td className="py-4 px-4 text-right">{formatRiskReward(trade.risk_reward)}</td>
                      <td className={`py-4 px-4 text-right font-extrabold ${trade.realized_pnl !== null && trade.realized_pnl < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{formatMoney(trade.realized_pnl, true)}</td>
                      <td className="py-4 px-4 uppercase">{trade.result || 'N/A'}</td>
                      <td className="py-4 px-4 text-center"><button onClick={() => setExpanded(open ? null : trade.trade_id)} className="text-indigo-400 hover:text-indigo-300">{open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</button></td>
                    </tr>
                    {open && (
                      <tr className="bg-slate-950/60">
                        <td colSpan={12} className="p-5">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2"><div className="text-[10px] uppercase text-slate-500 font-bold">Identifiers</div><div>Order ID: <span className="text-white font-mono">{trade.order_id || 'N/A'}</span></div><div>Signal ID: <span className="text-white font-mono">{trade.signal_id || 'N/A'}</span></div><div>Opened: <span className="text-white">{formatTimestamp(trade.opened_at)}</span></div></div>
                            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2"><div className="text-[10px] uppercase text-slate-500 font-bold">Risk Record</div><div>Planned Risk: <span className="text-white">{formatMoney(trade.planned_risk_usdt)}</span></div><div>PnL Multiple: <span className="text-white">{trade.pnl_multiple_of_risk === null ? 'N/A' : `${trade.pnl_multiple_of_risk.toFixed(2)}R`}</span></div><div>Stop Slippage: <span className="text-white">{formatNumber(trade.stop_slippage_usdt)}</span></div></div>
                            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-2"><div className="text-[10px] uppercase text-slate-500 font-bold">Backend Analysis</div><div>Status: <span className="text-white">{trade.status}</span></div><div>Reason: <span className="text-white">{trade.close_reason || 'N/A'}</span></div><p className="text-slate-400 leading-relaxed">{trade.operator_summary || trade.exit_analysis || 'No persisted analysis available.'}</p></div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              }) : (
                <tr><td colSpan={12} className="py-14 text-center text-sm text-slate-500">No backend-persisted journal records match the selected range and mode.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
