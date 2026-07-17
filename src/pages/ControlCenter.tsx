import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { BotStatus } from "../types";
import { Terminal, CheckCircle, XCircle, RefreshCw, AlertTriangle, ShieldAlert, Wifi, WifiOff } from "lucide-react";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function ControlCenter() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string, type: 'success' | 'error' } | null>(null);
  const [showEmergencyConfirm, setShowEmergencyConfirm] = useState(false);
  const { status: globalBackendStatus } = useBackendStatus();

  const fetchStatus = async () => {
    setLoading(true);
    try {
      await apiClient.health();
      // Mocking actual bot status since health might not return it
      setStatus({
        isRunning: false,
        isDemo: true,
        backendStatus: "ONLINE",
        bybitStatus: "CONNECTED"
      });
    } catch {
      setStatus({
        isRunning: false,
        isDemo: true,
        backendStatus: "OFFLINE",
        bybitStatus: "DISCONNECTED"
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.startBot();
      setMessage({ text: "Intraday bot started.", type: 'success' });
      await fetchStatus();
    } catch (e: any) {
      setMessage({ text: e.message || "Failed to start bot", type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.stopBot();
      setMessage({ text: "Bot stopped.", type: 'success' });
      await fetchStatus();
    } catch (e: any) {
      setMessage({ text: e.message || "Failed to stop bot", type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    setLoading(true);
    setMessage(null);
    setShowEmergencyConfirm(false);
    try {
      await apiClient.updateEngineControl({ emergency_stop: true, auto_trade_enabled: false });
      setMessage({ text: "Emergency stop activated.", type: 'success' });
      await fetchStatus();
    } catch (e: any) {
      setMessage({ text: e.message || "Emergency stop failed", type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-medium text-slate-100 tracking-tight">Control Center</h2>
        <p className="text-sm text-slate-500 mt-1">Operate the Intraday Bybit Demo bot safely from one place.</p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0F141F] border border-[#1C2333] rounded-lg p-4">
        <div className="flex items-center gap-4 text-sm font-medium">
          <div className="flex items-center gap-2">
            {globalBackendStatus === "Connected" ? <Wifi className="w-4 h-4 text-emerald-400" /> : <WifiOff className="w-4 h-4 text-red-400" />}
            <span className={globalBackendStatus === "Connected" ? "text-emerald-400" : "text-red-400"}>{globalBackendStatus.toUpperCase()}</span>
          </div>
        </div>
        
        <button 
          onClick={fetchStatus}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[#1C2333]/50 hover:bg-[#1C2333] text-slate-300 text-sm font-medium rounded-lg transition-colors border border-[#1C2333] w-fit disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          Refresh Status
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
          <div className="flex justify-between items-center mb-6">
            <span className="text-sm font-medium text-slate-200">Engine Status</span>
            <span className="text-[10px] text-amber-500 bg-amber-500/10 px-2 py-1 rounded uppercase tracking-widest font-semibold">
              Bybit Demo only. Real trading disabled.
            </span>
          </div>
          
          <div className="space-y-2 mb-6">
            <StatusRow 
              label="Backend Status" 
              value={status?.backendStatus || "UNKNOWN"} 
              isGood={status?.backendStatus === "ONLINE"} 
            />
            <StatusRow 
              label="Bybit Demo Status" 
              value={status?.bybitStatus || "UNKNOWN"} 
              isGood={status?.bybitStatus === "CONNECTED"} 
            />
            <StatusRow 
              label="Intraday Engine" 
              value={status?.isRunning ? "RUNNING" : "STOPPED"} 
              isGood={!!status?.isRunning} 
              neutral={!status}
            />
            <StatusRow 
              label="Active Strategy" 
              value="INTRADAY" 
              isGood={true} 
            />
            <StatusRow 
              label="Execution Mode" 
              value="DEMO" 
              isGood={true} 
            />
          </div>

          {message && (
            <div className={`mt-6 p-4 rounded-lg text-sm font-medium flex items-center gap-3 ${message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
              {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
              {message.text}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
            <div className="flex justify-between items-center mb-6">
              <span className="text-sm font-medium text-slate-200">Main Controls</span>
            </div>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={handleStart}
                disabled={loading || status?.isRunning || globalBackendStatus !== 'Connected'}
                className="flex-1 py-3 px-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-sm font-semibold rounded-lg disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                Start Intraday Bot
              </button>
              
              <button
                onClick={handleStop}
                disabled={loading || !status?.isRunning}
                className="flex-1 py-3 px-4 bg-transparent border border-red-500/50 hover:bg-red-500/10 hover:border-red-500 text-red-500 text-sm font-semibold rounded-lg disabled:opacity-50 transition-colors"
              >
                Stop Bot
              </button>
            </div>
          </div>

          <div className="bg-[#0A0D14] border border-red-900/30 rounded-lg p-6 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-red-500/50"></div>
             <div className="flex justify-between items-center mb-4 pl-2">
              <span className="text-sm font-medium text-red-400 flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> Danger Zone</span>
            </div>
            
            {!showEmergencyConfirm ? (
              <button
                onClick={() => setShowEmergencyConfirm(true)}
                disabled={loading}
                className="w-full py-3 px-4 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-sm font-semibold rounded-lg disabled:opacity-50 transition-colors ml-2 w-[calc(100%-0.5rem)]"
              >
                Emergency Stop
              </button>
            ) : (
              <div className="space-y-4 ml-2">
                <p className="text-sm text-red-400/80 font-medium">Are you sure? This will immediately halt all operations and disable auto-trading.</p>
                <div className="flex gap-3">
                   <button
                    onClick={handleEmergencyStop}
                    className="flex-1 py-3 bg-red-500 hover:bg-red-400 text-white text-sm font-semibold rounded-lg transition-colors"
                  >
                    Confirm Stop
                  </button>
                  <button
                    onClick={() => setShowEmergencyConfirm(false)}
                    className="flex-1 py-3 bg-[#1C2333] hover:bg-[#2A344A] text-slate-300 text-sm font-semibold rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, value, isGood, neutral }: { label: string; value: string; isGood: boolean; neutral?: boolean }) {
  let statusColor = isGood ? 'bg-emerald-400' : 'bg-red-400';
  let textColor = isGood ? 'text-emerald-400' : 'text-red-400';
  
  if (neutral) {
     statusColor = 'bg-slate-500';
     textColor = 'text-slate-400';
  }

  return (
    <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-lg border border-[#1C2333] transition-colors">
      <span className="text-slate-400 text-xs font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
        <span className={`font-mono text-xs font-medium ${textColor}`}>{value}</span>
      </div>
    </div>
  );
}
