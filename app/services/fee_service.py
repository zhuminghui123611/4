import logging
from typing import Dict, List, Any, Optional, Union
from decimal import Decimal
from datetime import datetime

from app.models.trading import (
    FeeType, 
    OrderSide, 
    OrderType, 
    OrderStatus, 
    CreateOrderRequest, 
    OrderResponse,
    TradingPlatform,
    FeeDetail,
    FeeCalculationResponse
)
from app.core.exceptions import BadRequestException
from app.core.config import settings
from app.services.exchange_service import ExchangeService
from app.exceptions.service_exceptions import ServiceUnavailableException
from app.services.settlement_service import SettlementService

logger = logging.getLogger(__name__)

class FeeService:
    """
    费用服务类，负责计算交易费用
    支持基于滑点的费用和固定路由费用
    """
    
    def __init__(self):
        # 从环境变量加载默认费率
        self.default_slippage_fee_rate = float(settings.DEFAULT_SLIPPAGE_FEE)
        self.fixed_routing_fee = float(settings.FIXED_ROUTING_FEE)
        
        # 用户等级与折扣的映射
        self.tier_discounts = {
            "basic": 1.0,      # 无折扣
            "silver": 0.9,     # 10% 折扣
            "gold": 0.75,      # 25% 折扣
            "platinum": 0.5    # 50% 折扣
        }
        
        # 平台类型与费率倍数的映射
        self.platform_multipliers = {
            "CEX": 1.0,        # 中心化交易所基准费率
            "DEX": 1.5,        # 去中心化交易所费率较高 
            "P2P": 0.8         # 点对点交易费率较低
        }
        
        # 初始化结算服务
        self.settlement_service = SettlementService()
        
        # 检查是否启用自动转账
        self.auto_transfer_enabled = settings.AUTO_TRANSFER_ENABLED
        self.fee_receiver_address = settings.FEE_RECEIVER_ADDRESS
        
        log_message = f"FeeService initialized with default_slippage_fee_rate={self.default_slippage_fee_rate}, fixed_routing_fee={self.fixed_routing_fee}"
        if self.auto_transfer_enabled and self.fee_receiver_address:
            log_message += f", auto_transfer_enabled=True, receiver_address={self.fee_receiver_address}"
        
        logger.info(log_message)

    async def calculate_fees(
        self,
        symbol: str,
        amount: float,
        price: float,
        platform_type: str = "CEX",
        custom_slippage_rate: Optional[float] = None,
        custom_routing_fee: Optional[float] = None,
        user_tier: str = "basic"
    ) -> Dict[str, Union[float, str]]:
        """
        计算交易费用
        
        参数:
            symbol: 交易对符号 (例如 BTC/USDT)
            amount: 交易数量
            price: 交易价格
            platform_type: 平台类型 (CEX, DEX, P2P)
            custom_slippage_rate: 自定义滑点率 (可选)
            custom_routing_fee: 自定义路由费 (可选)
            user_tier: 用户等级 (basic, silver, gold, platinum)
            
        返回:
            包含费用详情的字典
        """
        try:
            # 验证输入参数
            if amount <= 0 or price <= 0:
                raise BadRequestException("交易数量和价格必须大于零")
                
            if platform_type not in self.platform_multipliers:
                raise BadRequestException(f"不支持的平台类型: {platform_type}")
                
            if user_tier not in self.tier_discounts:
                raise BadRequestException(f"不支持的用户等级: {user_tier}")
                
            # 解析交易对以获取基础代币
            base_token = self._parse_base_token(symbol)
            
            # 计算交易的美元价值
            usd_value = amount * price
            
            # 计算滑点费用
            slippage_rate = custom_slippage_rate if custom_slippage_rate is not None else self.default_slippage_fee_rate
            slippage_fee = self._calculate_slippage_fee(
                usd_value, 
                slippage_rate, 
                self.platform_multipliers[platform_type], 
                self.tier_discounts[user_tier]
            )
            
            # 计算路由费用
            routing_fee = custom_routing_fee if custom_routing_fee is not None else self.fixed_routing_fee
            routing_fee = routing_fee * self.tier_discounts[user_tier]
            
            # 计算总费用
            total_fee_usd = slippage_fee + routing_fee
            
            # 计算以基础代币表示的费用
            fee_in_token = total_fee_usd / price if price > 0 else 0
            
            # 计算有效费率
            effective_fee_rate = total_fee_usd / usd_value if usd_value > 0 else 0
            
            # 如果启用了自动转账，简化返回的费用信息
            if self.auto_transfer_enabled and self.fee_receiver_address:
                # 隐性收费模式下，返回的信息更简洁
                return {
                    "symbol": symbol,
                    "baseToken": base_token,
                    "amount": amount,
                    "price": price,
                    "estimatedUsdValue": usd_value,
                    "totalFeeUsd": total_fee_usd,
                    "feeInToken": fee_in_token,
                }
            else:
                # 传统模式下，返回完整的费用信息
                return {
                    "symbol": symbol,
                    "baseToken": base_token,
                    "amount": amount,
                    "price": price,
                    "estimatedUsdValue": usd_value,
                    "slippageFee": slippage_fee,
                    "routingFee": routing_fee,
                    "totalFeeUsd": total_fee_usd,
                    "feeInToken": fee_in_token,
                    "effectiveFeeRate": effective_fee_rate,
                    "userTier": user_tier,
                    "platformType": platform_type
                }
            
        except BadRequestException as e:
            logger.warning(f"Bad request in calculate_fees: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calculating fees: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("计算费用时发生错误")
            
    def _calculate_slippage_fee(
        self, 
        usd_value: float, 
        slippage_rate: float, 
        platform_multiplier: float, 
        tier_discount: float
    ) -> float:
        """
        计算滑点费用
        
        参数:
            usd_value: 交易的美元价值
            slippage_rate: 滑点率
            platform_multiplier: 平台类型倍数
            tier_discount: 用户等级折扣
            
        返回:
            滑点费用金额
        """
        # 基于交易规模的动态滑点调整
        scale_factor = 1.0
        if usd_value > 100000:  # 大额交易 (>$100,000)
            scale_factor = 0.8
        elif usd_value > 10000:  # 中额交易 (>$10,000)
            scale_factor = 0.9
        elif usd_value < 100:    # 小额交易 (<$100)
            scale_factor = 1.2
            
        # 计算最终滑点费率
        final_slippage_rate = slippage_rate * platform_multiplier * tier_discount * scale_factor
        
        # 计算并返回滑点费用
        return usd_value * final_slippage_rate
        
    def _parse_base_token(self, symbol: str) -> str:
        """
        从交易对符号解析基础代币
        
        参数:
            symbol: 交易对符号 (例如 BTC/USDT)
            
        返回:
            基础代币符号
        """
        try:
            # 尝试分割交易对符号
            if '/' in symbol:
                base, _ = symbol.split('/')
                return base
            return symbol
        except Exception as e:
            logger.warning(f"Error parsing base token from symbol {symbol}: {str(e)}")
            return symbol
            
    async def apply_fees_to_order(self, order: Dict[str, Any], fee_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        将费用应用到订单
        
        参数:
            order: 原始订单
            fee_details: 费用详情
            
        返回:
            包含费用信息的更新订单
        """
        try:
            if not order:
                raise BadRequestException("订单不能为空")
                
            if not fee_details:
                raise BadRequestException("费用详情不能为空")
                
            # 克隆订单以避免修改原始对象
            updated_order = order.copy()
            
            # 根据收费模式的不同，添加不同的费用信息
            if self.auto_transfer_enabled and self.fee_receiver_address:
                # 隐性收费模式 - 简化的费用信息
                updated_order["fees"] = {
                    "totalFeeUsd": fee_details.get("totalFeeUsd", 0),
                    "feeInToken": fee_details.get("feeInToken", 0)
                }
            else:
                # 传统模式 - 完整的费用信息
                updated_order["fees"] = {
                    "slippageFee": fee_details.get("slippageFee", 0),
                    "routingFee": fee_details.get("routingFee", 0),
                    "totalFeeUsd": fee_details.get("totalFeeUsd", 0),
                    "feeInToken": fee_details.get("feeInToken", 0),
                    "effectiveFeeRate": fee_details.get("effectiveFeeRate", 0)
                }
            
            # 调整订单金额以反映费用
            if "amount" in updated_order and fee_details.get("feeInToken"):
                original_amount = float(updated_order["amount"])
                fee_in_token = float(fee_details.get("feeInToken", 0))
                
                # 根据订单类型调整金额
                if updated_order.get("side") == "buy":
                    # 买入订单：减少接收的代币数量
                    updated_order["receivedAmount"] = original_amount - fee_in_token
                else:
                    # 卖出订单：减少收到的法币金额
                    if "price" in updated_order:
                        price = float(updated_order["price"])
                        fee_in_fiat = fee_in_token * price
                        updated_order["receivedFiat"] = original_amount * price - fee_in_fiat
            
            # 处理费用结算 (将费用分配到相应账户或自动转账)
            if "id" in updated_order and fee_details.get("totalFeeUsd", 0) > 0:
                user_id = updated_order.get("userId") or "anonymous"
                order_id = updated_order["id"]
                total_fee = fee_details.get("totalFeeUsd", 0)
                currency = "USD"  # 假设费用以美元计价
                
                # 调用结算服务处理费用
                settlement_result = await self.settlement_service.process_fee(
                    fee_amount=total_fee,
                    currency=currency,
                    order_id=order_id,
                    user_id=user_id,
                    fee_type="trading"
                )
                
                # 隐性收费模式下，简化结算信息
                if self.auto_transfer_enabled and self.fee_receiver_address:
                    # 简化费用结算信息
                    if "auto_transferred" in settlement_result and settlement_result["auto_transferred"]:
                        # 如果费用已自动转账，添加简单标记
                        updated_order["feeSettled"] = True
                    else:
                        # 如果费用待转账，添加简单的结算信息
                        updated_order["feeSettled"] = False
                else:
                    # 传统模式，显示完整的结算信息
                    updated_order["feeSettlement"] = {
                        "settlementId": settlement_result.get("settlement_id"),
                        "timestamp": settlement_result.get("timestamp"),
                        "distribution": settlement_result.get("distribution")
                    }
            
            updated_order["feeApplied"] = True
            updated_order["feeTimestamp"] = datetime.now().isoformat()
            
            return updated_order
            
        except BadRequestException as e:
            logger.warning(f"Bad request in apply_fees_to_order: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error applying fees to order: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("应用费用到订单时发生错误")
            
    async def get_fee_configuration(self) -> Dict[str, Any]:
        """
        获取当前费用配置
        
        返回:
            当前费用配置
        """
        config = {
            "defaultSlippageFeeRate": self.default_slippage_fee_rate,
            "fixedRoutingFee": self.fixed_routing_fee,
            "tierDiscounts": self.tier_discounts,
            "platformMultipliers": self.platform_multipliers
        }
        
        # 如果启用了自动转账，添加相关信息
        if self.auto_transfer_enabled:
            config["autoTransferEnabled"] = True
            if self.fee_receiver_address:
                # 为安全起见，可以只返回部分地址
                masked_address = self._mask_address(self.fee_receiver_address)
                config["feeReceiverAddress"] = masked_address
            config["autoTransferThreshold"] = settings.AUTO_TRANSFER_THRESHOLD
        
        return config
        
    def _mask_address(self, address: str) -> str:
        """
        掩盖钱包地址，只显示前几位和后几位
        
        参数:
            address: 完整地址
            
        返回:
            掩盖后的地址
        """
        if not address or len(address) < 10:
            return "***"
            
        # 保留前6位和后4位，中间用...替代
        return address[:6] + "..." + address[-4:]
        
    async def update_fee_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新费用配置
        
        参数:
            config: 新的费用配置
            
        返回:
            更新后的费用配置
        """
        try:
            # 如果启用了自动转账，一些配置更新可能受限制
            if self.auto_transfer_enabled and self.fee_receiver_address:
                logger.warning("Fee configuration update requested while auto-transfer is enabled")
            
            # 更新滑点费率（如果提供）
            if "defaultSlippageFeeRate" in config:
                new_rate = float(config["defaultSlippageFeeRate"])
                if new_rate < 0:
                    raise BadRequestException("默认滑点费率不能为负数")
                self.default_slippage_fee_rate = new_rate
                
            # 更新固定路由费（如果提供）
            if "fixedRoutingFee" in config:
                new_fee = float(config["fixedRoutingFee"])
                if new_fee < 0:
                    raise BadRequestException("固定路由费不能为负数")
                self.fixed_routing_fee = new_fee
                
            # 更新用户等级折扣（如果提供）
            if "tierDiscounts" in config:
                new_discounts = config["tierDiscounts"]
                for tier, discount in new_discounts.items():
                    if tier not in self.tier_discounts:
                        raise BadRequestException(f"不支持的用户等级: {tier}")
                    if discount < 0 or discount > 1:
                        raise BadRequestException(f"用户等级折扣必须在0到1之间: {tier}={discount}")
                    self.tier_discounts[tier] = float(discount)
                    
            # 更新平台类型倍数（如果提供）
            if "platformMultipliers" in config:
                new_multipliers = config["platformMultipliers"]
                for platform, multiplier in new_multipliers.items():
                    if platform not in self.platform_multipliers:
                        raise BadRequestException(f"不支持的平台类型: {platform}")
                    if multiplier < 0:
                        raise BadRequestException(f"平台倍数不能为负数: {platform}={multiplier}")
                    self.platform_multipliers[platform] = float(multiplier)
                    
            logger.info("Fee configuration updated successfully")
            
            # 返回更新后的配置
            return await self.get_fee_configuration()
            
        except BadRequestException as e:
            logger.warning(f"Bad request in update_fee_configuration: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating fee configuration: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("更新费用配置时发生错误")
            
    async def get_fee_balances(self) -> Dict[str, Any]:
        """
        获取各账户的费用余额
        
        返回:
            包含各账户费用余额的字典
        """
        return await self.settlement_service.get_fee_balances()
    
    async def get_settlement_records(self, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取结算记录
        
        参数:
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            limit: 返回记录的最大数量
            
        返回:
            结算记录列表
        """
        return await self.settlement_service.get_settlement_records(start_date, end_date, limit)
    
    async def get_transfer_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取转账记录
        
        参数:
            limit: 返回记录的最大数量
            
        返回:
            转账记录列表
        """
        if self.auto_transfer_enabled:
            return await self.settlement_service.get_transfer_records(limit)
        return []
    
    async def update_fee_distribution(self, new_distribution: Dict[str, float]) -> Dict[str, Any]:
        """
        更新费用分配比例
        
        参数:
            new_distribution: 新的费用分配比例
            
        返回:
            更新后的费用分配比例
        """
        return await self.settlement_service.update_fee_distribution(new_distribution)
    
    async def generate_settlement_report(self, period: str, start_date: str, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        生成结算报告
        
        参数:
            period: 报告周期（daily, weekly, monthly）
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            
        返回:
            结算报告
        """
        return await self.settlement_service.generate_settlement_report(period, start_date, end_date) 