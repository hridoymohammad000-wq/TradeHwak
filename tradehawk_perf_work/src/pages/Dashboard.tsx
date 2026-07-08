/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { getBackendStatusPresentation } from '../lib/backendStatus';
import { formatMoney, formatPercent, formatRiskReward, formatTimestamp, modeLabel } from '../lib/tradeFormatting';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  RefreshCw,
  ShieldCheck,
  Target,
  Wallet,
  Zap,
} from 'lucide-react';

function stateMessage(state: string, error: string | null): string | null {
  if (state === 'loading' || state === 'idle') return 'Loading canonical backend summary…';
  if (state === 'unauthorized') return 'Unauthorized session. Sign in again with the private access token.';
  if (state === 'disconnected') return error || 'Canonical backend is unreachable.';
  if (state === 'backend_error') return error || 'Backend returned an error.';
  return null;
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
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
  const { connectionStatus } = useAuth();
  const backendStatus = getBackendStatusPresentation(connectionStatus);
  const {
    dashboardData,
    dashboardState,
    dashboardError,
    activeTradesData,
    refreshDashboard,
    refreshActiveTrades,
  } = useApp();

  const message = stateMessage(dashboardState, dashboardError);
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
            FASTAPI: {backendStatus.label.toUpperCase()}
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={dashboardState === 'loading'}
            className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-medium px-3 py-1.5 rounded border border-slate-700/60 transition-colors"
          >
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
        <StatCard
          label="Demo Equity"
          value={formatMoney(account?.equity ?? null)}
          detail={account?.status === 'connected' ? 'Authenticated Bybit Demo wallet value' : account?.status === 'not_configured' ? 'Bybit Demo credentials not configured' : 'Wallet data unavailable'}
          icon={Wallet}
        />
        <StatCard
          label="Available Balance"
          value={formatMoney(account?.available_balance ?? null)}
          detail="Backend-reported withdrawable or available Demo balance"
          icon={Database}
        />
        <StatCard
          label="Unrealized PnL"
          value={formatMoney(summary?.unrealized_pnl ?? null, true)}
          detail={`${summary?.total_open_trades ?? 0} open trade${summary?.total_open_trades === 1 ? '' : 's'} in today's backend range`}
          icon={Activity}
        />
        <StatCard
          label="Realized PnL Today"
          value={formatMoney(summary?.realized_pnl_today ?? null, true)}
          detail={`${summary?.closed_trades_today ?? 0} persisted closed trade${summary?.closed_trades_today === 1 ? '' : 's'}`}
          icon={Target}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
          <div className="p-4 border-b border-slate-850 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white">Today&apos;s Canonical Trade Summary</h2>
              <p className="text-[11px] text-slate-500 mt-1">All values come from the same persisted trade service used by Active Trades and Journal.</p>
            </div>
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-slate-850">
            {[
              ['Open', summary?.total_open_trades ?? 0],
              ['Closed', summary?.closed_trades_today ?? 0],
              ['Wins', summary?.wins_today ?? 0],
              ['Losses', summary?.losses_today ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="bg-slate-900 p-5">
                <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">{label}</div>
                <div className="text-2xl font-mono font-extrabold text-white mt-2">{value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border-t border-slate-850">
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Win Rate Today</div>
              <div className="text-xl font-mono font-extrabold text-indigo-400 mt-2">{formatPercent(summary?.win_rate_today ?? null)}</div>
              <p className="text-[10px] text-slate-500 mt-1">N/A when persisted result data cannot support the calculation.</p>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Average Risk–Reward Today</div>
              <div className="text-xl font-mono font-extrabold text-amber-400 mt-2">{formatRiskReward(summary?.average_risk_reward_today ?? null)}</div>
              <p className="text-[10px] text-slate-500 mt-1">Calculated by the backend only when the required persisted values are available.</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
          <div className="p-4 border-b border-slate-850">
            <h2 className="text-sm font-bold text-white">Trading Mode Separation</h2>
            <p className="text-[11px] text-slate-500 mt-1">No timeframe-based inference.</p>
          </div>
          <div className="p-4 space-y-3">
            {[
              ['Scalping', summary?.scalping_open_trades ?? 0, 'text-teal-400', 'bg-teal-950/30 border-teal-900/50'],
              ['Intraday', summary?.intraday_open_trades ?? 0, 'text-indigo-400', 'bg-indigo-950/30 border-indigo-900/50'],
              ['Unknown', summary?.unknown_open_trades ?? 0, 'text-slate-300', 'bg-slate-950 border-slate-800'],
            ].map(([label, count, textClass, boxClass]) => (
              <div key={label} className={`flex items-center justify-between rounded-lg border p-3 ${boxClass}`}>
                <span className={`text-xs font-bold ${textClass}`}>{label}</span>
                <span className="text-lg font-mono font-extrabold text-white">{count}</span>
              </div>
            ))}
            <div className="pt-2 text-[10px] text-slate-500 font-mono">
              System mode: <span className="text-emerald-400 font-bold">BYBIT DEMO ONLY</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
          <div className="p-4 border-b border-slate-850 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white">Today&apos;s Active Trades</h2>
              <p className="text-[11px] text-slate-500 mt-1">Preview from the canonical `/active-trades` response.</p>
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
              <div className="p-8 text-center text-sm text-slate-500">No backend-persisted active trades for today.</div>
            )}
          </div>
        </div>

        <div className="bg-slate-900 rounded-xl border border-slate-850 shadow-lg overflow-hidden">
          <div className="p-4 border-b border-slate-850 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-white">Recent Backend Events</h2>
              <p className="text-[11px] text-slate-500 mt-1">Persisted runtime events, not browser-generated activity.</p>
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
    </div>
  );
}
