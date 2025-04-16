from fastapi import APIRouter

from app.api.v1 import market, trading, prediction, health

# 创建API路由
router = APIRouter()

# 注册子路由
router.include_router(market.router, prefix="/market", tags=["市场数据"])
router.include_router(trading.router, prefix="/trading", tags=["交易"])
router.include_router(prediction.router, prefix="/prediction", tags=["预测"])
router.include_router(health.router, prefix="/health", tags=["系统状态"]) 