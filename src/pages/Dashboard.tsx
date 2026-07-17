import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, ArrowDownRight, DollarSign, Target, TrendingUp, AlertTriangle, ShieldCheck, Zap, Server, ActivitySquare } from "lucide-react";
import { apiClient } from "../lib/apiClient";
import { DashboardData } from "../types";
import { normalizeDashboardData } from "../lib/normalizers";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { status: backendStatus } = useBackendStatus();

  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiClient.getDashboard();
        setData(normalizeDashboardData(result));
      } catch (error) {
        setData(normalizeDashboardData(null));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return <div className="animate-pulse flex space-x-4"><div className="flex-1 space-y-4 py-1"><div className="h-4 bg-[#1C2333] rounded w-1/4"></div></div></div>;
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-medium text-slate-100 tracking-tight">Overview</h2>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard 
          title="Today's Signals" 
          value={data.recentSignals.length.toString()} 
          subtitle="Awaiting Execution"
        />
        <StatCard 
          title="Active Trades" 
          value={data.activeTrades.length.toString()} 
          subtitle="Positions Open"
        />
        <StatCard 
          title="Net PnL" 
          value={`$${data.stats.dailyPnl.toFixed(2)}`} 
          trend={data.stats.dailyPnl >= 0 ? "up" : "down"}
          subtitle="Realized Today"
        />
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">Loss Limit</span>
          </div>
          <div className="mt-3 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-300">0.0%</span>
              <span className="text-slate-500">100%</span>
            </div>
            <div className="h-1.5 w-full bg-[#1C2333] rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 w-0"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Workflow Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#0F141F] border border-[#1C2333] rounded-lg p-5">
          <div className="flex justify-between items-center mb-8">
            <h3 className="text-sm font-medium text-slate-200">Execution Pipeline</h3>
            <span className="text-xs text-slate-500">Active</span>
          </div>
          
          <div className="flex flex-col sm:flex-row items-center justify-between relative">
            <div className="absolute left-[50%] top-0 bottom-0 w-px bg-[#1C2333] sm:hidden -z-10" />
            <div className="absolute top-[50%] left-0 right-0 h-px bg-[#1C2333] hidden sm:block -z-10" />
            
            <PipelineStep label="1H Trend" status="active" />
            <PipelineStep label="15M Setup" status="active" />
            <PipelineStep label="5M Entry" status="active" />
            <PipelineStep label="Risk Check" status="waiting" />
            <PipelineStep label="Demo Order" status="waiting" />
          </div>
        </div>

        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-5">
          <h3 className="text-sm font-medium text-slate-200 mb-4">System Health</h3>
          <div className="space-y-4">
            <HealthItem label="API Connection" status={backendStatus === "Connected" ? "OK" : "ERROR"} isGood={backendStatus === "Connected"} />
            <HealthItem label="Bybit Demo" status={backendStatus === "Connected" ? "OK" : "DISCONNECTED"} isGood={backendStatus === "Connected"} />
            <HealthItem label="Bot Engine" status="STOPPED" isGood={false} />
            <HealthItem label="Last Scan" status={data.recentSignals.length > 0 ? "5m ago" : "N/A"} isGood={data.recentSignals.length > 0} />
          </div>
        </div>
      </div>

      {/* Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-[#1C2333]">
            <h3 className="text-sm font-medium text-slate-200">Active Trades</h3>
          </div>
          <div className="flex-1 p-0">
            {data.activeTrades.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No active trades currently open.
              </div>
            ) : (
               <div className="divide-y divide-[#1C2333]">
                 {data.activeTrades.map(trade => (
                   <div key={trade.id} className="flex items-center justify-between p-4 hover:bg-[#1C2333]/30 transition-colors">
                      <div className="flex items-center gap-4">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${trade.direction === 'LONG' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                          {trade.direction}
                        </span>
                        <div>
                          <div className="font-medium text-sm text-slate-200">{trade.symbol}</div>
                          <div className="text-xs text-slate-500 font-mono mt-0.5">{trade.entryPrice}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`font-mono text-sm font-medium ${trade.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                        </div>
                        <div className="text-xs text-slate-500 font-mono">{trade.pnlPercentage.toFixed(2)}%</div>
                      </div>
                   </div>
                 ))}
               </div>
            )}
          </div>
        </div>

        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-0 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-[#1C2333]">
            <h3 className="text-sm font-medium text-slate-200">Recent Signals</h3>
          </div>
          <div className="flex-1 p-0">
            {data.recentSignals.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No recent signals detected.
              </div>
            ) : (
              <div className="divide-y divide-[#1C2333]">
                {data.recentSignals.map(sig => (
                   <div key={sig.id} className="flex items-center justify-between p-4 hover:bg-[#1C2333]/30 transition-colors">
                      <div className="flex items-center gap-4">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${sig.grade === 'A+' ? 'bg-emerald-500/10 text-emerald-400' : sig.grade === 'A' ? 'bg-emerald-500/5 text-emerald-400/80' : 'bg-[#1C2333] text-slate-400'}`}>
                          {sig.grade}
                        </span>
                        <div>
                          <div className="font-medium text-sm text-slate-200">{sig.symbol}</div>
                          <div className="text-xs text-slate-500 mt-0.5 line-clamp-1">{sig.reason}</div>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${sig.direction === 'LONG' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                          {sig.direction}
                        </span>
                        <div className="text-[10px] text-slate-500 font-mono mt-1">{new Date(sig.createdAt).toLocaleTimeString()}</div>
                      </div>
                   </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function HealthItem({ label, status, isGood }: { label: string; status: string; isGood: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-xs font-mono font-medium ${isGood ? 'text-emerald-400' : 'text-slate-500'}`}>
        {status}
      </span>
    </div>
  );
}

function PipelineStep({ label, status }: { label: string; status: 'active' | 'waiting' | 'done' }) {
  const isActive = status === 'active';
  return (
    <div className="flex flex-col items-center gap-2 bg-[#0F141F] py-2 px-1 z-10 w-24">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${isActive ? 'bg-emerald-400/20 text-emerald-400 ring-4 ring-[#0F141F]' : 'bg-[#1C2333] text-slate-500 ring-4 ring-[#0F141F]'}`}>
        {isActive ? <div className="w-2 h-2 rounded-full bg-emerald-400" /> : <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />}
      </div>
      <span className={`text-[10px] uppercase tracking-wider font-semibold text-center ${isActive ? 'text-slate-300' : 'text-slate-500'}`}>{label}</span>
    </div>
  );
}

function StatCard({ title, value, subtitle, trend }: { title: string; value: string; subtitle?: string; trend?: "up" | "down" }) {
  return (
    <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-4 flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">{title}</span>
        {trend && (
          trend === "up" ? <ArrowUpRight className="w-4 h-4 text-emerald-400" /> : <ArrowDownRight className="w-4 h-4 text-red-400" />
        )}
      </div>
      <div className="mt-2 flex flex-col">
        <span className="font-mono text-2xl font-medium text-slate-100">{value}</span>
        {subtitle && <span className="text-xs text-slate-500 mt-1">{subtitle}</span>}
      </div>
    </div>
  );
}

