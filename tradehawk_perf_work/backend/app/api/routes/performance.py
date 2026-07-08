from datetime import datetime
from fastapi import APIRouter, Query
from app.core.state import performance_service
from app.schemas.performance import PerformanceResponse
router=APIRouter(tags=['performance'])
@router.get('/performance-analysis',response_model=PerformanceResponse)
def performance_analysis(start_time:datetime|None=Query(None),end_time:datetime|None=Query(None),mode:str|None=Query(None),strategy:str|None=Query(None),status:str|None=Query(None),exit_reason:str|None=Query(None)):
    return PerformanceResponse(success=True,message='Performance analysis fetched successfully.',data=performance_service.get_analysis(start_time,end_time,mode,strategy,status,exit_reason))
