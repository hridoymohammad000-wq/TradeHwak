import React, { FormEvent, useState } from 'react';
import { KeyRound, LoaderCircle, ShieldCheck, Zap } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getBackendStatusPresentation } from '../lib/backendStatus';

export default function Login() {
  const { authState, connectionStatus, errorMessage, login } = useAuth();
  const [accessToken, setAccessToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const status = getBackendStatusPresentation(connectionStatus);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login(accessToken);
    } finally {
      setAccessToken('');
      setSubmitting(false);
    }
  };

  const busy = submitting || authState === 'checking';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-5 font-sans selection:bg-emerald-500 selection:text-slate-950">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
        <div className="p-6 border-b border-slate-800 bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center shadow-sm shadow-emerald-500/20">
              <Zap className="h-6 w-6 text-slate-950 fill-slate-950" />
            </div>
            <div>
              <h1 className="text-lg font-extrabold tracking-wider text-white">TRADEHAWK</h1>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-mono font-bold">Private Terminal Access</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label htmlFor="access-token" className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-bold block mb-2">
              Access Token
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
              <input
                id="access-token"
                name="access-token"
                type="password"
                required
                autoComplete="off"
                value={accessToken}
                onChange={(event) => setAccessToken(event.target.value)}
                className="w-full bg-slate-950 text-sm font-mono text-white border border-slate-800 rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={busy || !accessToken.trim()}
            className="w-full flex items-center justify-center gap-2 bg-emerald-400 hover:bg-emerald-300 disabled:bg-slate-700 disabled:text-slate-400 text-slate-950 font-extrabold px-5 py-3 rounded-lg transition-colors uppercase text-xs tracking-wider"
          >
            {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            Enter
          </button>
        </form>

        <div className="px-6 pb-6">
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 flex gap-3 items-start">
            <span className={`mt-1 h-2.5 w-2.5 rounded-full shrink-0 ${status.dotClass}`} />
            <div>
              <p className={`text-xs font-bold ${status.textClass}`}>{status.label}</p>
              <p className="text-[11px] text-slate-500 mt-1">{errorMessage || status.detail}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
