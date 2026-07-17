import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Pause, Play, RotateCcw, ShieldAlert, Wallet } from 'lucide-react';
import { apiRequest } from '../api/client';

type ChallengeSnapshot = {
  config: {
    challenge_id: string;
    starting_balance: string;
    target_balance: string;
    failure_floor: string;
    cycle_risk_pct: string;
  };
  state: {
    status: string;
    current_balance: string;
    recovery_target: string;
    cycle_number: number;
    active_trade_count: number;
  };
  ledger: Array<{
    entry_id: string;
    cycle_number: number;
    entry_type: string;
    amount: string;
    balance_after: string;
    created_at: string;
  }>;
  runtime?: {
    active_cycle?: {
      cycle_number: number;
      approved_slots: Array<{
        symbol: string;
        slot_key: string;
        direction: string;
        quantity: string;
      }>;
      execution_results: Array<{
        slot_key: string;
        symbol: string;
        direction: string;
        approved: boolean;
        status: string;
        rejection_code?: string | null;
      }>;
    } | null;
    last_cycle?: {
      status: string;
      planned_at?: string;
      selected_slots?: Array<{
        symbol: string;
        slot_type: string;
        approved: boolean;
        direction?: string | null;
        rejection_code?: string | null;
        size_rejection_code?: string | null;
      }>;
      finalization?: {
        net_pnl: string;
        status: string;
      } | null;
    } | null;
  };
};

const money = (value: string | number) => `${Number(value).toFixed(2)} USDT`;

