from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
from decimal import Decimal


class OrderSide(str, Enum):
    """订单方向枚举"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型枚举"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"


class OrderStatus(str, Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 待处理
    OPEN = "open"  # 已开放
    FILLED = "filled"  # 已成交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    CANCELED = "canceled"  # 已取消
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期
    FAILED = "failed"  # 失败


class FeeType(str, Enum):
    """费用类型枚举"""
    SLIPPAGE = "slippage"  # 滑点费
    ROUTING = "routing"  # 路由费
    EXCHANGE = "exchange"  # 交易所费用
    GAS = "gas"  # 链上交易Gas费


class TradingPlatform(str, Enum):
    """交易平台枚举"""
    CENTRALIZED = "centralized"  # 中心化交易所
    DEX = "dex"  # 去中心化交易所
    NFT_MARKETPLACE = "nft_marketplace"  # NFT市场
    P2P = "p2p"  # 点对点交易


class CreateOrderRequest(BaseModel):
    """创建订单请求模型"""
    symbol: str
    side: OrderSide
    type: OrderType
    amount: Union[float, Decimal]
    price: Optional[Union[float, Decimal]] = None
    stop_price: Optional[Union[float, Decimal]] = None
    platform: TradingPlatform
    exchange: str
    client_order_id: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None


class OrderResponse(BaseModel):
    """订单响应模型"""
    order_id: str
    client_order_id: Optional[str] = None
    status: OrderStatus
    symbol: str
    side: OrderSide
    type: OrderType
    price: Optional[Union[float, Decimal]] = None
    amount: Union[float, Decimal]
    filled: Union[float, Decimal] = 0
    remaining: Union[float, Decimal]
    cost: Optional[Union[float, Decimal]] = None
    fee: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    platform: TradingPlatform
    exchange: str
    raw_response: Optional[Dict[str, Any]] = None


class FeeDetail(BaseModel):
    """费用详细信息模型"""
    type: FeeType
    amount: Union[float, Decimal]
    currency: str
    percentage: Optional[float] = None
    description: Optional[str] = None


class FeeCalculationResponse(BaseModel):
    """费用计算响应模型"""
    total_fee: Union[float, Decimal]
    fee_details: List[FeeDetail]
    fee_currency: str
    original_amount: Union[float, Decimal]
    final_amount: Union[float, Decimal]
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))


class TradeHistoryRequest(BaseModel):
    """交易历史请求模型"""
    symbol: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0
    exchange: Optional[str] = None
    platform: Optional[TradingPlatform] = None


class TradeRecord(BaseModel):
    """交易记录模型"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Union[float, Decimal]
    amount: Union[float, Decimal]
    cost: Union[float, Decimal]
    fee: Optional[Dict[str, Any]] = None
    timestamp: int
    datetime: datetime
    platform: TradingPlatform
    exchange: str


class TradeHistoryResponse(BaseModel):
    """交易历史响应模型"""
    trades: List[TradeRecord]
    total: int
    page: int
    per_page: int
    total_pages: int 