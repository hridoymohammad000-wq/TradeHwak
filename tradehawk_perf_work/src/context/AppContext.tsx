/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import {
  MarketTicker,
  DashboardStats,
  ScannerResult,
  TradingSignal,
  CanonicalScanData,
  CanonicalSignalsData,
  ScanRequestPayload,
  ActiveTrade,
  JournalEntry,
  ControlCenterSettings,
  AssetTicker,
  CanonicalDashboardData,
  CanonicalActiveTradesData,
  CanonicalJournalData,
  DataRequestState,
  DateTimeRange,
} from '../api/types';
import {
  getTickers,
  getSettings,
  updateSettings,
} from '../api/services';
import {
  ApiError,
  fetchCanonicalActiveTrades,
  fetchCanonicalJournal,
  fetchDashboardSummary,
  runBackendScan,
  fetchBackendSignals,
} from '../api/client';

export type PageName = 'dashboard' | 'scanner' | 'signals' | 'chart' | 'active_trades' | 'journal' | 'performance' | 'settings';

interface AppContextType {
  currentPage: PageName;
  navigate: (page: PageName) => void;

  // Legacy UI-only data retained for pages that are intentionally not wired in this phase.
  tickers: MarketTicker[];
  stats: DashboardStats | null;
  scannerData: ScannerResult[];
  signals: TradingSignal[];
  scannerResponse: CanonicalScanData | null;
  scannerState: DataRequestState;
  scannerError: string | null;
  signalsResponse: CanonicalSignalsData | null;
  signalsState: DataRequestState;
  signalsError: string | null;
  runScanner: (payload?: ScanRequestPayload) => Promise<void>;
  refreshSignals: () => Promise<void>;
  activeTrades: ActiveTrade[];
  journalEntries: JournalEntry[];
  settings: ControlCenterSettings | null;
  selectedSymbol: AssetTicker;
  setSelectedSymbol: (symbol: AssetTicker) => void;

  // Canonical FastAPI data for the three pages included in this phase.
  dashboardData: CanonicalDashboardData | null;
  dashboardState: DataRequestState;
  dashboardError: string | null;
  activeTradesData: CanonicalActiveTradesData | null;
  todayClosedTradesData: CanonicalJournalData | null;
  activeTradesState: DataRequestState;
  activeTradesError: string | null;
  journalData: CanonicalJournalData | null;
  journalState: DataRequestState;
  journalError: string | null;
  journalRange: DateTimeRange;
  refreshDashboard: () => Promise<void>;
  refreshActiveTrades: () => Promise<void>;
  refreshJournal: (range?: DateTimeRange) => Promise<void>;
  setJournalRange: (range: DateTimeRange) => void;

  executeSignal: (signalId: string, margin: number, leverage: number) => Promise<void>;
  submitOrder: (symbol: AssetTicker, direction: 'LONG' | 'SHORT', margin: number, leverage: number, stopLoss: number, takeProfit: number) => Promise<void>;
  closePosition: (tradeId: string) => Promise<void>;
  updateStopLossTakeProfit: (tradeId: string, stopLoss: number, takeProfit: number) => Promise<void>;
  addManualJournal: (entry: {
    symbol: string;
    direction: 'LONG' | 'SHORT';
    outcome: 'WIN' | 'LOSS' | 'BREAKEVEN';
    entryPrice: number;
    exitPrice: number;
    positionSizeUsd: number;
    netPnL: number;
    strategy: string;
    notes: string;
  }) => Promise<void>;
  saveSettings: (settings: ControlCenterSettings) => Promise<void>;
  triggerPriceTick: () => Promise<void>;
  toastMessage: { text: string; type: 'success' | 'error' | 'info' } | null;
  showToast: (text: string, type?: 'success' | 'error' | 'info') => void;
  clearToast: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
};