export default function DoubleDownChallenge() {
  const [startingBalance, setStartingBalance] = useState(100);
  const [failureFloor, setFailureFloor] = useState(20);
  const [challenges, setChallenges] = useState<ChallengeSnapshot[]>([]);
  const [selectedChallengeId, setSelectedChallengeId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ChallengeSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChallenges = async (preferredChallengeId?: string | null) => {
    const items = await apiRequest<ChallengeSnapshot[]>('/api/challenge', { method: 'GET' });
    setChallenges(items);
    const resolvedId = preferredChallengeId
      ?? selectedChallengeId
      ?? items[0]?.config.challenge_id
      ?? null;
    setSelectedChallengeId(resolvedId);
    setSnapshot(items.find((item) => item.config.challenge_id === resolvedId) || items[0] || null);
  };

  useEffect(() => {
    void loadChallenges().catch((reason) => {
      setError(reason instanceof Error ? reason.message : 'Failed to load challenge');
    });
  }, []);

  const progress = useMemo(() => {
    if (!snapshot) return 0;
    const start = Number(snapshot.config.starting_balance);
    const target = Number(snapshot.config.target_balance);
    const current = Number(snapshot.state.current_balance);
    if (target <= start) return 0;
    return Math.max(0, Math.min(100, ((current - start) / (target - start)) * 100));
  }, [snapshot]);

  const createChallenge = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await apiRequest<ChallengeSnapshot>('/api/challenge', {
        method: 'POST',
        body: { starting_balance: startingBalance, failure_floor: failureFloor },
      });
      await loadChallenges(created.config.challenge_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Challenge creation failed');
    } finally {
      setBusy(false);
    }
  };

  const action = async (name: 'start' | 'pause' | 'resume' | 'terminate' | 'run-cycle' | 'finalize-cycle') => {
    if (!snapshot) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await apiRequest<ChallengeSnapshot>(`/api/challenge/${snapshot.config.challenge_id}/${name}`, {
        method: 'POST',
      });
      await loadChallenges(updated.config.challenge_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Challenge action failed');
    } finally {
      setBusy(false);
    }
  };

  const status = snapshot?.state.status || 'not_created';
  const canStart = status === 'ready';
  const canPause = status === 'running' || status === 'recovery';
  const canResume = status === 'paused';
  const canRunCycle = status === 'running' || status === 'recovery';
  const canFinalizeCycle = status === 'cycle_active';
  const statusSummary = snapshot ? describeChallengeStatus(snapshot) : null;

  return (
    <div className="min-h-full bg-slate-950 p-4 md:p-6 space-y-6">
      <section className="rounded-2xl border border-amber-500/20 bg-slate-900 p-5 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.22em] text-amber-400">
              <ShieldAlert className="h-4 w-4" /> Isolated Demo Challenge
            </div>
            <h1 className="mt-3 text-3xl font-black text-white">Double Down Challenge</h1>
            <p className="mt-2 text-sm text-slate-400">Persistent challenge state and controls are connected to the backend. Live-money mode remains blocked.</p>
            {challenges.length > 0 && (
              <label className="mt-4 block max-w-sm">
                <span className="text-[10px] uppercase font-mono text-slate-500">Active challenge</span>
                <select
                  value={selectedChallengeId ?? ''}
                  onChange={(event) => {
                    const nextId = event.target.value || null;
                    setSelectedChallengeId(nextId);
                    setSnapshot(challenges.find((item) => item.config.challenge_id === nextId) || null);
                  }}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                >
                  {challenges.map((item, index) => (
                    <option key={item.config.challenge_id} value={item.config.challenge_id}>
                      {`Challenge ${index + 1} · ${item.state.status} · ${money(item.state.current_balance)}`}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {snapshot && (
            <div className="flex flex-wrap gap-2">
              {canStart && <ActionButton label="Start" icon={Play} onClick={() => void action('start')} disabled={busy} />}
              {canPause && <ActionButton label="Pause" icon={Pause} onClick={() => void action('pause')} disabled={busy} />}
              {canResume && <ActionButton label="Resume" icon={Play} onClick={() => void action('resume')} disabled={busy} />}
              {canRunCycle && <ActionButton label="Run Cycle" icon={Play} onClick={() => void action('run-cycle')} disabled={busy} />}
              {canFinalizeCycle && <ActionButton label="Finalize Cycle" icon={RotateCcw} onClick={() => void action('finalize-cycle')} disabled={busy} />}
              {!['completed', 'failed', 'terminated'].includes(status) && (
                <ActionButton label="Terminate" icon={RotateCcw} onClick={() => void action('terminate')} disabled={busy} secondary />
              )}
            </div>
          )}
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          <AlertTriangle className="h-5 w-5" /> {error}
        </div>
      )}

      {!snapshot ? (
        <section className="max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="mb-5 flex items-center gap-2"><Wallet className="h-5 w-5 text-emerald-400" /><h2 className="font-bold text-white">Create Challenge</h2></div>
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">Starting Balance</label>
          <input className="mb-4 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-white" type="number" min={10} value={startingBalance} onChange={(event) => setStartingBalance(Number(event.target.value))} />
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">Failure Floor</label>
          <input className="mb-5 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-white" type="number" min={1} value={failureFloor} onChange={(event) => setFailureFloor(Number(event.target.value))} />
          <button disabled={busy} onClick={() => void createChallenge()} className="rounded-lg bg-amber-400 px-4 py-2.5 text-sm font-black text-slate-950 disabled:opacity-50">Create Isolated Challenge</button>
          {challenges.length > 0 && (
            <p className="mt-4 text-xs text-slate-500">{`${challenges.length} challenge${challenges.length === 1 ? '' : 's'} available.`}</p>
          )}
        </section>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Metric label="Status" value={status.toUpperCase()} />
            <Metric label="Current Balance" value={money(snapshot.state.current_balance)} />
            <Metric label="Target" value={money(snapshot.config.target_balance)} />
            <Metric label="Cycle" value={String(snapshot.state.cycle_number)} />
            <Metric label="Active Trades" value={String(snapshot.state.active_trade_count)} />
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <div className="mb-2 flex justify-between text-xs font-bold text-slate-400"><span>Challenge progress</span><span>{progress.toFixed(2)}%</span></div>
            <div className="h-3 overflow-hidden rounded-full bg-slate-950"><div className="h-full rounded-full bg-emerald-400" style={{ width: `${progress}%` }} /></div>
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <Metric label="Starting Balance" value={money(snapshot.config.starting_balance)} />
              <Metric label="Failure Floor" value={money(snapshot.config.failure_floor)} />
              <Metric label="Cycle Risk" value={`${Number(snapshot.config.cycle_risk_pct) * 100}%`} />
            </div>
          </section>

          {statusSummary && (
            <section className="rounded-2xl border border-sky-500/20 bg-slate-900 p-5">
              <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-sky-400">Runtime status</div>
              <h2 className="mt-3 text-xl font-black text-white">{statusSummary.title}</h2>
              <p className="mt-2 text-sm text-slate-300">{statusSummary.description}</p>
              {statusSummary.detail && (
                <p className="mt-3 text-xs font-mono text-slate-400">{statusSummary.detail}</p>
              )}
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <h2 className="mb-4 font-bold text-white">Active Cycle</h2>
              {!snapshot.runtime?.active_cycle ? (
                <p className="text-sm text-slate-400">No active cycle is running.</p>
              ) : (
                <div className="space-y-3">
                  <Metric label="Cycle Number" value={String(snapshot.runtime.active_cycle.cycle_number)} />
                  {snapshot.runtime.active_cycle.approved_slots.map((slot) => (
                    <div key={`${slot.slot_key}-${slot.symbol}`} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm text-slate-200">
                      <div className="font-mono text-white">{slot.symbol}</div>
                      <div>{`${slot.slot_key} · ${slot.direction} · qty ${slot.quantity}`}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <h2 className="mb-4 font-bold text-white">Last Cycle</h2>
              {!snapshot.runtime?.last_cycle ? (
                <p className="text-sm text-slate-400">No cycle has been executed yet.</p>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-slate-200">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Status</div>
                    <div className="mt-1 font-mono text-white">{snapshot.runtime.last_cycle.status}</div>
                    {snapshot.runtime.last_cycle.finalization && (
                      <div className="mt-2 text-emerald-400">{`Net P&L ${money(snapshot.runtime.last_cycle.finalization.net_pnl)}`}</div>
                    )}
                  </div>
                  {(snapshot.runtime.last_cycle.selected_slots || []).map((slot) => (
                    <div key={`${slot.slot_type}-${slot.symbol}`} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-slate-200">
                      <div className="font-mono text-white">{`${slot.slot_type} · ${slot.symbol}`}</div>
                      <div>{slot.approved ? `approved ${slot.direction || ''}` : `rejected ${slot.rejection_code || slot.size_rejection_code || 'unknown'}`}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="mb-4 font-bold text-white">Challenge Ledger</h2>
            <div className="space-y-2">
              {snapshot.ledger.map((entry) => (
                <div key={entry.entry_id} className="grid grid-cols-2 gap-2 rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm md:grid-cols-4">
                  <span className="text-slate-400">{entry.entry_type}</span>
                  <span className="font-mono text-white">Cycle {entry.cycle_number}</span>
                  <span className="font-mono text-white">{money(entry.amount)}</span>
                  <span className="font-mono text-emerald-400">{money(entry.balance_after)}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-800 bg-slate-900 p-4"><p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p><p className="mt-2 font-mono font-black text-white">{value}</p></div>;
}

function ActionButton({ label, icon: Icon, onClick, disabled, secondary = false }: { label: string; icon: React.ComponentType<{ className?: string }>; onClick: () => void; disabled: boolean; secondary?: boolean }) {
  return <button type="button" disabled={disabled} onClick={onClick} className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-black disabled:opacity-50 ${secondary ? 'border border-slate-700 bg-slate-950 text-slate-200' : 'bg-amber-400 text-slate-950'}`}><Icon className="h-4 w-4" />{label}</button>;
}

function describeChallengeStatus(snapshot: ChallengeSnapshot): { title: string; description: string; detail?: string } {
  const activeCycle = snapshot.runtime?.active_cycle;
  const lastCycle = snapshot.runtime?.last_cycle;
  const selectedSlots = lastCycle?.selected_slots || [];
  const rejectedSlots = selectedSlots.filter((slot) => !slot.approved);

  if (snapshot.state.status === 'cycle_active' && activeCycle) {
    return {
      title: 'Cycle is active',
      description: 'The challenge executed trades successfully and is waiting for trade management or manual finalization.',
      detail: `${activeCycle.approved_slots.length} active slot(s), ${activeCycle.execution_results.length} execution result(s).`,
    };
  }

  if (lastCycle?.status === 'no_approved_slots') {
    const codes = rejectedSlots
      .map((slot) => slot.rejection_code || slot.size_rejection_code || 'unknown')
      .filter(Boolean)
      .join(', ');
    return {
      title: 'Cycle ran but no trade was opened',
      description: 'The strategy checked the selected markets, but current conditions did not pass the approval rules.',
      detail: codes ? `Latest rejection codes: ${codes}` : undefined,
    };
  }

  if (lastCycle?.status === 'no_executable_positions') {
    return {
      title: 'Signals were found but sizing blocked execution',
      description: 'The cycle reached the sizing stage, but no position passed the final risk and exchange checks.',
    };
  }

  if (lastCycle?.finalization) {
    return {
      title: 'Cycle completed',
      description: 'A cycle was opened and then finalized successfully.',
      detail: `Final status: ${lastCycle.finalization.status}. Net P&L: ${money(lastCycle.finalization.net_pnl)}.`,
    };
  }

  if (snapshot.state.status === 'running' || snapshot.state.status === 'recovery') {
    return {
      title: 'Challenge is ready to run',
      description: 'The challenge is active. Use Run Cycle to scan the selected markets and attempt a trade cycle.',
    };
  }

  if (snapshot.state.status === 'ready') {
    return {
      title: 'Challenge is ready to start',
      description: 'The challenge has been created successfully. Start it to enable cycle execution.',
    };
  }

  return {
    title: 'Challenge status available',
    description: `Current state: ${snapshot.state.status}.`,
  };
}
