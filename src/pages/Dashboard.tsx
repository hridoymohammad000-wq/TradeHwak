/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useApp } from '../context/AppContext';
import { formatMoney, formatPercent, formatTimestamp, modeLabel } from '../lib/tradeFormatting';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  RefreshCw,
  Target,
  Wallet,
  Zap,
} from 'lucide-react';

function stateMessage(state: string, error: string | null): string | null {
  if (state === 'loading' || state === 'idle') return 'Waking and loading the backend. Free instances can take up to 75 seconds…';
  if (state === 'unauthorized') return 'Unauthorized session. Sign in again with the private access token.';
  if (state === 'disconnected') return error || 'Canonical backend is unreachable.';
  if (state === 'backend_error') return error || 'Backend returned an error.';
  return null;
}

function connectionPresentation(state: string) {
  if (state === 'ready') return { label: 'CONNECTED', dotClass: 'bg-emerald-400' };
  if (state === 'loading' || state === 'idle') return { label: 'WAKING', dotClass: 'bg-amber-400 animate-pulse' };
  if (state === 'unauthorized') return { label: 'UNAUTHORIZED', dotClass: 'bg-amber-400' };
  return { label: 'DISCONNECTED', dotClass: 'bg-rose-400' };
}

function StatCard({ label, value, detail, icon: Icon }: {
  label: string;
  value: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="bg-slate-900 p-5 rounded-xl border border-slate-850 shadow-md relative overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">{label}</span>
        <div className="w-8 h-8 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center">
          <Icon className="h-4 w-4 text-emerald-400" />
        </div>
      </div>
      <div className="mt-4 text-2xl font-extrabold font-mono text-white tracking-tight">{value}</div>
      <p className="text-[11px] text-slate-500 mt-2">{detail}</p>
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500/40 to-transparent" />
    </div>
  );
}

export default function Dashboard() {
  const {
    dashboardData,
    dashboardState,
    dashboardError,
    activeTradesData,
    refreshDashboard,
    refreshActiveTrades,
  } = useApp();

  const message = stateMessage(dashboardState, dashboardError);
  const backendStatus = connectionPresentation(dashboardState);
  const summary = dashboardData?.today_summary;
  const account = dashboardData?.account;
  const activePreview = activeTradesData?.active_trades.slice(0, 5) || [];

  const refresh = async () => {
    await Promise.all([refreshDashboard(), refreshActiveTrades()]);
  };

  return (
    <div id="dashboard-view" className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800/80 backdrop-blur-sm">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Terminal Dashboard</h1>
          <p className="text-xs text-slate-400">Canonical FastAPI summary and Bybit Demo account state.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 text-[10px] uppercase font-mono px-2.5 py-1.5 bg-slate-800/80 rounded border border-slate-700/50 text-slate-300">
            <span className={`h-2 w-2 rounded-full ${backendStatus.dotClass}`} />
            FASTAPI: {backendStatus.label}
          </div>
          <button type="button" onClick={() => void refresh()} disabled={dashboardState === 'loading'} className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-medium px-3 py-1.5 rounded border border-slate-700/60 transition-colors">
            <RefreshCw className={`h-3.5 w-3.5 text-emerald-400 ${dashboardState === 'loading' ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {message && (
        <div className={`rounded-xl border px-4 py-3 flex items-start gap-3 text-sm ${dashboardState === 'unauthorized' ? 'bg-amber-950/30 border-amber-900/50 text-amber-300' : dashboardState === 'loading' || dashboardState === 'idle' ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-rose-950/30 border-rose-900/50 text-rose-300'}`}>
          {dashboardState === 'loading' || dashboardState === 'idle' ? <Activity className="h-4 w-4 mt-0.5 animate-pulse" /> : <AlertTriangle className="h-4 w-4 mt-0.5" />}
          <span>{message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Demo Equity" value={formatMoney(account?.equity ?? null)} detail={account?.status === 'connected' ? 'Authenticated Bybit Demo wallet value' : 'Wallet data unavailable'} icon={Wallet} />
        <StatCard label="Available Balance" value={formatMoney(account?.available_balance ?? null)} detail="Backend-reported available Demo balance" icon={Database} />
        <StatCard label="Unrealized PnL" value={formatMoney(summary?.unrealized_pnl ?? null, true)} detail={`${summary?.active_trades_now ?? 0} active trade${summary?.active_trades_now === 1 ? '' : 's'} now`} icon={Activity} />
        <StatCard label="Realized PnL Today" value={formatMoney(summary?.realized_pnl_today ?? null, true)} detail={`${summary?.closed_trades_today ?? 0} closed trade${summary?.closed_trades_today === 1 ? '' : 's'} today`} icon={Target} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-4">
        <StatCard label="Opened Today" value={String(summary?.opened_trades_today ?? 0)} detail="All trades opened today, including closed ones" icon={Zap} />
        <StatCard label="Active Now" value={String(summary?.active_trades_now ?? 0)} detail="Positions currently open" icon={Activity} />
        <StatCard label="Scalping Active" value={String(summary?.scalping_open_trades ?? 0)} detail="Current scalping positions" icon={Activity} />
        <StatCard label="Intraday Active" value={String(summary?.intraday_open_trades ?? 0)} detail="Current intraday positions" icon={Activity} />
        <StatCard label="Closed Today" value={String(summary?.closed_trades_today ?? 0)} detail="Positions closed today" icon={CheckCircle2} />
        <StatCard label="Winning %" value={formatPercent(summary?.win_rate_today ?? null)} detail="Positive realized PnL ÷ decided closed trades" icon={Target} />
        <StatCard label="Losing %" value={formatPercent(summary?.loss_rate_today ?? null)} detail="Negative realized PnL ÷ decided closed trades" icon={AlertTriangle} />
        <StatCard label="Break-even" value={String(summary?.breakeven_today ?? 0)} detail="Excluded from win/loss percentages" icon={Clock} />
      </div>

      <div className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
        <div className="p-4 border-b border-slate-850 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white">Active Positions — Now</h2>
            <p className="text-[11px] text-slate-500 mt-1">Current backend-synced open positions.</p>
          </div>
          <Zap className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="divide-y divide-slate-850">
          {activePreview.length > 0 ? activePreview.map((trade) => (
            <div key={trade.trade_id} className="p-4 flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{trade.symbol}</span>
                  <span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border border-slate-700 text-slate-300">{modeLabel(trade.mode)}</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-1">{formatTimestamp(trade.opened_at)} · {trade.status}</div>
              </div>
              <div className={`text-sm font-mono font-extrabold ${trade.pnl !== null && trade.pnl < 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                {formatMoney(trade.pnl, true)}
              </div>
            </div>
          )) : (
            <div className="p-8 text-center text-sm text-slate-500">No active positions now.</div>
          )}
        </div>
      </div>

      <div className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
        <div className="p-4 border-b border-slate-850 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white">Recent Backend Events</h2>
            <p className="text-[11px] text-slate-500 mt-1">Persisted runtime events.</p>
          </div>
          <Clock className="h-4 w-4 text-indigo-400" />
        </div>
        <div className="divide-y divide-slate-850">
          {(dashboardData?.recent_events || []).length > 0 ? dashboardData?.recent_events.map((event, index) => (
            <div key={`${event.created_at || 'event'}-${index}`} className="p-4 flex gap-3">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs text-slate-200">{event.message}</div>
                <div className="text-[10px] text-slate-500 mt-1">{event.event_type} · {formatTimestamp(event.created_at)}</div>
              </div>
            </div>
          )) : (
            <div className="p-8 text-center text-sm text-slate-500">No persisted backend events available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