function getLocalDayRange(target = new Date()): DateTimeRange {
  const start = new Date(target);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

function requestStateForError(error: unknown): DataRequestState {
  if (!(error instanceof ApiError)) return 'backend_error';
  if (error.kind === 'unauthorized') return 'unauthorized';
  if (error.kind === 'network' || error.kind === 'timeout' || error.kind === 'configuration') return 'disconnected';
  return 'backend_error';
}

function requestMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Backend request failed.';
}

export const AppProvider = ({ children }: { children: ReactNode }) => {
  const [currentPage, setCurrentPage] = useState<PageName>('dashboard');
  const [tickers, setTickers] = useState<MarketTicker[]>([]);
  const [scannerData, setScannerData] = useState<ScannerResult[]>([]);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [scannerResponse, setScannerResponse] = useState<CanonicalScanData | null>(null);
  const [scannerState, setScannerState] = useState<DataRequestState>('idle');
  const [scannerError, setScannerError] = useState<string | null>(null);
  const [signalsResponse, setSignalsResponse] = useState<CanonicalSignalsData | null>(null);
  const [signalsState, setSignalsState] = useState<DataRequestState>('idle');
  const [signalsError, setSignalsError] = useState<string | null>(null);
  const [settings, setSettings] = useState<ControlCenterSettings | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<AssetTicker>('BTC/USDT');

  // These legacy values intentionally remain empty so no local trade/journal data can leak into wired pages.
  const [stats] = useState<DashboardStats | null>(null);
  const [activeTrades] = useState<ActiveTrade[]>([]);
  const [journalEntries] = useState<JournalEntry[]>([]);

  const [dashboardData, setDashboardData] = useState<CanonicalDashboardData | null>(null);
  const [dashboardState, setDashboardState] = useState<DataRequestState>('idle');
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const [activeTradesData, setActiveTradesData] = useState<CanonicalActiveTradesData | null>(null);
  const [todayClosedTradesData, setTodayClosedTradesData] = useState<CanonicalJournalData | null>(null);
  const [activeTradesState, setActiveTradesState] = useState<DataRequestState>('idle');
  const [activeTradesError, setActiveTradesError] = useState<string | null>(null);

  const [journalRange, setJournalRange] = useState<DateTimeRange>(() => getLocalDayRange());
  const [journalData, setJournalData] = useState<CanonicalJournalData | null>(null);
  const [journalState, setJournalState] = useState<DataRequestState>('idle');
  const [journalError, setJournalError] = useState<string | null>(null);

  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'info') => setToastMessage({ text, type });
  const clearToast = () => setToastMessage(null);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') as PageName;
      const validPages: PageName[] = ['dashboard', 'scanner', 'signals', 'chart', 'active_trades', 'journal', 'performance', 'settings'];
      if (validPages.includes(hash)) setCurrentPage(hash);
    };
    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (page: PageName) => {
    window.location.hash = `#${page}`;
    setCurrentPage(page);
  };

  const runScanner = async (payload: ScanRequestPayload = {}) => {
    setScannerState('loading');
    setScannerError(null);
    try {
      const data = await runBackendScan(payload);
      setScannerResponse(data);
      setScannerData(data.results);
      setScannerState(data.results.length === 0 ? 'empty' : 'ready');
      const signalsData = await fetchBackendSignals({ mode: data.mode });
      setSignalsResponse(signalsData);
      setSignals(signalsData.signals);
      setSignalsState(signalsData.signals.length === 0 ? 'empty' : 'ready');
    } catch (error) {
      setScannerResponse(null);
      setScannerData([]);
      setScannerState(requestStateForError(error));
      setScannerError(requestMessage(error));
    }
  };

  const refreshSignals = async () => {
    setSignalsState('loading');
    setSignalsError(null);
    try {
      const data = await fetchBackendSignals();
      setSignalsResponse(data);
      setSignals(data.signals);
      setSignalsState(data.signals.length === 0 ? 'empty' : 'ready');
    } catch (error) {
      setSignalsResponse(null);
      setSignals([]);
      setSignalsState(requestStateForError(error));
      setSignalsError(requestMessage(error));
    }
  };

  const refreshDashboard = async () => {
    const todayRange = getLocalDayRange();
    setDashboardState('loading');
    setDashboardError(null);
    try {
      const data = await fetchDashboardSummary(todayRange);
      setDashboardData(data);
      setDashboardState('ready');
    } catch (error) {
      setDashboardData(null);
      setDashboardState(requestStateForError(error));
      setDashboardError(requestMessage(error));
    }
  };

  const refreshActiveTrades = async () => {
    const todayRange = getLocalDayRange();
    setActiveTradesState('loading');
    setActiveTradesError(null);
    try {
      const [activeData, closedData] = await Promise.all([
        fetchCanonicalActiveTrades(todayRange),
        fetchCanonicalJournal(todayRange),
      ]);
      setActiveTradesData(activeData);
      setTodayClosedTradesData(closedData);
      const hasRecords = activeData.active_trades.length > 0 || closedData.closed_trades.length > 0;
      setActiveTradesState(hasRecords ? 'ready' : 'empty');
    } catch (error) {
      setActiveTradesData(null);
      setTodayClosedTradesData(null);
      setActiveTradesState(requestStateForError(error));
      setActiveTradesError(requestMessage(error));
    }
  };

  const refreshJournal = async (range = journalRange) => {
    setJournalState('loading');
    setJournalError(null);
    try {
      const data = await fetchCanonicalJournal(range);
      setJournalData(data);
      setJournalState(data.closed_trades.length === 0 ? 'empty' : 'ready');
    } catch (error) {
      setJournalData(null);
      setJournalState(requestStateForError(error));
      setJournalError(requestMessage(error));
    }
  };

  useEffect(() => {
    const loadLegacyUnwiredPages = async () => {
      try {
        const [fetchedTickers, fetchedSettings] = await Promise.all([
          getTickers(),
          getSettings(),
        ]);
        setTickers(fetchedTickers);
        setSettings(fetchedSettings);
      } catch (error) {
        console.error('Failed loading UI-only data for unwired pages', error);
      }
    };

    void loadLegacyUnwiredPages();
    void refreshSignals();
    void refreshDashboard();
    void refreshActiveTrades();
    void refreshJournal(journalRange);
  }, []);

  const triggerPriceTick = async () => {
    await Promise.all([refreshDashboard(), refreshActiveTrades(), refreshJournal(journalRange)]);
    showToast('Canonical backend data refreshed.', 'info');
  };

  const unavailableAction = async (label: string) => {
    showToast(`${label} is not connected in this data-wiring phase.`, 'info');
  };

  const executeSignal = async () => unavailableAction('Signal execution');
  const submitOrder = async () => unavailableAction('Direct order submission');
  const closePosition = async () => unavailableAction('Manual position close');
  const updateStopLossTakeProfit = async () => unavailableAction('SL/TP editing');
  const addManualJournal = async () => unavailableAction('Manual journal entry');

  const saveSettings = async (newSettings: ControlCenterSettings) => {
    try {
      await updateSettings(newSettings);
      setSettings(newSettings);
      showToast('Control center settings saved successfully', 'success');
    } catch {
      showToast('Failed to save settings', 'error');
    }
  };

  return (
    <AppContext.Provider
      value={{
        currentPage,
        navigate,
        tickers,
        stats,
        scannerData,
        signals,
        scannerResponse,
        scannerState,
        scannerError,
        signalsResponse,
        signalsState,
        signalsError,
        runScanner,
        refreshSignals,
        activeTrades,
        journalEntries,
        settings,
        selectedSymbol,
        setSelectedSymbol,
        dashboardData,
        dashboardState,
        dashboardError,
        activeTradesData,
        todayClosedTradesData,
        activeTradesState,
        activeTradesError,
        journalData,
        journalState,
        journalError,
        journalRange,
        refreshDashboard,
        refreshActiveTrades,
        refreshJournal,
        setJournalRange,
        executeSignal,
        submitOrder,
        closePosition,
        updateStopLossTakeProfit,
        addManualJournal,
        saveSettings,
        triggerPriceTick,
        toastMessage,
        showToast,
        clearToast,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
