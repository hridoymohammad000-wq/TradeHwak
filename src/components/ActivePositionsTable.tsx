import React from 'react';
import { ActiveTrade } from '../api/types';

interface ActivePositionsTableProps {
  activeTrades: ActiveTrade[];
  selectedSymbol: string;
  setSelectedSymbol: (symbol: any) => void;
  closePosition: (id: string) => Promise<void>;
}

export const ActivePositionsTable: React.FC<ActivePositionsTableProps> = ({
  activeTrades,
  selectedSymbol,
  setSelectedSymbol,
  closePosition
}) => {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-850 overflow-hidden shadow-lg">
      <div className="p-4 bg-slate-950/60 border-b border-slate-850 flex justify-between items-center flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold text-slate-300 uppercase">Active Portfolio Positions</span>
          <span className="text-[10px] text-emerald-400 bg-emerald-950/40 px-2.5 py-0.5 rounded border border-emerald-900/40 font-mono font-bold tracking-wider">LIVE STREAMS</span>
        </div>
        <div className="text-xs text-slate-400 font-mono">
          Total Exposure: <span className="text-white font-bold">${activeTrades.reduce((sum, t) => sum + t.sizeUsd, 0).toLocaleString()} USD</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[700px]">
          <thead>
            <tr className="border-b border-slate-850 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 bg-slate-950/35 select-none">
              <th className="py-3 px-4">Market Symbol</th>
              <th className="py-3 px-4 text-center">Direction</th>
              <th className="py-3 px-4 text-right">Margin / Exposure</th>
              <th className="py-3 px-4 text-right">Entry / Mark Price</th>
              <th className="py-3 px-4 text-right">Stop / Profit Targets</th>
              <th className="py-3 px-4 text-right">Floating PnL ($ / %)</th>
              <th className="py-3 px-4 text-center">Action Executions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-855">
            {activeTrades.length > 0 ? (
              activeTrades.map((pos) => {
                const isUp = pos.unrealizedPnL >= 0;
                const isCurrentSymbol = pos.symbol === selectedSymbol;
                return (
                  <tr 
                    key={pos.id} 
                    className={`hover:bg-slate-850/30 transition-colors ${isCurrentSymbol ? 'bg-slate-850/15' : ''}`}
                  >
                    <td className="py-3 px-4 font-mono font-bold text-sm text-white">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedSymbol(pos.symbol)}
                          className="hover:text-emerald-400 font-bold font-mono transition-colors text-left cursor-pointer"
                        >
                          {pos.symbol}
                        </button>
                        {isCurrentSymbol && (
                          <span className="text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-900/40 px-1 py-0.2 rounded font-extrabold uppercase select-none">VIEWING</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`text-[10px] font-mono font-extrabold px-2 py-0.5 rounded border uppercase tracking-wider select-none ${pos.direction === 'LONG' ? 'bg-emerald-950/30 text-emerald-400 border-emerald-900/30' : 'bg-rose-950/30 text-rose-400 border-rose-900/30'}`}>
                        {pos.direction} {pos.leverage}x
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-xs">
                      <div className="text-white font-bold">${pos.margin.toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500 font-medium">Exposure: ${pos.sizeUsd.toLocaleString()}</div>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-xs">
                      <div className="text-slate-300">${pos.entryPrice.toLocaleString(undefined, { minimumFractionDigits: pos.symbol.includes('XRP') || pos.symbol.includes('ADA') ? 4 : 2 })}</div>
                      <div className="text-[10px] text-emerald-400 font-bold">Mark: ${pos.currentPrice.toLocaleString(undefined, { minimumFractionDigits: pos.symbol.includes('XRP') || pos.symbol.includes('ADA') ? 4 : 2 })}</div>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-xs">
                      <div className="text-rose-400 font-semibold">SL: {pos.stopLoss > 0 ? `$${pos.stopLoss.toLocaleString()}` : 'None'}</div>
                      <div className="text-emerald-400 font-semibold">TP: {pos.takeProfit > 0 ? `$${pos.takeProfit.toLocaleString()}` : 'None'}</div>
                    </td>
                    <td className="py-3 px-4 text-right font-mono">
                      <div className={`text-xs font-extrabold ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isUp ? '+' : ''}${pos.unrealizedPnL.toFixed(2)}
                      </div>
                      <div className={`text-[10px] font-bold ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ({pos.unrealizedPnLPercent.toFixed(1)}%)
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => closePosition(pos.id)}
                        className="bg-rose-950/40 text-rose-400 hover:bg-rose-900 hover:text-white border border-rose-900/40 font-bold text-[10px] uppercase px-3 py-1.5 rounded transition-all cursor-pointer shadow-sm"
                      >
                        Market Close
                      </button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={7} className="py-12 px-4 text-center text-xs text-slate-400 bg-slate-900/40 border-dashed border-t border-slate-850 font-mono">
                  No active leveraged perpetual trades currently running. Use the Order Ticket to deploy liquidity.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
