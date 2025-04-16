from pydantic import BaseSettings
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Settings(BaseSettings):
    # 基本配置
    PROJECT_NAME: str = "crypto-trading-api"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    
    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    ALGORITHM: str = "HS256"
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]
    
    # 数据库配置
    MONGO_HOST: str = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT: int = int(os.getenv("MONGO_PORT", "27017"))
    MONGO_DB: str = os.getenv("MONGO_DB", "crypto_trading")
    MONGO_USER: Optional[str] = os.getenv("MONGO_USER")
    MONGO_PASSWORD: Optional[str] = os.getenv("MONGO_PASSWORD")
    
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # 外部API配置
    ANKR_API_KEY: str = os.getenv("ANKR_API_KEY", "")
    RESERVOIR_API_KEY: str = os.getenv("RESERVOIR_API_KEY", "")
    OKX_API_KEY: str = os.getenv("OKX_API_KEY", "")
    OKX_API_SECRET: str = os.getenv("OKX_API_SECRET", "")
    OKX_API_PASSPHRASE: str = os.getenv("OKX_API_PASSPHRASE", "")
    
    # 费用配置
    DEFAULT_SLIPPAGE_FEE_PERCENTAGE: float = float(os.getenv("DEFAULT_SLIPPAGE_FEE", "0.1"))  # 默认滑点费率0.1%
    FIXED_ROUTING_FEE: float = float(os.getenv("FIXED_ROUTING_FEE", "0.05"))  # 固定路由费率0.05%
    
    # qlib模型配置
    QLIB_MODEL_PATH: str = os.getenv("QLIB_MODEL_PATH", "./models/qlib_model")
    
    # 自动转账设置
    AUTO_TRANSFER_ENABLED: bool = os.getenv("AUTO_TRANSFER_ENABLED", "false").lower() == "true"
    FEE_RECEIVER_ADDRESS: str = os.getenv("FEE_RECEIVER_ADDRESS", "")
    AUTO_TRANSFER_THRESHOLD: float = float(os.getenv("AUTO_TRANSFER_THRESHOLD", "10.0"))
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        
settings = Settings()

# API异常响应代码
class ErrorCode:
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    API_ERROR = "API_ERROR" 