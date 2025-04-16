import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.services.data_processing_service import DataProcessingService
from app.services.qlib_integration_service import QlibIntegrationService, QLIB_AVAILABLE
from app.models.market_data import TimeFrame, DataSourceType

router = APIRouter(prefix="/data-analysis", tags=["数据分析"])

logger = logging.getLogger(__name__)

@router.get("/prepare-data/{symbol}")
async def prepare_data(
    symbol: str = Path(..., description="交易对符号，如 BTC/USDT"),
    days: int = Query(30, description="历史数据天数"),
    exchange_id: str = Query("binance", description="交易所ID"),
    timeframe: str = Query("1d", description="时间周期"),
    include_on_chain: bool = Query(True, description="是否包含链上数据"),
    include_sentiment: bool = Query(True, description="是否包含情绪数据")
):
    """
    准备并处理交易对数据，返回多源数据结构
    """
    try:
        # 获取多数据源数据
        data_dict = await DataProcessingService.prepare_multi_source_data(
            symbol=symbol,
            days=days,
            include_on_chain=include_on_chain,
            include_sentiment=include_sentiment
        )
        
        # 将数据转换为可JSON序列化格式
        result = {}
        for source, df in data_dict.items():
            if not df.empty:
                # 转换时间索引为ISO格式字符串
                df_copy = df.copy()
                df_copy.index = df_copy.index.strftime('%Y-%m-%d %H:%M:%S')
                
                # 转换为字典格式
                result[source] = df_copy.to_dict(orient='index')
        
        return {
            "symbol": symbol,
            "data_sources": list(result.keys()),
            "days": days,
            "generated_at": datetime.now().isoformat(),
            "data": result
        }
    
    except BadRequestException as e:
        logger.error(f"准备数据失败 - 无效请求: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        logger.error(f"准备数据失败 - 服务不可用: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"准备数据失败 - 未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理数据时发生错误: {str(e)}")

@router.get("/qlib-format/{symbol}")
async def get_qlib_format_data(
    symbol: str = Path(..., description="交易对符号，如 BTC/USDT"),
    days: int = Query(90, description="历史数据天数"),
    target_column: str = Query("close", description="目标列"),
    features: Optional[List[str]] = Query(None, description="特征列列表")
):
    """
    准备符合qlib格式的数据，用于模型训练和预测
    """
    try:
        # 准备qlib格式数据
        data_df = await DataProcessingService.prepare_qlib_format_data(
            symbol=symbol,
            days=days,
            target_column=target_column,
            feature_columns=features
        )
        
        if data_df.empty:
            raise BadRequestException(f"无法获取{symbol}的数据")
        
        # 转换为可JSON序列化格式
        df_copy = data_df.copy()
        df_copy.index = df_copy.index.strftime('%Y-%m-%d %H:%M:%S')
        data_dict = df_copy.to_dict(orient='index')
        
        return {
            "symbol": symbol,
            "days": days,
            "target_column": target_column,
            "features": list(data_df.columns),
            "data_points": len(data_df),
            "generated_at": datetime.now().isoformat(),
            "data": data_dict
        }
    
    except BadRequestException as e:
        logger.error(f"准备qlib格式数据失败 - 无效请求: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        logger.error(f"准备qlib格式数据失败 - 服务不可用: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"准备qlib格式数据失败 - 未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理数据时发生错误: {str(e)}")

@router.get("/qlib-predict/{symbol}")
async def predict_with_qlib(
    symbol: str = Path(..., description="交易对符号，如 BTC/USDT"),
    prediction_horizon: int = Query(1, description="预测周期（天）"),
    historical_days: int = Query(90, description="历史数据天数"),
    model_type: str = Query("lstm", description="模型类型: lstm, gru, lgb")
):
    """
    使用qlib模型进行预测
    """
    if not QLIB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Qlib库不可用，无法进行预测")
    
    try:
        # 使用qlib进行预测
        prediction = await QlibIntegrationService.predict_with_qlib(
            symbol=symbol,
            prediction_horizon=prediction_horizon,
            historical_days=historical_days,
            model_type=model_type
        )
        
        return {
            "success": True,
            "symbol": symbol,
            "prediction_horizon": prediction_horizon,
            "model_type": model_type,
            "generated_at": datetime.now().isoformat(),
            "prediction": prediction
        }
    
    except BadRequestException as e:
        logger.error(f"qlib预测失败 - 无效请求: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        logger.error(f"qlib预测失败 - 服务不可用: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"qlib预测失败 - 未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预测时发生错误: {str(e)}")

