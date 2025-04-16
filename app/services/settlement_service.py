import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from decimal import Decimal

from app.core.exceptions import BadRequestException
from app.exceptions.service_exceptions import ServiceUnavailableException
from app.core.config import settings
from app.db.settlement_db import SettlementDB
from app.db.models import SettlementRecord, TransferRecord, FeeBalance

logger = logging.getLogger(__name__)

class SettlementService:
    """
    结算服务类，负责处理收取的交易费用并将其分配到指定账户
    """
    
    def __init__(self):
        """初始化结算服务"""
        # 定义费用分配比例
        self.fee_distribution = {
            "platform": 0.7,         # 平台账户获得70%的费用
            "liquidity_providers": 0.2,  # 流动性提供者获得20%的费用
            "risk_reserve": 0.1      # 风险储备金获得10%的费用
        }
        
        # 各账户的费用余额 - 将从数据库加载
        self.fee_balances = {
            "platform": 0.0,
            "liquidity_providers": 0.0,
            "risk_reserve": 0.0
        }
        
        # 累积未转账的费用金额 (按币种) - 将从数据库加载
        self.pending_transfers = {}
        
        logger.info("SettlementService initialized with fee_distribution={}".format(self.fee_distribution))
        
        # 记录自动转账设置
        if settings.AUTO_TRANSFER_ENABLED:
            if settings.FEE_RECEIVER_ADDRESS:
                logger.info(f"Auto-transfer enabled. Receiver address: {settings.FEE_RECEIVER_ADDRESS}")
                logger.info(f"Auto-transfer threshold: {settings.AUTO_TRANSFER_THRESHOLD}")
            else:
                logger.warning("Auto-transfer enabled but receiver address is not set")
        else:
            logger.info("Auto-transfer disabled")
    
    async def process_fee(self, 
                    fee_amount: float, 
                    currency: str, 
                    order_id: str, 
                    user_id: Optional[str] = None, 
                    fee_type: str = "trading") -> Dict[str, Any]:
        """
        处理收取的费用并将其分配到相应账户
        
        参数:
            fee_amount: 费用金额
            currency: 费用币种
            order_id: 关联的订单ID
            user_id: 用户ID（可选）
            fee_type: 费用类型（交易、提现等）
            
        返回:
            包含费用分配详情的字典
        """
        try:
            if fee_amount <= 0:
                raise BadRequestException("费用金额必须大于零")
                
            # 创建结算记录
            settlement_id = f"stl_{datetime.now().strftime('%Y%m%d%H%M%S')}_{order_id[-8:]}"
            
            receiver_address = settings.FEE_RECEIVER_ADDRESS
            auto_transfer = settings.AUTO_TRANSFER_ENABLED and receiver_address
            
            # 如果启用了自动转账且有接收地址，处理方式不同
            if auto_transfer:
                # 所有费用直接转入指定地址，不再分配到不同账户
                distribution = {"direct_transfer": fee_amount}
                
                # 累积待转账金额
                if currency not in self.pending_transfers:
                    self.pending_transfers[currency] = 0
                self.pending_transfers[currency] += fee_amount
                
                transfer_status = "pending"
                auto_transferred = False
                
                # 检查是否达到转账阈值
                if self.pending_transfers[currency] >= settings.AUTO_TRANSFER_THRESHOLD:
                    # 尝试执行转账
                    transfer_result = await self._transfer_fee_to_address(
                        amount=self.pending_transfers[currency],
                        currency=currency,
                        destination=receiver_address
                    )
                    
                    if transfer_result["success"]:
                        # 转账成功，清零待转金额
                        auto_transferred = True
                        transfer_status = "completed"
                        self.pending_transfers[currency] = 0
                        logger.info(f"Auto transfer completed: {transfer_result['transfer_id']} - {transfer_result['amount']} {currency} to {receiver_address}")
                    else:
                        # 转账失败，继续累积
                        transfer_status = "failed"
                        logger.error(f"Auto transfer failed: {fee_amount} {currency} to {receiver_address}")
                
                # 创建结算记录
                record = SettlementRecord(
                    settlement_id=settlement_id,
                    timestamp=datetime.now(),
                    order_id=order_id,
                    user_id=user_id,
                    fee_amount=fee_amount,
                    currency=currency,
                    fee_type=fee_type,
                    distribution=distribution,
                    receiver_address=receiver_address,
                    auto_transfer_pending=self.pending_transfers[currency],
                    auto_transferred=auto_transferred,
                    transfer_status=transfer_status,
                    status="completed" if auto_transferred else "pending_transfer"
                )
                
                # 保存到数据库
                await SettlementDB.save_settlement_record(record)
                
                # 更新费用余额
                fee_balance = FeeBalance(
                    balances=self.fee_balances,
                    pending_transfers=self.pending_transfers,
                    auto_transfer_enabled=True,
                    receiver_address=receiver_address
                )
                await SettlementDB.update_fee_balances(fee_balance)
                
                if auto_transferred:
                    logger.info(f"Fee auto transferred: settlement_id={settlement_id}, fee_amount={fee_amount} {currency}, destination={receiver_address}")
                else:
                    logger.info(f"Fee pending for auto transfer: settlement_id={settlement_id}, fee_amount={fee_amount} {currency}, accumulated={self.pending_transfers[currency]} {currency}")
                
                return {
                    "settlement_id": settlement_id,
                    "fee_amount": fee_amount,
                    "currency": currency,
                    "receiver_address": receiver_address,
                    "auto_transferred": auto_transferred,
                    "pending_amount": self.pending_transfers[currency],
                    "timestamp": record.timestamp.isoformat()
                }
            else:
                # 原有的费用分配逻辑
                # 计算各账户应得的份额
                distribution = {}
                for account, ratio in self.fee_distribution.items():
                    amount = fee_amount * ratio
                    distribution[account] = amount
                    self.fee_balances[account] += amount
                
                # 创建结算记录
                record = SettlementRecord(
                    settlement_id=settlement_id,
                    timestamp=datetime.now(),
                    order_id=order_id,
                    user_id=user_id,
                    fee_amount=fee_amount,
                    currency=currency,
                    fee_type=fee_type,
                    distribution=distribution,
                    status="completed"
                )
                
                # 保存到数据库
                await SettlementDB.save_settlement_record(record)
                
                # 更新费用余额
                fee_balance = FeeBalance(
                    balances=self.fee_balances,
                    auto_transfer_enabled=False
                )
                await SettlementDB.update_fee_balances(fee_balance)
                
                logger.info(f"Fee settlement completed: settlement_id={settlement_id}, fee_amount={fee_amount} {currency}")
                
                return {
                    "settlement_id": settlement_id,
                    "fee_amount": fee_amount,
                    "currency": currency,
                    "distribution": distribution,
                    "timestamp": record.timestamp.isoformat()
                }
                
        except BadRequestException as e:
            logger.warning(f"Bad request in process_fee: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing fee: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("处理费用时发生错误")
    
    async def _transfer_fee_to_address(self, amount: float, currency: str, destination: str) -> Dict[str, Any]:
        """
        将费用转账到指定地址
        
        这里需要集成实际的区块链钱包转账逻辑，例如:
        - 以太坊转账
        - 交易所API转账
        - 其他区块链转账
        
        参数:
            amount: 转账金额
            currency: 币种
            destination: 目标钱包地址
            
        返回:
            转账结果
        """
        try:
            # TODO: 集成实际的转账API
            # 示例：如果是以太坊转账，需要集成 Web3.py
            # 如果是交易所内部转账，需要集成交易所API
            
            # 此处为模拟实现，实际项目中请替换为真实的转账逻辑
            transfer_id = f"txn_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # 记录转账信息
            transfer_record = {
                "transfer_id": transfer_id,
                "timestamp": datetime.now().isoformat(),
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "status": "completed",
                "tx_hash": f"0x{transfer_id}123456789abcdef",  # 模拟交易哈希
                "network_fee": 0.001,  # 模拟网络费用
            }
            
            # 添加到转账记录
            await SettlementDB.save_transfer_record(transfer_record)
            
            logger.info(f"[模拟转账] 转账ID: {transfer_id}, 金额: {amount} {currency} 到地址: {destination}")
            
            # 返回转账结果
            return {
                "success": True,
                "transfer_id": transfer_id,
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "timestamp": transfer_record["timestamp"],
                "tx_hash": transfer_record["tx_hash"]
            }
            
        except Exception as e:
            logger.error(f"转账失败: {str(e)}", exc_info=True)
            
            # 记录失败的转账尝试
            failed_transfer = {
                "transfer_id": f"failed_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "status": "failed",
                "error": str(e)
            }
            await SettlementDB.save_transfer_record(failed_transfer)
            
            # 返回失败结果
            return {
                "success": False,
                "error": str(e),
                "amount": amount,
                "currency": currency,
                "destination": destination,
                "timestamp": datetime.now().isoformat()
            }
    
    async def withdraw_platform_fee(self, amount: float, currency: str, destination: str) -> Dict[str, Any]:
        """
        从平台费用账户提取费用到指定目的地
        
        参数:
            amount: 提取金额
            currency: 币种
            destination: 目的地地址或账户
            
        返回:
            提取操作的结果
        """
        try:
            # 如果启用了自动转账，平台账户提款方式可能需要调整
            if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                # 当启用自动转账时，管理员仍可以执行特殊的手动提款
                logger.warning(f"Manual withdrawal requested while auto-transfer is enabled: {amount} {currency} to {destination}")
                
            if amount <= 0:
                raise BadRequestException("提取金额必须大于零")
                
            if amount > self.fee_balances["platform"]:
                raise BadRequestException(f"余额不足。当前余额: {self.fee_balances['platform']} {currency}")
            
            # 减少平台账户余额
            self.fee_balances["platform"] -= amount
            
            # 创建提取记录
            withdraw_id = f"wdr_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            withdraw_record = {
                "withdraw_id": withdraw_id,
                "timestamp": datetime.now().isoformat(),
                "amount": amount,
                "currency": currency,
                "source": "platform",
                "destination": destination,
                "status": "completed"
            }
            
            logger.info(f"Platform fee withdrawn: withdraw_id={withdraw_id}, amount={amount} {currency}, destination={destination}")
            
            return withdraw_record
            
        except BadRequestException as e:
            logger.warning(f"Bad request in withdraw_platform_fee: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error withdrawing platform fee: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("提取平台费用时发生错误")
    
    async def distribute_liquidity_provider_fees(self, distribution_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将流动性提供者费用分配给多个流动性提供者
        
        参数:
            distribution_plan: 分配计划，包含流动性提供者ID和分配比例
            
        返回:
            分配操作的结果
        """
        try:
            # 如果启用了自动转账，流动性提供者分配方式可能需要调整
            if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                logger.warning("Liquidity provider fee distribution requested while auto-transfer is enabled")
            
            total_ratio = sum(provider["ratio"] for provider in distribution_plan)
            if not 0.99 <= total_ratio <= 1.01:  # 允许有小数点误差
                raise BadRequestException("分配比例总和必须为1.0")
            
            available_amount = self.fee_balances["liquidity_providers"]
            if available_amount <= 0:
                raise BadRequestException("没有可分配的流动性提供者费用")
            
            # 执行分配
            distribution_id = f"dist_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            distributions = []
            
            for provider in distribution_plan:
                provider_id = provider["provider_id"]
                ratio = provider["ratio"]
                amount = available_amount * ratio
                
                distributions.append({
                    "provider_id": provider_id,
                    "amount": amount,
                    "ratio": ratio
                })
            
            # 清空流动性提供者账户
            self.fee_balances["liquidity_providers"] = 0.0
            
            logger.info(f"Liquidity provider fees distributed: distribution_id={distribution_id}, total_amount={available_amount}")
            
            return {
                "distribution_id": distribution_id,
                "timestamp": datetime.now().isoformat(),
                "total_amount": available_amount,
                "distributions": distributions,
                "status": "completed"
            }
            
        except BadRequestException as e:
            logger.warning(f"Bad request in distribute_liquidity_provider_fees: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error distributing liquidity provider fees: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("分配流动性提供者费用时发生错误")
    
    async def get_fee_balances(self) -> Dict[str, Any]:
        """
        获取各账户的费用余额
        
        返回:
            包含各账户费用余额的字典
        """
        try:
            # 从数据库获取最新的费用余额
            fee_balance = await SettlementDB.get_latest_fee_balances()
            
            if fee_balance:
                # 使用数据库记录
                result = {
                    "balances": fee_balance.balances,
                    "timestamp": fee_balance.timestamp.isoformat()
                }
                
                # 如果启用了自动转账，添加待转账金额
                if fee_balance.auto_transfer_enabled:
                    result["auto_transfer_enabled"] = True
                    result["receiver_address"] = fee_balance.receiver_address
                    result["pending_transfers"] = fee_balance.pending_transfers
            else:
                # 使用内存中的数据
                result = {
                    "balances": self.fee_balances,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 如果启用了自动转账，添加待转账金额
                if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                    result["auto_transfer_enabled"] = True
                    result["receiver_address"] = settings.FEE_RECEIVER_ADDRESS
                    result["pending_transfers"] = self.pending_transfers
            
            return result
        except Exception as e:
            logger.error(f"Error getting fee balances: {str(e)}", exc_info=True)
            # 发生错误时，返回内存中的数据
            result = {
                "balances": self.fee_balances,
                "timestamp": datetime.now().isoformat(),
                "error": "获取数据库记录失败，返回内存中的数据"
            }
            
            if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                result["auto_transfer_enabled"] = True
                result["receiver_address"] = settings.FEE_RECEIVER_ADDRESS
                result["pending_transfers"] = self.pending_transfers
                
            return result
    
    async def get_transfer_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取自动转账记录
        
        参数:
            limit: 返回记录的最大数量
            
        返回:
            转账记录列表
        """
        try:
            # 从数据库获取转账记录
            records = await SettlementDB.get_transfer_records(limit)
            
            # 将Pydantic模型转换为字典列表
            return [record.dict() for record in records]
        except Exception as e:
            logger.error(f"Error getting transfer records: {str(e)}", exc_info=True)
            # 发生错误时，返回内存中的数据
            return self.transfer_records[-limit:] if hasattr(self, 'transfer_records') and limit > 0 else []
    
    async def get_settlement_records(self, 
                               start_date: Optional[str] = None, 
                               end_date: Optional[str] = None, 
                               limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取结算记录
        
        参数:
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            limit: 返回记录的最大数量
            
        返回:
            结算记录列表
        """
        try:
            # 转换日期字符串为datetime对象
            start_datetime = datetime.fromisoformat(start_date) if start_date else None
            end_datetime = datetime.fromisoformat(end_date) if end_date else None
            
            # 从数据库获取结算记录
            records = await SettlementDB.get_settlement_records(start_datetime, end_datetime, limit)
            
            # 将Pydantic模型转换为字典列表
            return [record.dict() for record in records]
        except Exception as e:
            logger.error(f"Error retrieving settlement records: {str(e)}", exc_info=True)
            
            # 发生错误时，尝试返回内存中的数据
            try:
                filtered_records = getattr(self, 'settlement_records', [])
                
                # 根据日期过滤
                if start_date:
                    start_datetime = datetime.fromisoformat(start_date)
                    filtered_records = [r for r in filtered_records if datetime.fromisoformat(r["timestamp"]) >= start_datetime]
                
                if end_date:
                    end_datetime = datetime.fromisoformat(end_date)
                    filtered_records = [r for r in filtered_records if datetime.fromisoformat(r["timestamp"]) <= end_datetime]
                
                # 限制记录数量
                return filtered_records[-limit:] if limit > 0 else filtered_records
            except:
                logger.error("Failed to return in-memory records as fallback", exc_info=True)
                raise ServiceUnavailableException("获取结算记录时发生错误")
    
    async def update_fee_distribution(self, new_distribution: Dict[str, float]) -> Dict[str, Any]:
        """
        更新费用分配比例
        
        参数:
            new_distribution: 新的费用分配比例
            
        返回:
            更新后的费用分配比例
        """
        try:
            # 如果启用了自动转账，费用分配比例可能不再重要
            if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                logger.warning("Fee distribution update requested while auto-transfer is enabled")
            
            # 验证新的分配比例
            total_ratio = sum(new_distribution.values())
            if not 0.99 <= total_ratio <= 1.01:  # 允许有小数点误差
                raise BadRequestException("分配比例总和必须为1.0")
            
            # 验证所有必要的账户都存在
            required_accounts = {"platform", "liquidity_providers", "risk_reserve"}
            if not required_accounts.issubset(set(new_distribution.keys())):
                raise BadRequestException(f"分配比例必须包含所有必要的账户: {required_accounts}")
            
            # 更新分配比例
            self.fee_distribution = new_distribution
            
            logger.info(f"Fee distribution updated: {new_distribution}")
            
            return {
                "fee_distribution": self.fee_distribution,
                "timestamp": datetime.now().isoformat()
            }
            
        except BadRequestException as e:
            logger.warning(f"Bad request in update_fee_distribution: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating fee distribution: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("更新费用分配比例时发生错误")
    
    async def generate_settlement_report(self, 
                                   period: str, 
                                   start_date: str, 
                                   end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        生成结算报告
        
        参数:
            period: 报告周期（daily, weekly, monthly）
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            
        返回:
            结算报告
        """
        try:
            # 获取指定时间段的结算记录
            records = await self.get_settlement_records(start_date, end_date, limit=0)
            
            if not records:
                report = {
                    "report_id": f"rep_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "period": period,
                    "start_date": start_date,
                    "end_date": end_date or datetime.now().isoformat(),
                    "total_fee_amount": 0,
                    "fee_by_currency": {},
                    "fee_by_type": {},
                    "record_count": 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 对于自动转账，添加相关信息
                if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                    report["auto_transfer_enabled"] = True
                    report["receiver_address"] = settings.FEE_RECEIVER_ADDRESS
                    report["pending_transfers"] = self.pending_transfers
                else:
                    report["distribution_summary"] = {account: 0 for account in self.fee_distribution.keys()}
                
                return report
            
            # 计算汇总数据
            total_fee_amount = sum(r["fee_amount"] for r in records)
            
            # 按币种汇总
            fee_by_currency = {}
            for r in records:
                currency = r["currency"]
                if currency not in fee_by_currency:
                    fee_by_currency[currency] = 0
                fee_by_currency[currency] += r["fee_amount"]
            
            # 按类型汇总
            fee_by_type = {}
            for r in records:
                fee_type = r["fee_type"]
                if fee_type not in fee_by_type:
                    fee_by_type[fee_type] = 0
                fee_by_type[fee_type] += r["fee_amount"]
            
            report = {
                "report_id": f"rep_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "period": period,
                "start_date": start_date,
                "end_date": end_date or datetime.now().isoformat(),
                "total_fee_amount": total_fee_amount,
                "fee_by_currency": fee_by_currency,
                "fee_by_type": fee_by_type,
                "record_count": len(records),
                "timestamp": datetime.now().isoformat()
            }
            
            # 根据转账模式添加不同的汇总数据
            if settings.AUTO_TRANSFER_ENABLED and settings.FEE_RECEIVER_ADDRESS:
                # 自动转账模式：汇总已转账和待转账金额
                auto_transferred_records = [r for r in records if r.get("auto_transferred", False)]
                pending_records = [r for r in records if not r.get("auto_transferred", False)]
                
                transferred_amount = sum(r["fee_amount"] for r in auto_transferred_records)
                pending_amount = sum(r["fee_amount"] for r in pending_records)
                
                report["auto_transfer_enabled"] = True
                report["receiver_address"] = settings.FEE_RECEIVER_ADDRESS
                report["transferred_amount"] = transferred_amount
                report["pending_amount"] = pending_amount
                report["pending_transfers"] = self.pending_transfers
                
                # 获取转账记录
                transfer_records = await self.get_transfer_records(limit=0)
                successful_transfers = [r for r in transfer_records if r["status"] == "completed"]
                failed_transfers = [r for r in transfer_records if r["status"] == "failed"]
                
                report["transfer_summary"] = {
                    "total_transfers": len(transfer_records),
                    "successful_transfers": len(successful_transfers),
                    "failed_transfers": len(failed_transfers),
                    "total_transferred": sum(r["amount"] for r in successful_transfers)
                }
            else:
                # 传统模式：按分配账户汇总
                distribution_summary = {account: 0 for account in self.fee_distribution.keys()}
                for r in records:
                    if "distribution" in r:
                        for account, amount in r["distribution"].items():
                            if account in distribution_summary:
                                distribution_summary[account] += amount
                
                report["distribution_summary"] = distribution_summary
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating settlement report: {str(e)}", exc_info=True)
            raise ServiceUnavailableException("生成结算报告时发生错误") 