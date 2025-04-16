from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, Security
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import os

from app.models.common_models import ErrorResponse, SuccessResponse
from app.services.fee_service import FeeService
from app.exceptions.service_exceptions import BadRequestException, ServiceUnavailableException
from app.core.config import settings
from app.core.security import verify_admin_key

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/settlements", tags=["结算"])

@router.get("/balances", summary="获取费用余额")
async def get_fee_balances(admin_key: str = Security(verify_admin_key)):
    """
    获取各账户的费用余额
    
    返回:
    - 各账户的费用余额，包括平台账户、流动性提供者和风险储备金
    """
    try:
        fee_service = FeeService()
        balances = await fee_service.get_fee_balances()
        
        return SuccessResponse(
            message="获取费用余额成功",
            data=balances
        )
    except Exception as e:
        logger.error(f"获取费用余额时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/records", summary="获取结算记录")
async def get_settlement_records(
    start_date: Optional[str] = Query(None, description="开始日期（ISO格式）"),
    end_date: Optional[str] = Query(None, description="结束日期（ISO格式）"),
    limit: int = Query(100, description="返回记录的最大数量"),
    admin_key: str = Security(verify_admin_key)
):
    """
    获取结算记录
    
    查询指定时间段内的交易费用结算记录
    
    参数:
    - start_date: 开始日期，ISO格式（可选）
    - end_date: 结束日期，ISO格式（可选）
    - limit: 返回记录的最大数量
    
    返回:
    - 结算记录列表
    """
    try:
        fee_service = FeeService()
        records = await fee_service.get_settlement_records(start_date, end_date, limit)
        
        return SuccessResponse(
            message="获取结算记录成功",
            data=records
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"获取结算记录时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/transfers", summary="获取自动转账记录")
async def get_transfer_records(
    limit: int = Query(100, description="返回记录的最大数量"),
    admin_key: str = Security(verify_admin_key)
):
    """
    获取自动转账记录
    
    查询系统执行的自动转账记录
    
    参数:
    - limit: 返回记录的最大数量
    
    返回:
    - 转账记录列表
    """
    try:
        # 检查是否启用了自动转账
        if not settings.AUTO_TRANSFER_ENABLED or not settings.FEE_RECEIVER_ADDRESS:
            return SuccessResponse(
                message="自动转账未启用",
                data={"enabled": False, "records": []}
            )
        
        fee_service = FeeService()
        records = await fee_service.get_transfer_records(limit)
        
        return SuccessResponse(
            message="获取转账记录成功",
            data={
                "enabled": True,
                "receiver_address": settings.FEE_RECEIVER_ADDRESS,
                "records": records
            }
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"获取转账记录时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.put("/distribution", summary="更新费用分配比例")
async def update_fee_distribution(
    distribution: Dict[str, float] = Body(..., description="新的费用分配比例"),
    admin_key: str = Security(verify_admin_key)
):
    """
    更新费用分配比例
    
    更新收取的交易费用在不同账户之间的分配比例
    
    参数:
    - distribution: 新的费用分配比例，格式为 {"account": ratio, ...}
    
    返回:
    - 更新后的费用分配比例
    """
    try:
        # 检查是否启用了自动转账
        if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
            logger.warning("尝试在自动转账模式下更新费用分配比例")
            # 返回警告信息
            return SuccessResponse(
                message="自动转账模式下，费用分配比例更新可能不起作用",
                data={
                    "auto_transfer_enabled": True,
                    "receiver_address": settings.FEE_RECEIVER_ADDRESS,
                    "warning": "在自动转账模式下，所有费用将直接转入指定地址，费用分配比例不会被使用"
                }
            )
            
        fee_service = FeeService()
        updated_distribution = await fee_service.update_fee_distribution(distribution)
        
        return SuccessResponse(
            message="更新费用分配比例成功",
            data=updated_distribution
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"更新费用分配比例时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.post("/withdraw/platform", summary="从平台账户提取费用")
async def withdraw_platform_fee(
    amount: float = Body(..., description="提取金额"),
    currency: str = Body(..., description="币种"),
    destination: str = Body(..., description="目的地地址或账户"),
    admin_key: str = Security(verify_admin_key)
):
    """
    从平台账户提取费用
    
    将收取的费用从平台账户提取到指定目的地
    
    参数:
    - amount: 提取金额
    - currency: 币种
    - destination: 目的地地址或账户
    
    返回:
    - 提取操作的结果
    """
    try:
        # 检查是否启用了自动转账
        if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
            logger.warning(f"尝试在自动转账模式下从平台账户提取费用: {amount} {currency} 到 {destination}")
            # 返回警告信息
            return SuccessResponse(
                message="自动转账模式下，平台账户提取操作可能不可用",
                data={
                    "auto_transfer_enabled": True,
                    "receiver_address": settings.FEE_RECEIVER_ADDRESS,
                    "warning": "在自动转账模式下，所有费用将直接转入指定地址，平台账户可能没有余额可供提取"
                }
            )
            
        fee_service = FeeService()
        # 直接访问结算服务的方法
        settlement_service = fee_service.settlement_service
        withdraw_result = await settlement_service.withdraw_platform_fee(amount, currency, destination)
        
        return SuccessResponse(
            message="从平台账户提取费用成功",
            data=withdraw_result
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"从平台账户提取费用时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.post("/distribute/liquidity", summary="分配流动性提供者费用")
async def distribute_liquidity_provider_fees(
    distribution_plan: List[Dict[str, Any]] = Body(..., description="分配计划"),
    admin_key: str = Security(verify_admin_key)
):
    """
    分配流动性提供者费用
    
    将收取的费用分配给多个流动性提供者
    
    参数:
    - distribution_plan: 分配计划，格式为 [{"provider_id": "...", "ratio": 0.x}, ...]
    
    返回:
    - 分配操作的结果
    """
    try:
        # 检查是否启用了自动转账
        if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
            logger.warning("尝试在自动转账模式下分配流动性提供者费用")
            # 返回警告信息
            return SuccessResponse(
                message="自动转账模式下，流动性提供者费用分配操作不可用",
                data={
                    "auto_transfer_enabled": True,
                    "receiver_address": settings.FEE_RECEIVER_ADDRESS,
                    "warning": "在自动转账模式下，所有费用将直接转入指定地址，流动性提供者账户没有余额可供分配"
                }
            )
            
        fee_service = FeeService()
        # 直接访问结算服务的方法
        settlement_service = fee_service.settlement_service
        distribution_result = await settlement_service.distribute_liquidity_provider_fees(distribution_plan)
        
        return SuccessResponse(
            message="分配流动性提供者费用成功",
            data=distribution_result
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"分配流动性提供者费用时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/report", summary="生成结算报告")
async def generate_settlement_report(
    period: str = Query(..., description="报告周期（daily, weekly, monthly）"),
    start_date: str = Query(..., description="开始日期（ISO格式）"),
    end_date: Optional[str] = Query(None, description="结束日期（ISO格式）"),
    admin_key: str = Security(verify_admin_key)
):
    """
    生成结算报告
    
    生成指定时间段内的费用结算报告
    
    参数:
    - period: 报告周期
    - start_date: 开始日期
    - end_date: 结束日期（可选）
    
    返回:
    - 结算报告
    """
    try:
        fee_service = FeeService()
        report = await fee_service.generate_settlement_report(period, start_date, end_date)
        
        return SuccessResponse(
            message="生成结算报告成功",
            data=report
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailableException as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"生成结算报告时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.put("/auto-transfer-settings", summary="更新自动转账设置")
async def update_auto_transfer_settings(
    enabled: bool = Body(..., description="是否启用自动转账"),
    receiver_address: str = Body(..., description="接收费用的钱包地址"),
    threshold: float = Body(..., description="自动转账阈值"),
    admin_key: str = Security(verify_admin_key)
):
    """
    更新自动转账设置
    
    更新系统的隐形收费和自动转账设置
    
    参数:
    - enabled: 是否启用自动转账
    - receiver_address: 接收费用的钱包地址
    - threshold: 自动转账阈值（达到该阈值时触发转账）
    
    返回:
    - 更新后的自动转账设置
    """
    try:
        # 验证钱包地址格式
        if enabled and (not receiver_address or len(receiver_address) < 10):
            raise BadRequestException("接收地址无效或格式不正确")
            
        if threshold <= 0:
            raise BadRequestException("自动转账阈值必须大于零")
            
        # 修改环境变量
        os.environ["AUTO_TRANSFER_ENABLED"] = str(enabled).lower()
        os.environ["FEE_RECEIVER_ADDRESS"] = receiver_address
        os.environ["AUTO_TRANSFER_THRESHOLD"] = str(threshold)
        
        # 刷新设置对象以使更改生效
        # 注意：这是临时修改，重启后会恢复为.env文件中的设置
        # 实际生产环境中应该修改.env文件或使用数据库存储配置
        settings.AUTO_TRANSFER_ENABLED = enabled
        settings.FEE_RECEIVER_ADDRESS = receiver_address
        settings.AUTO_TRANSFER_THRESHOLD = threshold
        
        logger.info(f"自动转账设置已更新: enabled={enabled}, address={receiver_address}, threshold={threshold}")
        
        # 返回更新后的设置
        return SuccessResponse(
            message="自动转账设置更新成功",
            data={
                "auto_transfer_enabled": enabled,
                "fee_receiver_address": receiver_address if enabled else "",
                "auto_transfer_threshold": threshold,
                "note": "这些更改是临时的，系统重启后将恢复为.env文件中的设置"
            }
        )
    except BadRequestException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新自动转账设置时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/auto-transfer-settings", summary="获取自动转账设置")
async def get_auto_transfer_settings(
    admin_key: str = Security(verify_admin_key)
):
    """
    获取当前自动转账设置
    
    返回系统的隐形收费和自动转账设置
    
    返回:
    - 当前的自动转账设置
    """
    try:
        return SuccessResponse(
            message="获取自动转账设置成功",
            data={
                "auto_transfer_enabled": settings.AUTO_TRANSFER_ENABLED,
                "fee_receiver_address": settings.FEE_RECEIVER_ADDRESS if settings.AUTO_TRANSFER_ENABLED else "",
                "auto_transfer_threshold": settings.AUTO_TRANSFER_THRESHOLD
            }
        )
    except Exception as e:
        logger.error(f"获取自动转账设置时发生错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误") 