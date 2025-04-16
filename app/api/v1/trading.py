from fastapi import APIRouter, Query, Path, Body, Depends, HTTPException
from typing import Dict, Any, Optional
import uuid

from app.models.trading import (
    CreateOrderRequest, 
    OrderResponse, 
    FeeCalculationResponse
)
from app.services.exchange_service import ExchangeService
from app.services.fee_service import FeeService
from app.core.exceptions import BadRequestException, ExternalAPIException

router = APIRouter()


@router.post("/order", response_model=OrderResponse)
async def create_order(
    order_request: CreateOrderRequest = Body(..., description="创建订单请求参数")
):
    """
    创建交易订单
    
    根据请求参数在指定交易所创建交易订单。
    """
    try:
        # 创建订单
        order_response = await ExchangeService.create_order(order_request)
        
        # 计算并应用费用
        order_with_fees = await FeeService.apply_fees_to_order(order_response)
        
        return order_with_fees
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-fees", response_model=FeeCalculationResponse)
async def calculate_fees(
    symbol: str = Body(..., description="交易对符号"),
    amount: float = Body(..., description="交易数量"),
    price: float = Body(..., description="交易价格"),
    platform_type: str = Body(..., description="交易平台类型 (centralized, dex, nft_marketplace, p2p)"),
    exchange: Optional[str] = Body(None, description="交易所名称"),
    order_type: Optional[str] = Body("market", description="订单类型 (market, limit, stop_limit, stop_market)"),
    order_side: Optional[str] = Body("buy", description="订单方向 (buy, sell)"),
    custom_slippage: Optional[float] = Body(None, description="自定义滑点费率 (百分比)"),
    custom_routing_fee: Optional[float] = Body(None, description="自定义路由费率 (百分比)")
):
    """
    计算交易费用
    
    根据请求参数计算交易费用，包括滑点费、路由费、交易所费用等。
    """
    try:
        # 计算费用
        fee_calculation = await FeeService.calculate_fees(
            symbol=symbol,
            amount=amount,
            price=price,
            platform_type=platform_type,
            exchange=exchange,
            order_type=order_type,
            order_side=order_side,
            custom_slippage=custom_slippage,
            custom_routing_fee=custom_routing_fee
        )
        
        return fee_calculation
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 