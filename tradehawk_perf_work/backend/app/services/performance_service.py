from datetime import datetime
from app.core.enums import TradingMode
from app.schemas.performance import PerformanceData, PerformanceSummaries, PerformanceSummary
from app.schemas.trades import ClosedTradeRecord
from app.services.trade_service import TradeService

class PerformanceService:
    def __init__(self, trade_service:TradeService)->None:
        self._trade_service=trade_service

    def get_analysis(self,start_time:datetime|None=None,end_time:datetime|None=None,mode:str|None=None,strategy:str|None=None,status:str|None=None,exit_reason:str|None=None)->PerformanceData:
        data=self._trade_service.get_closed_trades(start_time,end_time).data
        trades=data.closed_trades
        if mode:
            trades=[t for t in trades if (t.mode.value if t.mode else 'unknown')==mode.lower()]
        if strategy:
            trades=[t for t in trades if getattr(t,'strategy',None)==strategy]
        if status:
            trades=[t for t in trades if t.status==status]
        if exit_reason:
            trades=[t for t in trades if t.close_reason==exit_reason]
        scalping=[t for t in trades if t.mode==TradingMode.SCALPING]
        intraday=[t for t in trades if t.mode==TradingMode.INTRADAY]
        unknown=[t for t in trades if t.mode is None]
        return PerformanceData(
            trades=trades,
            summaries=PerformanceSummaries(scalping=self._summary(scalping),intraday=self._summary(intraday),unknown=self._summary(unknown),combined=self._summary(trades)),
            strategies=sorted({getattr(t,'strategy',None) for t in data.closed_trades if getattr(t,'strategy',None)}),
            statuses=sorted({t.status for t in data.closed_trades if t.status}),
            exit_reasons=sorted({t.close_reason for t in data.closed_trades if t.close_reason}),
            range_start=data.range_start,range_end=data.range_end,
        )

    @staticmethod
    def _summary(trades:list[ClosedTradeRecord])->PerformanceSummary:
        wins=sum((t.result or '').lower()=='win' for t in trades)
        losses=sum((t.result or '').lower()=='loss' for t in trades)
        breakeven=sum((t.result or '').lower()=='breakeven' for t in trades)
        pnls=[float(t.realized_pnl) for t in trades if t.realized_pnl is not None]
        rrs=[float(t.risk_reward) for t in trades if t.risk_reward is not None]
        classified=wins+losses
        reasons=[(t.close_reason or '').lower() for t in trades]
        return PerformanceSummary(
            total_trades=len(trades),wins=wins,losses=losses,breakeven=breakeven,
            realized_pnl=round(sum(pnls),8) if len(pnls)==len(trades) and trades else None,
            average_realized_pnl=round(sum(pnls)/len(pnls),8) if pnls else None,
            win_rate=round(wins/classified*100,2) if classified else None,
            average_risk_reward=round(sum(rrs)/len(rrs),4) if len(rrs)==len(trades) and trades else None,
            best_trade=max(pnls) if pnls else None,worst_trade=min(pnls) if pnls else None,
            stop_loss_hit_count=sum(r=='stop_loss_hit' for r in reasons),
            take_profit_hit_count=sum(r=='take_profit_hit' for r in reasons),
            manual_close_count=sum(r=='manual_close' for r in reasons),
            emergency_stop_count=sum(r=='emergency_stop' for r in reasons),
        )
