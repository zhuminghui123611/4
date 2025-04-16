from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

# 结算记录模型
class SettlementRecord(BaseModel):
    """费用结算记录"""
    settlement_id: str
    timestamp: datetime
    order_id: str
    user_id: Optional[str] = None
    fee_amount: float
    currency: str
    fee_type: str = "trading"
    distribution: Dict[str, float] = {}
    receiver_address: Optional[str] = None
    auto_transfer_pending: Optional[float] = None
    auto_transferred: bool = False
    transfer_status: Optional[str] = None
    status: str = "completed"

    class Config:
        schema_extra = {
            "example": {
                "settlement_id": "stl_20230701123456_1",
                "timestamp": "2023-07-01T12:34:56.789Z",
                "order_id": "ord_12345",
                "user_id": "user_123",
                "fee_amount": 1.5,
                "currency": "USD",
                "fee_type": "trading",
                "distribution": {"platform": 1.05, "liquidity_providers": 0.3, "risk_reserve": 0.15},
                "status": "completed"
            }
        }

# 转账记录模型
class TransferRecord(BaseModel):
    """费用转账记录"""
    transfer_id: str
    timestamp: datetime
    amount: float
    currency: str
    destination: str
    status: str
    tx_hash: Optional[str] = None
    network_fee: Optional[float] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "transfer_id": "txn_20230701123456",
                "timestamp": "2023-07-01T12:34:56.789Z",
                "amount": 10.5,
                "currency": "USD",
                "destination": "0x1234567890abcdef1234567890abcdef12345678",
                "status": "completed",
                "tx_hash": "0xtxn_20230701123456123456789abcdef",
                "network_fee": 0.001
            }
        }

# 费用余额模型
class FeeBalance(BaseModel):
    """费用余额记录"""
    balance_id: str = Field(default_factory=lambda: f"bal_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    timestamp: datetime = Field(default_factory=datetime.now)
    balances: Dict[str, float] = {}
    pending_transfers: Dict[str, float] = {}
    auto_transfer_enabled: bool = False
    receiver_address: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "balance_id": "bal_20230701123456",
                "timestamp": "2023-07-01T12:34:56.789Z",
                "balances": {
                    "platform": 100.5,
                    "liquidity_providers": 28.7,
                    "risk_reserve": 14.35
                },
                "pending_transfers": {"USD": 5.75, "USDT": 2.3},
                "auto_transfer_enabled": True,
                "receiver_address": "0x1234567890abcdef1234567890abcdef12345678"
            }
        }

# 结算报告模型
class SettlementReport(BaseModel):
    """结算报告"""
    report_id: str
    period: str
    start_date: str
    end_date: Optional[str] = None
    total_fee_amount: float = 0
    fee_by_currency: Dict[str, float] = {}
    fee_by_type: Dict[str, float] = {}
    record_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    auto_transfer_enabled: Optional[bool] = None
    receiver_address: Optional[str] = None
    transferred_amount: Optional[float] = None
    pending_amount: Optional[float] = None
    pending_transfers: Dict[str, float] = {}
    transfer_summary: Optional[Dict[str, Any]] = None
    distribution_summary: Optional[Dict[str, float]] = None

    class Config:
        schema_extra = {
            "example": {
                "report_id": "rep_20230701123456",
                "period": "monthly",
                "start_date": "2023-06-01T00:00:00.000Z",
                "end_date": "2023-06-30T23:59:59.999Z",
                "total_fee_amount": 156.75,
                "fee_by_currency": {
                    "USD": 130.25,
                    "USDT": 26.5
                },
                "fee_by_type": {
                    "trading": 150.25,
                    "withdrawal": 6.5
                },
                "record_count": 45,
                "timestamp": "2023-07-01T12:34:56.789Z"
            }
        }

# Qlib历史数据模型
class HistoricalData(BaseModel):
    """历史市场数据记录"""
    data_id: str = Field(default_factory=lambda: f"hist_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    additional_fields: Dict[str, Any] = {}
    source: str
    source_timestamp: Optional[datetime] = None
    processed: bool = False
    validated: bool = False
    data_quality_score: Optional[float] = None
    
    class Config:
        schema_extra = {
            "example": {
                "data_id": "hist_20230701123456",
                "symbol": "BTC/USDT",
                "timestamp": "2023-07-01T00:00:00.000Z",
                "open": 30123.45,
                "high": 30987.65,
                "low": 29876.54,
                "close": 30456.78,
                "volume": 1234.56,
                "amount": 37596789.12,
                "additional_fields": {
                    "vwap": 30453.21,
                    "number_of_trades": 45678
                },
                "source": "binance",
                "source_timestamp": "2023-07-01T00:00:01.123Z",
                "processed": True,
                "validated": True,
                "data_quality_score": 0.98
            }
        }

class FeatureData(BaseModel):
    """预处理后的特征数据"""
    feature_id: str = Field(default_factory=lambda: f"feat_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    symbol: str
    timestamp: datetime
    timeframe: str  # 1d, 1h, 15m 等
    features: Dict[str, Any]
    raw_data_ids: List[str] = []  # 引用原始数据ID
    feature_version: str
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "feature_id": "feat_20230701123456",
                "symbol": "BTC/USDT",
                "timestamp": "2023-07-01T00:00:00.000Z",
                "timeframe": "1d",
                "features": {
                    "return_1d": 0.0123,
                    "return_5d": 0.0345,
                    "volatility_10d": 0.0567,
                    "rsi_14": 62.5,
                    "macd": 123.45,
                    "ma_diff_50_200": 234.56
                },
                "raw_data_ids": ["hist_20230701123456", "hist_20230630123456"],
                "feature_version": "v1.2.0",
                "created_at": "2023-07-02T12:34:56.789Z"
            }
        }

