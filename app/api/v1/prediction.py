from fastapi import APIRouter, Query, Path, Body, Depends, HTTPException
from typing import Dict, Any, List, Optional

from app.models.prediction import (
    PredictionRequest, 
    PredictionResponse, 
    PredictionType,
    TimeHorizon
)
from app.services.prediction_service import PredictionService
from app.core.exceptions import BadRequestException, ServiceUnavailableException

router = APIRouter()


@router.post("", response_model=PredictionResponse)
async def generate_prediction(
    prediction_request: PredictionRequest = Body(..., description="预测请求参数")
):
    """
    生成市场预测
    
    根据请求参数生成市场预测，包括价格预测、趋势预测、波动率预测等。
    """
    try:
        # 生成预测
        prediction_response = await PredictionService.generate_prediction(prediction_request)
        
        return prediction_response
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types", response_model=List[Dict[str, Any]])
async def get_prediction_types():
    """
    获取预测类型列表
    
    返回系统支持的所有预测类型信息。
    """
    prediction_types = []
    
    for pred_type in PredictionType:
        prediction_types.append({
            "type": pred_type.value,
            "name": pred_type.name,
            "description": get_prediction_type_description(pred_type)
        })
    
    return prediction_types


@router.get("/horizons", response_model=List[Dict[str, Any]])
async def get_time_horizons():
    """
    获取时间周期列表
    
    返回系统支持的所有预测时间周期信息。
    """
    time_horizons = []
    
    for horizon in TimeHorizon:
        time_horizons.append({
            "horizon": horizon.value,
            "name": horizon.name,
            "description": get_time_horizon_description(horizon)
        })
    
    return time_horizons


def get_prediction_type_description(pred_type: PredictionType) -> str:
    """获取预测类型的描述"""
    descriptions = {
        PredictionType.PRICE: "价格预测 - 预测未来一段时间内的价格走势",
        PredictionType.TREND: "趋势预测 - 预测未来价格变动的方向和幅度",
        PredictionType.VOLATILITY: "波动率预测 - 预测未来价格的波动程度",
        PredictionType.SIGNAL: "交易信号 - 提供买入、卖出或观望的交易建议",
        PredictionType.SENTIMENT: "情绪分析 - 分析市场参与者对资产的情绪",
        PredictionType.RISK: "风险评估 - 评估投资资产的风险水平"
    }
    
    return descriptions.get(pred_type, "未知预测类型")


def get_time_horizon_description(horizon: TimeHorizon) -> str:
    """获取时间周期的描述"""
    descriptions = {
        TimeHorizon.SHORT_TERM: "短期 - 预测范围为几小时到数天",
        TimeHorizon.MEDIUM_TERM: "中期 - 预测范围为一周到数周",
        TimeHorizon.LONG_TERM: "长期 - 预测范围为数周到数月"
    }
    
    return descriptions.get(horizon, "未知时间周期") 