#!/usr/bin/env python3
"""
测试CCXT API集成的脚本
"""

import asyncio
import sys
import os
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
from pprint import pprint
from datetime import datetime

# 将项目根目录添加到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_basic_ccxt():
    """测试基本的CCXT功能"""
    print("===== 测试基本CCXT功能 =====")
    
    # 显示所有支持的交易所
    print(f"CCXT支持的交易所数量: {len(ccxt.exchanges)}")
    print(f"部分交易所: {', '.join(ccxt.exchanges[:10])}...")
    
    # 创建交易所实例
    exchange_id = 'binance'
    try:
        exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True
        })
        print(f"\n已创建{exchange.name}交易所实例")
        
        # 获取交易所信息
        markets = exchange.load_markets()
        print(f"支持的市场数量: {len(markets)}")
        print(f"支持的时间周期: {exchange.timeframes}")
        
        # 获取某个交易对的ticker
        symbol = 'BTC/USDT'
        ticker = exchange.fetch_ticker(symbol)
        print(f"\n{symbol} Ticker:")
        print(f"价格: {ticker['last']}")
        print(f"买一价: {ticker['bid']}, 卖一价: {ticker['ask']}")
        print(f"24h高: {ticker['high']}, 24h低: {ticker['low']}")
        print(f"24h成交量: {ticker['volume']}")
        
        # 获取K线数据
        timeframe = '1h'
        limit = 24  # 获取24小时数据
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        print(f"\n{symbol} {timeframe} K线数据 (最近{limit}条):")
        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        print(df.head())
        
        # 获取订单簿
        order_book = exchange.fetch_order_book(symbol)
        print(f"\n{symbol} 订单簿:")
        print(f"买单数量: {len(order_book['bids'])}")
        print(f"卖单数量: {len(order_book['asks'])}")
        print(f"最佳买价: {order_book['bids'][0][0]}")
        print(f"最佳卖价: {order_book['asks'][0][0]}")
        
        return True
        
    except Exception as e:
        print(f"测试CCXT时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_multiple_exchanges():
    """测试多个交易所数据比较"""
    print("\n===== 测试多个交易所数据比较 =====")
    
    exchanges = ['binance', 'okx', 'kucoin']
    symbol = 'BTC/USDT'
    
    print(f"比较{symbol}在不同交易所的价格")
    
    results = []
    for exchange_id in exchanges:
        try:
            exchange = getattr(ccxt, exchange_id)({
                'enableRateLimit': True
            })
            ticker = exchange.fetch_ticker(symbol)
            
            results.append({
                'exchange': exchange.name,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'spread': ticker['ask'] - ticker['bid'],
                'volume': ticker['volume']
            })
            
        except Exception as e:
            print(f"{exchange_id} 获取数据失败: {str(e)}")
    
    # 打印比较结果
    if results:
        df = pd.DataFrame(results)
        print(df)
    
    return True

async def main():
    """主函数"""
    print("===== 开始测试CCXT API =====")
    
    try:
        await test_basic_ccxt()
        await test_multiple_exchanges()
        
        print("\n===== CCXT API测试完成 =====")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 