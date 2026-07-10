import React, { useEffect, useMemo, useState } from 'react';
import { Save, Server, Power, RefreshCw, ShieldCheck, AlertTriangle, Play, Square } from 'lucide-react';
import { ApiError, apiRequest, getBackendBaseUrl, updateEngineControls } from '../api/client';
import { BackendGrade, TradingMode } from '../api/types';
import { useAuth } from '../context/AuthContext';

interface CanonicalSettings {
  system: { system_mode: 'demo' };
  strategy: { active_strategy_mode: TradingMode; allowed_signal_grades: BackendGrade[] };
  risk: { daily_max_loss: number; daily_max_trades: number; risk_per_trade_pct: number; max_open_positions: number };
  engine_control: { scalping_engine_enabled: boolean; intraday_engine_enabled: boolean };
  execution_control: { auto_trade_enabled: boolean; emergency_stop: boolean };
}

interface WorkflowStatus {
  selected_mode: TradingMode;
  scanner_status: string;
  signal_status: string;
  execution_status: string;
  execution_ready: boolean;
  execution_block_reason: string | null;
  auto_trade_enabled: boolean;
  bybit_connection_code: string;
  active_trade_count: number;
  daily_trade_count: number;
  last_reject_reason: string | null;
  last_cycle_at: string | null;
}

function classify(error: unknown) {
  if (error instanceof ApiError) {
    if (error.kind === 'unauthorized') return 'unauthorized';
    if (error.kind === 'timeout') return 'timeout';
    if (error.kind === 'network' || error.kind === 'configuration') return 'disconnected';
  }
  return 'error';
}

