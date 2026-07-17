import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function AuthGuard() {
  const { token, checkingSession } = useAuth();

  if (checkingSession) {
    return (
      <div className="min-h-screen bg-[#0A0D14] text-slate-300 flex items-center justify-center text-sm">
        Checking TradeHawk session...
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
