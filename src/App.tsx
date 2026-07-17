/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Scanner } from "./pages/Scanner";
import { Signals } from "./pages/Signals";
import { ChartWorkspace } from "./pages/ChartWorkspace";
import { ActiveTrades } from "./pages/ActiveTrades";
import { TradeJournal } from "./pages/TradeJournal";
import { Performance } from "./pages/Performance";
import { ControlCenter } from "./pages/ControlCenter";
import { Settings } from "./pages/Settings";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<AuthGuard />}>
            <Route element={<Layout><Outlet /></Layout>}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/scanner" element={<Scanner />} />
              <Route path="/signals" element={<Signals />} />
              <Route path="/charts" element={<ChartWorkspace />} />
              <Route path="/trades" element={<ActiveTrades />} />
              <Route path="/journal" element={<TradeJournal />} />
              <Route path="/performance" element={<Performance />} />
              <Route path="/control" element={<ControlCenter />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

