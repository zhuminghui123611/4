import logging
import uuid
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.prediction import (
    PredictionType,
    TimeHorizon,
    TrendDirection,
    SignalStrength,
    SentimentLevel,
    RiskLevel,
    PredictionRequest,
    PredictionResponse,
    PricePrediction,
    TrendPrediction,
    VolatilityPrediction,
    SignalPrediction,
    SentimentPrediction,
    RiskPrediction,
    PricePoint,
)
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.core.config import settings
from app.services.exchange_service import ExchangeService
from app.db.redis import RedisClient
from app.db.mongodb import MongoDB, COLLECTION_PREDICTIONS
from app.services.data_processing_service import DataProcessingService
from app.services.qlib_integration_service import QlibIntegrationService, QLIB_AVAILABLE

logger = logging.getLogger(__name__)

class PredictionService:
    """预测服务，整合qlib模型进行市场预测"""
    
    # 模型版本
    MODEL_VERSION = "1.1.0"
    
    # 预测类型映射到处理函数
    PREDICTION_HANDLERS = {
        PredictionType.PRICE: "_predict_price",
        PredictionType.TREND: "_predict_trend",
        PredictionType.VOLATILITY: "_predict_volatility",
        PredictionType.SIGNAL: "_predict_signal",
        PredictionType.SENTIMENT: "_predict_sentiment",
        PredictionType.RISK: "_predict_risk",
    }
    
    # 时间周期映射
    TIME_HORIZON_DAYS = {
        TimeHorizon.SHORT_TERM: 1,  # 1天
        TimeHorizon.MEDIUM_TERM: 7,  # 7天
        TimeHorizon.LONG_TERM: 30,  # 30天
    }
    
    @classmethod
    async def generate_prediction(cls, request: PredictionRequest) -> PredictionResponse:
        """
        生成预测
        
        Args:
            request: 预测请求
            
        Returns:
            PredictionResponse: 预测响应
            
        Raises:
            BadRequestException: 如果请求参数无效
            ServiceUnavailableException: 如果预测服务不可用
        """
        if not QLIB_AVAILABLE and request.prediction_type not in [PredictionType.SENTIMENT, PredictionType.SIGNAL]:
            logger.warning(f"Qlib库不可用，但将尝试使用备用方法生成{request.prediction_type}预测")
        
        # 生成唯一请求ID
        request_id = str(uuid.uuid4())
        
        # 检查缓存
        cache_key = f"prediction:{request.prediction_type}:{request.symbol}:{request.time_horizon}"
        cached_data = RedisClient.get(cache_key)
        
        if cached_data:
            # 使用缓存数据，但添加新的请求ID
            prediction_data = json.loads(cached_data)
            prediction_data["request_id"] = request_id
            prediction_data["timestamp"] = int(datetime.now().timestamp() * 1000)
            
            # 保存请求记录到数据库
            await cls._save_prediction_to_db(prediction_data, True)
            
            return PredictionResponse(**prediction_data)
        
        # 获取处理函数
        handler_name = cls.PREDICTION_HANDLERS.get(request.prediction_type)
        if not handler_name:
            raise BadRequestException(f"不支持的预测类型: {request.prediction_type}")
        
        # 获取多数据源数据
        try:
            # 默认使用binance交易所数据，可以根据实际情况修改
            exchange_id = "binance"
            
            # 为股票和其他传统资产修改exchange_id
            if '.' in request.symbol:  # 例如"AAPL.US"或"000001.SZ"
                exchange_id = "stock"
            
            # 获取多数据源数据
            data_dict = await DataProcessingService.prepare_multi_source_data(
                symbol=request.symbol,
                days=request.historical_data_days or 90,
                include_on_chain=True,
                include_sentiment=True
            )
            
            # 获取基本OHLCV数据
            historical_data = data_dict.get('ohlcv')
            if historical_data.empty:
                raise BadRequestException(f"无法获取{request.symbol}的历史数据")
            
            # 添加额外数据源信息到请求参数
            request.extra_data = {
                "data_sources": list(data_dict.keys()),
                "on_chain_available": 'on_chain' in data_dict and not data_dict['on_chain'].empty,
                "sentiment_available": 'sentiment' in data_dict and not data_dict['sentiment'].empty,
                "exchange_reserve_available": 'exchange_reserve' in data_dict and not data_dict['exchange_reserve'].empty
            }
            
            # 调用处理函数
            handler = getattr(cls, handler_name)
            prediction_data = await handler(request, historical_data, data_dict)
            
            # 构建完整响应
            response_data = {
                "request_id": request_id,
                "prediction_type": request.prediction_type,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "generated_at": datetime.now(),
                "symbol": request.symbol,
                "time_horizon": request.time_horizon,
                "data": prediction_data,
                "success": True,
                "data_sources": request.extra_data["data_sources"] if hasattr(request, "extra_data") else ["ohlcv"]
            }
            
            # 缓存预测结果
            # 短期预测缓存10分钟，中期预测缓存1小时，长期预测缓存6小时
            cache_time = 600
            if request.time_horizon == TimeHorizon.MEDIUM_TERM:
                cache_time = 3600
            elif request.time_horizon == TimeHorizon.LONG_TERM:
                cache_time = 21600
                
            RedisClient.set(cache_key, json.dumps(response_data), ex=cache_time)
            
            # 保存预测到数据库
            await cls._save_prediction_to_db(response_data, False)
            
            return PredictionResponse(**response_data)
        except Exception as e:
            logger.error(f"生成预测时发生错误: {str(e)}")
            raise ServiceUnavailableException(f"生成预测失败: {str(e)}")
    
    @classmethod
    async def _predict_price(
        cls, 
        request: PredictionRequest, 
        historical_data: pd.DataFrame,
        data_dict: Dict[str, pd.DataFrame] = None
    ) -> PricePrediction:
        """
        预测价格
        
        Args:
            request: 预测请求
            historical_data: 历史价格数据
            data_dict: 多数据源数据
            
        Returns:
            PricePrediction: 价格预测结果
        """
        if historical_data.empty:
            raise BadRequestException("历史数据不足，无法生成预测")
        
        # 获取最新价格
        current_price = historical_data.iloc[-1]['close']
        
        # 获取时间周期对应的天数
        horizon_days = cls.TIME_HORIZON_DAYS[request.time_horizon]
        
        # 生成预测时间点
        prediction_times = []
        now = datetime.now()
        
        if request.time_horizon == TimeHorizon.SHORT_TERM:
            # 短期预测按小时粒度
            for i in range(1, 25):  # 24小时
                prediction_times.append(now + timedelta(hours=i))
        elif request.time_horizon == TimeHorizon.MEDIUM_TERM:
            # 中期预测按天粒度
            for i in range(1, 8):  # 7天
                prediction_times.append(now + timedelta(days=i))
        else:
            # 长期预测，每3天一个点
            for i in range(3, 31, 3):
                prediction_times.append(now + timedelta(days=i))
        
        # 预测价格
        predicted_prices = []
        
        # 优先使用qlib进行预测
        if QLIB_AVAILABLE:
            try:
                # 调用qlib模型进行预测
                qlib_result = await QlibIntegrationService.predict_with_qlib(
                    symbol=request.symbol,
                    prediction_horizon=horizon_days,
                    historical_days=request.historical_data_days or 90,
                    model_type="lstm"  # 可以根据时间周期选择不同模型
                )
                
                # 使用qlib预测结果生成价格点
                base_price = current_price
                qlib_predicted_change = qlib_result["predicted_change"] / 100  # 转为比例
                
                # 短期预测使用线性变化，长期预测使用复合增长
                for i, predict_time in enumerate(prediction_times):
                    time_ratio = (i + 1) / len(prediction_times)
                    if request.time_horizon == TimeHorizon.SHORT_TERM:
                        # 线性变化
                        price_change = qlib_predicted_change * time_ratio
                    else:
                        # 复合变化
                        price_change = (1 + qlib_predicted_change) ** time_ratio - 1
                    
                    predicted_price = base_price * (1 + price_change)
                    
                    # 计算置信度 (随时间降低)
                    confidence = qlib_result["confidence"] * (1 - time_ratio * 0.3)
                    
                    predicted_prices.append(PricePoint(
                        timestamp=int(predict_time.timestamp() * 1000),
                        datetime=predict_time,
                        price=Decimal(str(round(predicted_price, 8))),
                        confidence=round(confidence, 2)
                    ))
                
                # 计算影响因素
                factors = {
                    "历史价格趋势": 0.25,
                    "技术指标": 0.25
                }
                
                # 加入额外数据源的影响因素
                if data_dict:
                    if 'on_chain' in data_dict and not data_dict['on_chain'].empty:
                        factors["链上数据"] = 0.2
                    if 'sentiment' in data_dict and not data_dict['sentiment'].empty:
                        factors["市场情绪"] = 0.15
                    if 'exchange_reserve' in data_dict and not data_dict['exchange_reserve'].empty:
                        factors["交易所储备"] = 0.15
                
                # 确保因素权重总和为1
                total_weight = sum(factors.values())
                factors = {k: round(v / total_weight, 2) for k, v in factors.items()}
                
                # 构建预测结果
                return PricePrediction(
                    symbol=request.symbol,
                    current_price=Decimal(str(current_price)),
                    predicted_prices=predicted_prices,
                    time_horizon=request.time_horizon,
                    confidence=qlib_result["confidence"],
                    model_version=f"{cls.MODEL_VERSION}-qlib",
                    factors=factors if request.include_factors else None
                )
                
            except Exception as e:
                logger.warning(f"使用qlib预测价格失败，将使用备用方法: {str(e)}")
                # 继续使用备用方法
        
        # 备用方法：如果qlib不可用或失败，使用传统方法
        
        # 计算历史波动率
        volatility = historical_data['close'].pct_change().std() * 100
        
        # 考虑多数据源
        sentiment_factor = 0
        if data_dict and 'sentiment' in data_dict and not data_dict['sentiment'].empty:
            # 获取最新情绪分数
            sentiment_df = data_dict['sentiment']
            if 'sentiment_score' in sentiment_df.columns:
                sentiment_factor = sentiment_df['sentiment_score'].iloc[-1] * 0.01  # 调整影响幅度
        
        for i, predict_time in enumerate(prediction_times):
            # 计算时间因子
            time_factor = (i + 1) / len(prediction_times)
            
            # 调整波动率随时间增加
            adjusted_volatility = volatility * (1 + time_factor * 0.5)
            
            # 生成随机价格变动，加入轻微的正向偏差和情绪因子
            price_change = np.random.normal(0.002 + sentiment_factor, adjusted_volatility / 100, 1)[0]
            
            # 累积价格变动
            if i == 0:
                base_price = current_price
            else:
                base_price = float(predicted_prices[-1].price)
            
            predicted_price = base_price * (1 + price_change)
            
            # 计算置信度 (随时间降低)
            confidence = max(0.3, 0.85 - time_factor * 0.5)
            
            predicted_prices.append(PricePoint(
                timestamp=int(predict_time.timestamp() * 1000),
                datetime=predict_time,
                price=Decimal(str(round(predicted_price, 8))),
                confidence=round(confidence, 2)
            ))
        
        # 计算影响因素
        factors = {
            "历史价格趋势": 0.35,
            "交易量变化": 0.25,
            "市场情绪": 0.15,
            "相关资产相关性": 0.15,
            "宏观经济指标": 0.10
        }
        
        # 构建预测结果
        return PricePrediction(
            symbol=request.symbol,
            current_price=Decimal(str(current_price)),
            predicted_prices=predicted_prices,
            time_horizon=request.time_horizon,
            confidence=0.7,  # 整体置信度
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _predict_trend(
        cls, 
        request: PredictionRequest, 
        historical_data: pd.DataFrame,
        data_dict: Dict[str, pd.DataFrame] = None
    ) -> TrendPrediction:
        """
        预测趋势
        
        Args:
            request: 预测请求
            historical_data: 历史数据
            data_dict: 多数据源数据
            
        Returns:
            TrendPrediction: 趋势预测结果
        """
        if historical_data.empty:
            raise BadRequestException("历史数据不足，无法生成预测")
        
        # 获取最新价格
        current_price = historical_data.iloc[-1]['close']
        
        # 分析历史趋势
        if len(historical_data) >= 7:
            # 计算多个移动平均线
            historical_data['ma7'] = historical_data['close'].rolling(window=7).mean()
            historical_data['ma14'] = historical_data['close'].rolling(window=14).mean()
            historical_data['ma30'] = historical_data['close'].rolling(window=30).mean()
            
            # 计算最近的趋势方向
            recent_trend_7d = historical_data['ma7'].iloc[-1] - historical_data['ma7'].iloc[-7] if len(historical_data) > 7 else 0
            recent_trend_14d = historical_data['ma14'].iloc[-1] - historical_data['ma14'].iloc[-7] if len(historical_data) > 14 else 0
            
            # 考虑情绪因素
            sentiment_factor = 0
            if data_dict and 'sentiment' in data_dict and not data_dict['sentiment'].empty:
                sentiment_df = data_dict['sentiment']
                if 'sentiment_score' in sentiment_df.columns:
                    sentiment_factor = sentiment_df['sentiment_score'].iloc[-1] * 0.5  # 调整影响幅度
            
            # 综合考虑，偏重于短期趋势
            trend_value = recent_trend_7d * 0.7 + recent_trend_14d * 0.3 + sentiment_factor
            
            if trend_value > 0:
                trend = TrendDirection.UP
            elif trend_value < 0:
                trend = TrendDirection.DOWN
            else:
                trend = TrendDirection.SIDEWAYS
        else:
            # 数据不足，默认为横盘
            trend = TrendDirection.SIDEWAYS
        
        # 计算预测幅度
        # 如果qlib可用，尝试使用qlib预测
        if QLIB_AVAILABLE:
            try:
                # 调用qlib模型进行预测
                qlib_result = await QlibIntegrationService.predict_with_qlib(
                    symbol=request.symbol,
                    prediction_horizon=cls.TIME_HORIZON_DAYS[request.time_horizon],
                    historical_days=request.historical_data_days or 90
                )
                
                # 使用预测的价格变化作为幅度
                magnitude = qlib_result["predicted_change"]
                confidence = qlib_result["confidence"]
                
                if magnitude > 0:
                    trend = TrendDirection.UP
                elif magnitude < 0:
                    trend = TrendDirection.DOWN
                else:
                    trend = TrendDirection.SIDEWAYS
                
            except Exception as e:
                logger.warning(f"使用qlib预测趋势失败，将使用备用方法: {str(e)}")
                # 继续使用备用方法
                
                # 这里使用近期的波动性作为参考
                volatility = historical_data['close'].pct_change().std() * 100
                horizon_factor = {
                    TimeHorizon.SHORT_TERM: 1, 
                    TimeHorizon.MEDIUM_TERM: 2.5, 
                    TimeHorizon.LONG_TERM: 5
                }
                
                # 根据趋势方向和时间周期调整预测幅度
                if trend == TrendDirection.SIDEWAYS:
                    magnitude = volatility * 0.5
                else:
                    magnitude = volatility * horizon_factor.get(request.time_horizon, 1)
                    if trend == TrendDirection.DOWN:
                        magnitude = -magnitude
                
                # 计算置信度
                if abs(magnitude) < volatility:
                    confidence = 0.5 + abs(magnitude) / (volatility * 2)
                else:
                    confidence = 0.5 + volatility / (abs(magnitude) * 2)
                
                confidence = min(0.9, max(0.4, confidence))
        else:
            # 备用方法：如果qlib不可用
            volatility = historical_data['close'].pct_change().std() * 100
            horizon_factor = {
                TimeHorizon.SHORT_TERM: 1, 
                TimeHorizon.MEDIUM_TERM: 2.5, 
                TimeHorizon.LONG_TERM: 5
            }
            
            # 根据趋势方向和时间周期调整预测幅度
            if trend == TrendDirection.SIDEWAYS:
                magnitude = volatility * 0.5
            else:
                magnitude = volatility * horizon_factor.get(request.time_horizon, 1)
                if trend == TrendDirection.DOWN:
                    magnitude = -magnitude
            
            # 计算置信度
            if abs(magnitude) < volatility:
                confidence = 0.5 + abs(magnitude) / (volatility * 2)
            else:
                confidence = 0.5 + volatility / (abs(magnitude) * 2)
            
            confidence = min(0.9, max(0.4, confidence))
        
        # 计算影响因素
        factors = {
            "技术指标趋势": 0.4,
            "成交量分析": 0.2,
            "市场情绪": 0.2,
            "周期性模式": 0.1,
            "支撑阻力位": 0.1
        }
        
        # 如果有链上数据，调整因素
        if data_dict and 'on_chain' in data_dict and not data_dict['on_chain'].empty:
            factors = {
                "技术指标趋势": 0.35,
                "成交量分析": 0.15,
                "市场情绪": 0.15,
                "链上数据": 0.2,
                "周期性模式": 0.1,
                "支撑阻力位": 0.05
            }
        
        # 构建预测结果
        return TrendPrediction(
            symbol=request.symbol,
            current_price=Decimal(str(current_price)),
            predicted_direction=trend,
            predicted_magnitude=round(magnitude, 2),
            time_horizon=request.time_horizon,
            confidence=round(confidence, 2),
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _predict_volatility(cls, request: PredictionRequest, historical_data: pd.DataFrame) -> VolatilityPrediction:
        """
        预测波动率
        
        Args:
            request: 预测请求
            historical_data: 历史数据
            
        Returns:
            VolatilityPrediction: 波动率预测结果
        """
        if historical_data.empty:
            raise BadRequestException("历史数据不足，无法生成预测")
        
        # 计算历史波动率 (标准差)
        if len(historical_data) >= 14:
            # 使用14天的历史数据计算波动率
            historical_volatility = historical_data['close'].pct_change().rolling(window=14).std() * 100
            current_volatility = historical_volatility.iloc[-1]
        else:
            # 数据不足，使用所有可用数据
            current_volatility = historical_data['close'].pct_change().std() * 100
        
        # 如果没有足够数据计算，使用默认值
        if pd.isna(current_volatility):
            current_volatility = 2.0  # 默认波动率
        
        # 预测未来波动率 (实际项目中应该使用模型预测)
        # 这里使用简单的时间调整因子
        horizon_factors = {
            TimeHorizon.SHORT_TERM: 1.1,  # 短期波动率略高
            TimeHorizon.MEDIUM_TERM: 0.9,  # 中期回归均值
            TimeHorizon.LONG_TERM: 0.8,  # 长期趋于稳定
        }
        
        # 市场环境因子 (可以根据宏观指标和市场状况动态调整)
        market_factor = 1.0
        
        # 预测波动率
        predicted_volatility = current_volatility * horizon_factors.get(request.time_horizon, 1.0) * market_factor
        
        # 计算影响因素
        factors = {
            "历史波动率": 0.35,
            "市场流动性": 0.2,
            "事件风险": 0.15,
            "宏观经济因素": 0.15,
            "季节性模式": 0.15
        }
        
        # 计算置信度
        confidence = 0.75  # 基础置信度
        
        # 数据点越多，置信度越高
        if len(historical_data) > 30:
            confidence += 0.1
        elif len(historical_data) < 10:
            confidence -= 0.1
        
        # 波动率的稳定性影响置信度
        volatility_stability = historical_volatility.rolling(window=7).std().iloc[-1] if len(historical_data) > 7 else None
        if volatility_stability and not pd.isna(volatility_stability):
            if volatility_stability > current_volatility * 0.5:
                confidence -= 0.1  # 波动率不稳定，降低置信度
        
        confidence = min(0.95, max(0.4, confidence))
        
        # 构建预测结果
        return VolatilityPrediction(
            symbol=request.symbol,
            current_volatility=round(float(current_volatility), 2),
            predicted_volatility=round(float(predicted_volatility), 2),
            time_horizon=request.time_horizon,
            confidence=round(confidence, 2),
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _predict_signal(cls, request: PredictionRequest, historical_data: pd.DataFrame) -> SignalPrediction:
        """
        预测交易信号
        
        Args:
            request: 预测请求
            historical_data: 历史数据
            
        Returns:
            SignalPrediction: 交易信号预测结果
        """
        if historical_data.empty:
            raise BadRequestException("历史数据不足，无法生成预测")
        
        # 获取最新价格
        current_price = historical_data.iloc[-1]['close']
        
        # 简单技术分析指标计算
        # 计算移动平均线
        if len(historical_data) >= 20:
            historical_data['ma5'] = historical_data['close'].rolling(window=5).mean()
            historical_data['ma10'] = historical_data['close'].rolling(window=10).mean()
            historical_data['ma20'] = historical_data['close'].rolling(window=20).mean()
            
            # 计算MACD
            historical_data['ema12'] = historical_data['close'].ewm(span=12).mean()
            historical_data['ema26'] = historical_data['close'].ewm(span=26).mean()
            historical_data['macd'] = historical_data['ema12'] - historical_data['ema26']
            historical_data['signal'] = historical_data['macd'].ewm(span=9).mean()
            
            # 计算RSI
            delta = historical_data['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            historical_data['rsi'] = 100 - (100 / (1 + rs))
            
            # 根据技术指标生成信号
            ma_signal = 0
            if (historical_data['ma5'].iloc[-1] > historical_data['ma10'].iloc[-1] and 
                historical_data['ma10'].iloc[-1] > historical_data['ma20'].iloc[-1]):
                ma_signal = 1  # 上升趋势
            elif (historical_data['ma5'].iloc[-1] < historical_data['ma10'].iloc[-1] and 
                  historical_data['ma10'].iloc[-1] < historical_data['ma20'].iloc[-1]):
                ma_signal = -1  # 下降趋势
            
            macd_signal = 0
            if (historical_data['macd'].iloc[-1] > historical_data['signal'].iloc[-1] and 
                historical_data['macd'].iloc[-1] > 0):
                macd_signal = 1  # 买入信号
            elif (historical_data['macd'].iloc[-1] < historical_data['signal'].iloc[-1] and 
                  historical_data['macd'].iloc[-1] < 0):
                macd_signal = -1  # 卖出信号
            
            rsi_signal = 0
            if historical_data['rsi'].iloc[-1] < 30:
                rsi_signal = 1  # 超卖，买入信号
            elif historical_data['rsi'].iloc[-1] > 70:
                rsi_signal = -1  # 超买，卖出信号
            
            # 综合信号
            total_signal = ma_signal + macd_signal + rsi_signal
            
            if total_signal >= 2:
                signal = SignalStrength.STRONG_BUY
            elif total_signal == 1:
                signal = SignalStrength.BUY
            elif total_signal == 0:
                signal = SignalStrength.NEUTRAL
            elif total_signal == -1:
                signal = SignalStrength.SELL
            else:
                signal = SignalStrength.STRONG_SELL
        else:
            # 数据不足，默认为中性
            signal = SignalStrength.NEUTRAL
        
        # 计算目标价、止损和止盈
        volatility = historical_data['close'].pct_change().std() * 100 if len(historical_data) > 1 else 5
        
        if signal in [SignalStrength.STRONG_BUY, SignalStrength.BUY]:
            target_price = current_price * (1 + volatility / 100 * 2)
            stop_loss = current_price * (1 - volatility / 100)
            take_profit = current_price * (1 + volatility / 100 * 3)
        elif signal in [SignalStrength.STRONG_SELL, SignalStrength.SELL]:
            target_price = current_price * (1 - volatility / 100 * 2)
            stop_loss = current_price * (1 + volatility / 100)
            take_profit = current_price * (1 - volatility / 100 * 3)
        else:
            target_price = current_price
            stop_loss = current_price * (1 - volatility / 100 * 1.5)
            take_profit = current_price * (1 + volatility / 100 * 1.5)
        
        # 计算影响因素
        factors = {
            "移动平均线交叉": 0.25,
            "MACD指标": 0.25,
            "RSI指标": 0.2,
            "成交量变化": 0.15,
            "价格模式": 0.15
        }
        
        # 计算置信度
        confidence = 0.6  # 基础置信度
        
        # 信号越极端，置信度可能越低
        if signal in [SignalStrength.STRONG_BUY, SignalStrength.STRONG_SELL]:
            confidence -= 0.1
        
        # 根据指标一致性调整置信度
        if abs(total_signal) == 3:
            confidence += 0.2  # 所有指标一致
        elif abs(total_signal) <= 1:
            confidence -= 0.1  # 指标不一致
        
        confidence = min(0.9, max(0.4, confidence))
        
        # 构建预测结果
        return SignalPrediction(
            symbol=request.symbol,
            current_price=Decimal(str(current_price)),
            signal=signal,
            target_price=Decimal(str(round(target_price, 8))),
            stop_loss=Decimal(str(round(stop_loss, 8))),
            take_profit=Decimal(str(round(take_profit, 8))),
            time_horizon=request.time_horizon,
            confidence=round(confidence, 2),
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _predict_sentiment(cls, request: PredictionRequest, historical_data: pd.DataFrame) -> SentimentPrediction:
        """
        预测市场情绪
        
        Args:
            request: 预测请求
            historical_data: 历史数据
            
        Returns:
            SentimentPrediction: 情绪预测结果
        """
        # 模拟情绪分析结果
        # 实际项目中可以调用外部情绪分析API或使用NLP模型分析社交媒体、新闻等
        
        # 基于最近价格变动假设情绪
        if len(historical_data) > 5:
            recent_change = (historical_data['close'].iloc[-1] / historical_data['close'].iloc[-5] - 1) * 100
        else:
            recent_change = 0
        
        # 基于价格变化、波动性等模拟情绪得分
        volatility = historical_data['close'].pct_change().std() * 100 if len(historical_data) > 1 else 5
        
        # 情绪得分 (-1.0 到 1.0)
        base_score = recent_change / (volatility * 2)  # 标准化
        
        # 确保在范围内
        sentiment_score = max(-1.0, min(1.0, base_score))
        
        # 确定情绪水平
        if sentiment_score > 0.6:
            sentiment = SentimentLevel.VERY_POSITIVE
        elif sentiment_score > 0.2:
            sentiment = SentimentLevel.POSITIVE
        elif sentiment_score > -0.2:
            sentiment = SentimentLevel.NEUTRAL
        elif sentiment_score > -0.6:
            sentiment = SentimentLevel.NEGATIVE
        else:
            sentiment = SentimentLevel.VERY_NEGATIVE
        
        # 假设分析了多个数据源
        sources_analyzed = 15
        
        # 计算影响因素
        factors = {
            "价格走势": 0.3,
            "社交媒体情绪": 0.25,
            "新闻情绪": 0.2,
            "市场波动性": 0.15,
            "交易量变化": 0.1
        }
        
        # 计算置信度
        confidence = 0.65  # 基础置信度
        
        # 根据信息来源数量调整置信度
        if sources_analyzed > 20:
            confidence += 0.1
        elif sources_analyzed < 10:
            confidence -= 0.1
        
        # 情绪越极端，置信度可能越低
        if sentiment in [SentimentLevel.VERY_POSITIVE, SentimentLevel.VERY_NEGATIVE]:
            confidence -= 0.05
        
        confidence = min(0.9, max(0.4, confidence))
        
        # 构建预测结果
        return SentimentPrediction(
            symbol=request.symbol,
            sentiment=sentiment,
            sentiment_score=round(sentiment_score, 2),
            time_horizon=request.time_horizon,
            confidence=round(confidence, 2),
            sources_analyzed=sources_analyzed,
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _predict_risk(cls, request: PredictionRequest, historical_data: pd.DataFrame) -> RiskPrediction:
        """
        预测风险
        
        Args:
            request: 预测请求
            historical_data: 历史数据
            
        Returns:
            RiskPrediction: 风险预测结果
        """
        if historical_data.empty:
            raise BadRequestException("历史数据不足，无法生成预测")
        
        # 计算历史风险指标
        
        # 1. 波动率
        volatility = historical_data['close'].pct_change().std() * 100 if len(historical_data) > 1 else 5
        
        # 2. 最大回撤
        max_drawdown = 0
        if len(historical_data) > 10:
            # 计算每个点的最大回撤
            cumulative_max = historical_data['close'].cummax()
            drawdown = (historical_data['close'] - cumulative_max) / cumulative_max
            max_drawdown = drawdown.min() * 100  # 转为百分比
        
        # 3. 在险价值 (VaR)
        var_95 = 0
        if len(historical_data) > 20:
            # 计算95%置信度的每日在险价值
            returns = historical_data['close'].pct_change().dropna()
            var_95 = -np.percentile(returns, 5) * 100  # 转为百分比
        
        # 综合风险评分 (0-100)
        # 将各指标标准化并加权
        
        # 波动率标准分数 (假设市场平均波动率为15%)
        volatility_score = min(100, volatility / 15 * 50)
        
        # 最大回撤标准分数 (假设30%回撤对应满分)
        drawdown_score = min(100, abs(max_drawdown) / 30 * 50)
        
        # VaR标准分数 (假设5%的每日VaR对应满分)
        var_score = min(100, var_95 / 5 * 50)
        
        # 加权平均
        risk_score = volatility_score * 0.4 + drawdown_score * 0.4 + var_score * 0.2
        
        # 风险水平
        if risk_score < 20:
            risk_level = RiskLevel.VERY_LOW
        elif risk_score < 40:
            risk_level = RiskLevel.LOW
        elif risk_score < 60:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 80:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.VERY_HIGH
        
        # 计算预期最大回撤
        expected_max_drawdown = max_drawdown * 1.2  # 预期可能比历史略高
        
        # 根据时间周期调整风险预期
        horizon_factors = {
            TimeHorizon.SHORT_TERM: 0.8,  # 短期风险可能较低
            TimeHorizon.MEDIUM_TERM: 1.0,  # 中期风险作为基准
            TimeHorizon.LONG_TERM: 1.2,  # 长期风险可能较高
        }
        
        risk_score *= horizon_factors.get(request.time_horizon, 1.0)
        expected_max_drawdown *= horizon_factors.get(request.time_horizon, 1.0)
        var_95 *= horizon_factors.get(request.time_horizon, 1.0)
        
        # 限制分数范围
        risk_score = max(1, min(99, risk_score))
        
        # 计算影响因素
        factors = {
            "历史波动率": 0.3,
            "最大回撤": 0.25,
            "在险价值": 0.2,
            "市场相关性": 0.15,
            "流动性风险": 0.1
        }
        
        # 计算置信度
        confidence = 0.7  # 基础置信度
        
        # 数据点越多，置信度越高
        if len(historical_data) > 60:
            confidence += 0.1
        elif len(historical_data) < 20:
            confidence -= 0.1
        
        confidence = min(0.9, max(0.5, confidence))
        
        # 构建预测结果
        return RiskPrediction(
            symbol=request.symbol,
            risk_level=risk_level,
            risk_score=round(float(risk_score), 1),
            value_at_risk=round(float(var_95), 2),
            max_drawdown=round(float(expected_max_drawdown), 2),
            time_horizon=request.time_horizon,
            confidence=round(confidence, 2),
            model_version=cls.MODEL_VERSION,
            factors=factors if request.include_factors else None
        )
    
    @classmethod
    async def _save_prediction_to_db(cls, prediction_data: Dict[str, Any], is_cached: bool) -> None:
        """
        保存预测数据到数据库
        
        Args:
            prediction_data: 预测数据
            is_cached: 是否为缓存数据
        """
        try:
            collection = MongoDB.get_db()[COLLECTION_PREDICTIONS]
            
            # 添加缓存标志和保存时间
            prediction_data['cache_hit'] = is_cached
            prediction_data['saved_at'] = datetime.now()
            
            # 保存到数据库
            await collection.insert_one(prediction_data)
            logger.info(f"预测数据已保存到数据库: {prediction_data['request_id']}")
        except Exception as e:
            logger.error(f"保存预测数据到数据库失败: {str(e)}") 