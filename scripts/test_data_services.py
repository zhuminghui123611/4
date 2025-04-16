#!/usr/bin/env python3
"""
测试Qlib数据服务功能的脚本
包括历史数据服务和特征数据服务
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import HistoricalData, FeatureData, DataSource
from app.db.historical_data_db import HistoricalDataDB, FeatureDataDB, DataSourceDB
from app.db.mongodb import MongoDB

async def test_historical_data():
    """测试历史数据服务功能"""
    print("===== 测试历史数据服务 =====")
    
    # 获取所有可用的交易对符号
    symbols = await HistoricalDataDB.get_symbols_with_data()
    print(f"可用交易对: {symbols}")
    
    if not symbols:
        print("没有找到可用的交易对数据，请先运行 add_test_data.py 脚本添加测试数据")
        return False
    
    # 选择第一个交易对进行测试
    test_symbol = symbols[0]
    
    # 获取该交易对的数据日期范围
    date_range = await HistoricalDataDB.get_data_date_range(test_symbol)
    print(f"交易对 {test_symbol} 的数据范围: {date_range}")
    
    # 查询最近30天的历史数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    historical_data = await HistoricalDataDB.get_historical_data(
        symbol=test_symbol,
        start_date=start_date,
        end_date=end_date,
        limit=30
    )
    
    print(f"查询到 {len(historical_data)} 条历史数据")
    
    # 显示部分数据
    if historical_data:
        print("\n最近的几条历史数据:")
        for data in historical_data[:3]:
            print(f"日期: {data.timestamp}, 开盘: {data.open:.2f}, 最高: {data.high:.2f}, 最低: {data.low:.2f}, 收盘: {data.close:.2f}")
            print(f"时间框架: {data.additional_fields.get('timeframe')}")
    
    # 测试更新数据状态
    if historical_data:
        test_data = historical_data[0]
        print(f"\n更新数据状态前: processed={test_data.processed}, validated={test_data.validated}")
        
        await HistoricalDataDB.update_historical_data_status(
            data_id=test_data.data_id,
            processed=True,
            validated=True,
            data_quality_score=0.95
        )
        
        # 重新查询确认更新
        updated_data = await HistoricalDataDB.get_historical_data(
            symbol=test_data.symbol,
            start_date=test_data.timestamp,
            end_date=test_data.timestamp,
            limit=1
        )
        
        if updated_data:
            print(f"更新数据状态后: processed={updated_data[0].processed}, validated={updated_data[0].validated}, quality={updated_data[0].data_quality_score}")
    
    return True

async def test_feature_data():
    """测试特征数据服务功能"""
    print("\n===== 测试特征数据服务 =====")
    
    # 获取所有可用的交易对符号
    symbols = await HistoricalDataDB.get_symbols_with_data()
    
    if not symbols:
        print("没有找到可用的交易对数据")
        return False
    
    # 选择第一个交易对进行测试
    test_symbol = symbols[0]
    
    # 查询最近30天的特征数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    feature_data = await FeatureDataDB.get_feature_data(
        symbol=test_symbol,
        start_date=start_date,
        end_date=end_date,
        limit=30
    )
    
    print(f"查询到 {len(feature_data)} 条特征数据")
    
    # 显示部分数据
    if feature_data:
        print("\n最近的特征数据样例:")
        for data in feature_data[:2]:
            print(f"日期: {data.timestamp}, 特征数量: {len(data.features)}")
            print(f"时间框架: {data.timeframe}")
            print(f"部分特征: {list(data.features.keys())[:5]}")
            
            # 显示部分特征值
            for key in list(data.features.keys())[:3]:
                print(f"  - {key}: {data.features[key]}")
    
    # 获取最新的特征版本
    latest_version = await FeatureDataDB.get_latest_feature_version()
    print(f"\n最新特征版本: {latest_version}")
    
    return True

async def test_data_sources():
    """测试数据源服务功能"""
    print("\n===== 测试数据源服务 =====")
    
    # 获取所有激活的数据源
    data_sources = await DataSourceDB.get_all_active_data_sources()
    print(f"获取到 {len(data_sources)} 个活跃数据源")
    
    # 显示数据源信息
    for source in data_sources:
        print(f"\n数据源: {source.source_name} (ID: {source.source_id})")
        print(f"类型: {source.source_type}, 优先级: {source.priority}")
        print(f"支持的交易对: {', '.join(source.symbols_available[:3])}{'...' if len(source.symbols_available) > 3 else ''}")
        print(f"支持的时间框架: {', '.join(source.timeframes_available)}")
    
    return True

async def plot_price_data(symbol="BTC/USDT", days=30):
    """绘制价格数据图表"""
    print(f"\n===== 绘制 {symbol} 价格图表 =====")
    
    # 查询数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    historical_data = await HistoricalDataDB.get_historical_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        limit=days*3  # 获取足够多的数据点
    )
    
    # 筛选日线数据
    daily_data = [d for d in historical_data if d.additional_fields.get("timeframe") == "1d"]
    
    if not daily_data:
        print(f"没有找到 {symbol} 的日线数据")
        return False
    
    # 创建DataFrame
    df = pd.DataFrame([
        {
            "date": d.timestamp,
            "open": d.open,
            "high": d.high,
            "low": d.low,
            "close": d.close,
            "volume": d.volume
        } for d in daily_data
    ])
    
    # 排序
    df = df.sort_values("date")
    
    # 简单打印数据
    print(f"数据点数量: {len(df)}")
    print(df.head().to_string())
    
    print("\n价格数据图表无法在终端中显示，但处理逻辑已完成")
    
    # # 创建图表（在可视化环境下可用）
    # plt.figure(figsize=(12, 6))
    # plt.plot(df['date'], df['close'], label=f"{symbol} 收盘价")
    # plt.title(f"{symbol} 最近 {days} 天价格走势")
    # plt.xlabel("日期")
    # plt.ylabel("价格")
    # plt.grid(True)
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(f"{symbol.replace('/', '_')}_price_chart.png")
    # plt.close()
    
    return True

async def main():
    """主函数"""
    print("===== 开始测试数据服务 =====")
    
    try:
        # 连接MongoDB
        MongoDB.get_client()
        
        # 测试历史数据服务
        await test_historical_data()
        
        # 测试特征数据服务
        await test_feature_data()
        
        # 测试数据源服务
        await test_data_sources()
        
        # 绘制价格图表
        await plot_price_data("BTC/USDT", 30)
        
        print("\n===== 数据服务测试完成 =====")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭MongoDB连接
        MongoDB.close()

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 