import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { Trade } from "../types";
import { Briefcase, RefreshCw, Clock } from "lucide-react";
import { normalizeTrades } from "../lib/normalizers";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function ActiveTrades() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getActiveTrades();
      setTrades(normalizeTrades(res));
      setLastUpdated(new Date());
    } catch {
      setTrades([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6 flex flex-col h-full min-h-0">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-medium text-slate-100 tracking-tight">Active Demo Trades</h2>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-slate-500">Open Bybit Demo Positions</span>
            {lastUpdated && (
              <span className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchTrades}
            disabled={loading}
            className="flex items-center justify-center px-3 py-2 bg-[#0F141F] hover:bg-[#1C2333]/50 text-slate-300 rounded-lg transition-colors border border-[#1C2333] disabled:opacity-50 text-sm font-medium"
            title="Refresh Trades"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 bg-[#0F141F] border border-[#1C2333] rounded-lg flex flex-col overflow-hidden">
        {loading && trades.length === 0 ? (
          <div className="flex-1 p-8 space-y-4">
            <div className="animate-pulse h-12 bg-[#1C2333]/50 rounded"></div>
            <div className="animate-pulse h-12 bg-[#1C2333]/50 rounded"></div>
            <div className="animate-pulse h-12 bg-[#1C2333]/50 rounded"></div>
          </div>
        ) : trades.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-8 text-center text-slate-500 gap-4">
            <Briefcase className="w-12 h-12 opacity-20" />
            <h3 className="text-sm font-medium text-slate-400">No Open Positions</h3>
            <p className="text-xs max-w-sm">There are currently no active intraday trades running in the demo environment.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left text-xs text-slate-300 border-collapse">
              <thead className="sticky top-0 bg-[#0A0D14] z-10 border-b border-[#1C2333]">
                <tr>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Symbol</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Dir</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Entry</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Current</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Qty</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">SL</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">TP</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap text-right">Unrealized P&L</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap text-right">Fees</th>
                  <th className="px-4 py-3 font-medium text-slate-200 whitespace-nowrap text-right">Net P&L</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap pl-6">Status</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C2333]">
                {trades.map(t => (
                  <TradeRow key={t.id} trade={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function TradeRow({ trade }: { trade: Trade }) {
  const isBuy = trade.direction === "BUY" || trade.direction === "LONG";
  const pnlClass = trade.grossPnl >= 0 ? "text-emerald-400" : "text-red-400";
  const netPnlClass = trade.netPnl >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <tr className="hover:bg-[#1C2333]/30 transition-colors group">
      <td className="px-4 py-3 font-mono font-medium text-slate-200 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <span className={`w-1.5 h-4 rounded-sm ${isBuy ? 'bg-emerald-500/50' : 'bg-red-500/50'}`}></span>
          {trade.symbol}
        </div>
      </td>
      <td className="px-4 py-3 whitespace-nowrap">
        <span className={`font-medium text-[10px] px-1.5 py-0.5 rounded ${isBuy ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
          {isBuy ? 'LONG' : 'SHORT'}
        </span>
      </td>
      <td className="px-4 py-3 font-mono text-slate-300 whitespace-nowrap">{trade.entryPrice}</td>
      <td className="px-4 py-3 font-mono text-slate-100 whitespace-nowrap">{trade.currentPrice}</td>
      <td className="px-4 py-3 font-mono text-slate-400 whitespace-nowrap">{trade.quantity}</td>
      <td className="px-4 py-3 font-mono text-red-400/80 whitespace-nowrap">{trade.sl || '-'}</td>
      <td className="px-4 py-3 font-mono text-emerald-400/80 whitespace-nowrap">{trade.tp || '-'}</td>
      <td className={`px-4 py-3 font-mono font-medium text-right whitespace-nowrap ${pnlClass}`}>
        {trade.grossPnl >= 0 ? '+' : ''}{trade.grossPnl.toFixed(2)}
      </td>
      <td className="px-4 py-3 font-mono text-slate-500 text-right whitespace-nowrap">
        {trade.fees === null ? 'N/A' : trade.fees.toFixed(2)}
      </td>
      <td className={`px-4 py-3 font-mono font-medium text-right whitespace-nowrap ${netPnlClass} bg-[#0A0D14]/50`}>
        {trade.netPnl >= 0 ? '+' : ''}{trade.netPnl.toFixed(2)}
      </td>
      <td className="px-4 py-3 pl-6 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          <span className="text-[10px] font-mono font-medium text-amber-400">
            {trade.status}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 font-mono text-[10px] text-slate-500 whitespace-nowrap text-right">
        {new Date(trade.openTime).toLocaleTimeString()}
      </td>
    </tr>
  );
}

