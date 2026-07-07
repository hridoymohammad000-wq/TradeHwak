/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Menu, Activity, Zap } from 'lucide-react';
import type { RuntimeMode, TradingMode } from '../types';

interface HeaderProps {
  currentMode: TradingMode;
  onModeChange: (mode: TradingMode) => void;
  onMenuToggle: () => void;
  systemMode: RuntimeMode;
  backendStatus: 'loading' | 'healthy' | 'error';
  modeUpdating?: boolean;
}

export function Header({
  currentMode,
  onModeChange,
  onMenuToggle,
  systemMode,
  backendStatus,
  modeUpdating = false,
}: HeaderProps) {
  const backendLabel =
    backendStatus === 'loading'
      ? 'Syncing'
      : backendStatus === 'healthy'
        ? 'Backend Connected'
        : 'Backend Offline';

  return (
    <header className="h-16 border-b border-slate-900 bg-slate-950/40 px-4 md:px-6 flex items-center justify-between shrink-0">
      
      {/* LEFT: MOBILE MENU BUTTON & APP BRAND */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-900 lg:hidden focus:outline-none"
          aria-label="Toggle menu"
        >
          <Menu size={20} />
        </button>
        
        {/* Visible only on header to reinforce branding */}
        <div className="flex items-center gap-2 lg:hidden">
          <Zap size={16} className="text-indigo-400" />
          <span className="font-bold text-xs tracking-wider uppercase text-slate-200">
            Crypto Scalping Trader
          </span>
        </div>
      </div>

      {/* CENTER / RIGHT: TRADING MODE SELECTOR & SYSTEM STATUS */}
      <div className="flex items-center gap-4 ml-auto">
        
        {/* MODE SELECTOR */}
        <div className="flex items-center gap-1.5 bg-slate-950/80 border border-slate-900 p-1 rounded">
          <button
            onClick={() => onModeChange('scalping')}
            disabled={modeUpdating}
            className={`px-3 py-1 text-xs font-bold font-mono rounded transition-colors ${
              currentMode === 'scalping'
                ? 'bg-purple-950/60 text-purple-400 border border-purple-800/40 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            SCALPING
          </button>
          
          <button
            onClick={() => onModeChange('intraday')}
            disabled={modeUpdating}
            className={`px-3 py-1 text-xs font-bold font-mono rounded transition-colors ${
              currentMode === 'intraday'
                ? 'bg-blue-950/60 text-blue-400 border border-blue-800/40 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            INTRADAY
          </button>
        </div>

        {/* SYSTEM STATUS LABELS */}
        <div className="hidden sm:flex items-center gap-2 font-mono text-[11px]">
          <div className="px-2.5 py-1 bg-slate-900/60 border border-slate-800 rounded flex items-center gap-1.5 text-slate-400">
            <span className={`w-1.5 h-1.5 rounded-full ${systemMode === 'live' ? 'bg-rose-500' : 'bg-amber-500'}`}></span>
            {systemMode === 'live' ? 'Live Mode' : 'Demo Mode'}
          </div>

          <div className={`px-2.5 py-1 rounded flex items-center gap-1.5 ${
            backendStatus === 'healthy'
              ? 'bg-indigo-950/20 border border-indigo-900/30 text-indigo-400'
              : backendStatus === 'loading'
                ? 'bg-amber-950/20 border border-amber-900/30 text-amber-400'
                : 'bg-rose-950/20 border border-rose-900/30 text-rose-400'
          }`}>
            <Activity size={10} className={backendStatus === 'loading' ? 'animate-pulse' : ''} />
            {backendLabel}
          </div>
        </div>

      </div>

    </header>
  );
}
