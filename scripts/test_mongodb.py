#!/usr/bin/env python3
"""
测试MongoDB连接和数据存储的脚本
"""

import asyncio
import sys
import os
from datetime import datetime
import json

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongodb import MongoDB, get_collection
from app.db.models import SettlementRecord, TransferRecord, FeeBalance, model_to_dict

async def test_mongodb_connection():
    """测试MongoDB连接"""
    print("\n===== 测试MongoDB连接 =====")
    try:
        # 获取客户端连接
        client = MongoDB.get_client()
        print("MongoDB连接成功!")
        
        # 获取数据库信息
        server_info = client.server_info()
        print(f"MongoDB版本: {server_info.get('version', 'unknown')}")
        
        # 列出数据库
        databases = await client.list_database_names()
        print(f"可用数据库: {', '.join(databases)}")
        
        # 获取数据库
        db = MongoDB.get_db()
        print(f"当前数据库: {db.name}")
        
        # 列出集合
        collections = await db.list_collection_names()
        print(f"集合列表: {', '.join(collections) if collections else '无集合'}")
        
        return True
    except Exception as e:
        print(f"MongoDB连接失败: {str(e)}")
        return False
    
async def test_create_sample_data():
    """创建示例数据"""
    print("\n===== 创建示例数据 =====")
    try:
        # 创建结算记录
        settlement_record = SettlementRecord(
            settlement_id=f"stl_test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            order_id="test_order_123",
            user_id="test_user_1",
            fee_amount=10.5,
            currency="USDT",
            fee_type="trading",
            distribution={"platform": 7.35, "liquidity_providers": 2.1, "risk_reserve": 1.05},
            status="completed"
        )
        
        # 创建转账记录
        transfer_record = TransferRecord(
            transfer_id=f"txn_test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            amount=10.5,
            currency="USDT",
            destination="0x1234567890abcdef1234567890abcdef12345678",
            status="completed",
            tx_hash="0xtesthash123456789abcdef",
            network_fee=0.001
        )
        
        # 创建费用余额
        fee_balance = FeeBalance(
            balances={"platform": 100.5, "liquidity_providers": 28.7, "risk_reserve": 14.35},
            pending_transfers={"USDT": 5.75, "ETH": 0.01},
            auto_transfer_enabled=True,
            receiver_address="0x1234567890abcdef1234567890abcdef12345678"
        )
        
        # 获取集合
        settlement_collection = get_collection("settlement_records")
        transfer_collection = get_collection("transfer_records")
        balance_collection = get_collection("fee_balances")
        
        # 插入数据
        settlement_result = await settlement_collection.insert_one(model_to_dict(settlement_record))
        transfer_result = await transfer_collection.insert_one(model_to_dict(transfer_record))
        balance_result = await balance_collection.insert_one(model_to_dict(fee_balance))
        
        print(f"结算记录已插入: {settlement_result.inserted_id}")
        print(f"转账记录已插入: {transfer_result.inserted_id}")
        print(f"费用余额已插入: {balance_result.inserted_id}")
        
        return True
    except Exception as e:
        print(f"创建示例数据失败: {str(e)}")
        return False

async def test_query_data():
    """查询数据"""
    print("\n===== 查询数据 =====")
    try:
        # 获取集合
        settlement_collection = get_collection("settlement_records")
        transfer_collection = get_collection("transfer_records")
        balance_collection = get_collection("fee_balances")
        
        # 查询结算记录
        settlement_cursor = settlement_collection.find().sort("timestamp", -1).limit(5)
        settlement_records = await settlement_cursor.to_list(length=5)
        print(f"最近5条结算记录:")
        for record in settlement_records:
            record["_id"] = str(record["_id"])  # 转换ObjectId为字符串
            print(json.dumps(record, default=str, indent=2))
        
        # 查询转账记录
        transfer_cursor = transfer_collection.find().sort("timestamp", -1).limit(5)
        transfer_records = await transfer_cursor.to_list(length=5)
        print(f"\n最近5条转账记录:")
        for record in transfer_records:
            record["_id"] = str(record["_id"])  # 转换ObjectId为字符串
            print(json.dumps(record, default=str, indent=2))
        
        # 查询费用余额
        balance_cursor = balance_collection.find().sort("timestamp", -1).limit(1)
        balance_records = await balance_cursor.to_list(length=1)
        print(f"\n最新费用余额:")
        for record in balance_records:
            record["_id"] = str(record["_id"])  # 转换ObjectId为字符串
            print(json.dumps(record, default=str, indent=2))
        
        return True
    except Exception as e:
        print(f"查询数据失败: {str(e)}")
        return False

async def main():
    """主函数"""
    print("===== MongoDB测试脚本 =====")
    
    # 测试MongoDB连接
    if not await test_mongodb_connection():
        print("MongoDB连接失败，退出测试")
        return
    
    # 测试创建示例数据
    if not await test_create_sample_data():
        print("创建示例数据失败，退出测试")
        return
    
    # 测试查询数据
    if not await test_query_data():
        print("查询数据失败，退出测试")
        return
    
    # 关闭连接
    MongoDB.close()
    print("\n===== 测试完成 =====")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main()) 