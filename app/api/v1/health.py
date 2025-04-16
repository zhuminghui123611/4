from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any, List

from app.db.mongodb import MongoDB
from app.db.redis import RedisClient

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    version: str
    services: Dict[str, Dict[str, Any]]


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    系统健康检查接口
    
    返回系统各组件的健康状态。
    """
    services = {}
    
    # 检查MongoDB连接
    try:
        # 执行ping命令检查连接
        MongoDB.get_client().admin.command('ping')
        mongo_status = {
            "status": "healthy",
            "message": "MongoDB连接正常"
        }
    except Exception as e:
        mongo_status = {
            "status": "unhealthy",
            "message": f"MongoDB连接异常: {str(e)}"
        }
    
    # 检查Redis连接
    try:
        RedisClient.get_client().ping()
        redis_status = {
            "status": "healthy",
            "message": "Redis连接正常"
        }
    except Exception as e:
        redis_status = {
            "status": "unhealthy",
            "message": f"Redis连接异常: {str(e)}"
        }
    
    # 构建服务状态字典
    services = {
        "mongodb": mongo_status,
        "redis": redis_status,
    }
    
    # 判断总体状态
    overall_status = "healthy"
    for service, status in services.items():
        if status["status"] != "healthy":
            overall_status = "degraded"
            break
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        services=services
    )


@router.get("/dependencies")
async def dependencies_check():
    """
    系统依赖健康检查接口
    
    返回系统外部依赖的健康状态。
    """
    dependencies = []
    
    # 检查交易所API连接
    try:
        # 这里可以添加对各交易所API的检查
        # 为了简化，这里只返回一个简单消息
        dependencies.append({
            "name": "CCXT API",
            "status": "available",
            "message": "CCXT库可用"
        })
    except Exception:
        dependencies.append({
            "name": "CCXT API",
            "status": "unavailable",
            "message": "CCXT库不可用"
        })
    
    # 检查qlib模型可用性
    try:
        import qlib
        dependencies.append({
            "name": "qlib",
            "status": "available",
            "message": "qlib库可用"
        })
    except ImportError:
        dependencies.append({
            "name": "qlib",
            "status": "unavailable",
            "message": "qlib库不可用"
        })
    
    return {"dependencies": dependencies} 