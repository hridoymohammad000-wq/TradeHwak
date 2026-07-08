/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useApp } from '../context/AppContext';
import { CanonicalActiveTrade, CanonicalClosedTrade } from '../api/types';
import { formatMoney, formatNumber, formatRiskReward, formatTimestamp, modeLabel } from '../lib/tradeFormatting';
import {
  Activity,
  AlertTriangle,
  Archive,
  Clock,
  Layers,
  RefreshCw,
  ShieldCheck,
  Target,
} from 'lucide-react';

function ModeBadge({ mode }: { mode: CanonicalActiveTrade['mode'] | CanonicalClosedTrade['mode'] }) {
  const label = modeLabel(mode);
  const classes = label === 'Scalping'
    ? 'bg-teal-950/60 text-teal-400 border-teal-900/60'
    : label === 'Intraday'
      ? 'bg-indigo-950/60 text-indigo-400 border-indigo-900/60'
      : 'bg-slate-800 text-slate-300 border-slate-700';
  return <span className={`text-[9px] uppercase font-extrabold tracking-wider px-2 py-0.5 rounded border ${classes}`}>{label}</span>;
}

function LoadState({ state, error }: { state: string; error: string | null }) {
  if (state === 'ready' || state === 'empty') return null;
  const loading = state === 'loading' || state === 'idle';
  const message = loading
    ? 'Loading today’s persisted active and closed trades…'
    : state === 'unauthorized'
      ? 'Unauthorized session. Sign in again with the private access token.'
      : error || 'Canonical backend data is unavailable.';
  return (
    <div className={`rounded-xl border p-4 flex items-start gap-3 text-sm ${loading ? 'bg-slate-900 border-slate-800 text-slate-300' : state === 'unauthorized' ? 'bg-amber-950/30 border-amber-900/50 text-amber-300' : 'bg-rose-950/30 border-rose-900/50 text-rose-300'}`}>
      {loading ? <Activity className="h-4 w-4 mt-0.5 animate-pulse" /> : <AlertTriangle className="h-4 w-4 mt-0.5" />}
      <span>{message}</span>
    </div>
  );
}

