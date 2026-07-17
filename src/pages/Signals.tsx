import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { Signal } from "../types";
import { Activity, RefreshCw, Wifi, WifiOff, Clock } from "lucide-react";
import { normalizeSignals } from "../lib/normalizers";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function Signals() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const { status: backendStatus } = useBackendStatus();

  const fetchSignals = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getSignals();
      setSignals(normalizeSignals(res));
      setLastUpdated(new Date());
    } catch {
      setSignals([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
  }, []);

  const aPlus = signals.filter(s => s.grade === "A+");
  const aGrade = signals.filter(s => s.grade === "A");
  const others = signals.filter(s => s.grade !== "A+" && s.grade !== "A");

  return (
    <div className="space-y-6 flex flex-col h-full min-h-0">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-medium text-slate-100 tracking-tight">Intraday Signals</h2>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-slate-500">Validated Bybit Demo Opportunities</span>
            {lastUpdated && (
              <span className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchSignals}
            disabled={loading}
            className="flex items-center justify-center px-3 py-2 bg-[#0F141F] hover:bg-[#1C2333]/50 text-slate-300 rounded-lg transition-colors border border-[#1C2333] disabled:opacity-50 text-sm font-medium"
            title="Refresh Signals"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto pr-2 pb-4">
        {loading && signals.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
               <div key={i} className="h-64 bg-[#0F141F] border border-[#1C2333] rounded-lg animate-pulse"></div>
            ))}
          </div>
        ) : signals.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center bg-[#0F141F] border border-[#1C2333] rounded-lg">
            <Activity className="w-12 h-12 text-slate-600 mb-4 opacity-50" />
            <h3 className="text-sm font-medium text-slate-400">No Active Signals</h3>
            <p className="text-slate-500 text-xs max-w-sm text-center mt-2">The intraday engine has not generated actionable opportunities. Check the scanner for current market conditions.</p>
          </div>
        ) : (
          <div className="space-y-8">
            <SignalSection title="A+ Signals" signals={aPlus} level="high" />
            <SignalSection title="A Signals" signals={aGrade} level="medium" />
            <SignalSection title="Waiting / Rejected" signals={others} level="low" />
          </div>
        )}
      </div>
    </div>
  );
}

function SignalSection({ title, signals, level }: { title: string; signals: Signal[]; level: "high" | "medium" | "low" }) {
  if (signals.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className={`text-sm font-medium ${level === 'high' ? 'text-emerald-400' : level === 'medium' ? 'text-slate-300' : 'text-slate-500'}`}>
          {title}
        </h3>
        <span className="text-[10px] font-mono bg-[#1C2333] text-slate-400 px-1.5 py-0.5 rounded">{signals.length}</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {signals.map(signal => (
          <SignalCard key={signal.id} signal={signal} level={level} />
        ))}
      </div>
    </div>
  );
}