@router.get("/technical-indicators/{symbol}")
async def get_technical_indicators(
    symbol: str = Path(..., description="交易对符号，如 BTC/USDT"),
    days: int = Query(30, description="历史数据天数"),
    exchange_id: str = Query("binance", description="交易所ID"),
    timeframe: str = Query("1d", description="时间周期")
):
    """
    获取交易对的技术指标
    """
    try:
        # 准备OHLCV数据
        data_df = await DataProcessingService.prepare_ohlcv_data(
            symbol=symbol,
            exchange_id=exchange_id,
            timeframe=timeframe,
            days=days
        )
        
        if data_df.empty:
            raise BadRequestException(f"无法获取{symbol}的数据")
        
        # 提取关键技术指标
        indicators = {
            "moving_averages": {
                "ma5": float(data_df['moving_avg_5'].iloc[-1]) if 'moving_avg_5' in data_df.columns else None,
                "ma10": float(data_df['moving_avg_10'].iloc[-1]) if 'moving_avg_10' in data_df.columns else None,
                "ma20": float(data_df['moving_avg_20'].iloc[-1]) if 'moving_avg_20' in data_df.columns else None
            },
            "volatility": {
                "volatility_5": float(data_df['volatility_5'].iloc[-1]) if 'volatility_5' in data_df.columns else None,
                "volatility_10": float(data_df['volatility_10'].iloc[-1]) if 'volatility_10' in data_df.columns else None,
                "volatility_20": float(data_df['volatility_20'].iloc[-1]) if 'volatility_20' in data_df.columns else None
            },
            "oscillators": {
                "rsi": float(data_df['rsi'].iloc[-1]) if 'rsi' in data_df.columns else None,
                "macd": float(data_df['macd'].iloc[-1]) if 'macd' in data_df.columns else None,
                "macd_signal": float(data_df['macd_signal'].iloc[-1]) if 'macd_signal' in data_df.columns else None,
                "macd_hist": float(data_df['macd_hist'].iloc[-1]) if 'macd_hist' in data_df.columns else None
            },
            "bands": {
                "bollinger_upper": float(data_df['bollinger_upper'].iloc[-1]) if 'bollinger_upper' in data_df.columns else None,
                "bollinger_lower": float(data_df['bollinger_lower'].iloc[-1]) if 'bollinger_lower' in data_df.columns else None
            },
            "price": {
                "current": float(data_df['close'].iloc[-1]) if 'close' in data_df.columns else None,
                "change_pct": float(data_df['close_pct_change'].iloc[-1]) if 'close_pct_change' in data_df.columns else None
            }
        }
        
        # 生成简单的技术分析信号
        signals = {}
        
        # 移动平均线信号
        ma5 = indicators["moving_averages"]["ma5"]
        ma10 = indicators["moving_averages"]["ma10"]
        ma20 = indicators["moving_averages"]["ma20"]
        current_price = indicators["price"]["current"]
        
        if ma5 and ma10 and ma20 and current_price:
            if current_price > ma5 > ma10 > ma20:
                signals["ma_trend"] = "强烈上升"
            elif current_price > ma5 and ma5 > ma10:
                signals["ma_trend"] = "上升"
            elif current_price < ma5 < ma10 < ma20:
                signals["ma_trend"] = "强烈下降"
            elif current_price < ma5 and ma5 < ma10:
                signals["ma_trend"] = "下降"
            else:
                signals["ma_trend"] = "横盘"
        
        # RSI信号
        rsi = indicators["oscillators"]["rsi"]
        if rsi:
            if rsi > 70:
                signals["rsi"] = "超买"
            elif rsi < 30:
                signals["rsi"] = "超卖"
            else:
                signals["rsi"] = "中性"
        
        # MACD信号
        macd = indicators["oscillators"]["macd"]
        macd_signal = indicators["oscillators"]["macd_signal"]
        if macd and macd_signal:
            if macd > macd_signal and macd > 0:
                signals["macd"] = "看涨"
            elif macd < macd_signal and macd < 0:
                signals["macd"] = "看跌"
            else:
                signals["macd"] = "中性"
        
        # 布林带信号
        upper = indicators["bands"]["bollinger_upper"]
        lower = indicators["bands"]["bollinger_lower"]
        if upper and lower and current_price:
            if current_price > upper:
                signals["bollinger"] = "超买区间"
            elif current_price < lower:
                signals["bollinger"] = "超卖区间"
            else:
                width = (upper - lower) / current_price * 100  # 带宽百分比
                if width < 5:
                    signals["bollinger"] = "收窄 (可能即将大幅波动)"
                else:
                    signals["bollinger"] = "正常范围"
        
        return {
            "symbol": symbol,
            "exchange": exchange_id,
            "timeframe": timeframe,
            "generated_at": datetime.now().isoformat(),
            "indicators": indicators,
            "signals": signals
        }
        
    except BadRequestException as e:
        logger.error(f"获取技术指标失败 - 无效请求: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        logger.error(f"获取技术指标失败 - 服务不可用: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"获取技术指标失败 - 未知错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理数据时发生错误: {str(e)}") 