export default function ControlCenter() {
  const { connectionStatus } = useAuth();
  const [settings, setSettings] = useState<CanonicalSettings | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowStatus | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'saving' | 'saved' | 'unauthorized' | 'disconnected' | 'timeout' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [risk, setRisk] = useState({ daily_max_loss: 0, daily_max_trades: 0, risk_per_trade_pct: 0, max_open_positions: 0 });
  const [mode, setMode] = useState<TradingMode>('scalping');

  const load = async () => {
    setState('loading');
    setMessage('');
    try {
      const [settingsData, workflowData] = await Promise.all([
        apiRequest<CanonicalSettings>('/api/settings', { method: 'GET' }),
        apiRequest<WorkflowStatus>('/api/workflow/status', { method: 'GET' }),
      ]);
      setSettings(settingsData);
      setWorkflow(workflowData);
      setRisk(settingsData.risk);
      setMode(settingsData.strategy.active_strategy_mode);
      setState('ready');
    } catch (error) {
      setState(classify(error));
      setMessage(error instanceof Error ? error.message : 'Unable to load control state.');
    }
  };

  useEffect(() => { void load(); }, []);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setState('saving');
    try {
      const updated = await apiRequest<CanonicalSettings>('/api/settings', {
        method: 'POST',
        body: { ...risk, active_strategy_mode: mode },
      });
      setSettings(updated);
      setRisk(updated.risk);
      setMode(updated.strategy.active_strategy_mode);
      setState('saved');
      setMessage('Canonical settings persisted successfully.');
      const refreshedWorkflow = await apiRequest<WorkflowStatus>('/api/workflow/status', { method: 'GET' });
      setWorkflow(refreshedWorkflow);
    } catch (error) {
      setState(classify(error));
      setMessage(error instanceof Error ? error.message : 'Save failed.');
    }
  };

  const control = async (
    key: 'scalping_engine_enabled' | 'intraday_engine_enabled' | 'emergency_stop',
    value: boolean,
  ) => {
    setMessage('');
    try {
      await updateEngineControls({ [key]: value });
      await load();
    } catch (error) {
      setState(classify(error));
      setMessage(error instanceof Error ? error.message : 'Control action failed.');
    }
  };

  const botAction = async (action: 'start' | 'stop') => {
    setState('saving');
    setMessage('');
    try {
      await apiRequest(`/api/bot/${action}`, { method: 'POST' });
      await load();
      setState('saved');
      setMessage(action === 'start'
        ? 'Bot started: immediate scan → signal → risk → execution → management cycle completed.'
        : 'Auto trading stopped. Existing positions were not modified.');
    } catch (error) {
      setState(classify(error));
      setMessage(error instanceof Error ? error.message : `Unable to ${action} bot.`);
    }
  };

  const field = (label: string, key: keyof typeof risk, step = '0.1') => (
    <label className="block">
      <span className="text-[10px] uppercase font-mono text-slate-400">{label}</span>
      <input
        type="number"
        min="0"
        step={step}
        value={risk[key]}
        onChange={(event) => setRisk((current) => ({ ...current, [key]: Number(event.target.value) }))}
        className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
      />
    </label>
  );

  const selectedEngineEnabled = settings
    ? mode === 'scalping'
      ? settings.engine_control.scalping_engine_enabled
      : settings.engine_control.intraday_engine_enabled
    : false;

  const statusTone = workflow?.execution_ready
    ? 'border-emerald-900/50 bg-emerald-950/20 text-emerald-300'
    : 'border-amber-900/50 bg-amber-950/20 text-amber-300';

  const executionLabel = useMemo(() => {
    if (!workflow) return 'Unavailable';
    if (workflow.execution_ready) return 'Ready';
    if (!workflow.auto_trade_enabled) return 'Auto trade off';
    return 'Blocked';
  }, [workflow]);

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-850 rounded-xl p-5 flex justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Control Center</h1>
          <p className="text-xs text-slate-400 mt-1">Manual scan stays scan-only. Start Bot owns the full automatic workflow.</p>
        </div>
        <button onClick={() => void load()} className="px-3 py-2 bg-slate-800 text-white rounded-lg text-xs flex gap-2"><RefreshCw className="h-4 w-4" />Reload</button>
      </div>

      {state === 'loading' ? (
        <div className="p-8 text-center text-slate-400">Loading canonical control state…</div>
      ) : !settings ? (
        <div className="p-8 bg-slate-900 rounded-xl text-center text-rose-400">{state.replace('_', ' ')}: {message}</div>
      ) : (
        <form onSubmit={save} className="space-y-6">
          <div className={`rounded-xl border p-4 flex items-start gap-3 ${statusTone}`}>
            {workflow?.execution_ready ? <ShieldCheck className="h-5 w-5 shrink-0" /> : <AlertTriangle className="h-5 w-5 shrink-0" />}
            <div>
              <div className="font-bold">Execution: {executionLabel}</div>
              <div className="mt-1 text-xs opacity-90">
                {workflow?.execution_ready
                  ? `${workflow.selected_mode} engine, risk controls and auto trade are ready.`
                  : workflow?.execution_block_reason || workflow?.last_reject_reason || 'Execution readiness is unavailable.'}
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div className="bg-slate-900 border border-slate-850 rounded-xl p-5">
              <h3 className="text-base font-bold text-white mb-4">Canonical Risk Limits</h3>
              <div className="grid grid-cols-2 gap-4">
                {field('Risk per trade %', 'risk_per_trade_pct')}
                {field('Daily max trades', 'daily_max_trades', '1')}
                {field('Daily max loss', 'daily_max_loss')}
                {field('Max open positions', 'max_open_positions', '1')}
              </div>
              <label className="block mt-4">
                <span className="text-[10px] uppercase font-mono text-slate-400">Active strategy mode</span>
                <select value={mode} onChange={(event) => setMode(event.target.value as TradingMode)} className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white">
                  <option value="scalping">Scalping</option>
                  <option value="intraday">Intraday</option>
                </select>
              </label>
            </div>

            <div className="bg-slate-900 border border-slate-850 rounded-xl p-5">
              <h3 className="font-bold text-white flex gap-2"><Power className="h-5 w-5 text-emerald-400" />Engine Controls</h3>
              {([
                ['scalping_engine_enabled', 'Scalping Engine', settings.engine_control.scalping_engine_enabled],
                ['intraday_engine_enabled', 'Intraday Engine', settings.engine_control.intraday_engine_enabled],
                ['emergency_stop', 'Emergency Stop', settings.execution_control.emergency_stop],
              ] as const).map(([key, label, checked]) => (
                <label key={key} className="mt-4 flex justify-between text-sm text-slate-300">
                  <span>{label}</span>
                  <input type="checkbox" checked={checked} onChange={(event) => void control(key, event.target.checked)} />
                </label>
              ))}

              <div className="mt-5 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => void botAction('start')}
                  disabled={state === 'saving' || Boolean(workflow?.auto_trade_enabled)}
                  className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-3 text-sm font-black text-slate-950 disabled:opacity-50"
                >
                  <Play className="h-4 w-4" /> Start Bot
                </button>
                <button
                  type="button"
                  onClick={() => void botAction('stop')}
                  disabled={state === 'saving' || !workflow?.auto_trade_enabled}
                  className="flex items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 py-3 text-sm font-black text-white disabled:opacity-50"
                >
                  <Square className="h-4 w-4" /> Stop Bot
                </button>
              </div>

              <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-400">
                Selected engine: <span className={selectedEngineEnabled ? 'text-emerald-400' : 'text-amber-400'}>{mode} {selectedEngineEnabled ? 'enabled' : 'disabled'}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-850 rounded-xl p-5">
            <h3 className="font-bold text-white flex gap-2"><Server className="h-5 w-5 text-indigo-400" />Authoritative Backend Status</h3>
            <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg bg-slate-950 p-3"><span className="text-slate-500">Connection</span><div className="mt-1 text-white capitalize">{connectionStatus}</div></div>
              <div className="rounded-lg bg-slate-950 p-3"><span className="text-slate-500">Bybit</span><div className="mt-1 text-white">{workflow?.bybit_connection_code ?? 'N/A'}</div></div>
              <div className="rounded-lg bg-slate-950 p-3"><span className="text-slate-500">Workflow</span><div className="mt-1 text-white">{workflow?.execution_status ?? 'N/A'}</div></div>
              <div className="rounded-lg bg-slate-950 p-3"><span className="text-slate-500">Last cycle</span><div className="mt-1 text-white">{workflow?.last_cycle_at ? new Date(workflow.last_cycle_at).toLocaleString() : 'N/A'}</div></div>
            </div>
            <p className="mt-3 text-[11px] text-slate-500">API: {getBackendBaseUrl() ?? 'Not configured'}</p>
          </div>

          {message && <div className={state === 'saved' ? 'text-emerald-400 text-sm' : 'text-rose-400 text-sm'}>{message}</div>}
          <button disabled={state === 'saving'} className="px-5 py-3 bg-emerald-500 text-slate-950 rounded-lg font-bold flex items-center gap-2"><Save className="h-4 w-4" />{state === 'saving' ? 'Saving…' : 'Save Canonical Settings'}</button>
        </form>
      )}
    </div>
  );
}
