import React, { useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bitcoin,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react';

type ChallengeState = 'draft' | 'ready' | 'running' | 'paused';

type SlotPreview = {
  name: string;
  symbol: string;
  direction: 'LONG' | 'SHORT' | 'WAIT';
  confidence: number | null;
  risk: number;
  status: 'Locked' | 'Scanning' | 'Waiting';
  icon: React.ComponentType<{ className?: string }>;
};

const formatMoney = (value: number) => `${value.toFixed(2)} USDT`;

export default function DoubleDownChallenge() {
  const [startingBalance, setStartingBalance] = useState(100);
  const [state, setState] = useState<ChallengeState>('draft');

  const targetBalance = startingBalance * 2;
  const cycleRisk = startingBalance * 0.3;
  const perSlotRisk = cycleRisk / 3;

  const slots = useMemo<SlotPreview[]>(
    () => [
      {
        name: 'BTC Anchor',
        symbol: 'BTCUSDT',
        direction: 'WAIT',
        confidence: null,
        risk: perSlotRisk,
        status: 'Locked',
        icon: Bitcoin,
      },
      {
        name: 'Top Gainer',
        symbol: 'Pending scan',
        direction: 'WAIT',
        confidence: null,
        risk: perSlotRisk,
        status: 'Scanning',
        icon: TrendingUp,
      },
      {
        name: 'Top Loser',
        symbol: 'Pending scan',
        direction: 'WAIT',
        confidence: null,
        risk: perSlotRisk,
        status: 'Scanning',
        icon: TrendingDown,
      },
    ],
    [perSlotRisk],
  );

  const handlePrimaryAction = () => {
    if (state === 'running') {
      setState('paused');
      return;
    }
    setState('running');
  };

  const resetPreview = () => {
    setStartingBalance(100);
    setState('draft');
  };

  return (
    <div className="min-h-full bg-slate-950 p-4 md:p-6 space-y-6">
      <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-slate-900 via-slate-900 to-amber-950/20 p-5 md:p-6 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-[0.22em]">
              <ShieldAlert className="h-4 w-4" />
              High-Risk Isolated Workspace
            </div>
            <h1 className="mt-3 text-2xl md:text-3xl font-black text-white">Double Down Challenge</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Local UI prototype only. No exchange connection, order execution, real balance mutation, or simulated market price is active in this phase.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handlePrimaryAction}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-400 px-4 py-2.5 text-sm font-black text-slate-950 hover:bg-amber-300 transition-colors"
            >
              {state === 'running' ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              {state === 'running' ? 'Pause Preview' : state === 'paused' ? 'Resume Preview' : 'Start Preview'}
            </button>
            <button
              type="button"
              onClick={resetPreview}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-bold text-slate-200 hover:bg-slate-800 transition-colors"
            >
              <RotateCcw className="h-4 w-4" />
              Reset
            </button>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-1 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center gap-2 mb-5">
            <Wallet className="h-5 w-5 text-emerald-400" />
            <h2 className="font-bold text-white">Challenge Setup</h2>
          </div>

          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
            Starting Balance
          </label>
          <div className="relative">
            <input
              type="number"
              min={10}
              step={10}
              value={startingBalance}
              onChange={(event) => setStartingBalance(Math.max(10, Number(event.target.value) || 10))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 pr-20 font-mono text-white outline-none focus:border-amber-400"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-500">USDT</span>
          </div>

          <div className="mt-5 space-y-3 text-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-slate-400">Target Balance</span>
              <span className="font-mono font-bold text-emerald-400">{formatMoney(targetBalance)}</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-slate-400">Timeframe</span>
              <span className="font-mono font-bold text-white">1m</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-slate-400">Risk : Reward</span>
              <span className="font-mono font-bold text-white">1 : 1</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Max Active Trades</span>
              <span className="font-mono font-bold text-white">3</span>
            </div>
          </div>
        </div>

        <div className="xl:col-span-2 rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-amber-400" />
              <h2 className="font-bold text-white">Challenge Status</h2>
            </div>
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[11px] font-black uppercase tracking-wider text-amber-300">
              {state}
            </span>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Metric label="Current Balance" value={formatMoney(startingBalance)} />
            <Metric label="Target" value={formatMoney(targetBalance)} />
            <Metric label="Net PnL" value="0.00 USDT" />
            <Metric label="Progress" value="0.00%" />
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between text-xs font-bold text-slate-400">
              <span>Challenge progress</span>
              <span>0 / 100%</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-950">
              <div className="h-full w-0 rounded-full bg-emerald-400" />
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-100/80 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
            Preview controls change local component state only. They do not start the Python engine or submit an order.
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-cyan-400" />
          <h2 className="font-bold text-white">Three-Slot Preview</h2>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {slots.map((slot) => (
            <SlotCard key={slot.name} slot={slot} />
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="font-bold text-white mb-4">Risk Preview</h2>
          <div className="space-y-3">
            <RiskLine label="Total cycle risk" value={formatMoney(cycleRisk)} emphasized />
            <RiskLine label="Risk per slot" value={formatMoney(perSlotRisk)} />
            <RiskLine label="Maximum gross cycle loss" value={`-${formatMoney(cycleRisk)}`} danger />
            <RiskLine label="Maximum gross cycle gain" value={`+${formatMoney(cycleRisk)}`} positive />
            <RiskLine label="Recovery target after loss" value={formatMoney(startingBalance)} />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="font-bold text-white mb-4">Active Trades</h2>
          <EmptyState text="No challenge trades are active. Phase 2 does not connect to execution." />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
        <h2 className="font-bold text-white mb-4">Trade History</h2>
        <EmptyState text="No trade history yet. Ledger and persistence arrive in later phases." />
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 font-mono text-base font-black text-white">{value}</p>
    </div>
  );
}

function SlotCard({ slot }: { slot: SlotPreview }) {
  const Icon = slot.icon;
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg border border-slate-700 bg-slate-950 p-2.5">
            <Icon className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <h3 className="font-bold text-white">{slot.name}</h3>
            <p className="text-xs text-slate-500">{slot.status}</p>
          </div>
        </div>
        <span className="rounded-full border border-slate-700 px-2.5 py-1 text-[10px] font-black text-slate-400">
          {slot.direction}
        </span>
      </div>

      <div className="mt-5 space-y-3 text-sm">
        <RiskLine label="Symbol" value={slot.symbol} />
        <RiskLine label="Approved risk" value={formatMoney(slot.risk)} />
        <RiskLine label="Confidence" value={slot.confidence == null ? 'Not evaluated' : `${slot.confidence}%`} />
      </div>
    </article>
  );
}

function RiskLine({
  label,
  value,
  emphasized = false,
  danger = false,
  positive = false,
}: {
  label: string;
  value: string;
  emphasized?: boolean;
  danger?: boolean;
  positive?: boolean;
}) {
  const valueClass = danger
    ? 'text-rose-400'
    : positive
      ? 'text-emerald-400'
      : emphasized
        ? 'text-amber-300'
        : 'text-slate-100';

  return (
    <div className="flex items-center justify-between border-b border-slate-800 pb-3 last:border-0 last:pb-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`font-mono text-sm font-bold ${valueClass}`}>{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-950/60 px-4 text-center">
      <div className="flex items-center gap-2 text-slate-500">
        <ArrowUpRight className="h-4 w-4" />
        <ArrowDownRight className="h-4 w-4" />
      </div>
      <p className="mt-3 max-w-md text-sm text-slate-500">{text}</p>
    </div>
  );
}
