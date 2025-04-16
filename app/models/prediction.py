from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
from decimal import Decimal


class PredictionType(str, Enum):
    """预测类型枚举"""
    PRICE = "price"  # 价格预测
    TREND = "trend"  # 趋势预测
    VOLATILITY = "volatility"  # 波动率预测
    SIGNAL = "signal"  # 交易信号
    SENTIMENT = "sentiment"  # 情绪分析
    RISK = "risk"  # 风险评估


class TrendDirection(str, Enum):
    """趋势方向枚举"""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


class SignalStrength(str, Enum):
    """信号强度枚举"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class SentimentLevel(str, Enum):
    """情绪水平枚举"""
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class RiskLevel(str, Enum):
    """风险水平枚举"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TimeHorizon(str, Enum):
    """时间周期枚举"""
    SHORT_TERM = "short_term"  # 短期 (小时-天)
    MEDIUM_TERM = "medium_term"  # 中期 (天-周)
    LONG_TERM = "long_term"  # 长期 (周-月)


class PredictionRequest(BaseModel):
    """预测请求模型"""
    symbol: str
    prediction_type: PredictionType
    time_horizon: TimeHorizon
    custom_parameters: Optional[Dict[str, Any]] = None
    historical_data_days: Optional[int] = 30  # 请求历史数据的天数
    include_confidence: bool = True  # 是否包含置信度
    include_factors: bool = True  # 是否包含影响因素


class PricePoint(BaseModel):
    """价格点模型"""
    timestamp: int
    datetime: datetime
    price: Union[float, Decimal]
    confidence: Optional[float] = None  # 置信度 0-1


class PricePrediction(BaseModel):
    """价格预测模型"""
    symbol: str
    current_price: Union[float, Decimal]
    predicted_prices: List[PricePoint]
    time_horizon: TimeHorizon
    confidence: float  # 整体置信度 0-1
    model_version: str
    factors: Optional[Dict[str, float]] = None  # 影响因素及其权重


class TrendPrediction(BaseModel):
    """趋势预测模型"""
    symbol: str
    current_price: Union[float, Decimal]
    predicted_direction: TrendDirection
    predicted_magnitude: float  # 预测的变化幅度 (百分比)
    time_horizon: TimeHorizon
    confidence: float
    model_version: str
    factors: Optional[Dict[str, float]] = None


class VolatilityPrediction(BaseModel):
    """波动率预测模型"""
    symbol: str
    current_volatility: float  # 当前波动率
    predicted_volatility: float  # 预测波动率
    time_horizon: TimeHorizon
    confidence: float
    model_version: str
    factors: Optional[Dict[str, float]] = None


class SignalPrediction(BaseModel):
    """信号预测模型"""
    symbol: str
    current_price: Union[float, Decimal]
    signal: SignalStrength
    target_price: Optional[Union[float, Decimal]] = None
    stop_loss: Optional[Union[float, Decimal]] = None
    take_profit: Optional[Union[float, Decimal]] = None
    time_horizon: TimeHorizon
    confidence: float
    model_version: str
    factors: Optional[Dict[str, float]] = None


class SentimentPrediction(BaseModel):
    """情绪预测模型"""
    symbol: str
    sentiment: SentimentLevel
    sentiment_score: float  # -1.0 到 1.0
    time_horizon: TimeHorizon
    confidence: float
    sources_analyzed: int  # 分析的数据源数量
    model_version: str
    factors: Optional[Dict[str, float]] = None


class RiskPrediction(BaseModel):
    """风险预测模型"""
    symbol: str
    risk_level: RiskLevel
    risk_score: float  # 0-100
    value_at_risk: Optional[float] = None  # 在险价值 (VaR)
    max_drawdown: Optional[float] = None  # 最大回撤预测
    time_horizon: TimeHorizon
    confidence: float
    model_version: str
    factors: Optional[Dict[str, float]] = None


class PredictionResponse(BaseModel):
    """预测响应模型"""
    request_id: str
    prediction_type: PredictionType
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    generated_at: datetime = Field(default_factory=datetime.now)
    symbol: str
    time_horizon: TimeHorizon
    data: Union[
        PricePrediction,
        TrendPrediction,
        VolatilityPrediction,
        SignalPrediction,
        SentimentPrediction,
        RiskPrediction
    ]
    success: bool = True
    message: Optional[str] = None 