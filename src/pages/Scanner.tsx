import React, { useMemo, useState } from 'react';
import { Activity, AlertCircle, RefreshCw } from 'lucide-react';
import { fetchBackendSignals, runBackendScan } from '../api/client';
import { CanonicalScanData, ScannerResult, TradingMode } from '../api/types';
import { useApp } from '../context/AppContext';

type PanelState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';

interface ModePanelState {
  state: PanelState;
  data: CanonicalScanData | null;
  error: string | null;
  movedSignals: number;
}

const initialPanel: ModePanelState = {
  state: 'idle',
  data: null,
  error: null,
  movedSignals: 0,
};

function strategyLabel(mode: TradingMode): string {
  return mode === 'scalping' ? 'EMA Pullback Scalping' : 'Trend Continuation Intraday';
}

function timeframeLabel(mode: TradingMode): string {
  return mode === 'scalping' ? 'M1 / M5' : 'M15 / H1';
}

function candidateReason(item: ScannerResult): string {
  return item.failure_reason || item.rejection_reason || item.reason || 'No additional backend reason.';
}

function CandidateTable({ rows, mode }: { rows: ScannerResult[]; mode: TradingMode }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center text-sm text-slate-500">
        No pending, rejected, skipped, or failed {mode} candidates.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full min-w-[760px] text-left text-xs">
        <thead className="bg-slate-950/80 text-[10px] uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-3 py-3">Symbol</th>
            <th className="px-3 py-3">Side</th>
            <th className="px-3 py-3">Grade</th>
            <th className="px-3 py-3">Price</th>
            <th className="px-3 py-3">TF</th>
            <th className="px-3 py-3">Status</th>
            <th className="px-3 py-3">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-900">
          {rows.map((item, index) => (
            <tr key={`${mode}-${item.symbol}-${item.timeframe}-${item.outcome}-${index}`} className="align-top">
              <td className="px-3 py-3 font-black text-white">{item.symbol}</td>
              <td className="px-3 py-3 font-bold text-slate-200">{item.direction?.toUpperCase() ?? 'N/A'}</td>
              <td className="px-3 py-3 font-bold text-slate-200">{item.grade ?? 'N/A'}</td>
              <td className="px-3 py-3 font-mono text-slate-300">{item.metrics?.current_price ?? 'N/A'}</td>
              <td className="px-3 py-3 text-slate-300">{item.timeframe ?? 'N/A'}</td>
              <td className="px-3 py-3">
                <span className={`rounded border px-2 py-1 text-[10px] font-black uppercase ${
                  item.outcome === 'rejected'
                    ? 'border-rose-900 bg-rose-950/30 text-rose-400'
                    : item.outcome === 'failed'
                      ? 'border-red-900 bg-red-950/30 text-red-400'
                      : 'border-amber-900 bg-amber-950/30 text-amber-400'
                }`}>
                  {item.outcome}
                </span>
              </td>
              <td className="max-w-[270px] px-3 py-3 leading-relaxed text-slate-400">
                <div className="font-semibold text-slate-300">{item.strategy ?? strategyLabel(mode)}</div>
                <div className="mt-1">{candidateReason(item)}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScannerPanel({
  mode,
  panel,
  disabled,
  onScan,
}: {
  mode: TradingMode;
  panel: ModePanelState;
  disabled: boolean;
  onScan: () => void;
}) {
  const rows = useMemo(
    () => (panel.data?.results ?? []).filter((item) => item.outcome !== 'actionable'),
    [panel.data],
  );

  const counts = useMemo(() => rows.reduce((acc, item) => {
    acc.total += 1;
    if (item.outcome === 'rejected') acc.rejected += 1;
    if (item.outcome === 'skipped') acc.skipped += 1;
    if (item.outcome === 'failed') acc.failed += 1;
    return acc;
  }, { total: 0, rejected: 0, skipped: 0, failed: 0 }), [rows]);

  const title = mode === 'scalping' ? 'Scalping Scanner' : 'Intraday Scanner';

  return (
    <section className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-lg">
      <div className="flex flex-col gap-3 border-b border-slate-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-black text-white">{title}</h2>
          <p className="mt-1 text-xs text-slate-500">{timeframeLabel(mode)} · {strategyLabel(mode)}</p>
        </div>
        <button
          type="button"
          onClick={onScan}
          disabled={disabled}
          className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-black text-slate-950 disabled:opacity-50"
        >
          <RefreshCw size={15} className={panel.state === 'loading' ? 'animate-spin' : ''} />
          {panel.state === 'loading' ? 'Scanning' : `Run ${mode === 'scalping' ? 'Scalping' : 'Intraday'}`}
        </button>
      </div>

      <div className="my-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
        {[
          ['Candidates', counts.total],
          ['Rejected', counts.rejected],
          ['Skipped', counts.skipped],
          ['Failed', counts.failed],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
            <div className="text-[9px] font-bold uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-1 text-xl font-black text-white">{value}</div>
          </div>
        ))}
      </div>

      {panel.movedSignals > 0 && (
        <div className="mb-4 rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-xs text-emerald-300">
          {panel.movedSignals} actionable signal{panel.movedSignals === 1 ? '' : 's'} moved to AI Signals and removed from this table.
        </div>
      )}

      {panel.state === 'idle' && (
        <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center text-sm text-slate-500">
          Run this scanner to load current candidates.
        </div>
      )}
      {panel.state === 'loading' && (
        <div className="rounded-lg border border-slate-800 p-8 text-center text-sm text-slate-400">Scanning canonical backend…</div>
      )}
      {panel.state === 'error' && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-900/50 bg-rose-950/20 p-4 text-sm text-rose-300">
          <AlertCircle size={17} className="mt-0.5 shrink-0" /> {panel.error || 'Scanner request failed.'}
        </div>
      )}
      {(panel.state === 'ready' || panel.state === 'empty') && <CandidateTable rows={rows} mode={mode} />}
    </section>
  );
}

export default function Scanner() {
  const { refreshSignals } = useApp();
  const [panels, setPanels] = useState<Record<TradingMode, ModePanelState>>({
    scalping: initialPanel,
    intraday: initialPanel,
  });
  const [activeScan, setActiveScan] = useState<TradingMode | null>(null);

  const scanMode = async (mode: TradingMode) => {
    setActiveScan(mode);
    setPanels((current) => ({
      ...current,
      [mode]: { ...current[mode], state: 'loading', error: null, movedSignals: 0 },
    }));

    try {
      const data = await runBackendScan({ mode });
      const signalData = await fetchBackendSignals({ mode });
      const actionableSymbols = new Set(
        signalData.signals
          .filter((signal) => signal.status !== 'filtered_by_risk_profile')
          .map((signal) => `${signal.symbol}:${signal.timeframe}:${signal.direction}`),
      );
      const movedSignals = data.results.filter((item) =>
        item.outcome === 'actionable'
        || actionableSymbols.has(`${item.symbol}:${item.timeframe}:${item.direction}`),
      ).length;
      const remaining = data.results.filter((item) => item.outcome !== 'actionable');
      const visibleData = { ...data, results: remaining };

      setPanels((current) => ({
        ...current,
        [mode]: {
          state: remaining.length ? 'ready' : 'empty',
          data: visibleData,
          error: null,
          movedSignals,
        },
      }));
      await refreshSignals();
    } catch (error) {
      setPanels((current) => ({
        ...current,
        [mode]: {
          ...current[mode],
          state: 'error',
          error: error instanceof Error ? error.message : 'Scanner request failed.',
        },
      }));
    } finally {
      setActiveScan(null);
    }
  };

  return (
    <div className="space-y-5 p-4 md:p-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-black text-white"><Activity className="text-emerald-400" /> Market Scanner</h1>
        <p className="mt-1 text-sm text-slate-500">Independent 50/50 scanner tables. Actionable setups are transferred to AI Signals.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ScannerPanel
          mode="scalping"
          panel={panels.scalping}
          disabled={activeScan !== null}
          onScan={() => void scanMode('scalping')}
        />
        <ScannerPanel
          mode="intraday"
          panel={panels.intraday}
          disabled={activeScan !== null}
          onScan={() => void scanMode('intraday')}
        />
      </div>
    </div>
  );
}
