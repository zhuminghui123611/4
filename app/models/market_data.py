from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum, auto
from decimal import Decimal


class DataSourceType(str, Enum):
    """数据源类型"""
    CCXT = "ccxt"           # CCXT库
    ANKR = "ankr"           # Ankr API (区块链RPC节点)
    RESERVOIR = "reservoir" # Reservoir API (NFT交易聚合器)
    OKX_P2P = "okx_p2p"     # OKX P2P API
    ONEINCH = "1inch"       # 1inch API (DEX聚合器)
    INTERNAL = "internal"   # 内部数据


class TimeFrame(str, Enum):
    """K线时间周期"""
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    DAY_3 = "3d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class MarketDataType(str, Enum):
    """市场数据类型枚举"""
    OHLCV = "ohlcv"  # 开盘、最高、最低、收盘价和交易量
    TICKER = "ticker"  # 24小时价格和交易量统计
    ORDER_BOOK = "order_book"  # 订单簿
    TRADE = "trade"  # 最近成交
    NFT_COLLECTION = "nft_collection"  # NFT集合数据
    NFT_ASSET = "nft_asset"  # NFT资产数据
    P2P_ORDER = "p2p_order"  # P2P订单数据
    TOKEN_INFO = "token_info"  # 代币信息
    BLOCKCHAIN_DATA = "blockchain_data"  # 区块链数据


class OHLCVData(BaseModel):
    """K线数据"""
    symbol: str
    datetime: datetime
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    class Config:
        arbitrary_types_allowed = True


class TickerData(BaseModel):
    """Ticker数据"""
    symbol: str
    last: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    timestamp: int
    datetime: datetime
    change: Optional[float] = None
    percentage: Optional[float] = None
    average: Optional[float] = None
    base_volume: Optional[float] = None
    quote_volume: Optional[float] = None
    info: Dict[str, Any] = {}
    
    class Config:
        arbitrary_types_allowed = True


class OrderBookEntry(BaseModel):
    """订单簿条目"""
    price: float
    amount: float


class OrderBookData(BaseModel):
    """订单簿数据"""
    symbol: str
    timestamp: int
    datetime: datetime
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    
    class Config:
        arbitrary_types_allowed = True


class TradeData(BaseModel):
    """交易数据"""
    id: Optional[str] = None
    symbol: str
    timestamp: int
    datetime: datetime
    order: Optional[str] = None
    type: Optional[str] = None
    side: str  # buy or sell
    price: float
    amount: float
    cost: Optional[float] = None
    fee: Optional[Dict[str, Any]] = None
    
    class Config:
        arbitrary_types_allowed = True


class TokenInfo(BaseModel):
    """代币信息"""
    id: str
    symbol: str
    name: Optional[str] = None
    address: Optional[str] = None
    chain: Optional[str] = None
    precision: Optional[int] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class OnChainData(BaseModel):
    """链上数据基类"""
    chain: str
    timestamp: int
    datetime: datetime
    
    class Config:
        arbitrary_types_allowed = True


class EthereumOnChainData(OnChainData):
    """以太坊链上数据"""
    gas_price: float  # Gwei
    tx_count: int
    block_number: int
    block_hash: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class BitcoinOnChainData(OnChainData):
    """比特币链上数据"""
    difficulty: float
    tx_count: int
    block_number: int
    block_hash: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class SentimentData(BaseModel):
    """情绪数据"""
    symbol: str
    timestamp: int
    datetime: datetime
    sentiment_score: float  # -1.0 to 1.0
    social_volume: Optional[int] = None
    source: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class ExchangeReserveData(BaseModel):
    """交易所储备数据"""
    symbol: str
    timestamp: int
    datetime: datetime
    reserve: float
    exchange: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class MarketAggregateData(BaseModel):
    """市场聚合数据"""
    symbol: str
    timestamp: int
    datetime: datetime
    price: float
    volume_24h: Optional[float] = None
    change_24h: Optional[float] = None
    market_cap: Optional[float] = None
    sources: List[DataSourceType] = []
    ohlcv: Optional[OHLCVData] = None
    on_chain: Optional[Union[EthereumOnChainData, BitcoinOnChainData]] = None
    sentiment: Optional[SentimentData] = None
    exchange_reserve: Optional[ExchangeReserveData] = None
    
    class Config:
        arbitrary_types_allowed = True


class NFTCollectionData(BaseModel):
    """NFT集合数据模型"""
    collection_id: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    floor_price: Optional[Dict[str, float]] = None  # 以币种为键的地板价
    volume_24h: Optional[Dict[str, float]] = None  # 以币种为键的24小时交易量
    market_cap: Optional[Dict[str, float]] = None  # 以币种为键的市值
    num_owners: Optional[int] = None
    total_supply: Optional[int] = None
    timestamp: int
    datetime: datetime
    source: DataSourceType = DataSourceType.RESERVOIR


class NFTAssetData(BaseModel):
    """NFT资产数据模型"""
    token_id: str
    collection_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    animation_url: Optional[str] = None
    traits: Optional[List[Dict[str, Any]]] = None
    last_sale: Optional[Dict[str, Any]] = None
    owner: Optional[str] = None
    timestamp: int
    datetime: datetime
    source: DataSourceType = DataSourceType.RESERVOIR


class P2POrderData(BaseModel):
    """P2P订单数据模型"""
    order_id: str
    crypto_currency: str
    fiat_currency: str
    price: float
    available_amount: float
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    payment_methods: List[str]
    user_info: Dict[str, Any]
    side: str  # 'buy' or 'sell'
    timestamp: int
    datetime: datetime
    source: DataSourceType = DataSourceType.OKX_P2P


class TokenInfoData(BaseModel):
    """代币信息数据模型"""
    symbol: str
    name: str
    address: Optional[str] = None
    chain: str
    decimals: int
    total_supply: Optional[float] = None
    circulating_supply: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: int
    datetime: datetime
    source: DataSourceType


class BlockchainData(BaseModel):
    """区块链数据模型"""
    chain: str
    block_number: Optional[int] = None
    transaction_hash: Optional[str] = None
    timestamp: int
    datetime: datetime
    data: Dict[str, Any]
    source: DataSourceType = DataSourceType.ANKR


class MarketDataResponse(BaseModel):
    """市场数据API响应模型"""
    success: bool = True
    data_type: MarketDataType
    data: Any
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    source: DataSourceType
    cache_hit: bool = False 