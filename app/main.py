import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1 import market_data, trading, prediction, data_analysis, fees, settlements
from app.core.config import settings
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.core.logging import setup_logging
from app.db.mongodb import MongoDB
from app.core.middleware import request_handler

# 设置日志
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行的代码
    logger.info("应用程序启动...")
    
    # 初始化数据库连接
    await MongoDB.connect()
    logger.info("MongoDB连接已初始化")
    
    yield
    
    # 关闭时执行的代码
    logger.info("应用程序关闭...")
    await MongoDB.close()
    logger.info("MongoDB连接已关闭")

# 创建FastAPI应用实例
app = FastAPI(
    title="加密货币交易数据分析与执行后端服务",
    description=(
        "提供加密货币市场数据获取、分析、预测和交易执行的综合API服务。"
        "使用CCXT库与交易所集成，支持qlib进行高级数据分析和预测。"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加请求处理中间件
app.middleware("http")(request_handler)

# 异常处理
@app.exception_handler(BadRequestException)
async def bad_request_exception_handler(request, exc):
    return HTTPException(status_code=400, detail=str(exc))

@app.exception_handler(ServiceUnavailableException)
async def service_unavailable_exception_handler(request, exc):
    return HTTPException(status_code=503, detail=str(exc))

# 注册路由
app.include_router(market_data.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(prediction.router, prefix="/api/v1")
app.include_router(data_analysis.router, prefix="/api/v1")
app.include_router(fees.router, prefix="/api/v1")
app.include_router(settlements.router, prefix="/api/v1")

# 健康检查接口
@app.get("/health", tags=["系统"])
async def health_check():
    """服务健康检查接口"""
    return {"status": "healthy", "version": app.version}

# 根路径
@app.get("/", tags=["系统"])
async def root():
    """API根入口"""
    return {
        "message": "欢迎使用加密货币交易数据分析与执行后端服务 API",
        "documentation": "/docs",
        "health": "/health"
    } 