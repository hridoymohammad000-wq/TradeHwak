import React, { useEffect, useState } from 'react';
import {
  Badge,
  EmptyState,
  PageHeader,
  SectionHeader,
  StatusBadge,
  Table,
  ToggleButton,
} from '../UIFoundation';
import { backendApi } from '../../api/services';
import type {
  ActiveTradeRecord,
  ActiveTradesData,
  ClosedTradeRecord,
  EngineControlPayload,
  SettingsViewData,
} from '../../api/types';
import type { BackendStatus } from '../../App';
import { Activity, AlertTriangle, History, LoaderCircle } from 'lucide-react';

function formatPrice(value: number | null) {
  return value === null ? '-' : value.toFixed(4);
}

function formatPnL(value: number | null) {
  return value === null ? 'N/A' : value.toFixed(2);
}

function formatText(value: string | null | undefined) {
  return value && value.trim() ? value : '-';
}

function getTradeStatusBadge(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes('open') || normalized.includes('active')) {
    return 'active';
  }
  if (normalized.includes('pending')) {
    return 'pending';
  }
  return 'inactive';
}

function renderTradeRows(trades: ActiveTradeRecord[]) {
  return trades.map((trade) => (
    <tr key={`${trade.mode}-${trade.symbol}-${trade.direction}-${trade.timeframe || 'NA'}`}>
      <td className="px-4 py-3 font-mono text-xs">{trade.symbol}</td>
      <td className="px-4 py-3 font-mono text-xs uppercase">{trade.direction}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatText(trade.qty)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPnL(trade.planned_risk_usdt)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.entry_price)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.current_price)}</td>
      <td className="px-4 py-3 font-mono text-xs">{trade.risk_reward === null ? '-' : trade.risk_reward.toFixed(2)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPnL(trade.pnl)}</td>
    </tr>
  ));
}

function renderClosedTradeRows(trades: ClosedTradeRecord[]) {
  return trades.map((trade) => (
    <tr key={`${trade.mode}-${trade.symbol}-${trade.closed_time || trade.status}`}>
      <td className="px-4 py-3 font-mono text-xs">{trade.symbol}</td>
      <td className="px-4 py-3 font-mono text-xs uppercase">{trade.direction}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.entry_price)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.exit_price)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatText(trade.qty)}</td>
      <td className="px-4 py-3 font-mono text-xs">{formatPnL(trade.realized_pnl)}</td>
      <td className="px-4 py-3">
        <StatusBadge
          status={getTradeStatusBadge(trade.close_reason || trade.status)}
          label={trade.close_reason || trade.result || trade.status}
        />
      </td>
      <td className="px-4 py-3 text-xs text-slate-400">{trade.closed_time || 'Pending'}</td>
    </tr>
  ));
}

