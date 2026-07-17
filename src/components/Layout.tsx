import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { 
  LayoutDashboard, 
  ScanSearch, 
  Activity, 
  LineChart, 
  Briefcase, 
  BookOpen, 
  BarChart2, 
  Settings, 
  Terminal,
  LogOut,
  Wifi,
  WifiOff,
  RefreshCw
} from "lucide-react";
import { cn } from "../lib/utils";
import { useAuth } from "../context/AuthContext";
import { useBackendStatus } from "../hooks/useBackendStatus";

const navItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Scanner", href: "/scanner", icon: ScanSearch },
  { name: "Signals", href: "/signals", icon: Activity },
  { name: "Chart Workspace", href: "/charts", icon: LineChart },
  { name: "Active Trades", href: "/trades", icon: Briefcase },
  { name: "Trade Journal", href: "/journal", icon: BookOpen },
  { name: "Performance", href: "/performance", icon: BarChart2 },
  { name: "Control Center", href: "/control", icon: Terminal },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { logout, token } = useAuth();
  const { status, checkStatus } = useBackendStatus();

  return (
    <div className="min-h-screen bg-[#0A0D14] text-slate-200 font-sans flex overflow-hidden">
      {/* Sidebar */}
      <aside className="w-16 bg-[#0F141F] border-r border-[#1C2333] flex-col items-center py-4 hidden md:flex shrink-0">
        <div className="flex flex-col gap-2 w-full items-center">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                title={item.name}
                className={cn(
                  "w-10 h-10 rounded-lg flex items-center justify-center transition-colors relative group",
                  isActive 
                    ? "text-emerald-400 bg-emerald-400/10" 
                    : "text-slate-500 hover:text-slate-200 hover:bg-[#1C2333]/50"
                )}
              >
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-emerald-400 rounded-r-full" />
                )}
                <item.icon className="w-5 h-5" strokeWidth={isActive ? 2 : 1.5} />
                
                {/* Tooltip */}
                <div className="absolute left-full ml-3 px-2 py-1 bg-[#1C2333] text-slate-200 text-xs rounded opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 border border-[#2A344A]">
                  {item.name}
                </div>
              </Link>
            );
          })}
        </div>

        <div className="mt-auto flex flex-col gap-2 w-full items-center">
          <button
            onClick={checkStatus}
            title={`Backend: ${status}`}
            className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center transition-colors group relative",
              status === "Connected" ? "text-emerald-500 hover:bg-emerald-500/10" : status === "Degraded" ? "text-amber-500 hover:bg-amber-500/10" : "text-red-500 hover:bg-red-500/10"
            )}
          >
            {status === "Connected" ? <Wifi className="w-4 h-4" strokeWidth={1.5} /> : <WifiOff className="w-4 h-4" strokeWidth={1.5} />}
            <div className="absolute left-full ml-3 px-2 py-1 bg-[#1C2333] text-slate-200 text-xs rounded opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 border border-[#2A344A]">
              Backend: {status}
            </div>
          </button>
          <button 
            onClick={logout}
            title="Logout"
            className="w-10 h-10 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-[#1C2333]/50 transition-colors group relative"
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
            <div className="absolute left-full ml-3 px-2 py-1 bg-[#1C2333] text-slate-200 text-xs rounded opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 border border-[#2A344A]">
              Logout
            </div>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden bg-[#0A0D14]">
        <header className="h-[52px] border-b border-[#1C2333] flex items-center justify-between px-6 bg-[#0F141F] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
            <div className="font-semibold text-sm tracking-wide text-slate-200">TradeHawk</div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2">
              <span className="px-2 py-1 rounded-md bg-[#1C2333] text-slate-300 text-[10px] uppercase tracking-widest font-medium flex items-center gap-1.5">
                <span className={cn(
                  "w-1.5 h-1.5 rounded-full",
                  status === "Connected" ? "bg-emerald-500" : status === "Degraded" ? "bg-amber-500" : "bg-red-500"
                )}></span>
                {status}
              </span>
              <span className="px-2 py-1 rounded-md bg-[#1C2333] text-slate-300 text-[10px] uppercase tracking-widest font-medium">
                Bybit Demo
              </span>
              <span className="px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-[10px] uppercase tracking-widest font-medium">
                Intraday
              </span>
            </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-y-auto p-6">
          <div className="w-full max-w-[1400px] mx-auto">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
