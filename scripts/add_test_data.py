#!/usr/bin/env python3
"""
向MongoDB添加测试数据的脚本
包括历史数据、数据源信息和特征数据
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import uuid
import random
import numpy as np

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import HistoricalData, DataSource, FeatureData
from app.db.historical_data_db import HistoricalDataDB, DataSourceDB, FeatureDataDB
from app.db.mongodb import MongoDB

# 设置测试数据参数
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
DAYS_OF_DATA = 60  # 生成多少天的数据
TIMEFRAMES = ["1h", "4h", "1d"]

async def create_data_sources():
    """创建数据源信息"""
    print("正在创建数据源信息...")
    
    # 数据源1 - Binance
    binance_source = DataSource(
        source_id=f"src_{datetime.now().strftime('%Y%m%d%H%M%S')}_binance",
        source_name="Binance",
        source_type="exchange",
        status="active",
        priority=1,
        symbols_available=SYMBOLS,
        timeframes_available=TIMEFRAMES,
        historical_data_start=datetime(2017, 9, 1),
        update_frequency="1h",
        last_updated=datetime.now(),
        api_details={
            "base_url": "https://api.binance.com",
            "rate_limit": 1200,
            "rate_limit_period": 60
        },
        created_at=datetime.now()
    )
    
    # 数据源2 - CoinGecko
    coingecko_source = DataSource(
        source_id=f"src_{datetime.now().strftime('%Y%m%d%H%M%S')}_coingecko",
        source_name="CoinGecko",
        source_type="aggregator",
        status="active",
        priority=2,
        symbols_available=SYMBOLS,
        timeframes_available=["1d"],
        historical_data_start=datetime(2015, 1, 1),
        update_frequency="1d",
        last_updated=datetime.now(),
        api_details={
            "base_url": "https://api.coingecko.com/api/v3",
            "rate_limit": 50,
            "rate_limit_period": 60
        },
        created_at=datetime.now()
    )
    
    # 数据源3 - 自定义数据源(非活跃)
    custom_source = DataSource(
        source_id=f"src_{datetime.now().strftime('%Y%m%d%H%M%S')}_custom",
        source_name="自定义数据源",
        source_type="custom",
        status="inactive",
        priority=3,
        symbols_available=["BTC/USDT", "ETH/USDT"],
        timeframes_available=["1d"],
        historical_data_start=datetime(2020, 1, 1),
        update_frequency="manual",
        last_updated=datetime.now() - timedelta(days=30),
        api_details={},
        created_at=datetime.now()
    )
    
    # 保存数据源
    sources = [binance_source, coingecko_source, custom_source]
    for source in sources:
        await DataSourceDB.save_data_source(source)
    
    print(f"成功创建 {len(sources)} 个数据源")
    return sources

async def generate_historical_data(sources):
    """生成历史市场数据"""
    print("正在生成历史市场数据...")
    
    all_data = []
    
    # 获取主数据源
    primary_source = sources[0]  # Binance
    
    # 生成每个交易对的数据
    for symbol in SYMBOLS:
        print(f"生成 {symbol} 的历史数据...")
        
        # 设置初始价格和其他参数
        if symbol == "BTC/USDT":
            base_price = 50000.0
            volatility = 0.03
        elif symbol == "ETH/USDT":
            base_price = 3000.0
            volatility = 0.04
        elif symbol == "SOL/USDT":
            base_price = 100.0
            volatility = 0.05
        elif symbol == "BNB/USDT":
            base_price = 400.0
            volatility = 0.025
        elif symbol == "XRP/USDT":
            base_price = 0.5
            volatility = 0.035
        
        # 生成每天的数据
        current_price = base_price
        for day in range(DAYS_OF_DATA):
            date = datetime.now() - timedelta(days=DAYS_OF_DATA-day)
            
            # 每天的基本价格变动
            daily_change = np.random.normal(0, volatility)
            current_price = current_price * (1 + daily_change)
            
            # 为每个时间框架生成数据
            for timeframe in primary_source.timeframes_available:
                if timeframe == "1d":
                    # 每天一条数据
                    daily_open = current_price * (1 + np.random.normal(0, volatility/3))
                    daily_high = daily_open * (1 + abs(np.random.normal(0, volatility/2)))
                    daily_low = daily_open * (1 - abs(np.random.normal(0, volatility/2)))
                    daily_close = current_price  # 当天结束价格
                    daily_volume = random.uniform(1000, 10000) * daily_close
                    
                    data = HistoricalData(
                        data_id=f"data_{symbol.replace('/', '_')}_{date.strftime('%Y%m%d')}_{timeframe}",
                        symbol=symbol,
                        timestamp=date,
                        open=daily_open,
                        high=daily_high,
                        low=daily_low,
                        close=daily_close,
                        volume=daily_volume,
                        amount=daily_volume * daily_close,
                        source=primary_source.source_id,
                        processed=False,
                        validated=True,
                        data_quality_score=random.uniform(0.8, 1.0),
                        additional_fields={"timeframe": timeframe},
                        created_at=datetime.now()
                    )
                    all_data.append(data)
                
                elif timeframe == "4h":
                    # 每天6条数据
                    for hour in range(0, 24, 4):
                        time_point = date.replace(hour=hour)
                        hourly_change = np.random.normal(0, volatility/6)
                        price_at_hour = current_price * (1 + hourly_change)
                        
                        hourly_open = price_at_hour * (1 + np.random.normal(0, volatility/4))
                        hourly_high = hourly_open * (1 + abs(np.random.normal(0, volatility/3)))
                        hourly_low = hourly_open * (1 - abs(np.random.normal(0, volatility/3)))
                        hourly_close = price_at_hour * (1 + np.random.normal(0, volatility/4))
                        hourly_volume = random.uniform(100, 1000) * hourly_close
                        
                        data = HistoricalData(
                            data_id=f"data_{symbol.replace('/', '_')}_{time_point.strftime('%Y%m%d%H')}_{timeframe}",
                            symbol=symbol,
                            timestamp=time_point,
                            open=hourly_open,
                            high=hourly_high,
                            low=hourly_low,
                            close=hourly_close,
                            volume=hourly_volume,
                            amount=hourly_volume * hourly_close,
                            source=primary_source.source_id,
                            processed=False,
                            validated=True,
                            data_quality_score=random.uniform(0.8, 1.0),
                            additional_fields={"timeframe": timeframe},
                            created_at=datetime.now()
                        )
                        all_data.append(data)
                
                elif timeframe == "1h":
                    # 每天24条数据
                    for hour in range(24):
                        time_point = date.replace(hour=hour)
                        hourly_change = np.random.normal(0, volatility/8)
                        price_at_hour = current_price * (1 + hourly_change)
                        
                        hourly_open = price_at_hour * (1 + np.random.normal(0, volatility/5))
                        hourly_high = hourly_open * (1 + abs(np.random.normal(0, volatility/4)))
                        hourly_low = hourly_open * (1 - abs(np.random.normal(0, volatility/4)))
                        hourly_close = price_at_hour * (1 + np.random.normal(0, volatility/5))
                        hourly_volume = random.uniform(10, 100) * hourly_close
                        
                        data = HistoricalData(
                            data_id=f"data_{symbol.replace('/', '_')}_{time_point.strftime('%Y%m%d%H')}_{timeframe}",
                            symbol=symbol,
                            timestamp=time_point,
                            open=hourly_open,
                            high=hourly_high,
                            low=hourly_low,
                            close=hourly_close,
                            volume=hourly_volume,
                            amount=hourly_volume * hourly_close,
                            source=primary_source.source_id,
                            processed=False,
                            validated=True,
                            data_quality_score=random.uniform(0.8, 1.0),
                            additional_fields={"timeframe": timeframe},
                            created_at=datetime.now()
                        )
                        all_data.append(data)
    
    # 批量保存历史数据
    batch_size = 1000
    for i in range(0, len(all_data), batch_size):
        batch = all_data[i:i+batch_size]
        await HistoricalDataDB.save_historical_data(batch)
        print(f"保存了 {len(batch)} 条历史数据, 进度: {i+len(batch)}/{len(all_data)}")
    
    print(f"成功生成 {len(all_data)} 条历史数据")
    return all_data

async def generate_feature_data(historical_data):
    """根据历史数据生成特征数据"""
    print("正在生成特征数据...")
    
    # 仅处理1d时间框架的数据用于特征生成
    daily_data = [d for d in historical_data if d.additional_fields.get("timeframe") == "1d"]
    
    # 按符号分组
    symbols_data = {}
    for data in daily_data:
        if data.symbol not in symbols_data:
            symbols_data[data.symbol] = []
        symbols_data[data.symbol].append(data)
    
    # 为每个符号生成特征
    all_features = []
    for symbol, data_list in symbols_data.items():
        print(f"生成 {symbol} 的特征数据...")
        
        # 按时间排序
        data_list.sort(key=lambda x: x.timestamp)
        
        # 计算基本和技术特征
        for i, data in enumerate(data_list):
            if i < 14:  # 需要至少14天的数据来计算某些指标
                continue
            
            # 提取过去的价格
            past_closes = [d.close for d in data_list[max(0, i-30):i+1]]
            
            # 计算基本特征
            features = {
                # 基本价格数据
                "open": data.open,
                "high": data.high,
                "low": data.low,
                "close": data.close,
                "volume": data.volume,
                
                # 回报率特征
                "return_1d": data.close / data_list[i-1].close - 1,
                "return_5d": data.close / data_list[i-5].close - 1 if i >= 5 else None,
                "return_10d": data.close / data_list[i-10].close - 1 if i >= 10 else None,
                "return_30d": data.close / data_list[i-30].close - 1 if i >= 30 else None,
                
                # 波动率特征
                "volatility_5d": np.std([d.close / data_list[j-1].close - 1 for j, d in enumerate(data_list[i-5:i+1]) if j > 0]) if i >= 5 else None,
                "volatility_10d": np.std([d.close / data_list[j-1].close - 1 for j, d in enumerate(data_list[i-10:i+1]) if j > 0]) if i >= 10 else None,
                "volatility_30d": np.std([d.close / data_list[j-1].close - 1 for j, d in enumerate(data_list[i-30:i+1]) if j > 0]) if i >= 30 else None,
                
                # 成交量变化
                "volume_change_1d": data.volume / data_list[i-1].volume - 1,
                "volume_change_5d": data.volume / data_list[i-5].volume - 1 if i >= 5 else None,
                
                # 技术指标
                "sma_5": np.mean(past_closes[-5:]) if len(past_closes) >= 5 else None,
                "sma_10": np.mean(past_closes[-10:]) if len(past_closes) >= 10 else None,
                "sma_20": np.mean(past_closes[-20:]) if len(past_closes) >= 20 else None,
                "sma_50": np.mean(past_closes[-30:]) if len(past_closes) >= 30 else None,  # 使用可用的最多30天
                
                # RSI
                "rsi_14": calculate_rsi(past_closes, 14) if len(past_closes) >= 14 else None,
                
                # MACD相关指标
                "macd": calculate_macd(past_closes)[0] if len(past_closes) >= 26 else None,
                "macd_signal": calculate_macd(past_closes)[1] if len(past_closes) >= 26 else None,
                "macd_hist": calculate_macd(past_closes)[2] if len(past_closes) >= 26 else None,
                
                # 布林带
                "bollinger_upper": calculate_bollinger_bands(past_closes)[0] if len(past_closes) >= 20 else None,
                "bollinger_lower": calculate_bollinger_bands(past_closes)[1] if len(past_closes) >= 20 else None,
                "bollinger_pct": calculate_bollinger_bands(past_closes)[2] if len(past_closes) >= 20 else None,
            }
            
            # 创建特征数据记录
            feature_data = FeatureData(
                feature_id=f"feat_{data.timestamp.strftime('%Y%m%d')}_{symbol.replace('/', '_')}_{uuid.uuid4().hex[:8]}",
                symbol=symbol,
                timestamp=data.timestamp,
                timeframe=data.additional_fields.get("timeframe"),
                features={k: v for k, v in features.items() if v is not None},  # 移除空值
                raw_data_ids=[data.data_id],
                feature_version="1.0.0",
                created_at=datetime.now()
            )
            
            all_features.append(feature_data)
    
    # 批量保存特征数据
    batch_size = 500
    for i in range(0, len(all_features), batch_size):
        batch = all_features[i:i+batch_size]
        await FeatureDataDB.save_feature_data(batch)
        print(f"保存了 {len(batch)} 条特征数据, 进度: {i+len(batch)}/{len(all_features)}")
    
    print(f"成功生成 {len(all_features)} 条特征数据")
    return all_features

def calculate_rsi(prices, period=14):
    """计算RSI技术指标"""
    if len(prices) <= period:
        return None
    
    # 计算价格变化
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # 分离涨跌
    gain = [delta if delta > 0 else 0 for delta in deltas]
    loss = [-delta if delta < 0 else 0 for delta in deltas]
    
    # 计算平均涨跌
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    
    if avg_loss == 0:
        return 100
    
    # 计算RS和RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD技术指标"""
    if len(prices) < slow+signal:
        return None, None, None
    
    # 计算EMA
    ema_fast = np.mean(prices[-fast:])  # 简化版本，实际应使用真正的EMA
    ema_slow = np.mean(prices[-slow:])
    
    # 计算MACD和信号线
    macd_line = ema_fast - ema_slow
    signal_line = np.mean(prices[-signal:])  # 简化版本
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """计算布林带技术指标"""
    if len(prices) < period:
        return None, None, None
    
    # 计算SMA和标准差
    current_price = prices[-1]
    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    
    # 计算上下轨和位置百分比
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    
    # 计算当前价格在布林带中的位置(百分比)
    if upper_band == lower_band:
        bb_pct = 0.5
    else:
        bb_pct = (current_price - lower_band) / (upper_band - lower_band)
    
    return upper_band, lower_band, bb_pct

async def main():
    """主函数"""
    print("===== 开始生成测试数据 =====")
    
    try:
        # 连接MongoDB
        client = MongoDB.get_client()
        
        # 创建数据源
        sources = await create_data_sources()
        
        # 生成历史数据
        historical_data = await generate_historical_data(sources)
        
        # 生成特征数据
        await generate_feature_data(historical_data)
        
        print("===== 测试数据生成完成 =====")
    except Exception as e:
        print(f"生成测试数据时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭MongoDB连接
        MongoDB.close()

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 