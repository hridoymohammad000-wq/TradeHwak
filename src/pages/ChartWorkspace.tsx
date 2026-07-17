import { LineChart as ChartIcon, Maximize2 } from "lucide-react";

export function ChartWorkspace() {
  return (
    <div className="space-y-6 h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/10 rounded-lg">
            <ChartIcon className="w-6 h-6 text-indigo-500" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-100">Chart Workspace</h2>
            <p className="text-sm text-slate-400">Integrated TradingView Advanced Charts</p>
          </div>
        </div>
        <button className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md transition-colors border border-slate-700">
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 bg-slate-900 border border-slate-800 rounded flex flex-col items-center justify-center relative overflow-hidden">
         <div className="absolute inset-0 bg-[linear-gradient(to_right,#27272a_1px,transparent_1px),linear-gradient(to_bottom,#27272a_1px,transparent_1px)] bg-[size:2rem_2rem] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] opacity-20" />
         
         <div className="relative z-10 text-center space-y-4">
           <ChartIcon className="w-12 h-12 text-slate-700 mx-auto" />
           <div className="text-[12px] font-semibold uppercase tracking-wider text-slate-500">TradingView Chart Area</div>
           <p className="text-slate-500 max-w-md mx-auto text-sm">
             Integrated TradingView Advanced Charts would render here.
           </p>
         </div>
      </div>
    </div>
  );
}
