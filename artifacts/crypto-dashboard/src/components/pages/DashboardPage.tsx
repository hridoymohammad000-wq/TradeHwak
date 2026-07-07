import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from '../UIFoundation';
import { backendApi } from '../../api/services';
import type {
  BybitMarketSnapshotData,
  DashboardSummaryData,
  HealthData,
  TradingMode,
  WorkflowStatusData,
} from '../../api/types';
import type { BackendStatus } from '../../App';
import { ActivePage } from '../../types';
import {
  AlertTriangle,
  BellRing,
  Bot,
  ChevronDown,
  Cpu,
  Database,
  LoaderCircle,
  Play,
  RefreshCw,
  Settings2,
  Square,
  Zap,
} from 'lucide-react';

type BotOperationStatus = 'Idle' | 'Starting' | 'Running' | 'Stopped' | 'Failed';

function formatCount(value: number) {
  return value.toLocaleString();
}

function formatTimestamp(value: Date | null) {
  return value ? value.toLocaleString() : 'Not yet';
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

interface DashboardPageProps {
  backendStatus: BackendStatus;
  onNavigate: (page: ActivePage) => void;
}

export function DashboardPage({ backendStatus, onNavigate }: DashboardPageProps) {
  const [summary, setSummary] = useState<DashboardSummaryData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowStatusData | null>(null);
  const [marketSnapshot, setMarketSnapshot] = useState<BybitMarketSnapshotData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [botStatus, setBotStatus] = useState<BotOperationStatus>('Idle');
  const [commandBusy, setCommandBusy] = useState(false);
  const [latestError, setLatestError] = useState<string | null>(null);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [lastScanTime, setLastScanTime] = useState<Date | null>(null);
  const [latestSignalCount, setLatestSignalCount] = useState(0);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const commandLockRef = useRef(false);

  const acquireCommandLock = () => {
    if (commandLockRef.current) return false;
    commandLockRef.current = true;
    setCommandBusy(true);
    return true;
  };

  const releaseCommandLock = () => {
    commandLockRef.current = false;
    setCommandBusy(false);
  };

  const loadSharedStatus = useCallback(async (signal?: AbortSignal) => {
    const [summaryResponse, healthResponse, workflowResponse, marketSnapshotResponse] = await Promise.all([
      backendApi.getDashboardSummary(signal),
      backendApi.getHealth(signal),
      backendApi.getWorkflowStatus(signal),
      backendApi.getBybitMarketSnapshot('BTCUSDT', signal),
    ]);

    setSummary(summaryResponse.data);
    setHealth(healthResponse.data);
    setWorkflow(workflowResponse.data);
    setMarketSnapshot(marketSnapshotResponse.data);
    setLastRefreshTime(new Date());

    const running =
      summaryResponse.data.auto_trade_enabled &&
      (summaryResponse.data.scalping_engine_enabled || summaryResponse.data.intraday_engine_enabled) &&
      !summaryResponse.data.emergency_stop;
    setBotStatus(running ? 'Running' : 'Stopped');

    return summaryResponse.data;
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDashboard() {
      if (backendStatus !== 'healthy') {
        setSummary(null);
        setHealth(null);
        setWorkflow(null);
        setMarketSnapshot(null);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        if (backendStatus === 'error') setBotStatus('Failed');
        return;
      }

      try {
        setIsLoading(true);
        setError(null);
        await loadSharedStatus(controller.signal);
      } catch (loadError) {
        const message = getErrorMessage(loadError, 'Failed to load dashboard summary');
        setError(message);
        setLatestError(message);
        setBotStatus('Failed');
      } finally {
        setIsLoading(false);
      }
    }

    void loadDashboard();
    return () => controller.abort();
  }, [backendStatus, loadSharedStatus]);

  const refreshStatus = async () => {
    if (backendStatus !== 'healthy' || !acquireCommandLock()) return;
    setLatestError(null);

    try {
      await loadSharedStatus();
    } catch (refreshError) {
      const message = getErrorMessage(refreshError, 'Failed to refresh status');
      setLatestError(message);
      setBotStatus('Failed');
    } finally {
      releaseCommandLock();
    }
  };

  const startBot = async () => {
    if (botStatus === 'Running' || backendStatus !== 'healthy' || !acquireCommandLock()) return;

    setBotStatus('Starting');
    setLatestError(null);

    try {
      const modeResponse = await backendApi.getMode();
      const mode: TradingMode = modeResponse.data.active_strategy_mode;

      await backendApi.updateEngineControl({
        emergency_stop: false,
        auto_trade_enabled: true,
        ...(mode === 'scalping'
          ? { scalping_engine_enabled: true }
          : { intraday_engine_enabled: true }),
      });

      await backendApi.scanMarket({ mode });
      setLastScanTime(new Date());

      const signalsResponse = await backendApi.getSignals({ mode });
      setLatestSignalCount(signalsResponse.data.signals.length);

      await loadSharedStatus();
      setBotStatus('Running');
    } catch (startError) {
      const message = getErrorMessage(startError, 'Failed to start bot');
      setLatestError(message);
      setBotStatus('Failed');
    } finally {
      releaseCommandLock();
    }
  };

  const stopBot = async () => {
    if (backendStatus !== 'healthy' || !acquireCommandLock()) return;

    setLatestError(null);

    try {
      await backendApi.updateEngineControl({
        auto_trade_enabled: false,
        scalping_engine_enabled: false,
        intraday_engine_enabled: false,
      });
      await loadSharedStatus();
      setBotStatus('Stopped');
    } catch (stopError) {
      const message = getErrorMessage(stopError, 'Failed to stop bot');
      setLatestError(message);
      setBotStatus('Failed');
    } finally {
      releaseCommandLock();
    }
  };

  const guiBadge = error
    ? { status: 'danger' as const, label: 'Backend Offline' }
    : isLoading
      ? { status: 'pending' as const, label: 'Loading' }
      : { status: 'active' as const, label: 'Connected' };

  const commandBadge =
    botStatus === 'Running'
      ? { status: 'active' as const, label: botStatus }
      : botStatus === 'Starting'
        ? { status: 'pending' as const, label: botStatus }
        : botStatus === 'Failed'
          ? { status: 'danger' as const, label: botStatus }
          : { status: 'inactive' as const, label: botStatus };

  const diagnostics = [
    {
      icon: Database,
      label: 'Backend Phase',
      status: health?.phase === 'foundation' ? 'pending' : 'active',
      value: health?.phase || 'Pending',
    },
    {
      icon: Zap,
      label: 'Execution Engine',
      status: health?.execution_enabled ? 'active' : 'inactive',
      value: health?.execution_enabled ? 'Enabled' : 'Disabled',
    },
    {
      icon: Cpu,
      label: 'Scalping Engine',
      status: summary?.scalping_engine_enabled ? 'active' : 'inactive',
      value: summary?.scalping_engine_enabled ? 'Enabled' : 'Disabled',
    },
    {
      icon: BellRing,
      label: 'Intraday Engine',
      status: summary?.intraday_engine_enabled ? 'active' : 'inactive',
      value: summary?.intraday_engine_enabled ? 'Enabled' : 'Disabled',
    },
  ];

  const formatMarketValue = (value: number | null, digits = 2) =>
    value === null ? 'No Data' : value.toFixed(digits);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard Console"
        description="System telemetry, daemon logs, and dual-strategy coordination."
        action={
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 uppercase font-mono font-bold">GUI State:</span>
            <StatusBadge status={guiBadge.status} label={guiBadge.label} />
          </div>
        }
      />

      <div className="space-y-4">
        <SectionHeader title="Command Center / Bot Control" />
        <Card className="border-indigo-500/30 bg-indigo-950/10">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-2.5">
                  <Bot size={22} className="text-indigo-300" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-slate-100">Bot Operation</h3>
                    <StatusBadge status={commandBadge.status} label={commandBadge.label} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    Start runs the existing engine, scanner, signals, dashboard, workflow, and logs flow in sequence.
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="success"
                  onClick={() => void startBot()}
                  disabled={commandBusy || botStatus === 'Running' || backendStatus !== 'healthy'}
                  className="min-w-28"
                >
                  {botStatus === 'Starting' ? <LoaderCircle size={16} className="animate-spin" /> : <Play size={16} />}
                  Start Bot
                </Button>
                <Button
                  variant="danger"
                  onClick={() => void stopBot()}
                  disabled={commandBusy || backendStatus !== 'healthy' || botStatus === 'Stopped'}
                  className="min-w-28"
                >
                  <Square size={15} />
                  Stop Bot
                </Button>
                <Button
                  variant="outline"
                  onClick={() => void refreshStatus()}
                  disabled={commandBusy || backendStatus !== 'healthy'}
                  className="min-w-32"
                >
                  <RefreshCw size={16} className={commandBusy ? 'animate-spin' : ''} />
                  Refresh Status
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 border-t border-slate-800/70 pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded border border-slate-800 bg-slate-950/35 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Last Refresh</p>
                <p className="mt-1 text-xs font-mono text-slate-300">{formatTimestamp(lastRefreshTime)}</p>
              </div>
              <div className="rounded border border-slate-800 bg-slate-950/35 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Last Scan</p>
                <p className="mt-1 text-xs font-mono text-slate-300">
                  {lastScanTime ? formatTimestamp(lastScanTime) : workflow?.last_cycle_at || 'Not available'}
                </p>
              </div>
              <div className="rounded border border-slate-800 bg-slate-950/35 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Latest Signals</p>
                <p className="mt-1 text-xs font-mono text-slate-300">{latestSignalCount}</p>
              </div>
              <div className="rounded border border-slate-800 bg-slate-950/35 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Workflow</p>
                <p className="mt-1 text-xs font-mono text-slate-300">
                  {workflow ? `${workflow.scanner_status} / ${workflow.signal_status}` : 'Not available'}
                </p>
              </div>
            </div>

            {latestError && (
              <div className="flex items-start gap-2 rounded border border-rose-900/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-300">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold">Latest error</p>
                  <p className="mt-0.5 text-xs text-rose-300/80">{latestError}</p>
                </div>
              </div>
            )}

            <div className="border-t border-slate-800/70 pt-3">
              <button
                type="button"
                onClick={() => setAdvancedOpen((current) => !current)}
                className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 transition-colors hover:text-slate-200"
              >
                <Settings2 size={14} />
                Advanced Controls
                <ChevronDown size={14} className={`transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
              </button>
              {advancedOpen && (
                <div className="mt-3 flex flex-wrap gap-2 rounded border border-slate-800 bg-slate-950/25 p-3">
                  <Button size="sm" variant="outline" onClick={() => onNavigate(ActivePage.SCANNER)}>Scanner</Button>
                  <Button size="sm" variant="outline" onClick={() => onNavigate(ActivePage.SIGNALS)}>Signals</Button>
                  <Button size="sm" variant="outline" onClick={() => onNavigate(ActivePage.CHART)}>Chart</Button>
                  <Button size="sm" variant="outline" onClick={() => onNavigate(ActivePage.SETTINGS)}>Settings</Button>
                  <span className="self-center text-[10px] text-slate-500">
                    Existing manual controls remain unchanged on their original pages.
                  </span>
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <SectionHeader title="Today's Session Performance Summary" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card title="Active Trades Open">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                {summary ? formatCount(summary.today_summary.total_open_trades) : 'No Data'}
              </span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                {summary ? 'Live count from backend summary' : 'Waiting for backend integration'}
              </p>
            </div>
          </Card>
          <Card title="Closed Trades Today">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                {summary ? formatCount(summary.today_summary.closed_trades_today) : 'No Data'}
              </span>
              <p className="text-xs text-slate-500 mt-2 font-sans">
                {summary ? 'Backend-provided trade completion count' : 'Waiting for backend integration'}
              </p>
            </div>
          </Card>
          <Card title="Strategy Mode">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                {summary?.active_strategy_mode || 'No Data'}
              </span>
              <p className="text-xs text-slate-500 mt-2 font-sans">Current backend-selected strategy mode</p>
            </div>
          </Card>
          <Card title="System Mode">
            <div className="py-2">
              <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                {summary?.system_mode || 'No Data'}
              </span>
              <p className="text-xs text-slate-500 mt-2 font-sans">Demo/live mode from backend runtime state</p>
            </div>
          </Card>
        </div>
      </div>

      {isLoading && (
        <EmptyState
          title="Loading dashboard summary"
          description="Fetching backend dashboard state."
          icon={<LoaderCircle size={24} className="animate-spin" />}
        />
      )}

      {!isLoading && error && (
        <EmptyState
          title="Failed to load dashboard summary"
          description={error}
          icon={<AlertTriangle size={24} />}
        />
      )}

      {!isLoading && !error && summary && (
        <>
          <div className="space-y-4">
            <SectionHeader title="Bybit Demo Market Snapshot" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card title={marketSnapshot?.symbol || 'BTCUSDT'}>
                <div className="py-2">
                  <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                    {formatMarketValue(marketSnapshot?.last_price ?? null, 4)}
                  </span>
                  <p className="text-xs text-slate-500 mt-2 font-sans">Last traded price</p>
                </div>
              </Card>
              <Card title="24H Change">
                <div className="py-2">
                  <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                    {marketSnapshot?.price_change_percent_24h !== null && marketSnapshot?.price_change_percent_24h !== undefined
                      ? `${(marketSnapshot.price_change_percent_24h * 100).toFixed(2)}%`
                      : 'No Data'}
                  </span>
                  <p className="text-xs text-slate-500 mt-2 font-sans">Realtime Bybit ticker move</p>
                </div>
              </Card>
              <Card title="Bid / Ask">
                <div className="py-2 space-y-2">
                  <div className="flex justify-between gap-3 text-xs font-mono">
                    <span className="text-slate-500">Bid</span>
                    <span className="text-slate-200">{formatMarketValue(marketSnapshot?.best_bid_price ?? null, 4)}</span>
                  </div>
                  <div className="flex justify-between gap-3 text-xs font-mono">
                    <span className="text-slate-500">Ask</span>
                    <span className="text-slate-200">{formatMarketValue(marketSnapshot?.best_ask_price ?? null, 4)}</span>
                  </div>
                </div>
              </Card>
              <Card title="Spread">
                <div className="py-2">
                  <span className="text-lg font-bold font-mono text-slate-200 uppercase">
                    {marketSnapshot?.spread_percent !== null && marketSnapshot?.spread_percent !== undefined
                      ? `${marketSnapshot.spread_percent.toFixed(4)}%`
                      : 'No Data'}
                  </span>
                  <p className="text-xs text-slate-500 mt-2 font-sans">
                    {marketSnapshot?.fetched_at || 'Waiting for Bybit response'}
                  </p>
                </div>
              </Card>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-4">
              <SectionHeader title="Engine Workflow Coordination" />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-purple-400 font-mono">SCALPING MODULE</span>
                      <StatusBadge
                        status={summary.scalping_engine_enabled ? 'active' : 'inactive'}
                        label={summary.scalping_engine_enabled ? 'Enabled' : 'Disabled'}
                      />
                    </div>
                    <h3 className="text-base font-bold text-slate-200">Ultra-Fast Order Matching</h3>
                    <p className="text-xs text-slate-400 font-sans leading-relaxed">
                      Existing backend engine state and controls are used without modifying trading logic.
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-800/60 font-mono text-[10px] text-slate-500 flex justify-between">
                    <span className="uppercase font-bold">{summary.active_strategy_mode === 'scalping' ? 'Primary Mode' : 'Standby'}</span>
                  </div>
                </div>
                <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-blue-400 font-mono">INTRADAY MODULE</span>
                      <StatusBadge
                        status={summary.intraday_engine_enabled ? 'active' : 'inactive'}
                        label={summary.intraday_engine_enabled ? 'Enabled' : 'Disabled'}
                      />
                    </div>
                    <h3 className="text-base font-bold text-slate-200">Macro Breakout Strategy</h3>
                    <p className="text-xs text-slate-400 font-sans leading-relaxed">
                      Existing backend engine state and controls are used without modifying trading logic.
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-800/60 font-mono text-[10px] text-slate-500 flex justify-between">
                    <span className="uppercase font-bold">{summary.active_strategy_mode === 'intraday' ? 'Primary Mode' : 'Standby'}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="space-y-4">
              <SectionHeader title="Subsystem Diagnostics" />
              <div className="space-y-3.5 bg-slate-900/40 border border-slate-800/80 rounded-lg p-4">
                {diagnostics.map(({ icon: Icon, label, status, value }) => (
                  <div key={label} className="flex items-center justify-between p-2.5 rounded bg-slate-950/30 border border-slate-900">
                    <div className="flex items-center gap-2.5">
                      <Icon size={16} className="text-slate-500" />
                      <span className="text-xs font-semibold text-slate-300 font-mono">{label}</span>
                    </div>
                    <StatusBadge status={status as 'active' | 'inactive' | 'pending'} label={value} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <SectionHeader title="Operator Telemetry Logs" />
            {summary.recent_events.length > 0 ? (
              <div className="space-y-3">
                {summary.recent_events.map((event, index) => (
                  <div key={`${event.event_type}-${index}`} className="rounded border border-slate-800 bg-slate-900/30 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-300 font-mono">{event.event_type}</span>
                      <span className="text-[10px] uppercase text-slate-500 font-mono">
                        {event.created_at || 'Timestamp unavailable'}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-400 font-sans">{event.message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Waiting for backend integration" description="No operational events are being emitted yet." />
            )}
          </div>
        </>
      )}
    </div>
  );
}
