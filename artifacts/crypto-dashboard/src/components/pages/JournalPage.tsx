import React, { useEffect, useState } from 'react';
import { Card, EmptyState, PageHeader, SectionHeader, Table } from '../UIFoundation';
import { backendApi } from '../../api/services';
import type { ClosedTradeRecord } from '../../api/types';
import type { BackendStatus } from '../../App';
import { Edit3, AlertTriangle, LoaderCircle } from 'lucide-react';

function formatPrice(value: number | null) {
  return value === null ? '-' : value.toFixed(4);
}

function formatRate(value: number | null) {
  return value === null ? 'No Data' : `${value.toFixed(1)}%`;
}

function formatPnL(value: number | null) {
  return value === null ? 'N/A' : value.toFixed(2);
}

export function JournalPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const headers = ['Symbol', 'Mode', 'Direction', 'Entry', 'Exit', 'PnL', 'Reason', 'Closed Time'];
  const [closedTrades, setClosedTrades] = useState<ClosedTradeRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadJournal() {
      if (backendStatus !== 'healthy') {
        setClosedTrades([]);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        return;
      }
      try {
        setIsLoading(true);
        setError(null);
        const response = await backendApi.getClosedTrades(controller.signal);
        setClosedTrades(response.data.closed_trades);
      } catch (loadError) {
        setClosedTrades([]);
        setError(loadError instanceof Error ? loadError.message : 'Failed to load trade history');
      } finally {
        setIsLoading(false);
      }
    }

    void loadJournal();
    return () => controller.abort();
  }, [backendStatus]);

  const results = closedTrades.map((trade) => trade.result?.toLowerCase() || '');
  const winCount = results.filter((result) => result === 'win').length;
  const lossCount = results.filter((result) => result === 'loss').length;
  const resolvedCount = winCount + lossCount;
  const winRate = resolvedCount > 0 ? (winCount / resolvedCount) * 100 : null;
  const lossRate = resolvedCount > 0 ? (lossCount / resolvedCount) * 100 : null;
  const netResult = closedTrades.reduce((sum, trade) => sum + (trade.realized_pnl || 0), 0);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Operator Trade Journal"
        description="Historical trade records, performance audit, and operator notes."
      />

      <div className="space-y-4">
        <SectionHeader title="Global Performance Overview" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card title="Total Closed Trades">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                {isLoading ? 'Loading' : closedTrades.length.toLocaleString()}
              </span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                {closedTrades.length > 0 ? 'Loaded from backend history' : 'Waiting for backend integration'}
              </p>
            </div>
          </Card>
          <Card title="Overall Win Rate">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">{formatRate(winRate)}</span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                {winRate === null ? 'Waiting for backend integration' : 'Computed from backend result values'}
              </p>
            </div>
          </Card>
          <Card title="Overall Loss Rate">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">{formatRate(lossRate)}</span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                {lossRate === null ? 'Waiting for backend integration' : 'Computed from backend result values'}
              </p>
            </div>
          </Card>
          <Card title="Net Result">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">{formatPnL(netResult)}</span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                Sum of realized backend trade pnl
              </p>
            </div>
          </Card>
        </div>
      </div>

      {isLoading && (
        <EmptyState
          title="Loading trade history"
          description="Fetching backend journal records."
          icon={<LoaderCircle size={24} className="animate-spin" />}
        />
      )}

      {!isLoading && error && (
        <EmptyState
          title="Failed to load trade history"
          description={error}
          icon={<AlertTriangle size={24} />}
        />
      )}

      {!isLoading && !error && (
        <>
          <div className="space-y-4">
            <SectionHeader title="Closed Trade History" />
            <div className="overflow-x-auto">
              <Table headers={headers}>
                {closedTrades.length > 0 ? (
                  closedTrades.map((trade) => (
                    <tr key={`${trade.mode}-${trade.symbol}-${trade.closed_time || trade.status}`}>
                      <td className="px-4 py-3 font-mono text-xs">{trade.symbol}</td>
                      <td className="px-4 py-3 uppercase text-xs text-slate-300">{trade.mode}</td>
                      <td className="px-4 py-3 uppercase text-xs text-slate-300">{trade.direction}</td>
                      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.entry_price)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{formatPrice(trade.exit_price)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{formatPnL(trade.realized_pnl)}</td>
                      <td className="px-4 py-3 text-xs text-slate-300">{trade.close_reason || trade.exit_analysis || trade.status}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{trade.closed_time || 'Pending'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={headers.length} className="text-center p-0">
                      <EmptyState
                        title="No trade history available"
                        description="Waiting for backend integration"
                        className="border-none bg-transparent py-16"
                      />
                    </td>
                  </tr>
                )}
              </Table>
            </div>
          </div>

          <div className="space-y-4">
            <SectionHeader title="Operator Notes & Audit Comments" />
            <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5">
              <div className="flex items-start gap-4 text-slate-500">
                <Edit3 size={20} className="mt-1 shrink-0" />
                <div className="w-full">
                  <h4 className="text-sm font-bold text-slate-300 font-mono mb-2">Session Notes Workspace</h4>
                  <textarea
                    className="w-full h-24 bg-slate-950 border border-slate-800 rounded p-3 text-xs text-slate-500 font-sans focus:outline-none focus:border-indigo-500 cursor-not-allowed"
                    placeholder="Operator review notes feature pending backend storage integration..."
                    disabled
                  ></textarea>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
