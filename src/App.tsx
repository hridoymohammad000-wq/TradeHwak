/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { AppProvider, useApp, PageName } from './context/AppContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import Scanner from './pages/Scanner';
import Signals from './pages/Signals';
import ChartWorkspace from './pages/ChartWorkspace';
import ActiveTrades from './pages/ActiveTrades';
import OperatorJournal from './pages/OperatorJournal';
import ControlCenter from './pages/ControlCenter';
import PerformanceStrategy from './pages/PerformanceStrategy';
import Login from './pages/Login';
import { getBackendStatusPresentation } from './lib/backendStatus';
import {
  TrendingUp,
  TrendingDown,
  LayoutDashboard,
  LineChart,
  Bell,
  Cpu,
  Sliders,
  LogOut,
  Menu,
  X,
  Target,
  ShieldAlert,
  Clock,
  Activity,
  Zap,
  Info,
  CheckCircle,
  AlertOctagon,
  Layers,
  BarChart3
} from 'lucide-react';

function TerminalShell() {
  const { connectionStatus, logout } = useAuth();
  const backendStatus = getBackendStatusPresentation(connectionStatus);
  const {
    currentPage,
    navigate,
    scannerData,
    signals,
    activeTrades,
    activeTradesData,
    todayClosedTradesData,
    dashboardData,
    toastMessage,
    clearToast
  } = useApp();

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [utcTime, setUtcTime] = useState('');

  // Clock Update
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const string = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
      setUtcTime(string);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Dismiss Toast automatically
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => {
        clearToast();
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  const todaysClosedTrades = todayClosedTradesData?.closed_trades.length;
  
  const visibleSignalsCount = signals?.length;

  const navItems = [
    { name: 'dashboard' as PageName, label: 'Dashboard', icon: LayoutDashboard },
    { name: 'scanner' as PageName, label: 'Scanner', icon: Activity, badge: scannerData ? scannerData.length : undefined },
    { name: 'signals' as PageName, label: 'AI Signals', icon: Bell, badge: visibleSignalsCount },
    { name: 'chart' as PageName, label: 'Chart Workspace', icon: LineChart },
    { name: 'active_trades' as PageName, label: 'Active Trades', icon: Layers, badge: activeTradesData?.active_trades.length },
    { name: 'journal' as PageName, label: 'Operator Journal', icon: Target, badge: todaysClosedTrades },
    { name: 'performance' as PageName, label: 'Performance & Strategy', icon: BarChart3 },
    { name: 'settings' as PageName, label: 'Control Center', icon: Sliders },
  ];

  const renderActivePage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'scanner':
        return <Scanner />;
      case 'signals':
        return <Signals />;
      case 'chart':
        return <ChartWorkspace />;
      case 'active_trades':
        return <ActiveTrades />;
      case 'journal':
        return <OperatorJournal />;
      case 'performance':
        return <PerformanceStrategy />;
      case 'settings':
        return <ControlCenter />;
      default:
        return <Dashboard />;
    }
  };



  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-slate-950">
      
      {/* Top Asset Ticker Ribbon */}
      <header className="bg-slate-900 border-b border-slate-850 h-14 shrink-0 px-5 flex items-center justify-between gap-4 z-40 relative shadow-md">
        <div className="flex items-center gap-4">
          {/* Mobile hamburger menu toggle */}
          <button 
            onClick={() => setMobileSidebarOpen(true)}
            className="md:hidden text-slate-400 hover:text-white p-1.5 rounded hover:bg-slate-800"
          >
            <Menu className="h-5 w-5" />
          </button>
          
          <div className="flex items-center gap-2 cursor-pointer group" onClick={() => navigate('dashboard')}>
            <div className="w-8 h-8 bg-emerald-500 rounded flex items-center justify-center text-[#0A0B0D] font-bold text-lg shadow-sm shadow-emerald-500/20 group-hover:scale-105 transition-transform duration-150">
              <Zap className="h-5 w-5 text-slate-950 fill-slate-950 stroke-[2.5]" />
            </div>
            <span className="font-bold text-white text-[15px] tracking-wider font-sans">TRADEHAWK</span>
            <span className="text-[10px] uppercase tracking-wider font-extrabold bg-slate-950 text-emerald-400 px-2 py-0.5 rounded border border-slate-800">Terminal v1.2</span>
          </div>
        </div>

        {/* Market data is intentionally not wired in this phase. */}
        <div className="hidden md:flex items-center gap-2 text-[11px] font-mono text-slate-400 border border-slate-800 bg-slate-950/60 rounded-lg px-3 py-1.5">
          <Activity className="h-3.5 w-3.5 text-slate-500" />
          Market ribbon unavailable — no simulated prices
        </div>

        {/* Portfolio aggregate value on top-right */}
        <div className="flex items-center gap-5">
          <div className="text-right hidden sm:block">
            <span className="text-[10px] uppercase text-slate-400 font-mono font-bold block">Demo Equity</span>
            <span className="text-[13px] font-mono font-extrabold text-white">{dashboardData?.account.equity == null ? 'N/A' : `$${dashboardData.account.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}</span>
          </div>
          
          <div className="h-7 w-[1px] bg-slate-850 hidden sm:block"></div>
          
          <div className="text-[11px] text-slate-300 font-mono font-semibold flex items-center gap-1.5">
            <Clock className="h-4 w-4 text-slate-400" />
            <span className="hidden lg:inline">{utcTime}</span>
          </div>
        </div>
      </header>

      {/* Main Container Layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Sidebar Layout (Desktop) */}
        <nav className="w-56 bg-slate-900 border-r border-slate-850 shrink-0 hidden md:flex flex-col justify-between p-4 z-30 shadow-lg">
          <div className="space-y-6">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-widest pl-2 font-bold flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
              <span>Navigation Board</span>
            </div>
            
            <ul className="space-y-1.5">
              {navItems.map((item) => {
                const IconComp = item.icon;
                const isSelected = currentPage === item.name;
                
                return (
                  <li key={item.name}>
                    <button
                      onClick={() => navigate(item.name)}
                      className={`w-full flex items-center justify-between py-2.5 rounded-lg text-[13px] font-semibold tracking-wide transition-all border ${
                        isSelected 
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 font-bold pl-3.5 shadow-sm' 
                          : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/40 border-transparent pl-3'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <IconComp className={`h-4.5 w-4.5 ${isSelected ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                        <span>{item.label}</span>
                      </div>
                      
                      {item.badge !== undefined && (
                        <span className="h-5 px-1.5 flex items-center justify-center rounded-full text-[10px] font-mono font-bold bg-rose-500 text-slate-950 animate-pulse">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Sidebar Footer */}
          <div className="border-t border-slate-850 pt-4 space-y-3.5">
            {/* User Profile Block */}
            <div className="flex items-center gap-3 p-2 rounded-lg border border-slate-800">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-white">TH</div>
              <div className="flex-1 overflow-hidden">
                <p className="text-xs font-bold text-slate-200 truncate">Private Operator</p>
                <p className="text-[10px] text-slate-400 truncate">Single-user session</p>
              </div>
            </div>

            <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-850 flex items-center gap-2.5 text-[11px] font-mono text-slate-300">
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 shrink-0 ${backendStatus.dotClass}`}></span>
              <div>
                <p className="text-slate-200 font-bold">Canonical Backend</p>
                <p className={`text-[9px] ${backendStatus.textClass}`}>{backendStatus.label}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void logout()}
              className="w-full flex items-center justify-center gap-2 text-[11px] font-bold text-slate-300 hover:text-white bg-slate-950/60 hover:bg-slate-800 border border-slate-850 rounded-lg px-3 py-2 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>

            <div className="text-[10px] text-slate-400 font-mono text-center font-semibold">
              TradeHawk Workspace v1.2
            </div>
          </div>
        </nav>

        {/* Mobile Slide-out Sidebar drawer */}
        {mobileSidebarOpen && (
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex animate-in fade-in duration-200">
            <div className="w-64 bg-slate-900 h-full p-4 flex flex-col justify-between border-r border-slate-800 shadow-2xl animate-in slide-in-from-left duration-200">
              <div className="space-y-6">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-1.5">
                    <Zap className="h-5 w-5 text-emerald-400" />
                    <span className="font-bold text-white text-sm tracking-widest font-mono">TRADEHAWK</span>
                  </div>
                  <button 
                    onClick={() => setMobileSidebarOpen(false)}
                    className="text-slate-400 hover:text-white"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <ul className="space-y-1">
                  {navItems.map((item) => {
                    const IconComp = item.icon;
                    const isSelected = currentPage === item.name;
                    
                    return (
                      <li key={item.name}>
                        <button
                          onClick={() => {
                            navigate(item.name);
                            setMobileSidebarOpen(false);
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                            isSelected 
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' 
                              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850 border border-transparent'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <IconComp className={`h-4 w-4 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                            <span>{item.label}</span>
                          </div>
                          
                          {item.badge !== undefined && (
                            <span className="h-5 px-1.5 flex items-center justify-center rounded-full text-[10px] font-mono font-bold bg-rose-500 text-slate-950">
                              {item.badge}
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className="border-t border-slate-800/80 pt-4 space-y-3">
                <div className="flex items-center justify-center gap-2 text-[10px] font-mono">
                  <span className={`h-2 w-2 rounded-full ${backendStatus.dotClass}`}></span>
                  <span className={backendStatus.textClass}>{backendStatus.label}</span>
                </div>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="w-full flex items-center justify-center gap-2 text-xs text-slate-300 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
                <div className="text-[10px] text-slate-500 font-mono text-center">TradeHawk Workspace v1.2</div>
              </div>
            </div>
          </div>
        )}

        {/* Core Main View Container */}
        <main className="flex-1 overflow-y-auto p-4 md:px-6 xl:px-7 py-6 bg-slate-950">
          <div className="w-full mx-auto">
            {renderActivePage()}
          </div>
        </main>
      </div>

      {/* Global Toast Overlay */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom duration-250">
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-2xl flex items-start gap-3 w-full max-w-sm relative">
            <button 
              onClick={clearToast}
              className="absolute right-3 top-3 text-slate-500 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>

            {toastMessage.type === 'success' && (
              <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
            )}
            {toastMessage.type === 'error' && (
              <AlertOctagon className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            )}
            {toastMessage.type === 'info' && (
              <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
            )}

            <div>
              <span className="text-xs font-bold text-slate-200 block">
                {toastMessage.type === 'success' ? 'Execution Complete' : toastMessage.type === 'error' ? 'System Warning' : 'System Information'}
              </span>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{toastMessage.text}</p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function ProtectedTradeHawk() {
  const { authState } = useAuth();

  if (authState !== 'authenticated') {
    return <Login />;
  }

  return (
    <AppProvider>
      <TerminalShell />
    </AppProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ProtectedTradeHawk />
    </AuthProvider>
  );
}
