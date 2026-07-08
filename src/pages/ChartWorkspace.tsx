import React,{useEffect,useRef,useState} from 'react';
import {createChart,ColorType,CrosshairMode,CandlestickSeries,HistogramSeries,IChartApi,ISeriesApi} from 'lightweight-charts';
import {LineChart,RefreshCw} from 'lucide-react';
import {fetchChartContext,ApiError} from '../api/client';
import {AssetTicker,BackendTimeframe,ChartContextData,TradingMode} from '../api/types';
import {useApp} from '../context/AppContext';

const symbols:AssetTicker[]=['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','ADA/USDT','AVAX/USDT','LINK/USDT'];
const frames:BackendTimeframe[]=['M1','M5','M15','H1'];
export default function ChartWorkspace(){
 const {selectedSymbol,setSelectedSymbol}=useApp(); const [mode,setMode]=useState<TradingMode>('scalping'); const [timeframe,setTimeframe]=useState<BackendTimeframe>('M15');
 const [data,setData]=useState<ChartContextData|null>(null); const [state,setState]=useState<'loading'|'ready'|'empty'|'unauthorized'|'disconnected'|'timeout'|'error'>('loading'); const [error,setError]=useState('');
 const container=useRef<HTMLDivElement>(null); const chart=useRef<IChartApi|null>(null); const candles=useRef<ISeriesApi<'Candlestick'>|null>(null); const volume=useRef<ISeriesApi<'Histogram'>|null>(null);
 const load=async()=>{setState('loading');setError('');try{const result=await fetchChartContext(selectedSymbol.replace('/',''),mode,timeframe);setData(result);setState(result.candles.length?'ready':'empty')}catch(e){setData(null);setError(e instanceof Error?e.message:'Chart request failed');if(e instanceof ApiError){setState(e.kind==='unauthorized'?'unauthorized':e.kind==='timeout'?'timeout':e.kind==='network'||e.kind==='configuration'?'disconnected':'error')}else setState('error')}};
 useEffect(()=>{void load()},[selectedSymbol,mode,timeframe]);
 useEffect(()=>{if(!container.current)return; const c=createChart(container.current,{layout:{background:{type:ColorType.Solid,color:'#0B0F19'},textColor:'#94a3b8'},grid:{vertLines:{color:'rgba(30,41,59,.5)'},horzLines:{color:'rgba(30,41,59,.5)'}},crosshair:{mode:CrosshairMode.Normal},timeScale:{timeVisible:true},autoSize:true}); chart.current=c; candles.current=c.addSeries(CandlestickSeries,{}); volume.current=c.addSeries(HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:''}); return()=>{c.remove();chart.current=null}},[]);
 useEffect(()=>{if(!data||!candles.current||!volume.current)return; const rows=data.candles.map(x=>({time:Math.floor(x.open_time/1000) as any,open:x.open,high:x.high,low:x.low,close:x.close})); candles.current.setData(rows); volume.current.setData(data.candles.map(x=>({time:Math.floor(x.open_time/1000) as any,value:x.volume??0}))); chart.current?.timeScale().fitContent()},[data]);
 const statusText={loading:'Loading real chart data…',empty:'No closed candles returned.',unauthorized:'Unauthorized session.',disconnected:'Backend disconnected.',timeout:'Chart request timed out.',error:'Backend error.',ready:''}[state];
 return <div className="space-y-6">
  <div className="bg-slate-900 p-5 rounded-xl border border-slate-850 flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-xl font-bold text-white flex items-center gap-2"><LineChart className="h-5 w-5 text-emerald-400"/>Chart Workspace</h1><p className="text-xs text-slate-400 mt-1">Real closed candles from the canonical backend and Bybit Demo market data.</p></div><button onClick={()=>void load()} className="px-3 py-2 rounded-lg bg-slate-800 text-xs font-bold text-white flex gap-2"><RefreshCw className="h-4 w-4"/>Refresh</button></div>
  <div className="bg-slate-900 rounded-xl border border-slate-850 overflow-hidden"><div className="p-3 border-b border-slate-800 flex flex-wrap gap-3">
   <select value={selectedSymbol} onChange={e=>setSelectedSymbol(e.target.value as AssetTicker)} className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white">{symbols.map(x=><option key={x}>{x}</option>)}</select>
   <select value={mode} onChange={e=>setMode(e.target.value as TradingMode)} className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"><option value="scalping">Scalping</option><option value="intraday">Intraday</option></select>
   <select value={timeframe} onChange={e=>setTimeframe(e.target.value as BackendTimeframe)} className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white">{frames.map(x=><option key={x}>{x}</option>)}</select>
   <span className="ml-auto text-xs text-slate-400">Last: <b className="text-white">{data?.last_price??'N/A'}</b></span></div>
   {state!=='ready'&&<div className="h-[520px] flex items-center justify-center text-sm text-slate-400">{statusText}{error&&<span className="ml-2 text-rose-400">{error}</span>}</div>}
   <div ref={container} className={state==='ready'?'h-[520px]':'hidden'}/></div>
  <div className="grid grid-cols-2 md:grid-cols-6 gap-3">{[['EMA20',data?.indicator_context.ema20],['EMA50',data?.indicator_context.ema50],['EMA200',data?.indicator_context.ema200],['RSI',data?.indicator_context.rsi],['MACD',data?.indicator_context.macd],['Signal',data?.indicator_context.macd_signal]].map(([k,v])=><div key={String(k)} className="bg-slate-900 border border-slate-850 rounded-lg p-3"><div className="text-[10px] uppercase text-slate-500">{k}</div><div className="text-sm font-bold text-white mt-1">{v??'N/A'}</div></div>)}</div>
 </div>
}
