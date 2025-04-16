from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional, List
import logging

from app.models.trading_models import CreateOrderRequest
from app.models.common_models import ErrorResponse, SuccessResponse
from app.services.fee_service import FeeService
from app.exceptions.service_exceptions import BadRequestException, ServiceUnavailableException

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/fees", tags=["费用"])

@router.post("/calculate", summary="计算交易费用")
async def calculate_fees(
    symbol: str,
    amount: float,
    price: float,
    platform_type: str = Query("CEX", description="平台类型 (CEX, DEX, P2P)"),
    custom_slippage_rate: Optional[float] = Query(None, description="自定义滑点率"),
    custom_routing_fee: Optional[float] = Query(None, description="自定义路由费"),
    user_tier: str = Query("basic", description="用户等级 (basic, silver, gold, platinum)")
):
    """
    计算交易费用
    
    根据提供的交易对、数量、价格和其他参数计算费用
    
    返回:
    - 费用详情，包括滑点费、路由费、总费用、基础代币费用和有效费率
    """
    try:
        fee_service = FeeService()
        fee_details = await fee_service.calculate_fees(
            symbol=symbol,
            amount=amount,
            price=price,
            platform_type=platform_type,
            custom_slippage_rate=custom_slippage_rate,
            custom_routing_fee=custom_routing_fee,
            user_tier=user_tier
        )
        
        return SuccessResponse(
            message="费用计算成功",
            data=fee_details
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"计算费用时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.post("/apply-to-order", summary="将费用应用到订单")
async def apply_fees_to_order(
    order: Dict[str, Any],
    fee_details: Dict[str, Any]
):
    """
    将费用应用到订单
    
    接收订单和费用详情，返回包含费用信息的更新订单
    
    返回:
    - 包含费用信息的更新订单
    """
    try:
        fee_service = FeeService()
        updated_order = await fee_service.apply_fees_to_order(order, fee_details)
        
        return SuccessResponse(
            message="费用已应用到订单",
            data=updated_order
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"应用费用到订单时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/configuration", summary="获取费用配置")
async def get_fee_configuration():
    """
    获取当前费用配置
    
    返回当前的费用配置，包括默认滑点费率、固定路由费、用户等级折扣和平台倍数
    
    返回:
    - 当前费用配置
    """
    try:
        fee_service = FeeService()
        config = await fee_service.get_fee_configuration()
        
        return SuccessResponse(
            message="获取费用配置成功",
            data=config
        )
    except Exception as e:
        logger.error(f"获取费用配置时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.put("/configuration", summary="更新费用配置")
async def update_fee_configuration(config: Dict[str, Any]):
    """
    更新费用配置
    
    更新费用配置，可以更新默认滑点费率、固定路由费、用户等级折扣和平台倍数
    
    返回:
    - 更新后的费用配置
    """
    try:
        fee_service = FeeService()
        updated_config = await fee_service.update_fee_configuration(config)
        
        return SuccessResponse(
            message="更新费用配置成功",
            data=updated_config
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"更新费用配置时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误") 