class TrainedModel(BaseModel):
    """训练完成的模型记录"""
    model_id: str = Field(default_factory=lambda: f"mdl_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    model_name: str
    model_type: str  # LSTM, GRU, Linear, LightGBM 等
    model_version: str
    training_start_time: datetime
    training_end_time: datetime
    symbols: List[str]
    timeframe: str
    features_used: List[str]
    hyperparameters: Dict[str, Any]
    performance_metrics: Dict[str, float]  # 如 accuracy, mae, rmse, sharpe 等
    model_file_path: str  # 模型文件在存储中的路径
    model_file_hash: Optional[str] = None  # 模型文件哈希用于验证
    is_active: bool = False
    created_by: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "model_id": "mdl_20230705123456",
                "model_name": "btc_price_predictor_v1",
                "model_type": "LSTM",
                "model_version": "1.0.0",
                "training_start_time": "2023-07-01T00:00:00.000Z",
                "training_end_time": "2023-07-01T03:45:23.456Z",
                "symbols": ["BTC/USDT"],
                "timeframe": "1d",
                "features_used": ["return_1d", "volatility_10d", "rsi_14", "macd"],
                "hyperparameters": {
                    "layers": 3,
                    "units": 128,
                    "dropout": 0.2,
                    "learning_rate": 0.001
                },
                "performance_metrics": {
                    "accuracy": 0.78,
                    "mae": 0.0234,
                    "rmse": 0.0345,
                    "sharpe": 1.23
                },
                "model_file_path": "/models/btc_price_predictor_v1_20230705.pkl",
                "model_file_hash": "a1b2c3d4e5f6...",
                "is_active": True,
                "created_by": "system",
                "notes": "优化了特征选择和超参数"
            }
        }

class ModelPerformance(BaseModel):
    """模型性能评估记录"""
    performance_id: str = Field(default_factory=lambda: f"perf_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    model_id: str
    evaluation_time: datetime = Field(default_factory=datetime.now)
    evaluation_period: Dict[str, str]  # {"start": "2023-01-01", "end": "2023-06-30"}
    metrics: Dict[str, float]
    predictions_sample: List[Dict[str, Any]] = []
    is_production: bool = False
    comparison_models: List[str] = []  # 其他模型的ID列表，用于比较
    notes: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "performance_id": "perf_20230710123456",
                "model_id": "mdl_20230705123456",
                "evaluation_time": "2023-07-10T12:34:56.789Z",
                "evaluation_period": {"start": "2023-01-01", "end": "2023-06-30"},
                "metrics": {
                    "accuracy": 0.76,
                    "mae": 0.0256,
                    "rmse": 0.0378,
                    "sharpe": 1.21,
                    "max_drawdown": 0.15,
                    "win_rate": 0.68
                },
                "predictions_sample": [
                    {"timestamp": "2023-06-28", "actual": 30123.45, "predicted": 30245.67, "error": 122.22},
                    {"timestamp": "2023-06-29", "actual": 29876.54, "predicted": 29754.32, "error": -122.22}
                ],
                "is_production": True,
                "comparison_models": ["mdl_20230615123456", "mdl_20230625123456"],
                "notes": "在牛市波动场景下表现良好，但在剧烈下跌时预测偏差较大"
            }
        }

class DataSource(BaseModel):
    """数据源信息记录"""
    source_id: str = Field(default_factory=lambda: f"src_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    source_name: str
    source_type: str  # API, CSV, Database等
    connection_details: Dict[str, Any] = {}
    symbols_available: List[str] = []
    timeframes_available: List[str] = []
    historical_data_start: Optional[datetime] = None
    update_frequency: str = "daily"
    last_updated: Optional[datetime] = None
    status: str = "active"
    priority: int = 1  # 数据源优先级，较低数字表示较高优先级
    additional_info: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "source_id": "src_20230701123456",
                "source_name": "Binance",
                "source_type": "API",
                "connection_details": {
                    "api_url": "https://api.binance.com",
                    "api_version": "v3",
                    "has_authentication": True
                },
                "symbols_available": ["BTC/USDT", "ETH/USDT", "BNB/USDT"],
                "timeframes_available": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "historical_data_start": "2017-09-01T00:00:00.000Z",
                "update_frequency": "real-time",
                "last_updated": "2023-07-01T12:30:00.000Z",
                "status": "active",
                "priority": 1,
                "additional_info": {
                    "rate_limit": 1200,
                    "supports_websocket": True
                },
                "created_at": "2023-07-01T12:34:56.789Z"
            }
        }

# 模型转换工具函数
def model_to_dict(model: BaseModel) -> dict:
    """将Pydantic模型转换为字典，供MongoDB存储"""
    return model.dict(by_alias=True)

def dict_to_model(model_class, data: dict):
    """将MongoDB查询结果转换为Pydantic模型"""
    if data and "_id" in data:
        # 移除MongoDB的_id字段
        data.pop("_id")
    return model_class(**data) 