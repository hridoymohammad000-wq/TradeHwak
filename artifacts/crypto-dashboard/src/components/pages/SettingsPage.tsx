import React, { useEffect, useMemo, useState } from 'react';
import { Badge, Button, EmptyState, PageHeader, StatusBadge, ToggleButton } from '../UIFoundation';
import { backendApi } from '../../api/services';
import { getBackendConnectionInfo } from '../../api/client';
import type {
  BybitConfigStatusData,
  BybitConnectionStatusData,
  HealthData,
  ModeData,
  RuntimeMode,
  SettingsViewData,
  SignalGrade,
  TradingMode,
  WorkflowStatusData,
} from '../../api/types';
import type { BackendStatus } from '../../App';
import { AlertTriangle, CheckCircle2, Info, LoaderCircle, Server } from 'lucide-react';

function parseNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const riskOptions = [0, 0.25, 0.5, 1, 2, 3, 5];
const slotOptions = [0, 1, 2, 3, 5, 10, 20];

export function SettingsPage({ backendStatus }: { backendStatus: BackendStatus }) {
  const connectionInfo = useMemo(() => getBackendConnectionInfo(), []);
  const [settings, setSettings] = useState<SettingsViewData | null>(null);
  const [mode, setMode] = useState<ModeData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [bybitConfig, setBybitConfig] = useState<BybitConfigStatusData | null>(null);
  const [bybitConnection, setBybitConnection] = useState<BybitConnectionStatusData | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatusData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTestingBybit, setIsTestingBybit] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSettings() {
      if (backendStatus !== 'healthy') {
        setSettings(null);
        setMode(null);
        setHealth(null);
        setBybitConfig(null);
        setBybitConnection(null);
        setWorkflowStatus(null);
        setError(backendStatus === 'error' ? 'Backend unavailable' : null);
        setIsLoading(backendStatus === 'loading');
        return;
      }
      try {
        setIsLoading(true);
        setError(null);
        const [settingsResponse, modeResponse, healthResponse, bybitConfigResponse, bybitConnectionResponse, workflowResponse] = await Promise.all([
          backendApi.getSettingsView(controller.signal),
          backendApi.getMode(controller.signal),
          backendApi.getHealth(controller.signal),
          backendApi.getBybitConfigStatus(controller.signal),
          backendApi.getBybitConnection(controller.signal),
          backendApi.getWorkflowStatus(controller.signal),
        ]);
        setSettings(settingsResponse.data);
        setMode(modeResponse.data);
        setHealth(healthResponse.data);
        setBybitConfig(bybitConfigResponse.data);
        setBybitConnection(bybitConnectionResponse.data);
        setWorkflowStatus(workflowResponse.data);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load settings');
      } finally {
        setIsLoading(false);
      }
    }

    void loadSettings();
    const intervalId = window.setInterval(() => {
      void loadSettings();
    }, 10000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [backendStatus]);

  async function refreshSettings() {
    const [settingsResponse, modeResponse, healthResponse, bybitConfigResponse, bybitConnectionResponse, workflowResponse] = await Promise.all([
      backendApi.getSettingsView(),
      backendApi.getMode(),
      backendApi.getHealth(),
      backendApi.getBybitConfigStatus(),
      backendApi.getBybitConnection(),
      backendApi.getWorkflowStatus(),
    ]);
    setSettings(settingsResponse.data);
    setMode(modeResponse.data);
    setHealth(healthResponse.data);
    setBybitConfig(bybitConfigResponse.data);
    setBybitConnection(bybitConnectionResponse.data);
    setWorkflowStatus(workflowResponse.data);
  }

  async function runMutation(run: () => Promise<void>, success: string) {
    if (backendStatus !== 'healthy') {
      setError('Backend unavailable');
      return;
    }
    try {
      setIsSaving(true);
      setError(null);
      setSuccessMessage(null);
      await run();
      await refreshSettings();
      setSuccessMessage(success);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to update settings');
      setSuccessMessage(null);
    } finally {
      setIsSaving(false);
    }
  }

  const currentRiskOptions = settings
    ? Array.from(new Set([...riskOptions, settings.risk.risk_per_trade_pct])).sort((a, b) => a - b)
    : riskOptions;
  const currentSlotOptions = settings
    ? Array.from(new Set([...slotOptions, settings.risk.max_open_positions])).sort((a, b) => a - b)
    : slotOptions;

  async function runBybitConnectionTest() {
    if (backendStatus !== 'healthy') {
      setError('Backend unavailable');
      return;
    }
    try {
      setIsTestingBybit(true);
      setError(null);
      setSuccessMessage(null);
      const response = await backendApi.testBybitConnection();
      setBybitConnection(response.data);
      setSuccessMessage(response.data.status);
      const refreshedConfig = await backendApi.getBybitConfigStatus();
      setBybitConfig(refreshedConfig.data);
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : 'Failed to test Bybit connection');
    } finally {
      setIsTestingBybit(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="System Control Center"
        description="Configure, monitor, and command core trading engines and driver settings."
        action={
          <div className="flex items-center gap-3">
            {successMessage && (
              <Badge variant="success" className="px-3 py-1.5 text-xs font-mono font-bold uppercase">
                {successMessage}
              </Badge>
            )}
            <Badge variant="gray" className="px-3 py-1.5 text-xs font-mono font-bold uppercase">
              {isSaving ? 'Saving Changes' : 'Phase 1 Connected'}
            </Badge>
          </div>
        }
      />

      {isLoading && (
        <EmptyState
          title="Loading settings"
          description="Fetching backend configuration."
          icon={<LoaderCircle size={24} className="animate-spin" />}
        />
      )}

      {!isLoading && error && !settings && (
        <EmptyState
          title="Failed to load settings"
          description={error}
          icon={<AlertTriangle size={24} />}
        />
      )}

      {!isLoading && settings && mode && (
        <>
          {error && (
            <div className="rounded border border-rose-900/40 bg-rose-950/20 px-4 py-3 text-sm text-rose-300 font-sans">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">01.</span>
                  System Status Indicators
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  System telemetry indicating module connection status.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">GUI Console:</span>
                    <StatusBadge
                      status={backendStatus === 'healthy' ? 'active' : 'danger'}
                      label={backendStatus === 'healthy' ? 'Connected' : 'Offline'}
                    />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Core Loop:</span>
                    <StatusBadge
                      status={backendStatus === 'healthy' ? 'active' : 'inactive'}
                      label={health?.phase || 'Pending'}
                    />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">WebSocket Port:</span>
                    <StatusBadge status="inactive" label="Not Used" />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">SQLite Driver:</span>
                    <StatusBadge status="pending" label="Pending" />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-800/60">
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">System Mode</label>
                    <select
                      value={mode.system_mode}
                      onChange={(event) => {
                        const nextValue = event.target.value as RuntimeMode;
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ system_mode: nextValue });
                          },
                          'System Mode Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none font-mono"
                    >
                      {mode.available_system_modes.map((systemMode) => (
                        <option key={systemMode} value={systemMode}>
                          {systemMode.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Strategy Mode</label>
                    <select
                      value={mode.active_strategy_mode}
                      onChange={(event) => {
                        const nextValue = event.target.value as TradingMode;
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ active_strategy_mode: nextValue });
                          },
                          'Strategy Mode Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none font-mono"
                    >
                      {mode.available_strategy_modes.map((strategyMode) => (
                        <option key={strategyMode} value={strategyMode}>
                          {strategyMode.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">02.</span>
                  Bybit Demo Connection
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Demo exchange config and authenticated connection status for the first Bybit integration slice.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Frontend Host</label>
                    <input
                      type="text"
                      value={connectionInfo.host}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-300 rounded font-bold focus:outline-none"
                      readOnly
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Backend Port</label>
                    <input
                      type="text"
                      value={connectionInfo.port}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-300 rounded font-bold focus:outline-none"
                      readOnly
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">API Key</span>
                    <StatusBadge
                      status={bybitConfig?.api_key_configured ? 'active' : 'inactive'}
                      label={bybitConfig?.api_key_configured ? 'Configured' : 'Missing'}
                    />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">API Secret</span>
                    <StatusBadge
                      status={bybitConfig?.api_secret_configured ? 'active' : 'inactive'}
                      label={bybitConfig?.api_secret_configured ? 'Configured' : 'Missing'}
                    />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Environment</span>
                    <StatusBadge
                      status={bybitConfig?.environment === 'demo' ? 'active' : 'danger'}
                      label={bybitConfig?.environment?.toUpperCase() || 'UNKNOWN'}
                    />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Connection</span>
                    <StatusBadge
                      status={
                        bybitConnection?.code === 'CONNECTED'
                          ? 'active'
                          : bybitConnection?.code === 'NOT_CONFIGURED'
                            ? 'inactive'
                            : 'danger'
                      }
                      label={bybitConnection?.code || 'PENDING'}
                    />
                  </div>
                </div>
                <div className="space-y-2 rounded border border-slate-800/80 bg-slate-950/30 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[10px] text-slate-400 uppercase font-bold font-mono">Bybit Base URL</span>
                    <span className="text-[10px] text-slate-500 font-mono uppercase">
                      {bybitConfig?.environment || 'demo'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-300 break-all font-mono">
                    {bybitConfig?.base_url || 'Not loaded'}
                  </div>
                  <div className="text-[11px] text-slate-500 font-sans">
                    {bybitConnection?.detail || 'Run a connection test after setting demo credentials.'}
                  </div>
                  {bybitConnection?.equity && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800/60">
                      <div>
                        <span className="block text-[10px] text-slate-500 uppercase font-bold font-mono">Demo Equity</span>
                        <span className="block mt-1 text-xs text-slate-200 font-mono">{bybitConnection.equity} USDT</span>
                      </div>
                      <div>
                        <span className="block text-[10px] text-slate-500 uppercase font-bold font-mono">Available Balance</span>
                        <span className="block mt-1 text-xs text-slate-200 font-mono">
                          {bybitConnection.available_balance || '0'} USDT
                        </span>
                      </div>
                    </div>
                  )}
                </div>
                <div className="pt-2 flex items-center gap-2 font-mono">
                  <Server size={14} className="text-slate-600" />
                  <span className="text-[10px] text-slate-600 font-bold uppercase">{connectionInfo.baseUrl}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full sm:w-auto uppercase font-mono font-bold"
                  disabled={isTestingBybit}
                  onClick={() => {
                    void runBybitConnectionTest();
                  }}
                >
                  {isTestingBybit ? <LoaderCircle size={14} className="animate-spin" /> : null}
                  Test Bybit Demo Connection
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">03.</span>
                  Operator Notifications & Alerts
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Configure telemetry notification outputs to track trading triggers.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                    <div>
                      <h4 className="text-sm font-bold text-slate-300 font-mono">Sound Alerts</h4>
                      <p className="text-[11px] text-slate-500 font-sans mt-1">Audible sound effect on trigger matches</p>
                    </div>
                    <ToggleButton
                      checked={settings.notifications.chime}
                      onChange={(checked) => {
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ notifications: { chime: checked } });
                          },
                          'Notification Saved',
                        );
                      }}
                      disabled={isSaving}
                    />
                  </div>
                  <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                    <div>
                      <h4 className="text-sm font-bold text-slate-300 font-mono">Telegram Push</h4>
                      <p className="text-[11px] text-slate-500 font-sans mt-1">Relay execution signals directly</p>
                    </div>
                    <ToggleButton
                      checked={settings.notifications.telegram}
                      onChange={(checked) => {
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ notifications: { telegram: checked } });
                          },
                          'Notification Saved',
                        );
                      }}
                      disabled={isSaving}
                    />
                  </div>
                  <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                    <div>
                      <h4 className="text-sm font-bold text-slate-300 font-mono">Toast Alerts</h4>
                      <p className="text-[11px] text-slate-500 font-sans mt-1">Local visual prompt inside the operator console</p>
                    </div>
                    <ToggleButton
                      checked={settings.notifications.toast}
                      onChange={(checked) => {
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ notifications: { toast: checked } });
                          },
                          'Notification Saved',
                        );
                      }}
                      disabled={isSaving}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">04.</span>
                  Strategy & Risk Parameters
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4 font-mono text-xs">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Locked risk controls. Backend connection is required to sync or override active variables.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Max Risk Per Trade</label>
                    <select
                      value={settings.risk.risk_per_trade_pct}
                      onChange={(event) => {
                        const nextValue = parseNumber(event.target.value);
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ risk_per_trade_pct: nextValue });
                          },
                          'Risk Settings Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none"
                    >
                      {currentRiskOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}%
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Max Active Slots</label>
                    <select
                      value={settings.risk.max_open_positions}
                      onChange={(event) => {
                        const nextValue = parseNumber(event.target.value);
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ max_open_positions: nextValue });
                          },
                          'Risk Settings Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none"
                    >
                      {currentSlotOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-800/60">
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Daily Max Trades</label>
                    <input
                      type="number"
                      min={0}
                      value={settings.risk.daily_max_trades}
                      onChange={(event) => {
                        const nextValue = parseNumber(event.target.value);
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ daily_max_trades: nextValue });
                          },
                          'Risk Settings Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-[10px] text-slate-400 uppercase font-bold">Daily Max Loss</label>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      value={settings.risk.daily_max_loss}
                      onChange={(event) => {
                        const nextValue = parseNumber(event.target.value);
                        void runMutation(
                          async () => {
                            await backendApi.updateSettings({ daily_max_loss: nextValue });
                          },
                          'Risk Settings Saved',
                        );
                      }}
                      disabled={isSaving}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 text-slate-200 rounded font-bold focus:outline-none"
                    />
                  </div>
                </div>
                <div className="space-y-1 pt-2 border-t border-slate-800/60">
                  <label className="block text-[10px] text-slate-400 uppercase font-bold">Allowed Signal Grades</label>
                  <div className="flex flex-wrap gap-2">
                    {(['A+', 'A', 'B+', 'B'] as SignalGrade[]).map((grade) => {
                      const active = settings.strategy.allowed_signal_grades.includes(grade);
                      return (
                        <Button
                          key={grade}
                          variant={active ? 'primary' : 'outline'}
                          size="sm"
                          disabled={isSaving}
                          onClick={() => {
                            const nextGrades = active
                              ? settings.strategy.allowed_signal_grades.filter((currentGrade) => currentGrade !== grade)
                              : [...settings.strategy.allowed_signal_grades, grade];
                            if (nextGrades.length === 0) {
                              return;
                            }
                            void runMutation(
                              async () => {
                                await backendApi.updateSettings({ allowed_signal_grades: nextGrades });
                              },
                              'Signal Grades Saved',
                            );
                          }}
                        >
                          {grade}
                        </Button>
                      );
                    })}
                  </div>
                </div>
                <p className="text-[10px] text-slate-500 font-sans flex items-center gap-1.5 pt-2 border-t border-slate-800/60">
                  <Info size={12} className="text-slate-500 shrink-0" />
                  Config variables are now synced with backend in-memory settings.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">05.</span>
                  Engine Control Board
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Selectively activate trading engines once connected.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                    <div>
                      <h4 className="text-sm font-bold text-slate-300 font-mono">Scalping Engine</h4>
                      <p className="text-[11px] text-slate-500 font-sans mt-1">Ultra-fast high frequency positions</p>
                    </div>
                    <ToggleButton
                      checked={settings.engine_control.scalping_engine_enabled}
                      onChange={(checked) => {
                        void runMutation(
                          async () => {
                            await backendApi.updateEngineControl({ scalping_engine_enabled: checked });
                          },
                          'Engine Controls Saved',
                        );
                      }}
                      disabled={isSaving}
                    />
                  </div>
                  <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                    <div>
                      <h4 className="text-sm font-bold text-slate-300 font-mono">Intraday Engine</h4>
                      <p className="text-[11px] text-slate-500 font-sans mt-1">Macro breakout structures</p>
                    </div>
                    <ToggleButton
                      checked={settings.engine_control.intraday_engine_enabled}
                      onChange={(checked) => {
                        void runMutation(
                          async () => {
                            await backendApi.updateEngineControl({ intraday_engine_enabled: checked });
                          },
                          'Engine Controls Saved',
                        );
                      }}
                      disabled={isSaving}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">06.</span>
                  Execution Master Override
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Critical live dispatch override controls for operator intervention.
                </p>
                <div className="flex items-center justify-between p-3.5 bg-slate-950/40 border border-slate-900 rounded">
                  <div>
                    <h4 className="text-sm font-bold text-slate-300 font-mono">Auto Trade Dispatcher</h4>
                    <p className="text-[11px] text-slate-500 font-sans mt-1">
                      Requires Bybit connection, one active engine, risk above 0%, active slots above 0, and daily max trades above 0.
                    </p>
                  </div>
                  <ToggleButton
                    checked={settings.execution_control.auto_trade_enabled}
                    onChange={(checked) => {
                      void runMutation(
                        async () => {
                          await backendApi.updateEngineControl({ auto_trade_enabled: checked });
                        },
                        'Execution Controls Saved',
                      );
                    }}
                    disabled={isSaving}
                  />
                </div>
                <div className="pt-4 border-t border-slate-800/60 space-y-3">
                  <div className="flex items-center justify-between text-xs font-mono uppercase text-slate-500">
                    <span>Emergency Stop</span>
                    <StatusBadge
                      status={settings.execution_control.emergency_stop ? 'danger' : 'inactive'}
                      label={settings.execution_control.emergency_stop ? 'Active' : 'Clear'}
                    />
                  </div>
                  <Button
                    variant={settings.execution_control.emergency_stop ? 'danger' : 'outline'}
                    size="lg"
                    className="w-full uppercase font-mono tracking-wider font-bold text-xs"
                    disabled={isSaving}
                    onClick={() => {
                      void runMutation(
                        async () => {
                          await backendApi.updateEngineControl({
                            emergency_stop: !settings.execution_control.emergency_stop,
                          });
                        },
                        'Execution Controls Saved',
                      );
                    }}
                  >
                    {settings.execution_control.emergency_stop ? 'Release System Lockout' : 'Trigger System Lockout'}
                  </Button>
                  <p className="text-[10px] text-slate-500 font-sans">
                    UI button is only the trigger. Backend safety gate still decides whether auto trade can actually turn on.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4 lg:col-span-2">
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 font-mono flex items-center gap-2">
                  <span className="text-indigo-400">07.</span>
                  Workflow Control Feed
                </h3>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-5 space-y-4">
                <p className="text-xs text-slate-500 leading-relaxed font-sans">
                  Shared control flow status from backend health to scan, signal selection, execution, and trade registration.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 font-mono text-xs">
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Scanner</span>
                    <StatusBadge status={workflowStatus?.scanner_status ? 'active' : 'inactive'} label={workflowStatus?.scanner_status || 'idle'} />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Signal</span>
                    <StatusBadge status={workflowStatus?.signal_status === 'candidate_ready' ? 'active' : workflowStatus?.signal_status === 'filtered' ? 'pending' : 'inactive'} label={workflowStatus?.signal_status || 'idle'} />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Execution</span>
                    <StatusBadge status={workflowStatus?.execution_status === 'submitted' ? 'active' : workflowStatus?.execution_status === 'blocked' || workflowStatus?.execution_status === 'rejected' ? 'danger' : 'inactive'} label={workflowStatus?.execution_status || 'idle'} />
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-900 rounded flex items-center justify-between">
                    <span className="text-slate-500 font-bold uppercase text-[10px]">Open Trades</span>
                    <span className="text-slate-200 font-bold">{workflowStatus?.active_trade_count ?? 0}</span>
                  </div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2 border-t border-slate-800/60">
                  <div className="rounded border border-slate-800/80 bg-slate-950/30 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[10px] text-slate-400 uppercase font-bold font-mono">Last Candidate Signal</span>
                      <span className="text-[10px] text-slate-500 font-mono uppercase">{workflowStatus?.selected_mode || mode.active_strategy_mode}</span>
                    </div>
                    {workflowStatus?.candidate_signal ? (
                      <>
                        <div className="text-xs text-slate-200 font-mono">
                          {workflowStatus.candidate_signal.symbol} | {workflowStatus.candidate_signal.direction.toUpperCase()} | {workflowStatus.candidate_signal.grade}
                        </div>
                        <div className="text-[11px] text-slate-500 font-sans">
                          {workflowStatus.candidate_signal.reason}
                        </div>
                      </>
                    ) : (
                      <div className="text-[11px] text-slate-500 font-sans">No candidate signal captured yet.</div>
                    )}
                  </div>
                  <div className="rounded border border-slate-800/80 bg-slate-950/30 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[10px] text-slate-400 uppercase font-bold font-mono">Last Execution Result</span>
                      <span className="text-[10px] text-slate-500 font-mono uppercase">{workflowStatus?.last_cycle_at ? 'updated' : 'idle'}</span>
                    </div>
                    {workflowStatus?.last_order ? (
                      <>
                        <div className="text-xs text-slate-200 font-mono">
                          {workflowStatus.last_order.symbol} | {workflowStatus.last_order.side.toUpperCase()} | Qty {workflowStatus.last_order.qty}
                        </div>
                        <div className="text-[11px] text-slate-500 font-sans">
                          Order {workflowStatus.last_order.order_id || 'accepted'} | {workflowStatus.last_order.status}
                        </div>
                      </>
                    ) : (
                      <div className="text-[11px] text-slate-500 font-sans">
                        {workflowStatus?.last_reject_reason || 'No execution attempt recorded yet.'}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {health?.status === 'healthy' && (
            <div className="rounded border border-emerald-900/30 bg-emerald-950/10 px-4 py-3 text-sm text-emerald-300 font-sans flex items-center gap-2">
              <CheckCircle2 size={16} />
              Backend connected. Settings are updating against the live FastAPI foundation state.
            </div>
          )}
        </>
      )}
    </div>
  );
}