export default function ActiveTrades() {
  const {
    activeTradesData,
    todayClosedTradesData,
    activeTradesState,
    activeTradesError,
    refreshActiveTrades,
    refreshDashboard,
  } = useApp();

  const active = activeTradesData?.active_trades || [];
  const closed = todayClosedTradesData?.closed_trades || [];
  const summary = todayClosedTradesData?.summaries.combined;
  const totalUnrealized = active.length > 0 && active.every((trade) => trade.pnl !== null)
    ? active.reduce((total, trade) => total + (trade.pnl || 0), 0)
    : null;

  const refresh = async () => {
    await Promise.all([refreshActiveTrades(), refreshDashboard()]);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Active Trades</h1>
          <p className="text-xs text-slate-400">Today&apos;s real open and closed positions from the canonical FastAPI trade service.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase font-mono px-2.5 py-1.5 bg-emerald-950/30 text-emerald-400 rounded border border-emerald-900/50 font-bold">Bybit Demo Only</span>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={activeTradesState === 'loading'}
            className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-medium px-3 py-1.5 rounded border border-slate-700/60"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-emerald-400 ${activeTradesState === 'loading' ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <LoadState state={activeTradesState} error={activeTradesError} />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          ['Open Today', activeTradesData?.today_summary.total_open_trades ?? 0, Layers, 'text-white'],
          ['Scalping', activeTradesData?.today_summary.scalping_open_trades ?? 0, Activity, 'text-teal-400'],
          ['Intraday', activeTradesData?.today_summary.intraday_open_trades ?? 0, Clock, 'text-indigo-400'],
          ['Closed Today', closed.length, Archive, 'text-amber-400'],
          ['Unrealized PnL', formatMoney(totalUnrealized, true), Target, totalUnrealized !== null && totalUnrealized < 0 ? 'text-rose-400' : 'text-emerald-400'],
        ].map(([label, value, Icon, valueClass]) => (
          <div key={String(label)} className="bg-slate-900 rounded-xl border border-slate-850 p-4 shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">{String(label)}</span>
              <Icon className="h-4 w-4 text-slate-500" />
            </div>
            <div className={`text-xl font-mono font-extrabold mt-3 ${String(valueClass)}`}>{String(value)}</div>
          </div>
        ))}
      </div>

      <section className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
        <div className="p-4 border-b border-slate-850 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white">Open Positions — Today</h2>
            <p className="text-[11px] text-slate-500 mt-1">Read-only exchange-synced records. No browser-generated PnL or price movement.</p>
          </div>
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1100px]">
            <thead>
              <tr className="border-b border-slate-850 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 bg-slate-950/40">
                <th className="py-3 px-4">Opened</th>
                <th className="py-3 px-4">Trade ID</th>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4 text-right">Entry</th>
                <th className="py-3 px-4 text-right">Current</th>
                <th className="py-3 px-4 text-right">Qty</th>
                <th className="py-3 px-4 text-right">Notional</th>
                <th className="py-3 px-4 text-right">SL</th>
                <th className="py-3 px-4 text-right">TP</th>
                <th className="py-3 px-4 text-right">R:R</th>
                <th className="py-3 px-4 text-right">PnL</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {active.length > 0 ? active.map((trade) => (
                <tr key={trade.trade_id} className="hover:bg-slate-850/30 text-xs font-mono text-slate-300">
                  <td className="py-4 px-4 text-slate-500 whitespace-nowrap">{formatTimestamp(trade.opened_at)}</td>
                  <td className="py-4 px-4 text-slate-500 max-w-[150px] truncate" title={trade.trade_id}>{trade.trade_id}</td>
                  <td className="py-4 px-4 font-extrabold text-white">{trade.symbol}</td>
                  <td className="py-4 px-4"><ModeBadge mode={trade.mode} /></td>
                  <td className={`py-4 px-4 font-bold uppercase ${trade.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}`}>{trade.direction}</td>
                  <td className="py-4 px-4 text-right">{formatNumber(trade.entry_price)}</td>
                  <td className="py-4 px-4 text-right">{formatNumber(trade.current_price)}</td>
                  <td className="py-4 px-4 text-right">{trade.qty || 'N/A'}</td>
                  <td className="py-4 px-4 text-right">{formatMoney(trade.notional)}</td>
                  <td className="py-4 px-4 text-right text-rose-300">{formatNumber(trade.stop_loss)}</td>
                  <td className="py-4 px-4 text-right text-emerald-300">{formatNumber(trade.take_profit)}</td>
                  <td className="py-4 px-4 text-right">{formatRiskReward(trade.risk_reward)}</td>
                  <td className={`py-4 px-4 text-right font-extrabold ${trade.pnl !== null && trade.pnl < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{formatMoney(trade.pnl, true)}</td>
                  <td className="py-4 px-4"><span className="text-[9px] uppercase px-2 py-0.5 rounded border border-slate-700 bg-slate-800 text-slate-300">{trade.status}</span></td>
                </tr>
              )) : (
                <tr><td colSpan={14} className="py-12 text-center text-sm text-slate-500">No backend-persisted active trades opened today.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
        <div className="p-4 border-b border-slate-850 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-bold text-white">Closed Positions — Today</h2>
            <p className="text-[11px] text-slate-500 mt-1">The same persisted records and identifiers used by Operator Journal.</p>
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            Wins: <span className="text-emerald-400 font-bold">{summary?.wins ?? 0}</span> · Losses: <span className="text-rose-400 font-bold">{summary?.losses ?? 0}</span> · Realized: <span className="text-white font-bold">{formatMoney(summary?.realized_pnl ?? null, true)}</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1050px]">
            <thead>
              <tr className="border-b border-slate-850 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 bg-slate-950/40">
                <th className="py-3 px-4">Closed</th>
                <th className="py-3 px-4">Trade ID</th>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-4">Mode</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4 text-right">Entry</th>
                <th className="py-3 px-4 text-right">Exit</th>
                <th className="py-3 px-4 text-right">R:R</th>
                <th className="py-3 px-4 text-right">Realized PnL</th>
                <th className="py-3 px-4">Result</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {closed.length > 0 ? closed.map((trade) => (
                <tr key={trade.trade_id} className="hover:bg-slate-850/30 text-xs font-mono text-slate-300">
                  <td className="py-4 px-4 text-slate-500 whitespace-nowrap">{formatTimestamp(trade.closed_time)}</td>
                  <td className="py-4 px-4 text-slate-500 max-w-[150px] truncate" title={trade.trade_id}>{trade.trade_id}</td>
                  <td className="py-4 px-4 font-extrabold text-white">{trade.symbol}</td>
                  <td className="py-4 px-4"><ModeBadge mode={trade.mode} /></td>
                  <td className={`py-4 px-4 font-bold uppercase ${trade.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}`}>{trade.direction}</td>
                  <td className="py-4 px-4 text-right">{formatNumber(trade.entry_price)}</td>
                  <td className="py-4 px-4 text-right">{formatNumber(trade.exit_price)}</td>
                  <td className="py-4 px-4 text-right">{formatRiskReward(trade.risk_reward)}</td>
                  <td className={`py-4 px-4 text-right font-extrabold ${trade.realized_pnl !== null && trade.realized_pnl < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>{formatMoney(trade.realized_pnl, true)}</td>
                  <td className="py-4 px-4 uppercase">{trade.result || 'N/A'}</td>
                  <td className="py-4 px-4"><span className="text-[9px] uppercase px-2 py-0.5 rounded border border-slate-700 bg-slate-800 text-slate-300">{trade.status}</span></td>
                </tr>
              )) : (
                <tr><td colSpan={11} className="py-12 text-center text-sm text-slate-500">No backend-persisted closed trades for today.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
