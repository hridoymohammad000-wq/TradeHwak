import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

export function Login() {
  const [tokenInput, setTokenInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const accessToken = tokenInput.trim();
    if (!accessToken) return;

    setError(null);
    setLoading(true);
    try {
      await login(accessToken);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Login failed. Check the backend URL and access token.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded p-8 shadow-2xl flex flex-col items-center">
        <div className="flex flex-col items-center mb-8 w-full">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-6 h-6 bg-emerald-500 rounded-sm"></div>
            <div className="font-bold text-sm tracking-wider uppercase text-slate-100">TradeHawk Intraday</div>
          </div>
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500 mt-2">
            <Lock className="w-3 h-3" />
            Backend Cookie Session
          </div>
        </div>

        <form onSubmit={handleSubmit} className="w-full space-y-4">
          <div>
            <label htmlFor="token" className="block text-[10px] uppercase tracking-wider font-medium text-slate-500 mb-2 text-center">
              Enter Access Token
            </label>
            <input
              type="password"
              id="token"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-3 text-slate-200 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all font-mono text-center text-sm placeholder:text-slate-700"
              placeholder="••••••••••••"
              disabled={loading}
              required
            />
          </div>

          {error && (
            <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300 text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full p-3 bg-emerald-500 text-slate-950 text-[12px] font-bold uppercase tracking-wider rounded transition-opacity hover:opacity-90 disabled:opacity-50 mt-4"
          >
            {loading ? "Connecting..." : "Connect"}
          </button>
        </form>
      </div>
    </div>
  );
}
