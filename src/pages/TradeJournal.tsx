import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { Trade } from "../types";
import { BookOpen, RefreshCw, AlertTriangle, Clock } from "lucide-react";
import { normalizeTrades } from "../lib/normalizers";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function TradeJournal() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchJournal = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getJournal();
      setTrades(normalizeTrades(res));
      setLastUpdated(new Date());
    } catch {
      setTrades([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJournal();
  }, []);

  const totalClosed = trades.length;
  const wins = trades.filter(t => t.netPnl > 0).length;
  const losses = trades.filter(t => t.netPnl < 0).length;
  const winRate = totalClosed > 0 ? (wins / totalClosed) * 100 : 0;
  
  const totalGrossPnl = trades.reduce((sum, t) => sum + (t.grossPnl || 0), 0);
  const totalFees = trades.reduce((sum, t) => sum + (t.fees || 0), 0);
  const totalNetPnl = trades.reduce((sum, t) => sum + (t.netPnl || 0), 0);

  return (
    <div className="space-y-6 flex flex-col h-full min-h-0">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-medium text-slate-100 tracking-tight">Trade Journal</h2>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-slate-500">Completed Bybit Demo Trades & Performance</span>
            {lastUpdated && (
              <span className="text-xs text-slate-500 font-mono flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchJournal}
            disabled={loading}
            className="flex items-center justify-center px-3 py-2 bg-[#0F141F] hover:bg-[#1C2333]/50 text-slate-300 rounded-lg transition-colors border border-[#1C2333] disabled:opacity-50 text-sm font-medium"
            title="Refresh Journal"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 shrink-0">
        <SummaryCard title="Total Trades" value={totalClosed.toString()} />
        <SummaryCard title="Wins" value={wins.toString()} accent="emerald" />
        <SummaryCard title="Losses" value={losses.toString()} accent="red" />
        <SummaryCard title="Win Rate" value={`${winRate.toFixed(1)}%`} accent={winRate >= 50 ? 'emerald' : 'amber'} />
        <SummaryCard title="Gross P&L" value={`${totalGrossPnl >= 0 ? '+' : ''}${totalGrossPnl.toFixed(2)}`} accent={totalGrossPnl >= 0 ? 'emerald' : 'red'} />
        <SummaryCard title="Total Fees" value={totalFees.toFixed(2)} accent="slate" />
        <SummaryCard title="Net P&L" value={`${totalNetPnl >= 0 ? '+' : ''}${totalNetPnl.toFixed(2)}`} accent={totalNetPnl >= 0 ? 'emerald' : 'red'} isPrimary />
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
            <BookOpen className="w-12 h-12 opacity-20" />
            <h3 className="text-sm font-medium text-slate-400">No Historical Trades</h3>
            <p className="text-xs max-w-sm">Completed trades will appear here along with net P&L and execution results.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left text-xs text-slate-300 border-collapse">
              <thead className="sticky top-0 bg-[#0A0D14] z-10 border-b border-[#1C2333]">
                <tr>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Symbol</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Dir</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Grade</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Entry</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Exit</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Qty</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap text-right">Gross P&L</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap text-right">Fees</th>
                  <th className="px-4 py-3 font-medium text-slate-200 whitespace-nowrap text-right">Net P&L</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap pl-6">Result</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Reason</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Opened</th>
                  <th className="px-4 py-3 font-medium text-slate-400 whitespace-nowrap">Closed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C2333]">
                {trades.map(t => <JournalRow key={t.id} trade={t} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function JournalRow({ trade }: { trade: Trade }) {
  const isBuy = trade.direction === "BUY" || trade.direction === "LONG";
  const pnlClass = trade.grossPnl >= 0 ? "text-emerald-400" : "text-red-400";
  const netPnlClass = trade.netPnl >= 0 ? "text-emerald-400" : "text-red-400";
  
  const resultClass = trade.result === "WIN" ? "text-emerald-400" : 
                      trade.result === "LOSS" ? "text-red-400" : 
                      trade.result === "BREAKEVEN" ? "text-slate-300" : "text-slate-500";
  const resultDot = trade.result === "WIN" ? "bg-emerald-500/50" : 
                    trade.result === "LOSS" ? "bg-red-500/50" : 
                    trade.result === "BREAKEVEN" ? "bg-slate-500/50" : "bg-slate-600/50";

  const feeWarning = trade.grossPnl > 0 && trade.netPnl < 0;

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
      <td className="px-4 py-3 whitespace-nowrap">
        <span className={`font-medium text-[10px] px-1.5 py-0.5 rounded ${trade.grade === 'A+' ? 'bg-emerald-500/10 text-emerald-400' : trade.grade === 'A' ? 'bg-emerald-500/5 text-emerald-400/80' : 'bg-[#1C2333] text-slate-400'}`}>
          {trade.grade}
        </span>
      </td>
      <td className="px-4 py-3 font-mono text-slate-300 whitespace-nowrap">{trade.entryPrice}</td>
      <td className="px-4 py-3 font-mono text-slate-300 whitespace-nowrap">{trade.exitPrice || trade.currentPrice || '-'}</td>
      <td className="px-4 py-3 font-mono text-slate-400 whitespace-nowrap">{trade.quantity}</td>
      <td className={`px-4 py-3 font-mono font-medium text-right whitespace-nowrap ${pnlClass}`}>
        {trade.grossPnl >= 0 ? '+' : ''}{trade.grossPnl.toFixed(2)}
      </td>
      <td className="px-4 py-3 font-mono text-slate-500 text-right whitespace-nowrap">
        {trade.fees === null ? 'N/A' : trade.fees.toFixed(2)}
      </td>
      <td className={`px-4 py-3 font-mono font-medium text-right whitespace-nowrap ${netPnlClass} bg-[#0A0D14]/50`}>
        <div className="flex items-center justify-end gap-1.5">
          {feeWarning && <span title="Fees turned this trade net negative."><AlertTriangle className="w-3.5 h-3.5 text-amber-500" /></span>}
          {trade.netPnl >= 0 ? '+' : ''}{trade.netPnl.toFixed(2)}
        </div>
      </td>
      <td className="px-4 py-3 pl-6 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${resultDot}`} />
          <span className={`text-[10px] font-mono font-medium ${resultClass}`}>
            {trade.result}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-[10px] font-mono text-slate-500 max-w-[150px] truncate group-hover:text-slate-300 transition-colors" title={trade.reason}>{trade.reason}</td>
      <td className="px-4 py-3 font-mono text-[10px] text-slate-500 whitespace-nowrap text-right">{new Date(trade.openTime).toLocaleString()}</td>
      <td className="px-4 py-3 font-mono text-[10px] text-slate-500 whitespace-nowrap text-right">{trade.closeTime ? new Date(trade.closeTime).toLocaleString() : '-'}</td>
    </tr>
  );
}

function SummaryCard({ title, value, accent, isPrimary = false }: { title: string; value: string; accent?: 'emerald' | 'amber' | 'red' | 'slate'; isPrimary?: boolean }) {
  let valueColor = 'text-slate-200';
  let borderClass = 'border-[#1C2333]';
  let bgClass = 'bg-[#0F141F]';
  
  if (accent === 'emerald') valueColor = 'text-emerald-400';
  if (accent === 'red') valueColor = 'text-red-400';
  if (accent === 'amber') valueColor = 'text-amber-400';
  if (accent === 'slate') valueColor = 'text-slate-400';

  if (isPrimary) {
    borderClass = 'border-[#1C2333]';
    bgClass = 'bg-[#0A0D14]';
  }

  return (
    <div className={`${bgClass} border ${borderClass} rounded-lg p-4 flex flex-col justify-between gap-1`}>
      <span className="text-[10px] text-slate-500 uppercase tracking-widest font-medium">{title}</span>
      <span className={`font-mono font-medium truncate ${isPrimary ? 'text-lg' : 'text-base'} ${valueColor}`}>{value}</span>
    </div>
  );
}
