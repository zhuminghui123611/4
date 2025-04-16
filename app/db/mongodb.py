from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError

from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    _client = None
    _db = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        """获取MongoDB客户端连接"""
        if cls._client is None:
            try:
                # 使用完整的连接字符串
                uri = "mongodb://root:dkh7zdsg@test-db-mongodb.ns-vbg4dujj.svc:27017"
                
                # 创建连接
                cls._client = AsyncIOMotorClient(uri)
                
                # 测试连接不再需要，motor会自动在需要时建立连接
                logger.info("MongoDB连接成功创建")
            except (ConnectionFailure, ConfigurationError) as e:
                logger.error(f"MongoDB连接失败: {str(e)}")
                raise
        return cls._client

    @classmethod
    def get_db(cls):
        """获取数据库实例"""
        if cls._db is None:
            client = cls.get_client()
            # 使用默认的数据库名称，也可以从连接字符串中提取
            cls._db = client[settings.MONGO_DB]
        return cls._db
    
    @classmethod
    def close(cls):
        """关闭MongoDB连接"""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB连接已关闭")

# 常用集合名称常量
COLLECTION_MARKET_DATA = "market_data"
COLLECTION_TRADING_ORDERS = "trading_orders"
COLLECTION_USER_PROFILES = "user_profiles"
COLLECTION_NFT_DATA = "nft_data"
COLLECTION_P2P_ORDERS = "p2p_orders"
COLLECTION_PREDICTIONS = "model_predictions"
COLLECTION_API_LOGS = "api_logs"
COLLECTION_SETTLEMENT_RECORDS = "settlement_records"
COLLECTION_TRANSFER_RECORDS = "transfer_records"
COLLECTION_FEE_BALANCES = "fee_balances"
# 添加qlib历史数据相关集合
COLLECTION_HISTORICAL_DATA = "historical_data"
COLLECTION_FEATURE_DATA = "feature_data"
COLLECTION_TRAINED_MODELS = "trained_models"
COLLECTION_MODEL_PERFORMANCES = "model_performances"
COLLECTION_DATA_SOURCES = "data_sources"

def get_collection(collection_name: str):
    """获取指定名称的集合"""
    db = MongoDB.get_db()
    return db[collection_name] 