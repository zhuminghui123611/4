#!/usr/bin/env python3
"""
测试历史数据服务和模型服务的脚本
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import json

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.mongodb import MongoDB
from app.services.historical_data_service import HistoricalDataService
from app.services.feature_data_service import FeatureDataService
from app.services.model_service import ModelService

async def test_historical_data_service():
    """测试历史数据服务"""
    print("\n===== 测试历史数据服务 =====")
    try:
        # 创建并初始化服务
        service = HistoricalDataService()
        await service.initialize()
        
        print("历史数据服务初始化成功!")
        
        # 获取可用交易对
        symbols = await service.get_available_symbols()
        print(f"可用交易对: {', '.join(symbols[:5])}...等共{len(symbols)}个")
        
        # 选择一个交易对进行测试
        test_symbol = "BTC/USDT"
        print(f"\n测试交易对: {test_symbol}")
        
        # 获取数据覆盖情况
        coverage = await service.get_data_coverage(test_symbol)
        print(f"数据覆盖情况: {json.dumps(coverage, indent=2, default=str)}")
        
        # 同步历史数据
        print("\n同步历史数据...")
        sync_result = await service.sync_historical_data(
            symbol=test_symbol,
            start_date=(datetime.now() - timedelta(days=30)).isoformat(),
            force_update=True
        )
        print(f"同步结果: {json.dumps(sync_result, indent=2, default=str)}")
        
        # 获取历史数据
        print("\n获取历史数据...")
        data = await service.get_historical_data(
            symbol=test_symbol,
            start_date=(datetime.now() - timedelta(days=7)).isoformat(),
            limit=5
        )
        print(f"获取到 {len(data)} 条历史数据，示例:")
        for i, record in enumerate(data[:3]):
            print(f"{i+1}. {record['timestamp']} - Open: {record['open']}, Close: {record['close']}")
        
        return True
    except Exception as e:
        print(f"测试历史数据服务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_feature_data_service():
    """测试特征数据服务"""
    print("\n===== 测试特征数据服务 =====")
    try:
        # 创建并初始化服务
        service = FeatureDataService()
        await service.initialize()
        
        print("特征数据服务初始化成功!")
        
        # 获取可用特征
        features = await service.get_available_features()
        print("可用特征类型:")
        for feature_type, feature_list in features.items():
            print(f"- {feature_type}: {', '.join(feature_list[:3])}...等共{len(feature_list)}个")
        
        # 选择一个交易对进行测试
        test_symbol = "BTC/USDT"
        test_timeframe = "1d"
        print(f"\n测试交易对: {test_symbol}, 时间框架: {test_timeframe}")
        
        # 处理特征数据
        print("\n处理特征数据...")
        process_result = await service.process_features(
            symbol=test_symbol,
            timeframe=test_timeframe,
            feature_types=["basic", "technical"],
            start_date=(datetime.now() - timedelta(days=60)).isoformat(),
            refresh=True
        )
        print(f"处理结果: {json.dumps(process_result, indent=2, default=str)}")
        
        # 获取特征数据
        print("\n获取特征数据...")
        data = await service.get_feature_data(
            symbol=test_symbol,
            timeframe=test_timeframe,
            start_date=(datetime.now() - timedelta(days=7)).isoformat(),
            limit=5
        )
        print(f"获取到 {len(data)} 条特征数据，示例:")
        for i, record in enumerate(data[:2]):
            print(f"{i+1}. {record['timestamp']} - 特征数量: {len(record['features'])}")
            print(f"   示例特征: {list(record['features'].items())[:3]}")
        
        return True
    except Exception as e:
        print(f"测试特征数据服务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_model_service():
    """测试模型服务"""
    print("\n===== 测试模型服务 =====")
    try:
        # 创建并初始化服务
        service = ModelService()
        await service.initialize()
        
        print("模型服务初始化成功!")
        
        # 获取可用模型
        models = await service.get_available_models()
        print(f"可用模型: {len(models)} 个")
        for i, model in enumerate(models[:3]):
            print(f"{i+1}. {model['model_name']} ({model['model_id']})")
        
        # 如果没有可用模型，训练一个新模型
        if not models:
            print("\n训练新模型...")
            
            # 选择一个交易对和特征进行测试
            test_symbol = "BTC/USDT"
            test_timeframe = "1d"
            test_features = ["return_1d", "return_5d", "volatility_10d", "rsi_14", "sma_50", "sma_200"]
            
            # 训练模型
            train_result = await service.train_model({
                "symbol": test_symbol,
                "model_name": "测试价格方向预测模型",
                "model_type": "random_forest",
                "timeframe": test_timeframe,
                "features": test_features,
                "target": "price_direction",
                "target_horizon": 5,
                "hyperparameters": {
                    "n_estimators": 100,
                    "max_depth": 5
                },
                "notes": "测试训练模型"
            })
            print(f"训练结果: {json.dumps(train_result, indent=2, default=str)}")
            
            # 使用刚训练的模型ID
            test_model_id = train_result["model_id"]
        else:
            # 使用第一个可用模型
            test_model_id = models[0]["model_id"]
        
        print(f"\n使用模型进行预测: {test_model_id}")
        
        # 进行预测
        prediction_result = await service.predict({
            "model_id": test_model_id,
            "latest": True
        })
        print(f"预测结果: {json.dumps(prediction_result, indent=2, default=str)}")
        
        # 评估模型
        print("\n评估模型...")
        evaluation_result = await service.evaluate_model(
            model_id=test_model_id,
            evaluation_period={
                "start": (datetime.now() - timedelta(days=30)).isoformat(),
                "end": datetime.now().isoformat()
            }
        )
        print(f"评估结果: {json.dumps(evaluation_result, indent=2, default=str)}")
        
        return True
    except Exception as e:
        print(f"测试模型服务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("===== 历史数据和模型服务测试脚本 =====")
    
    # 测试MongoDB连接
    try:
        client = MongoDB.get_client()
        print("MongoDB连接成功!")
    except Exception as e:
        print(f"MongoDB连接失败: {str(e)}")
        return
    
    # 测试历史数据服务
    if not await test_historical_data_service():
        print("历史数据服务测试失败，跳过后续测试")
        return
    
    # 测试特征数据服务
    if not await test_feature_data_service():
        print("特征数据服务测试失败，跳过后续测试")
        return
    
    # 测试模型服务
    if not await test_model_service():
        print("模型服务测试失败")
        return
    
    # 关闭连接
    MongoDB.close()
    print("\n===== 测试完成 =====")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main()) 