/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { ActivePage } from '../types';
import {
  LayoutDashboard,
  Radio,
  TrendingUp,
  Activity,
  BookOpen,
  Settings,
  Radar,
  X,
  Layers
} from 'lucide-react';

interface SidebarProps {
  activePage: ActivePage;
  onPageChange: (page: ActivePage) => void;
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ activePage, onPageChange, isOpen, onClose }: SidebarProps) {
  // Configured sidebar navigation elements with matching Lucide icons
  const navItems = [
    { page: ActivePage.DASHBOARD, label: 'Dashboard', icon: LayoutDashboard },
    { page: ActivePage.SCANNER, label: 'Scanner', icon: Radar },
    { page: ActivePage.SIGNALS, label: 'Signals', icon: Radio },
    { page: ActivePage.CHART, label: 'Chart Workspace', icon: TrendingUp },
    { page: ActivePage.ACTIVE_TRADES, label: 'Active Trades', icon: Activity },
    { page: ActivePage.JOURNAL, label: 'Operator Journal', icon: BookOpen },
    { page: ActivePage.SETTINGS, label: 'Control Center', icon: Settings },
    { page: ActivePage.PERFORMANCE, label: 'Performance & Strategy', icon: Activity },
  ];

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-950/80 z-40 lg:hidden transition-opacity duration-200"
          onClick={onClose}
        />
      )}

      {/* SIDEBAR PANEL */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col w-64 bg-[#090d16] border-r border-slate-900 text-slate-300 transform transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:h-screen ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between px-5 h-16 border-b border-slate-900 bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <Layers className="text-indigo-400 w-5 h-5 shrink-0" />
            <span className="font-bold text-sm tracking-tight text-white font-sans">
              Crypto Scalping Trader
            </span>
          </div>
          {/* Mobile Close Button */}
          <button
            onClick={onClose}
            className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-900 lg:hidden"
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.page;

            return (
              <button
                key={item.page}
                onClick={() => {
                  onPageChange(item.page);
                  onClose();
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-sm font-semibold tracking-wide transition-all duration-150 text-left font-sans ${
                  isActive
                    ? 'bg-indigo-650 text-white shadow-md shadow-indigo-950/50'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                <Icon
                  size={16}
                  className={`shrink-0 transition-colors ${
                    isActive ? 'text-white' : 'text-slate-500'
                  }`}
                />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-slate-900 bg-slate-950/20 font-mono text-[10px] text-slate-500 leading-relaxed space-y-1">
          <p className="font-semibold uppercase tracking-wider text-slate-400">FOUNDATION STAGE</p>
          <p>Local Daemon: Standby</p>
          <p>System Version: v1.0.0-fnd</p>
        </div>
      </aside>
    </>
  );
}
