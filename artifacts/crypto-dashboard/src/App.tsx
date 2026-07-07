import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { backendApi } from './api/services';
import { ApiError } from './api/client';
import { ActivePage } from './types';
import type { RuntimeMode, TradingMode } from './types';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';

import { DashboardPage } from './components/pages/DashboardPage';
import { ScannerPage } from './components/pages/ScannerPage';
import { SignalsPage } from './components/pages/SignalsPage';
import { ChartPage } from './components/pages/ChartPage';
import { ActiveTradesPage } from './components/pages/ActiveTradesPage';
import { JournalPage } from './components/pages/JournalPage';
import { SettingsPage } from './components/pages/SettingsPage';

export type BackendStatus = 'loading' | 'healthy' | 'error';

export default function App() {
  const [activePage, setActivePage] = useState<ActivePage>(ActivePage.DASHBOARD);
  const [tradingMode, setTradingMode] = useState<TradingMode>('scalping');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [systemMode, setSystemMode] = useState<RuntimeMode>('demo');
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('loading');
  const [modeUpdating, setModeUpdating] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadAppState(signal: AbortSignal) {
      try {
        const [modeResponse, healthResponse] = await Promise.all([
          backendApi.getMode(signal),
          backendApi.getHealth(signal),
        ]);
        setTradingMode(modeResponse.data.active_strategy_mode);
        setSystemMode(modeResponse.data.system_mode);
        setBackendStatus(healthResponse.data.status === 'healthy' ? 'healthy' : 'error');
      } catch {
        setBackendStatus('error');
      }
    }

    setBackendStatus('loading');
    void loadAppState(controller.signal);

    const intervalId = window.setInterval(() => {
      void loadAppState(controller.signal);
    }, 15000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  const handleModeChange = async (mode: TradingMode) => {
    const previousMode = tradingMode;
    setTradingMode(mode);
    setModeUpdating(true);

    try {
      const response = await backendApi.updateSettings({ active_strategy_mode: mode });
      setTradingMode(response.data.strategy.active_strategy_mode);
      setBackendStatus('healthy');
    } catch (error) {
      setTradingMode(previousMode);
      if (error instanceof ApiError) {
        setBackendStatus(error.status === 0 ? 'error' : backendStatus);
      }
    } finally {
      setModeUpdating(false);
    }
  };

  const renderPage = () => {
    switch (activePage) {
      case ActivePage.DASHBOARD:
        return <DashboardPage backendStatus={backendStatus} onNavigate={setActivePage} />;
      case ActivePage.SCANNER:
        return <ScannerPage backendStatus={backendStatus} />;
      case ActivePage.SIGNALS:
        return <SignalsPage backendStatus={backendStatus} />;
      case ActivePage.CHART:
        return <ChartPage backendStatus={backendStatus} />;
      case ActivePage.ACTIVE_TRADES:
        return <ActiveTradesPage backendStatus={backendStatus} />;
      case ActivePage.JOURNAL:
        return <JournalPage backendStatus={backendStatus} />;
      case ActivePage.SETTINGS:
        return <SettingsPage backendStatus={backendStatus} />;
      default:
        return <DashboardPage backendStatus={backendStatus} onNavigate={setActivePage} />;
    }
  };

  return (
    <div className="flex h-screen w-screen bg-[#040810] text-slate-100 overflow-hidden font-sans select-none">
      <Sidebar
        activePage={activePage}
        onPageChange={(page) => setActivePage(page)}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <Header
          currentMode={tradingMode}
          onModeChange={handleModeChange}
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
          systemMode={systemMode}
          backendStatus={backendStatus}
          modeUpdating={modeUpdating}
        />

        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 bg-[#050914] relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={activePage}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15, ease: 'easeInOut' }}
              className="h-full max-w-7xl mx-auto"
            >
              {renderPage()}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