function SignalCard({ signal, level }: { signal: Signal; level: "high" | "medium" | "low" }) {
  const isBuy = signal.direction === "BUY" || signal.direction === "LONG";
  
  let cardClasses = "bg-[#0F141F] rounded-lg p-5 flex flex-col gap-4 transition-colors border ";
  if (level === "high") {
    cardClasses += "border-emerald-500/30 hover:border-emerald-500/50";
  } else if (level === "medium") {
    cardClasses += "border-[#1C2333] hover:border-slate-700";
  } else {
    cardClasses += "border-[#1C2333] opacity-70 hover:opacity-100 bg-[#0A0D14]";
  }

  return (
    <div className={cardClasses}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <span className="font-medium text-base text-slate-200 tracking-tight">{signal.symbol}</span>
          <span className={`font-bold text-[10px] px-1.5 py-0.5 rounded ${isBuy ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
            {isBuy ? 'LONG' : 'SHORT'}
          </span>
          <span className={`font-medium text-[10px] px-1.5 py-0.5 rounded ${signal.grade === 'A+' ? 'bg-emerald-500/10 text-emerald-400' : signal.grade === 'A' ? 'bg-emerald-500/5 text-emerald-400/80' : signal.grade === 'REJECTED' ? 'bg-[#1C2333] text-slate-500' : 'bg-amber-500/10 text-amber-400'}`}>
            {signal.grade}
          </span>
        </div>
        <div className="flex items-center gap-2">
           <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Score</span>
           <span className="font-mono text-xs font-medium text-slate-300">{signal.score || 'N/A'}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-3">
        <PipelineStep label="1H Trend" value={signal.trend1H} />
        <PipelineStep label="15M Setup" value={signal.setup15M} />
        <PipelineStep label="5M Entry" value={signal.entry5M} />
      </div>

      <div className="grid grid-cols-4 gap-3 bg-[#0A0D14] border border-[#1C2333] rounded-lg p-3">
        <div className="flex flex-col">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest font-medium">Entry</span>
          <span className="text-xs font-mono text-slate-300 mt-1">{signal.entryPrice || 'N/A'}</span>
        </div>
        <div className="flex flex-col border-l border-[#1C2333] pl-3">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest font-medium">SL</span>
          <span className="text-xs font-mono text-red-400 mt-1">{signal.stopLoss || 'N/A'}</span>
        </div>
        <div className="flex flex-col border-l border-[#1C2333] pl-3">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest font-medium">TP</span>
          <span className="text-xs font-mono text-emerald-400 mt-1">{signal.takeProfit || 'N/A'}</span>
        </div>
        <div className="flex flex-col border-l border-[#1C2333] pl-3">
          <span className="text-[9px] text-slate-500 uppercase tracking-widest font-medium">R:R</span>
          <span className="text-xs font-mono text-slate-300 mt-1">{signal.riskReward ? `1:${signal.riskReward}` : 'N/A'}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <span className="text-slate-500 font-medium">Status:</span>
        <StatusText value={signal.status} />
      </div>

      <div className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
        <span className="text-slate-500 font-medium mr-1">Reason:</span> {signal.reason}
      </div>
      
      <div className="flex justify-between items-center mt-auto pt-4 border-t border-[#1C2333]">
        <div className="flex gap-6">
          <div className="flex flex-col">
            <span className="text-[9px] uppercase tracking-widest font-medium text-slate-500">Created</span>
            <span className="text-[10px] font-mono text-slate-400 mt-1">{new Date(signal.createdAt).toLocaleTimeString()}</span>
          </div>
          {signal.updatedAt && (
             <div className="flex flex-col">
               <span className="text-[9px] uppercase tracking-widest font-medium text-slate-500">Updated</span>
               <span className="text-[10px] font-mono text-slate-400 mt-1">{new Date(signal.updatedAt).toLocaleTimeString()}</span>
             </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PipelineStep({ label, value }: { label: string; value: string }) {
  let color = "text-slate-400";
  if (["UP", "CONFIRMED", "BULL_FLAG", "ACTIVE"].includes(value)) color = "text-emerald-400";
  if (["DOWN", "REJECTED", "BEAR_FLAG"].includes(value)) color = "text-red-400";
  if (["PENDING", "CONSOLIDATION", "WAITING", "FLAT"].includes(value)) color = "text-amber-400";

  return (
    <div className="flex flex-col border border-[#1C2333] p-2 rounded bg-[#0A0D14] text-center">
      <span className="text-[9px] text-slate-500 uppercase tracking-widest font-medium">{label}</span>
      <span className={`text-[10px] font-mono mt-1 font-medium ${color}`}>{value.replace("_", " ")}</span>
    </div>
  );
}

function StatusText({ value }: { value: string }) {
  let color = "text-slate-400";
  if (["ACTIONABLE", "EXECUTED", "COMPLETED"].includes(value)) color = "text-emerald-400";
  if (["REJECTED", "CANCELLED"].includes(value)) color = "text-red-400";
  if (["WAITING", "PENDING"].includes(value)) color = "text-amber-400";

  return (
    <span className={`font-mono font-medium ${color}`}>{value}</span>
  );
}

