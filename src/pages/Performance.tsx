import React, { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { PerformanceStats } from "../types";
import { BarChart2, TrendingUp, TrendingDown, Target, Activity, DollarSign, RefreshCw, AlertTriangle } from "lucide-react";
import { normalizePerformance } from "../lib/normalizers";

export function Performance() {
  const [stats, setStats] = useState<PerformanceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPerf = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getPerformance();
      setStats(normalizePerformance(res));
    } catch (err) {
      setStats(null);
      setError("Performance endpoint is unavailable or returned no data. No fallback performance values are shown.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPerf();
  }, []);

  return (
    <div className="space-y-4 flex flex-col h-full min-h-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-100 tracking-tight">Performance Metrics</h2>
          <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest font-semibold">Net Bybit Demo intraday results after fees</p>
        </div>

        <button 
          onClick={fetchPerf}
          disabled={loading}
          className="flex items-center justify-center w-8 h-8 bg-slate-800/50 hover:bg-slate-700 text-slate-200 rounded-lg transition-colors border border-slate-700 disabled:opacity-50"
          title="Refresh Performance"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`} />
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="h-24 bg-slate-800/40 rounded-xl animate-pulse"></div>
          <div className="h-24 bg-slate-800/40 rounded-xl animate-pulse"></div>
          <div className="h-24 bg-slate-800/40 rounded-xl animate-pulse"></div>
        </div>
      ) : !stats ? (
        <div className="flex-1 bg-slate-900 border border-slate-800 rounded-xl shadow-sm p-10 text-center flex flex-col items-center justify-center">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-300">No Verified Performance Data</h3>
          <p className="text-slate-500 text-sm max-w-md mx-auto mt-2">
            {error || "No performance data is available from the backend."}
          </p>
        </div>
      ) : (
        <div className="space-y-4 flex-1 flex flex-col overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 shrink-0">
            <MetricCard title="Total Net P&L" value={`$${stats.totalPnl.toFixed(2)}`} trend={stats.totalPnl >= 0 ? "up" : "down"} icon={<DollarSign className="w-5 h-5 text-emerald-400" />} />
            <MetricCard title="Win Rate" value={`${stats.winRate.toFixed(1)}%`} icon={<Target className="w-5 h-5 text-amber-400" />} />
            <MetricCard title="Max Drawdown" value={`${stats.drawdown.toFixed(1)}%`} trend="down" icon={<Activity className="w-5 h-5 text-red-400" />} />
          </div>

          <div className="bg-slate-900/80 border border-slate-800 backdrop-blur-sm rounded-xl p-6 flex flex-col flex-1 shadow-sm min-h-[220px]">
            <div className="flex items-center gap-3 mb-4">
              <BarChart2 className="w-4 h-4 text-slate-500" />
              <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Equity Curve</span>
            </div>
            <div className="flex-1 flex items-center justify-center text-center text-sm text-slate-500">
              Equity curve is hidden until the backend provides verified time-series performance data.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ title, value, icon, trend }: { title: string; value: string; icon: React.ReactNode; trend?: "up" | "down" }) {
  const isUp = trend === "up";
  const isDown = trend === "down";
  const valColor = isUp ? "text-emerald-400" : isDown ? "text-red-400" : "text-slate-100";

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 backdrop-blur-sm rounded-xl p-5 relative flex flex-col justify-between h-[110px] group hover:bg-slate-800/60 transition-colors">
      <div className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-400">{title}</p>
        <div className="text-slate-500 opacity-60 group-hover:opacity-100 transition-opacity">{icon}</div>
      </div>
      <div className="flex items-end gap-3 mt-2">
        <h4 className={`font-mono text-2xl font-bold truncate ${valColor}`}>{value}</h4>
        {trend && (
          <span className={`flex items-center text-xs font-semibold mb-1 bg-slate-950/40 px-1.5 py-0.5 rounded ${isUp ? "text-emerald-400 border border-emerald-500/20" : "text-red-400 border border-red-500/20"}`}>
            {isUp ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
            {isUp ? "UP" : "DWN"}
          </span>
        )}
      </div>
    </div>
  );
}
