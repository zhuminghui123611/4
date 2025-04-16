from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
import uuid
import json
import os

from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.db.historical_data_db import HistoricalDataDB, FeatureDataDB
from app.db.models import HistoricalData, FeatureData

logger = logging.getLogger(__name__)

class FeatureDataService:
    """特征数据服务，负责从历史数据中提取特征并进行预处理"""
    
    def __init__(self):
        """初始化特征数据服务"""
        self.feature_processors = {
            "basic": self._process_basic_features,
            "technical": self._process_technical_features,
            "advanced": self._process_advanced_features
        }
        self.current_feature_version = "1.0.0"  # 当前特征版本
    
    async def initialize(self):
        """初始化服务，获取最新的特征版本"""
        try:
            # 获取数据库中最新的特征版本
            latest_version = await FeatureDataDB.get_latest_feature_version()
            if latest_version:
                self.current_feature_version = latest_version
            
            logger.info(f"特征数据服务初始化完成，当前特征版本: {self.current_feature_version}")
        except Exception as e:
            logger.error(f"初始化特征数据服务失败: {str(e)}")
            raise ServiceUnavailableException("初始化特征数据服务失败")
    
    async def get_available_features(self) -> Dict[str, List[str]]:
        """
        获取可用的特征列表
        
        返回:
            按特征类型分组的特征列表
        """
        # 返回所有可用特征的映射
        return {
            "basic": [
                "return_1d", "return_5d", "return_10d", "return_30d",
                "volatility_5d", "volatility_10d", "volatility_30d",
                "volume_change_1d", "volume_change_5d"
            ],
            "technical": [
                "sma_5", "sma_10", "sma_20", "sma_50", "sma_200",
                "ema_5", "ema_10", "ema_20", "ema_50",
                "rsi_14", "macd", "macd_signal", "macd_hist",
                "bollinger_upper", "bollinger_lower", "bollinger_pct"
            ],
            "advanced": [
                "price_momentum", "volume_momentum", "relative_strength",
                "mean_reversion", "trend_strength", "market_regime",
                "volatility_regime", "support_resistance_level",
                "fibonacci_retracement", "elliott_wave_count"
            ]
        }
    
    async def process_features(self, symbol: str, timeframe: str,
                         feature_types: List[str] = ["basic"],
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         refresh: bool = False) -> Dict[str, Any]:
        """
        处理特征数据
        
        参数:
            symbol: 交易对符号
            timeframe: 时间框架（1d, 1h等）
            feature_types: 特征类型列表
            start_date: 开始日期（ISO格式，可选）
            end_date: 结束日期（ISO格式，可选）
            refresh: 是否强制刷新已处理的特征
            
        返回:
            处理结果
        """
        try:
            # 验证特征类型
            available_types = list(self.feature_processors.keys())
            for feature_type in feature_types:
                if feature_type not in available_types:
                    raise BadRequestException(f"不支持的特征类型: {feature_type}，可用类型: {', '.join(available_types)}")
            
            # 处理日期范围
            start_datetime = None
            end_datetime = None
            
            if start_date:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                # 默认处理最近90天的数据
                start_datetime = datetime.now() - timedelta(days=90)
            
            if end_date:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_datetime = datetime.now()
            
            # 获取原始历史数据
            raw_data = await HistoricalDataDB.get_historical_data(
                symbol=symbol,
                start_date=start_datetime,
                end_date=end_datetime,
                limit=10000  # 获取足够的数据用于特征计算
            )
            
            if not raw_data:
                raise BadRequestException(f"没有找到交易对 {symbol} 在指定时间范围的历史数据")
            
            # 将数据转换为DataFrame
            data_dict = [record.dict() for record in raw_data]
            df = pd.DataFrame(data_dict)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # 设置时间戳为索引
            df.set_index('timestamp', inplace=True)
            
            # 根据时间框架重采样数据
            if timeframe != '1d':
                # 将DataFrame重采样为指定的时间框架
                # 例如：'1h'表示1小时，'4h'表示4小时
                rule_map = {
                    '1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min',
                    '1h': '1H', '2h': '2H', '4h': '4H', '6h': '6H', '12h': '12H',
                    '1d': '1D', '1w': '1W'
                }
                
                if timeframe not in rule_map:
                    raise BadRequestException(f"不支持的时间框架: {timeframe}")
                
                rule = rule_map[timeframe]
                
                # 重采样OHLCV数据
                df = df.resample(rule).agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'amount': 'sum' if 'amount' in df.columns else None
                }).dropna()
            
            # 处理特征
            all_features = {}
            raw_data_ids = [record.data_id for record in raw_data]
            
            for feature_type in feature_types:
                if feature_type in self.feature_processors:
                    # 调用相应的特征处理函数
                    processor_func = self.feature_processors[feature_type]
                    features = processor_func(df)
                    all_features.update(features)
            
            # 创建特征数据记录
            feature_records = []
            for idx, row in df.iterrows():
                if idx in all_features:
                    feature_data = FeatureData(
                        feature_id=f"feat_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                        symbol=symbol,
                        timestamp=idx.to_pydatetime(),
                        timeframe=timeframe,
                        features=all_features[idx],
                        raw_data_ids=raw_data_ids,
                        feature_version=self.current_feature_version,
                        created_at=datetime.now()
                    )
                    feature_records.append(feature_data)
            
            # 保存特征数据
            if feature_records:
                inserted_ids = await FeatureDataDB.save_feature_data(feature_records)
                
                return {
                    "status": "success",
                    "message": f"成功处理 {len(feature_records)} 条特征数据",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "feature_types": feature_types,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat(),
                    "feature_version": self.current_feature_version,
                    "record_count": len(feature_records)
                }
            else:
                return {
                    "status": "warning",
                    "message": "没有生成特征数据",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "feature_types": feature_types,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat()
                }
            
        except BadRequestException as e:
            logger.warning(f"处理特征数据参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"处理特征数据失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"处理特征数据失败: {str(e)}")
    
    def _process_basic_features(self, df: pd.DataFrame) -> Dict[pd.Timestamp, Dict[str, float]]:
        """
        处理基础特征
        
        参数:
            df: 原始数据DataFrame
            
        返回:
            按时间戳索引的特征字典
        """
        features = {}
        
        # 计算收益率
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_30d'] = df['close'].pct_change(30)
        
        # 计算波动率
        df['volatility_5d'] = df['return_1d'].rolling(window=5).std()
        df['volatility_10d'] = df['return_1d'].rolling(window=10).std()
        df['volatility_30d'] = df['return_1d'].rolling(window=30).std()
        
        # 计算成交量变化
        df['volume_change_1d'] = df['volume'].pct_change(1)
        df['volume_change_5d'] = df['volume'].pct_change(5)
        
        # 提取有效特征
        feature_columns = [
            'return_1d', 'return_5d', 'return_10d', 'return_30d',
            'volatility_5d', 'volatility_10d', 'volatility_30d',
            'volume_change_1d', 'volume_change_5d'
        ]
        
        for idx, row in df.iterrows():
            feature_dict = {}
            for col in feature_columns:
                if not pd.isna(row[col]):
                    feature_dict[col] = float(row[col])
            
            if feature_dict:  # 只添加非空特征
                features[idx] = feature_dict
        
        return features
    
    def _process_technical_features(self, df: pd.DataFrame) -> Dict[pd.Timestamp, Dict[str, float]]:
        """
        处理技术指标特征
        
        参数:
            df: 原始数据DataFrame
            
        返回:
            按时间戳索引的特征字典
        """
        features = {}
        
        # 计算移动平均线
        df['sma_5'] = df['close'].rolling(window=5).mean()
        df['sma_10'] = df['close'].rolling(window=10).mean()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        # 计算指数移动平均线
        df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 计算RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # 计算MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 计算布林带
        df['bollinger_mid'] = df['close'].rolling(window=20).mean()
        df['bollinger_std'] = df['close'].rolling(window=20).std()
        df['bollinger_upper'] = df['bollinger_mid'] + (df['bollinger_std'] * 2)
        df['bollinger_lower'] = df['bollinger_mid'] - (df['bollinger_std'] * 2)
        df['bollinger_pct'] = (df['close'] - df['bollinger_lower']) / (df['bollinger_upper'] - df['bollinger_lower'])
        
        # 提取有效特征
        feature_columns = [
            'sma_5', 'sma_10', 'sma_20', 'sma_50', 'sma_200',
            'ema_5', 'ema_10', 'ema_20', 'ema_50',
            'rsi_14', 'macd', 'macd_signal', 'macd_hist',
            'bollinger_upper', 'bollinger_lower', 'bollinger_pct'
        ]
        
        for idx, row in df.iterrows():
            feature_dict = {}
            for col in feature_columns:
                if not pd.isna(row[col]):
                    feature_dict[col] = float(row[col])
            
            if feature_dict:  # 只添加非空特征
                features[idx] = feature_dict
        
        return features
    
    def _process_advanced_features(self, df: pd.DataFrame) -> Dict[pd.Timestamp, Dict[str, float]]:
        """
        处理高级特征
        
        参数:
            df: 原始数据DataFrame
            
        返回:
            按时间戳索引的特征字典
        """
        features = {}
        
        # 价格动量
        df['price_momentum'] = df['close'].pct_change(10) + df['close'].pct_change(20) + df['close'].pct_change(30)
        
        # 成交量动量
        df['volume_momentum'] = df['volume'].pct_change(10) + df['volume'].pct_change(20) + df['volume'].pct_change(30)
        
        # 相对强度 (相对于过去30日最高最低价的位置)
        df['30d_high'] = df['high'].rolling(window=30).max()
        df['30d_low'] = df['low'].rolling(window=30).min()
        df['relative_strength'] = (df['close'] - df['30d_low']) / (df['30d_high'] - df['30d_low'])
        
        # 均值回归指标
        df['distance_from_sma50'] = (df['close'] - df['close'].rolling(window=50).mean()) / df['close']
        df['mean_reversion'] = -df['distance_from_sma50']  # 负值表示价格高于均线，正值表示价格低于均线
        
        # 趋势强度 (根据50日和200日均线的关系)
        if 'sma_50' not in df.columns:
            df['sma_50'] = df['close'].rolling(window=50).mean()
        if 'sma_200' not in df.columns:
            df['sma_200'] = df['close'].rolling(window=200).mean()
        
        df['trend_strength'] = df['sma_50'] / df['sma_200'] - 1
        
        # 市场状态判断
        df['return_60d'] = df['close'].pct_change(60)
        df['volatility_60d'] = df['return_1d'].rolling(window=60).std() if 'return_1d' in df.columns else None
        
        if 'volatility_60d' in df.columns and not df['volatility_60d'].isnull().all():
            df['market_regime'] = np.where(df['return_60d'] > 0, 
                                          np.where(df['volatility_60d'] > df['volatility_60d'].mean(), 1, 2), 
                                          np.where(df['volatility_60d'] > df['volatility_60d'].mean(), 3, 4))
        else:
            df['market_regime'] = np.nan
        
        # 波动率状态判断
        if 'volatility_30d' in df.columns and not df['volatility_30d'].isnull().all():
            vola_mean = df['volatility_30d'].mean()
            vola_std = df['volatility_30d'].std()
            df['volatility_regime'] = np.where(df['volatility_30d'] < vola_mean - vola_std, 1,  # 低波动
                                             np.where(df['volatility_30d'] < vola_mean + vola_std, 2,  # 中波动
                                                     3))  # 高波动
        else:
            df['volatility_regime'] = np.nan
        
        # 简化的支撑/阻力水平检测 (使用近期的高点和低点)
        df['support_level'] = df['low'].rolling(window=20).min()
        df['resistance_level'] = df['high'].rolling(window=20).max()
        df['support_resistance_level'] = (df['close'] - df['support_level']) / (df['resistance_level'] - df['support_level'])
        
        # 简化的斐波那契回调水平
        df['swing_high'] = df['high'].rolling(window=20).max()
        df['swing_low'] = df['low'].rolling(window=20).min()
        price_range = df['swing_high'] - df['swing_low']
        df['fib_0'] = df['swing_low']
        df['fib_236'] = df['swing_low'] + 0.236 * price_range
        df['fib_382'] = df['swing_low'] + 0.382 * price_range
        df['fib_500'] = df['swing_low'] + 0.500 * price_range
        df['fib_618'] = df['swing_low'] + 0.618 * price_range
        df['fib_1000'] = df['swing_high']
        
        # 当前价格最接近哪个斐波那契水平
        fib_levels = [0, 0.236, 0.382, 0.500, 0.618, 1.000]
        fib_columns = ['fib_0', 'fib_236', 'fib_382', 'fib_500', 'fib_618', 'fib_1000']
        
        def get_closest_fib(row):
            if all(pd.isna(row[col]) for col in fib_columns):
                return np.nan
            
            diffs = [abs(row['close'] - row[col]) if not pd.isna(row[col]) else float('inf') for col in fib_columns]
            closest_idx = np.argmin(diffs)
            return fib_levels[closest_idx]
        
        df['fibonacci_retracement'] = df.apply(get_closest_fib, axis=1)
        
        # 简化的艾略特波浪计数 (这里只是一个非常简化的示例)
        def simplified_elliott_wave(series, window=40):
            result = np.zeros(len(series))
            
            if len(series) < window:
                return result
            
            # 找到窗口内的显著高点和低点
            for i in range(window, len(series)):
                window_slice = series.iloc[i-window:i+1]
                
                # 计算前半窗口的趋势
                first_half = window_slice.iloc[:window//2]
                first_trend = 1 if first_half.iloc[-1] > first_half.iloc[0] else -1
                
                # 计算后半窗口的趋势
                second_half = window_slice.iloc[window//2:]
                second_trend = 1 if second_half.iloc[-1] > second_half.iloc[0] else -1
                
                # 趋势变化计数 (简化的波浪计数)
                if first_trend == 1 and second_trend == -1:
                    result[i] = 5  # 完成5浪上升后开始调整
                elif first_trend == -1 and second_trend == 1:
                    result[i] = 2  # 完成下跌调整后开始新一轮上升
                elif first_trend == 1 and second_trend == 1:
                    result[i] = 3  # 可能在第3浪强劲上升中
                elif first_trend == -1 and second_trend == -1:
                    result[i] = 1  # 可能在调整的A浪或初始下跌中
                else:
                    result[i] = 0
            
            return result
        
        if len(df) > 40:
            df['elliott_wave_count'] = simplified_elliott_wave(df['close'])
        else:
            df['elliott_wave_count'] = np.nan
        
        # 提取有效特征
        feature_columns = [
            'price_momentum', 'volume_momentum', 'relative_strength',
            'mean_reversion', 'trend_strength', 'market_regime',
            'volatility_regime', 'support_resistance_level',
            'fibonacci_retracement', 'elliott_wave_count'
        ]
        
        for idx, row in df.iterrows():
            feature_dict = {}
            for col in feature_columns:
                if col in df.columns and not pd.isna(row[col]):
                    if isinstance(row[col], (int, float, np.integer, np.floating)):
                        feature_dict[col] = float(row[col])
            
            if feature_dict:  # 只添加非空特征
                features[idx] = feature_dict
        
        return features
    
    async def get_feature_data(self, symbol: str, timeframe: str,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         feature_version: Optional[str] = None,
                         limit: int = 1000) -> List[Dict[str, Any]]:
        """
        获取特征数据
        
        参数:
            symbol: 交易对符号
            timeframe: 时间框架
            start_date: 开始日期（ISO格式，可选）
            end_date: 结束日期（ISO格式，可选）
            feature_version: 特征版本（可选）
            limit: 返回记录的最大数量
            
        返回:
            特征数据列表
        """
        try:
            # 处理日期范围
            start_datetime = None
            end_datetime = None
            
            if start_date:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            
            if end_date:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            # 从数据库获取数据
            feature_records = await FeatureDataDB.get_feature_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_datetime,
                end_date=end_datetime,
                feature_version=feature_version,
                limit=limit
            )
            
            # 转换为字典列表
            result = []
            for record in feature_records:
                record_dict = record.dict()
                # 转换时间戳为ISO格式字符串
                if isinstance(record_dict['timestamp'], datetime):
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                if isinstance(record_dict['created_at'], datetime):
                    record_dict['created_at'] = record_dict['created_at'].isoformat()
                
                result.append(record_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"获取 {symbol} 的特征数据失败: {str(e)}")
            raise ServiceUnavailableException(f"获取特征数据失败: {str(e)}") 