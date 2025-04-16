from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from app.services.historical_data_service import HistoricalDataService
from app.services.feature_data_service import FeatureDataService
from app.services.model_service import ModelService
from app.core.exceptions import BadRequestException
from app.exceptions.service_exceptions import ServiceUnavailableException

router = APIRouter(prefix="/predictions", tags=["predictions"])
logger = logging.getLogger(__name__)

# 服务实例
historical_data_service = HistoricalDataService()
feature_data_service = FeatureDataService()
model_service = ModelService()

# 初始化标志
_initialized = False

async def ensure_initialized():
    """确保服务已初始化"""
    global _initialized
    if not _initialized:
        await historical_data_service.initialize()
        await feature_data_service.initialize()
        await model_service.initialize()
        _initialized = True

# 请求/响应模型
class HistoricalDataRequest(BaseModel):
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)

class SyncDataRequest(BaseModel):
    symbol: str
    source_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    force_update: bool = False

class FeatureProcessRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    feature_types: List[str] = ["basic"]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    refresh: bool = False

class FeatureDataRequest(BaseModel):
    symbol: str
    timeframe: str = "1d"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    feature_version: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)

class TrainModelRequest(BaseModel):
    symbol: str
    model_name: str
    model_type: str
    timeframe: str = "1d"
    features: List[str]
    target: str
    target_horizon: int = 1
    train_start_date: Optional[str] = None
    train_end_date: Optional[str] = None
    hyperparameters: Dict[str, Any] = {}
    notes: Optional[str] = None

class PredictionRequest(BaseModel):
    model_id: str
    input_data: Optional[Dict[str, Any]] = None
    feature_id: Optional[str] = None
    latest: bool = False

class EvaluateModelRequest(BaseModel):
    model_id: str
    evaluation_period: Dict[str, str]
    comparison_models: Optional[List[str]] = None

class ModelStatusRequest(BaseModel):
    model_id: str
    is_active: bool

# API路由
@router.get("/health")
async def health_check():
    """健康检查接口"""
    await ensure_initialized()
    return {"status": "healthy", "initialized": _initialized}

# 历史数据接口
@router.get("/symbols")
async def get_symbols():
    """获取可用交易对列表"""
    await ensure_initialized()
    try:
        symbols = await historical_data_service.get_available_symbols()
        return {"symbols": symbols, "count": len(symbols)}
    except Exception as e:
        logger.error(f"获取交易对列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取交易对列表失败: {str(e)}")

@router.get("/symbols/{symbol}/coverage")
async def get_symbol_coverage(symbol: str = Path(..., description="交易对符号")):
    """获取交易对数据覆盖情况"""
    await ensure_initialized()
    try:
        coverage = await historical_data_service.get_data_coverage(symbol)
        return coverage
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取交易对 {symbol} 数据覆盖情况失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据覆盖情况失败: {str(e)}")

@router.post("/data/sync")
async def sync_historical_data(request: SyncDataRequest):
    """同步历史数据"""
    await ensure_initialized()
    try:
        result = await historical_data_service.sync_historical_data(
            symbol=request.symbol,
            source_id=request.source_id,
            start_date=request.start_date,
            end_date=request.end_date,
            force_update=request.force_update
        )
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"同步历史数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"同步历史数据失败: {str(e)}")

@router.post("/data/historical")
async def get_historical_data(request: HistoricalDataRequest):
    """获取历史数据"""
    await ensure_initialized()
    try:
        data = await historical_data_service.get_historical_data(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit
        )
        return {"data": data, "count": len(data)}
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取历史数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取历史数据失败: {str(e)}")

# 特征数据接口
@router.get("/features")
async def get_available_features():
    """获取可用特征列表"""
    await ensure_initialized()
    try:
        features = await feature_data_service.get_available_features()
        return features
    except Exception as e:
        logger.error(f"获取可用特征列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取可用特征列表失败: {str(e)}")

@router.post("/features/process")
async def process_features(request: FeatureProcessRequest):
    """处理特征数据"""
    await ensure_initialized()
    try:
        result = await feature_data_service.process_features(
            symbol=request.symbol,
            timeframe=request.timeframe,
            feature_types=request.feature_types,
            start_date=request.start_date,
            end_date=request.end_date,
            refresh=request.refresh
        )
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理特征数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理特征数据失败: {str(e)}")

@router.post("/features/data")
async def get_feature_data(request: FeatureDataRequest):
    """获取特征数据"""
    await ensure_initialized()
    try:
        data = await feature_data_service.get_feature_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            feature_version=request.feature_version,
            limit=request.limit
        )
        return {"data": data, "count": len(data)}
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取特征数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取特征数据失败: {str(e)}")

# 模型接口
@router.get("/models")
async def get_available_models(
    symbol: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """获取可用模型列表"""
    await ensure_initialized()
    try:
        models = await model_service.get_available_models(symbol, is_active)
        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.error(f"获取可用模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取可用模型列表失败: {str(e)}")

@router.post("/models/train")
async def train_model(request: TrainModelRequest):
    """训练新模型"""
    await ensure_initialized()
    try:
        result = await model_service.train_model(request.dict())
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"训练模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"训练模型失败: {str(e)}")

@router.post("/models/predict")
async def predict(request: PredictionRequest):
    """使用模型进行预测"""
    await ensure_initialized()
    try:
        result = await model_service.predict(request.dict())
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"预测失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")

@router.post("/models/evaluate")
async def evaluate_model(request: EvaluateModelRequest):
    """评估模型性能"""
    await ensure_initialized()
    try:
        result = await model_service.evaluate_model(
            model_id=request.model_id,
            evaluation_period=request.evaluation_period,
            comparison_models=request.comparison_models
        )
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"评估模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"评估模型失败: {str(e)}")

@router.post("/models/status")
async def update_model_status(request: ModelStatusRequest):
    """更新模型状态"""
    await ensure_initialized()
    try:
        result = await model_service.update_model_status(
            model_id=request.model_id,
            is_active=request.is_active
        )
        return result
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新模型状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新模型状态失败: {str(e)}") 