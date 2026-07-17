import { Settings as SettingsType } from "../types";
import { useEffect, useState } from "react";
import { apiClient } from "../lib/apiClient";
import { config } from "../lib/config";
import { normalizeSettings } from "../lib/normalizers";
import { Server, Activity, ShieldAlert, Bell, Palette, CheckCircle, XCircle } from "lucide-react";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [loading, setLoading] = useState(false);
  const { status: backendStatus, checkStatus } = useBackendStatus();
  
  // UI Preferences
  const [uiPrefs, setUiPrefs] = useState({
    compactTables: false,
    netPnlPrimary: true,
    toastAlerts: true,
    soundAlerts: false,
  });

  useEffect(() => {
    // Load UI prefs from local storage
    try {
      const saved = localStorage.getItem("th_ui_prefs");
      if (saved) {
        setUiPrefs(JSON.parse(saved));
      }
    } catch {}

    const fetchSettings = async () => {
      setLoading(true);
      try {
        const res = await apiClient.getSettings();
        setSettings(normalizeSettings(res));
      } catch {
        setSettings(null);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleUiPrefToggle = (key: keyof typeof uiPrefs) => {
    const newPrefs = { ...uiPrefs, [key]: !uiPrefs[key] };
    setUiPrefs(newPrefs);
    localStorage.setItem("th_ui_prefs", JSON.stringify(newPrefs));
  };

  const handleTestConnection = async () => {
    await checkStatus();
  };

  return (
    <div className="space-y-6 flex flex-col h-full min-h-0 overflow-y-auto pb-8">
      <div>
        <h2 className="text-xl font-medium text-slate-100 tracking-tight">System Settings</h2>
        <p className="text-xs text-slate-500 mt-1">Backend configuration & UI preferences</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        
        {/* 1. API Connection */}
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
          <div className="flex items-center gap-3 mb-6 border-b border-[#1C2333] pb-4">
            <Server className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-200">API Connection</span>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-2">Base URL</label>
              <div className="bg-[#0A0D14] border border-[#1C2333] rounded-md px-3 py-2 text-slate-300 font-mono text-sm truncate">
                {config.apiBaseUrl || "Same-origin (Current Host)"}
              </div>
            </div>
            <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-md border border-[#1C2333]">
              <span className="text-xs font-medium text-slate-400">Health Check</span>
              <div className="flex items-center gap-2">
                {backendStatus === "Connected" ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                <span className={`font-mono text-xs font-medium ${backendStatus === "Connected" ? "text-emerald-400" : "text-red-400"}`}>{backendStatus}</span>
              </div>
            </div>
            <button 
              onClick={handleTestConnection}
              className="w-full px-4 py-2 bg-[#1C2333] hover:bg-[#2A344A] text-slate-200 text-sm font-medium rounded-md transition-colors"
            >
              Test Connection
            </button>
            <p className="text-xs text-slate-500/80 font-medium pt-2">API keys and secrets must be managed securely on the backend server.</p>
          </div>
        </div>

        {/* 2. Strategy Mode */}
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
           <div className="flex items-center gap-3 mb-6 border-b border-[#1C2333] pb-4">
            <Activity className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-200">Strategy Mode</span>
          </div>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-md border border-[#1C2333]">
              <span className="text-xs font-medium text-slate-400">Active Strategy</span>
              <span className="font-mono text-xs font-medium text-slate-200">INTRADAY</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-md border border-[#1C2333] opacity-50">
              <span className="text-xs font-medium text-slate-500">Scalping</span>
              <span className="font-mono text-xs font-medium text-slate-500 line-through">DISABLED</span>
            </div>
            
            <div className="p-3 bg-[#0A0D14] rounded-md border border-[#1C2333]">
              <p className="text-xs text-slate-400 leading-relaxed font-medium">
                This frontend is built exclusively for the Intraday <span className="font-mono font-medium text-slate-300">1H → 15M → 5M</span> pipeline. Scalping mode has been disabled from the execution flow.
              </p>
            </div>
          </div>
        </div>

        {/* 3. Risk Display */}
        <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
          <div className="flex items-center gap-3 mb-6 border-b border-[#1C2333] pb-4">
            <ShieldAlert className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-200">Risk Parameters (Read-Only)</span>
          </div>
          
          <div className="space-y-2.5">
             <ReadOnlyRow label="Risk Per Trade" value={settings?.riskPerTrade !== undefined ? `${settings.riskPerTrade}%` : 'N/A'} />
             <ReadOnlyRow label="Max Daily Loss" value={settings?.maxDailyLoss !== undefined ? `${settings.maxDailyLoss}%` : 'N/A'} />
             <ReadOnlyRow label="Max Open Positions" value={settings?.maxOpenPositions !== undefined ? `${settings.maxOpenPositions}` : 'N/A'} />
             <ReadOnlyRow label="Daily Max Trades" value={settings?.dailyMaxTrades !== undefined ? `${settings.dailyMaxTrades}` : 'N/A'} />
             <ReadOnlyRow 
               label="Allowed Grades" 
               value={settings?.allowedSignalGrades ? settings.allowedSignalGrades.join(", ") : 'N/A'} 
             />
             <p className="text-xs text-slate-500/80 font-medium pt-2">These parameters are enforced strictly by the backend.</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* 4. Notifications Display */}
          <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
             <div className="flex items-center gap-3 mb-6 border-b border-[#1C2333] pb-4">
              <Bell className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-200">Notifications</span>
            </div>
            
            <div className="space-y-2.5">
              <ToggleRow label="Toast Alerts" checked={uiPrefs.toastAlerts} onChange={() => handleUiPrefToggle("toastAlerts")} />
              <ToggleRow label="Sound Chimes" checked={uiPrefs.soundAlerts} onChange={() => handleUiPrefToggle("soundAlerts")} />
              <div className="pt-4 border-t border-[#1C2333] mt-4 space-y-2.5">
                 <ReadOnlyRow label="Telegram Integration" value={settings?.telegramStatus || 'N/A'} highlight={settings?.telegramStatus === 'Connected'} />
                 <ReadOnlyRow label="Email Notifications" value={settings?.emailStatus || 'N/A'} highlight={settings?.emailStatus === 'Connected'} />
              </div>
            </div>
          </div>

          {/* 5. UI Preferences */}
          <div className="bg-[#0F141F] border border-[#1C2333] rounded-lg p-6">
             <div className="flex items-center gap-3 mb-6 border-b border-[#1C2333] pb-4">
              <Palette className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-200">UI Preferences</span>
            </div>
            
            <div className="space-y-2.5">
              <ToggleRow label="Compact Tables" checked={uiPrefs.compactTables} onChange={() => handleUiPrefToggle("compactTables")} />
              <ToggleRow label="Show Net P&L as Primary" checked={uiPrefs.netPnlPrimary} onChange={() => handleUiPrefToggle("netPnlPrimary")} />
              <p className="text-xs text-slate-500/80 font-medium pt-2">Saved locally to this browser.</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function ReadOnlyRow({ label, value, highlight = false }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-md border border-[#1C2333]">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      <span className={`font-mono text-xs font-medium ${highlight ? 'text-emerald-400' : 'text-slate-300'}`}>{value}</span>
    </div>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between p-3 bg-[#0A0D14] rounded-md border border-[#1C2333] cursor-pointer hover:bg-[#1C2333]/50 transition-colors group" onClick={onChange}>
      <span className="text-xs font-medium text-slate-400 group-hover:text-slate-300 transition-colors">{label}</span>
      <div className={`w-8 h-4 rounded-full flex items-center p-0.5 transition-colors ${checked ? 'bg-emerald-500' : 'bg-slate-700'}`}>
        <div className={`bg-white w-3 h-3 rounded-full shadow-sm transition-transform ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
      </div>
    </div>
  );
}
