from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
import asyncio
import uuid
import json
import os

from app.core.exceptions import BadRequestException
from app.exceptions.service_exceptions import ServiceUnavailableException
from app.db.historical_data_db import HistoricalDataDB, FeatureDataDB, DataSourceDB
from app.db.models import HistoricalData, FeatureData, DataSource

logger = logging.getLogger(__name__)

class HistoricalDataService:
    """历史数据服务，负责处理历史数据的获取、处理和管理"""
    
    def __init__(self):
        """初始化历史数据服务"""
        self.data_sources = {}  # 缓存数据源信息
    
    async def initialize(self):
        """初始化服务，加载数据源信息"""
        try:
            # 加载所有活跃的数据源
            sources = await DataSourceDB.get_all_active_data_sources()
            for source in sources:
                self.data_sources[source.source_id] = source
            
            logger.info(f"已加载 {len(sources)} 个活跃数据源")
        except Exception as e:
            logger.error(f"初始化历史数据服务失败: {str(e)}")
            raise ServiceUnavailableException("初始化历史数据服务失败")
    
    async def get_available_symbols(self) -> List[str]:
        """
        获取所有可用的交易对符号
        
        返回:
            交易对符号列表
        """
        try:
            # 从数据库获取已有数据的符号
            db_symbols = await HistoricalDataDB.get_symbols_with_data()
            
            # 从数据源获取可用的符号
            source_symbols = set()
            for source_id, source in self.data_sources.items():
                source_symbols.update(source.symbols_available)
            
            # 合并去重
            all_symbols = list(set(db_symbols).union(source_symbols))
            all_symbols.sort()  # 排序方便展示
            
            return all_symbols
        except Exception as e:
            logger.error(f"获取可用交易对符号失败: {str(e)}")
            raise ServiceUnavailableException("获取可用交易对符号失败")
    
    async def get_data_coverage(self, symbol: str) -> Dict[str, Any]:
        """
        获取指定交易对的数据覆盖情况
        
        参数:
            symbol: 交易对符号
            
        返回:
            数据覆盖情况
        """
        try:
            # 从数据库获取该交易对的数据日期范围
            date_range = await HistoricalDataDB.get_data_date_range(symbol)
            
            # 确定该交易对在哪些数据源可用
            available_sources = []
            for source_id, source in self.data_sources.items():
                if symbol in source.symbols_available:
                    available_sources.append({
                        "source_id": source_id,
                        "source_name": source.source_name,
                        "timeframes_available": source.timeframes_available,
                        "historical_data_start": source.historical_data_start,
                        "update_frequency": source.update_frequency,
                        "last_updated": source.last_updated
                    })
            
            # 返回综合信息
            return {
                "symbol": symbol,
                "has_data": bool(date_range),
                "date_range": date_range,
                "available_sources": available_sources,
                "data_quality": await self._assess_data_quality(symbol)
            }
        except Exception as e:
            logger.error(f"获取交易对 {symbol} 的数据覆盖情况失败: {str(e)}")
            raise ServiceUnavailableException(f"获取交易对 {symbol} 的数据覆盖情况失败")
    
    async def _assess_data_quality(self, symbol: str) -> Dict[str, Any]:
        """
        评估指定交易对的数据质量
        
        参数:
            symbol: 交易对符号
            
        返回:
            数据质量评估结果
        """
        try:
            # 获取最近的100条数据用于质量评估
            recent_data = await HistoricalDataDB.get_historical_data(
                symbol=symbol,
                limit=100
            )
            
            if not recent_data:
                return {
                    "status": "unknown",
                    "message": "没有可用数据进行质量评估"
                }
            
            # 将数据转换为DataFrame方便处理
            data_dict = [record.dict() for record in recent_data]
            df = pd.DataFrame(data_dict)
            
            # 评估缺失值
            missing_values = df[['open', 'high', 'low', 'close', 'volume']].isnull().sum().to_dict()
            has_missing = any(v > 0 for v in missing_values.values())
            
            # 评估异常值（使用简单的Z-score方法）
            anomalies = {}
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                    anomalies[col] = (z_scores > 3).sum()  # Z-score大于3视为异常
            
            has_anomalies = any(v > 0 for v in anomalies.values())
            
            # 评估数据连续性 (检查时间戳间隔是否一致)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            time_diffs = df['timestamp'].diff().dropna()
            std_time_diff = time_diffs.std().total_seconds()
            has_gaps = std_time_diff > 60  # 如果标准差大于60秒，认为有间隙
            
            # 综合评估
            quality_score = 1.0
            if has_missing:
                quality_score -= 0.3
            if has_anomalies:
                quality_score -= 0.3
            if has_gaps:
                quality_score -= 0.2
            
            quality_score = max(0.0, quality_score)
            
            status = "good"
            if quality_score < 0.6:
                status = "poor"
            elif quality_score < 0.8:
                status = "fair"
            
            return {
                "status": status,
                "score": quality_score,
                "missing_values": missing_values,
                "anomalies": anomalies,
                "time_consistency": {
                    "has_gaps": has_gaps,
                    "std_time_diff_seconds": std_time_diff
                },
                "sample_size": len(df),
                "assessed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"评估交易对 {symbol} 的数据质量失败: {str(e)}")
            return {
                "status": "error",
                "message": f"评估数据质量失败: {str(e)}"
            }
    
    async def sync_historical_data(self, symbol: str, source_id: Optional[str] = None, 
                             start_date: Optional[str] = None, end_date: Optional[str] = None,
                             force_update: bool = False) -> Dict[str, Any]:
        """
        同步历史数据
        
        参数:
            symbol: 交易对符号
            source_id: 数据源ID（可选，如果不指定则使用优先级最高的数据源）
            start_date: 开始日期（ISO格式，可选）
            end_date: 结束日期（ISO格式，可选）
            force_update: 是否强制更新已有数据
            
        返回:
            同步结果
        """
        try:
            # 参数验证
            if symbol not in await self.get_available_symbols():
                raise BadRequestException(f"交易对 {symbol} 不可用")
            
            # 如果没有指定数据源，选择优先级最高的数据源
            if not source_id:
                available_sources = []
                for src_id, source in self.data_sources.items():
                    if symbol in source.symbols_available:
                        available_sources.append(source)
                
                if not available_sources:
                    raise BadRequestException(f"没有可用的数据源提供交易对 {symbol} 的数据")
                
                # 按优先级排序
                available_sources.sort(key=lambda x: x.priority)
                source = available_sources[0]
                source_id = source.source_id
            else:
                # 验证指定的数据源
                if source_id not in self.data_sources:
                    raise BadRequestException(f"数据源 {source_id} 不存在")
                
                source = self.data_sources[source_id]
                if symbol not in source.symbols_available:
                    raise BadRequestException(f"数据源 {source_id} 不提供交易对 {symbol} 的数据")
            
            # 处理日期范围
            if start_date:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                # 如果没有指定开始日期，使用数据源支持的最早日期或默认为30天前
                if source.historical_data_start:
                    start_datetime = source.historical_data_start
                else:
                    start_datetime = datetime.now() - timedelta(days=30)
            
            if end_date:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                # 如果没有指定结束日期，使用当前时间
                end_datetime = datetime.now()
            
            # 调用数据源适配器获取数据
            # 注意：这里应该实现对不同数据源的适配，根据source.source_type调用不同的适配器
            # 为了示例，我们模拟数据获取过程
            raw_data = await self._fetch_data_from_source(source, symbol, start_datetime, end_datetime)
            
            # 处理和保存数据
            processed_data = []
            for data_point in raw_data:
                # 创建历史数据记录
                data_record = HistoricalData(
                    data_id=f"hist_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    timestamp=data_point['timestamp'],
                    open=data_point['open'],
                    high=data_point['high'],
                    low=data_point['low'],
                    close=data_point['close'],
                    volume=data_point['volume'],
                    amount=data_point.get('amount'),
                    additional_fields=data_point.get('additional_fields', {}),
                    source=source.source_name,
                    source_timestamp=data_point.get('source_timestamp'),
                    processed=False,
                    validated=False
                )
                processed_data.append(data_record)
            
            # 批量保存到数据库
            if processed_data:
                inserted_ids = await HistoricalDataDB.save_historical_data(processed_data)
                
                # 更新数据源的最后更新时间
                await DataSourceDB.update_last_updated(source_id)
                
                return {
                    "status": "success",
                    "message": f"成功同步 {len(processed_data)} 条历史数据",
                    "symbol": symbol,
                    "source": source.source_name,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat(),
                    "record_count": len(processed_data)
                }
            else:
                return {
                    "status": "warning",
                    "message": "没有新数据可同步",
                    "symbol": symbol,
                    "source": source.source_name,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat()
                }
            
        except BadRequestException as e:
            logger.warning(f"同步历史数据参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"同步历史数据失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"同步历史数据失败: {str(e)}")
    
    async def _fetch_data_from_source(self, source: DataSource, symbol: str,
                                start_datetime: datetime, end_datetime: datetime) -> List[Dict[str, Any]]:
        """
        从数据源获取数据
        
        参数:
            source: 数据源信息
            symbol: 交易对符号
            start_datetime: 开始日期时间
            end_datetime: 结束日期时间
            
        返回:
            原始数据列表
        """
        # 在实际应用中，这里应该根据数据源类型调用不同的适配器
        # 为了示例，我们返回模拟数据
        try:
            logger.info(f"从数据源 {source.source_name} 获取 {symbol} 的历史数据")
            
            # 模拟数据，实际应用中替换为真实的数据获取逻辑
            simulated_data = []
            current_time = start_datetime
            
            while current_time <= end_datetime:
                # 只生成工作日的数据
                if current_time.weekday() < 5:  # 0-4对应周一到周五
                    # 生成随机价格数据
                    base_price = 100 + (current_time.timestamp() % 1000)
                    
                    data_point = {
                        'timestamp': current_time,
                        'open': base_price * (1 + 0.01 * np.random.randn()),
                        'high': base_price * (1 + 0.02 + 0.01 * np.random.randn()),
                        'low': base_price * (1 - 0.02 + 0.01 * np.random.randn()),
                        'close': base_price * (1 + 0.01 * np.random.randn()),
                        'volume': 1000 + 5000 * np.random.random(),
                        'amount': (1000 + 5000 * np.random.random()) * base_price,
                        'source_timestamp': current_time,
                        'additional_fields': {
                            'vwap': base_price * (1 + 0.005 * np.random.randn()),
                            'number_of_trades': int(100 + 200 * np.random.random())
                        }
                    }
                    simulated_data.append(data_point)
                
                # 增加时间，这里假设为每天数据
                current_time += timedelta(days=1)
            
            return simulated_data
            
        except Exception as e:
            logger.error(f"从数据源 {source.source_name} 获取 {symbol} 的历史数据失败: {str(e)}")
            raise
            
    async def get_historical_data(self, symbol: str, start_date: Optional[str] = None,
                            end_date: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        获取历史数据
        
        参数:
            symbol: 交易对符号
            start_date: 开始日期（ISO格式，可选）
            end_date: 结束日期（ISO格式，可选）
            limit: 返回记录的最大数量
            
        返回:
            历史数据列表
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
            data_records = await HistoricalDataDB.get_historical_data(
                symbol=symbol,
                start_date=start_datetime,
                end_date=end_datetime,
                limit=limit
            )
            
            # 转换为字典列表
            result = []
            for record in data_records:
                record_dict = record.dict()
                # 转换时间戳为ISO格式字符串
                if isinstance(record_dict['timestamp'], datetime):
                    record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                if record_dict.get('source_timestamp') and isinstance(record_dict['source_timestamp'], datetime):
                    record_dict['source_timestamp'] = record_dict['source_timestamp'].isoformat()
                
                result.append(record_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"获取 {symbol} 的历史数据失败: {str(e)}")
            raise ServiceUnavailableException(f"获取历史数据失败: {str(e)}") 