export function ActiveTradesPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const activeHeaders = ['Asset', 'Dir', 'Qty', 'Risk USDT', 'Entry Price', 'Mark Price', 'R:R', 'Unrealized PnL'];
  const closedHeaders = ['Asset', 'Dir', 'Entry', 'Exit', 'Size', 'Realized PnL', 'Close Reason', 'Timestamp'];
  const [activeTrades, setActiveTrades] = useState<ActiveTradesData | null>(null);
  const [closedTrades, setClosedTrades] = useState<ClosedTradeRecord[]>([]);
  const [settings, setSettings] = useState<SettingsViewData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadTrades() {
      if (backendStatus !== 'healthy') {
        setActiveTrades(null);
        setClosedTrades([]);
        setSettings(null);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        return;
      }
      try {
        setIsLoading(true);
        setError(null);
        const [activeResponse, closedResponse, settingsResponse] = await Promise.all([
          backendApi.getActiveTrades(controller.signal),
          backendApi.getClosedTrades(controller.signal),
          backendApi.getSettingsView(controller.signal),
        ]);
        setActiveTrades(activeResponse.data);
        setClosedTrades(closedResponse.data.closed_trades);
        setSettings(settingsResponse.data);
      } catch (loadError) {
        setActiveTrades(null);
        setClosedTrades([]);
        setSettings(null);
        setError(loadError instanceof Error ? loadError.message : 'Failed to load active trades');
      } finally {
        setIsLoading(false);
      }
    }

    void loadTrades();
    return () => controller.abort();
  }, [backendStatus]);

  async function updateEngineControls(payload: EngineControlPayload) {
    if (backendStatus !== 'healthy') {
      setError('Backend unavailable');
      return;
    }
    try {
      setIsSaving(true);
      setError(null);
      await backendApi.updateEngineControl(payload);
      const [activeResponse, settingsResponse] = await Promise.all([
        backendApi.getActiveTrades(),
        backendApi.getSettingsView(),
      ]);
      setActiveTrades(activeResponse.data);
      setSettings(settingsResponse.data);
    } catch (saveError) {
      setActiveTrades(null);
      setSettings(null);
      setError(saveError instanceof Error ? saveError.message : 'Failed to update trade controls');
    } finally {
      setIsSaving(false);
    }
  }

  const totalPnL = activeTrades
    ? [...activeTrades.scalping_trades, ...activeTrades.intraday_trades]
        .reduce((sum, trade) => sum + (trade.pnl || 0), 0)
    : null;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Active Trades Control Room"
        description="Monitor, manage, and manually override active algorithmic trading positions."
      />

      <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5">
        <h3 className="text-sm font-bold uppercase tracking-wider text-indigo-400 font-mono mb-4 flex items-center gap-2">
          <Activity size={16} />
          Live Performance Summary
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-mono">
          <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded">
            <span className="block text-[11px] text-slate-500 uppercase font-mono font-bold">Active Scalper Positions</span>
            <span className="text-base font-bold text-slate-200 font-mono mt-2 block uppercase">
              {activeTrades ? activeTrades.today_summary.scalping_open_trades : 'No Data'}
            </span>
          </div>
          <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded">
            <span className="block text-[11px] text-slate-500 uppercase font-mono font-bold">Active Intraday Positions</span>
            <span className="text-base font-bold text-slate-200 font-mono mt-2 block uppercase">
              {activeTrades ? activeTrades.today_summary.intraday_open_trades : 'No Data'}
            </span>
          </div>
          <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded">
            <span className="block text-[11px] text-slate-500 uppercase font-mono font-bold">Net Unrealized PnL</span>
            <span className="text-base font-bold text-slate-200 font-mono mt-2 block uppercase">
              {activeTrades ? formatPnL(totalPnL) : 'No Data'}
            </span>
          </div>
          <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded">
            <span className="block text-[11px] text-slate-500 uppercase font-mono font-bold">Total Execution Volume</span>
            <span className="text-base font-bold text-slate-400 font-mono mt-2 block uppercase">N/A</span>
          </div>
        </div>
      </div>

      {isLoading && (
        <EmptyState
          title="Loading active trades"
          description="Fetching backend trade state."
          icon={<LoaderCircle size={24} className="animate-spin" />}
        />
      )}

      {!isLoading && error && (
        <EmptyState
          title="Failed to load active trades"
          description={error}
          icon={<AlertTriangle size={24} />}
        />
      )}

      {!isLoading && !error && activeTrades && settings && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                    <span className="w-1.5 h-3.5 bg-purple-500 rounded-sm inline-block"></span>
                    Scalping Trades Workspace
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 font-sans">High-frequency order matching logic</p>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="text-xs text-slate-500 font-mono uppercase font-bold">Control:</span>
                  <ToggleButton
                    checked={settings.engine_control.scalping_engine_enabled}
                    onChange={(checked) => void updateEngineControls({ scalping_engine_enabled: checked })}
                    disabled={isSaving}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-xs bg-slate-950/40 border border-slate-800 p-2.5 rounded">
                <span className="text-slate-500 font-mono font-bold uppercase">Strategy state:</span>
                <Badge variant={settings.engine_control.scalping_engine_enabled ? 'success' : 'gray'}>
                  {settings.engine_control.scalping_engine_enabled ? 'ENABLED' : 'DISABLED'}
                </Badge>
              </div>
              <div className="overflow-x-auto">
                <Table headers={activeHeaders}>
                  {activeTrades.scalping_trades.length > 0 ? (
                    renderTradeRows(activeTrades.scalping_trades)
                  ) : (
                    <tr>
                      <td colSpan={activeHeaders.length} className="text-center p-0">
                        <EmptyState
                          title="No active trades available"
                          description="Waiting for backend integration"
                          className="border-none bg-transparent py-12"
                        />
                      </td>
                    </tr>
                  )}
                </Table>
              </div>
            </div>

            <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                    <span className="w-1.5 h-3.5 bg-blue-500 rounded-sm inline-block"></span>
                    Intraday Trades Workspace
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 font-sans">Macro breakout support/resistance strategy</p>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="text-xs text-slate-500 font-mono uppercase font-bold">Control:</span>
                  <ToggleButton
                    checked={settings.engine_control.intraday_engine_enabled}
                    onChange={(checked) => void updateEngineControls({ intraday_engine_enabled: checked })}
                    disabled={isSaving}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-xs bg-slate-950/40 border border-slate-800 p-2.5 rounded">
                <span className="text-slate-500 font-mono font-bold uppercase">Strategy state:</span>
                <Badge variant={settings.engine_control.intraday_engine_enabled ? 'success' : 'gray'}>
                  {settings.engine_control.intraday_engine_enabled ? 'ENABLED' : 'DISABLED'}
                </Badge>
              </div>
              <div className="overflow-x-auto">
                <Table headers={activeHeaders}>
                  {activeTrades.intraday_trades.length > 0 ? (
                    renderTradeRows(activeTrades.intraday_trades)
                  ) : (
                    <tr>
                      <td colSpan={activeHeaders.length} className="text-center p-0">
                        <EmptyState
                          title="No active trades available"
                          description="Waiting for backend integration"
                          className="border-none bg-transparent py-12"
                        />
                      </td>
                    </tr>
                  )}
                </Table>
              </div>
            </div>
          </div>

          <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5">
            <SectionHeader
              title="Closed Trades Workspace"
              action={
                <div className="flex items-center gap-2">
                  <History size={14} className="text-slate-500" />
                  <span className="text-xs text-slate-500 font-mono font-bold uppercase">Archive</span>
                </div>
              }
            />
            <div className="overflow-x-auto mt-4">
              <Table headers={closedHeaders}>
                {closedTrades.length > 0 ? (
                  renderClosedTradeRows(closedTrades)
                ) : (
                  <tr>
                    <td colSpan={closedHeaders.length} className="text-center p-0">
                      <EmptyState
                        title="No trade history available"
                        description="Waiting for backend integration"
                        className="border-none bg-transparent py-12"
                      />
                    </td>
                  </tr>
                )}
              </Table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
