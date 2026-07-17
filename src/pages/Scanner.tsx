import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { Signal } from "../types";
import { RefreshCw, Play, CheckCircle, Wifi, WifiOff, Zap, ShieldAlert, Clock, AlertTriangle } from "lucide-react";
import { normalizeSignals } from "../lib/normalizers";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function Scanner() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const { status: backendStatus } = useBackendStatus();

  const fetchScanner = async () => {
    try {
      setLoading(true);
      const res = await apiClient.getScanner();
      setSignals(normalizeSignals(res));
      setLastUpdated(new Date());
    } catch {
      setSignals([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScanner();
  }, []);

  const handleRunScan = async () => {
    setScanning(true);
    try {
      await apiClient.runScanner();
      await fetchScanner();
      setToastMessage("Scan completed successfully");
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error) {
      setToastMessage("Scan failed");
      setTimeout(() => setToastMessage(null), 3000);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6 relative flex flex-col h-[calc(100vh-8rem)]">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 right-4 bg-[#0F141F] border border-[#1C2333] text-slate-200 px-4 py-2 rounded shadow-lg flex items-center gap-2 z-50">
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium">{toastMessage}</span>
        </div>
      )}

      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-medium text-slate-100 tracking-tight">Market Scanner</h2>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-slate-500">1H → 15M → 5M Pipeline</span>
            {lastUpdated && (
              <span className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchScanner}
            disabled={loading}
            className="flex items-center justify-center px-3 py-2 bg-[#0F141F] hover:bg-[#1C2333]/50 text-slate-300 rounded-lg transition-colors border border-[#1C2333] disabled:opacity-50 text-sm font-medium"
            title="Refresh Scanner"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button 
            onClick={handleRunScan}
            disabled={scanning || backendStatus !== "Connected"}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-sm font-medium rounded-lg transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            {scanning ? "Scanning..." : "Run Scan"}
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="flex-1 bg-[#0F141F] border border-[#1C2333] rounded-lg flex flex-col overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center gap-6 px-4 border-b border-[#1C2333] shrink-0 overflow-x-auto">
          {["All", "A+ Grade", "A Grade", "Waiting", "Rejected"].map((tab, i) => (
            <button key={tab} className={`py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${i === 0 ? 'border-emerald-400 text-emerald-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
              {tab}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto">
          {signals.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="bg-[#1C2333]/20 border border-[#1C2333]/50 rounded-lg p-6 max-w-sm text-center">
                <span className="text-sm text-slate-400 block mb-1">No scanner results yet.</span>
                <span className="text-xs text-slate-500">Run scanner to fetch intraday candidates.</span>
              </div>
            </div>
          ) : (
            <table className="w-full text-left text-sm text-slate-300 border-collapse">
              <thead className="sticky top-0 bg-[#0F141F] z-10 border-b border-[#1C2333]">
                <tr>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">Symbol</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">Grade</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">1H Trend</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">15M Setup</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">5M Entry</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">Entry Price</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap max-w-[200px]">Reason</th>
                  <th className="px-4 py-3 font-medium text-slate-500 whitespace-nowrap text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C2333]">
                {signals.map(s => (
                  <tr key={s.id} className="hover:bg-[#1C2333]/30 transition-colors group">
                    <td className="px-4 py-3 font-mono font-medium text-slate-200 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className={`w-1 h-3 rounded-sm ${s.direction === 'LONG' ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
                        {s.symbol}
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`font-medium px-1.5 py-0.5 rounded text-[10px] ${s.grade === 'A+' ? 'bg-emerald-500/10 text-emerald-400' : s.grade === 'A' ? 'bg-emerald-500/5 text-emerald-400/80' : 'bg-[#1C2333] text-slate-400'}`}>
                        {s.grade}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge value={s.trend1H} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge value={s.setup15M} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge value={s.entry5M} />
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-400 whitespace-nowrap">{s.entryPrice || '-'}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge value={s.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500 truncate max-w-[200px] text-xs group-hover:text-slate-300 transition-colors" title={s.reason}>{s.reason}</td>
                    <td className="px-4 py-3 font-mono text-slate-500 text-xs whitespace-nowrap text-right">{new Date(s.createdAt).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  let color = "text-slate-500";
  let dotColor = "bg-slate-500";

  if (["UP", "CONFIRMED", "BULL_FLAG", "ACTIVE"].includes(value)) {
    color = "text-emerald-400";
    dotColor = "bg-emerald-400";
  }
  if (["DOWN", "REJECTED", "BEAR_FLAG", "CANCELLED"].includes(value)) {
    color = "text-red-400";
    dotColor = "bg-red-400";
  }
  if (["PENDING", "CONSOLIDATION", "WAITING", "FLAT"].includes(value)) {
    color = "text-amber-400";
    dotColor = "bg-amber-400";
  }
  
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span className={`text-[11px] font-medium ${color}`}>
        {value.replace("_", " ")}
      </span>
    </div>
  );
}

