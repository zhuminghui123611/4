from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pymongo
from bson.objectid import ObjectId

from app.db.mongodb import get_collection, COLLECTION_SETTLEMENT_RECORDS, COLLECTION_TRANSFER_RECORDS, COLLECTION_FEE_BALANCES
from app.db.models import SettlementRecord, TransferRecord, FeeBalance, SettlementReport, model_to_dict, dict_to_model
import logging

logger = logging.getLogger(__name__)

class SettlementDB:
    """结算数据库服务，用于处理结算和转账记录的数据库操作"""
    
    @staticmethod
    async def save_settlement_record(record: SettlementRecord) -> str:
        """
        保存结算记录
        
        参数:
            record: 结算记录模型
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection(COLLECTION_SETTLEMENT_RECORDS)
            result = collection.insert_one(model_to_dict(record))
            logger.info(f"结算记录已保存: {record.settlement_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存结算记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_settlement_records(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SettlementRecord]:
        """
        获取结算记录
        
        参数:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回记录的最大数量
            
        返回:
            结算记录列表
        """
        try:
            collection = get_collection(COLLECTION_SETTLEMENT_RECORDS)
            
            # 构建查询条件
            query = {}
            if start_date:
                query["timestamp"] = {"$gte": start_date}
            if end_date:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = end_date
                else:
                    query["timestamp"] = {"$lte": end_date}
            
            # 执行查询
            cursor = collection.find(query).sort("timestamp", pymongo.DESCENDING).limit(limit)
            
            # 转换为模型列表
            records = []
            async for doc in cursor:
                records.append(dict_to_model(SettlementRecord, doc))
            
            return records
        except Exception as e:
            logger.error(f"获取结算记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def save_transfer_record(record: TransferRecord) -> str:
        """
        保存转账记录
        
        参数:
            record: 转账记录模型
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection(COLLECTION_TRANSFER_RECORDS)
            result = collection.insert_one(model_to_dict(record))
            logger.info(f"转账记录已保存: {record.transfer_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存转账记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_transfer_records(limit: int = 100) -> List[TransferRecord]:
        """
        获取转账记录
        
        参数:
            limit: 返回记录的最大数量
            
        返回:
            转账记录列表
        """
        try:
            collection = get_collection(COLLECTION_TRANSFER_RECORDS)
            cursor = collection.find().sort("timestamp", pymongo.DESCENDING).limit(limit)
            
            records = []
            async for doc in cursor:
                records.append(dict_to_model(TransferRecord, doc))
            
            return records
        except Exception as e:
            logger.error(f"获取转账记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def update_fee_balances(fee_balance: FeeBalance) -> str:
        """
        更新费用余额
        
        参数:
            fee_balance: 费用余额模型
            
        返回:
            更新的记录ID
        """
        try:
            collection = get_collection(COLLECTION_FEE_BALANCES)
            
            # 尝试获取最新的余额记录
            latest = collection.find_one(sort=[("timestamp", pymongo.DESCENDING)])
            
            # 如果存在，则更新，否则插入新记录
            if latest:
                result = collection.update_one(
                    {"_id": latest["_id"]},
                    {"$set": model_to_dict(fee_balance)}
                )
                record_id = str(latest["_id"])
            else:
                result = collection.insert_one(model_to_dict(fee_balance))
                record_id = str(result.inserted_id)
            
            logger.info(f"费用余额已更新: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"更新费用余额失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_latest_fee_balances() -> Optional[FeeBalance]:
        """
        获取最新的费用余额
        
        返回:
            费用余额模型，如果不存在则返回None
        """
        try:
            collection = get_collection(COLLECTION_FEE_BALANCES)
            latest = collection.find_one(sort=[("timestamp", pymongo.DESCENDING)])
            
            if latest:
                return dict_to_model(FeeBalance, latest)
            return None
        except Exception as e:
            logger.error(f"获取费用余额失败: {str(e)}")
            raise
    
    @staticmethod
    async def save_settlement_report(report: SettlementReport) -> str:
        """
        保存结算报告
        
        参数:
            report: 结算报告模型
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection("settlement_reports")
            result = collection.insert_one(model_to_dict(report))
            logger.info(f"结算报告已保存: {report.report_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存结算报告失败: {str(e)}")
            raise 