import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
import asyncio
import time

from app.services.data_integration_service import DataIntegrationService
from app.services.exchange_service import ExchangeService
from app.models.market_data import DataSourceType, OHLCVData, TickerData, TimeFrame
from app.core.exceptions import BadRequestException, ServiceUnavailableException

logger = logging.getLogger(__name__)

class DataProcessingService:
    """数据处理服务，负责数据预处理和准备"""
    
    # 默认特征列表
    DEFAULT_FEATURES = [
        'open', 'high', 'low', 'close', 'volume', 
        'open_pct_change', 'high_pct_change', 'low_pct_change', 'close_pct_change', 'volume_pct_change',
        'moving_avg_5', 'moving_avg_10', 'moving_avg_20', 
        'volatility_5', 'volatility_10', 'volatility_20',
        'rsi', 'macd', 'macd_signal', 'macd_hist', 'bollinger_upper', 'bollinger_lower'
    ]
    
    @classmethod
    async def prepare_ohlcv_data(
        cls, 
        symbol: str, 
        exchange_id: str, 
        timeframe: str = '1d', 
        days: int = 90,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        准备OHLCV数据
        
        Args:
            symbol: 交易对符号
            exchange_id: 交易所ID
            timeframe: 时间周期
            days: 获取的历史数据天数
            limit: 获取的数据条数限制
            
        Returns:
            pd.DataFrame: 处理后的OHLCV数据
        """
        try:
            # 计算开始时间
            since = None
            if days > 0:
                since_dt = datetime.now() - timedelta(days=days)
                since = int(since_dt.timestamp() * 1000)
            
            # 从交易所获取OHLCV数据
            ohlcv_list = await ExchangeService.get_ohlcv(
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit or 1000,  # 使用较大的限制以确保获取足够的数据
                since=since
            )
            
            if not ohlcv_list:
                raise BadRequestException(f"无法获取{symbol}的OHLCV数据")
            
            # 将OHLCVData对象列表转换为字典列表
            data_list = [item.dict() for item in ohlcv_list]
            
            # 创建DataFrame
            df = pd.DataFrame(data_list)
            
            # 设置时间戳为索引
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            df.sort_index(inplace=True)
            
            # 保留必要的列
            keep_columns = ['open', 'high', 'low', 'close', 'volume']
            df = df[keep_columns]
            
            # 计算缺失的标准特征
            df = cls._calculate_standard_features(df)
            
            # 检查结果是否有效
            if df.empty:
                raise ServiceUnavailableException(f"处理后的{symbol} OHLCV数据为空")
            
            return df
        
        except BadRequestException as e:
            logger.error(f"获取OHLCV数据失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"准备OHLCV数据时出错: {str(e)}")
            raise ServiceUnavailableException(f"准备OHLCV数据失败: {str(e)}")
    
    @classmethod
    async def prepare_multi_source_data(
        cls, 
        symbol: str, 
        days: int = 90,
        include_on_chain: bool = True,
        include_sentiment: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        准备多源数据
        
        Args:
            symbol: 交易对符号
            days: 获取的历史数据天数
            include_on_chain: 是否包含链上数据
            include_sentiment: 是否包含情绪数据
            
        Returns:
            Dict[str, pd.DataFrame]: 包含不同数据源数据的字典
        """
        result = {}
        tasks = []
        
        # 获取基本OHLCV数据
        tasks.append(cls.prepare_ohlcv_data(symbol, 'binance', '1d', days))
        
        # 如果需要链上数据
        if include_on_chain and ('ETH' in symbol or 'BTC' in symbol):
            token = 'ETH' if 'ETH' in symbol else 'BTC'
            tasks.append(cls._get_on_chain_data(token, days))
        
        # 如果需要情绪数据
        if include_sentiment:
            tasks.append(cls._get_sentiment_data(symbol, days))
        
        # 获取交易所存量数据
        if 'BTC' in symbol or 'ETH' in symbol:
            tasks.append(cls._get_exchange_reserve_data(symbol.split('/')[0], days))
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        result['ohlcv'] = results[0] if not isinstance(results[0], Exception) else pd.DataFrame()
        
        index = 1
        if include_on_chain and ('ETH' in symbol or 'BTC' in symbol):
            result['on_chain'] = results[index] if not isinstance(results[index], Exception) else pd.DataFrame()
            index += 1
        
        if include_sentiment:
            result['sentiment'] = results[index] if not isinstance(results[index], Exception) else pd.DataFrame()
            index += 1
        
        if 'BTC' in symbol or 'ETH' in symbol:
            result['exchange_reserve'] = results[index] if not isinstance(results[index], Exception) else pd.DataFrame()
        
        return result
    
    @classmethod
    async def prepare_qlib_format_data(
        cls, 
        symbol: str, 
        days: int = 90,
        target_column: str = 'close',
        feature_columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        准备符合qlib格式的数据
        
        Args:
            symbol: 交易对符号
            days: 获取的历史数据天数
            target_column: 目标列名
            feature_columns: 特征列名列表
            
        Returns:
            pd.DataFrame: qlib格式的数据
        """
        # 获取多源数据
        data_dict = await cls.prepare_multi_source_data(symbol, days)
        
        # 获取基本OHLCV数据
        ohlcv_df = data_dict.get('ohlcv')
        if ohlcv_df.empty:
            raise ServiceUnavailableException(f"无法获取{symbol}的OHLCV数据")
        
        # 使用默认特征或指定特征
        if not feature_columns:
            feature_columns = cls.DEFAULT_FEATURES
        
        # 确保所有特征列都存在
        for col in feature_columns:
            if col not in ohlcv_df.columns and col != target_column:
                logger.warning(f"特征列{col}不存在，将被忽略")
        
        available_features = [col for col in feature_columns if col in ohlcv_df.columns or col == target_column]
        
        # 准备qlib格式数据
        df = ohlcv_df.copy()
        
        # 添加链上数据特征 (如果有)
        if 'on_chain' in data_dict and not data_dict['on_chain'].empty:
            on_chain_df = data_dict['on_chain']
            # 重采样使时间索引匹配
            on_chain_df = on_chain_df.resample('D').mean().fillna(method='ffill')
            # 根据OHLCV数据的索引对齐
            on_chain_df = on_chain_df.reindex(df.index, method='ffill')
            # 将链上数据列添加到主数据框
            for col in on_chain_df.columns:
                df[f'on_chain_{col}'] = on_chain_df[col]
                available_features.append(f'on_chain_{col}')
        
        # 添加情绪数据特征 (如果有)
        if 'sentiment' in data_dict and not data_dict['sentiment'].empty:
            sentiment_df = data_dict['sentiment']
            # 重采样和对齐
            sentiment_df = sentiment_df.resample('D').mean().fillna(method='ffill')
            sentiment_df = sentiment_df.reindex(df.index, method='ffill')
            # 添加情绪数据列
            for col in sentiment_df.columns:
                df[f'sentiment_{col}'] = sentiment_df[col]
                available_features.append(f'sentiment_{col}')
        
        # 添加交易所存量数据特征 (如果有)
        if 'exchange_reserve' in data_dict and not data_dict['exchange_reserve'].empty:
            reserve_df = data_dict['exchange_reserve']
            # 重采样和对齐
            reserve_df = reserve_df.resample('D').mean().fillna(method='ffill')
            reserve_df = reserve_df.reindex(df.index, method='ffill')
            # 添加交易所存量数据列
            for col in reserve_df.columns:
                df[f'exchange_reserve_{col}'] = reserve_df[col]
                available_features.append(f'exchange_reserve_{col}')
        
        # 移除包含NaN的行
        df.dropna(inplace=True)
        
        # 准备目标变量
        # 向后移动一行目标列以预测下一天的值
        if target_column in df.columns:
            df[f'label'] = df[target_column].shift(-1)
        
        # 删除最后一行，因为它没有标签
        df = df[:-1]
        
        # 最终检查和清理
        df.dropna(inplace=True)
        
        # 保留可用特征和标签列
        available_features = [col for col in available_features if col in df.columns]
        columns_to_keep = available_features + ['label']
        df = df[columns_to_keep]
        
        return df
    
    @classmethod
    def _calculate_standard_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算标准技术指标特征
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            pd.DataFrame: 增加了技术指标的DataFrame
        """
        # 检查DataFrame是否有必要的列
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            logger.warning(f"缺少计算技术指标所需的列: {missing}")
            return df
        
        # 复制DataFrame以避免修改原始数据
        df_copy = df.copy()
        
        try:
            # 计算百分比变化
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df_copy[f'{col}_pct_change'] = df_copy[col].pct_change()
            
            # 计算移动平均线
            df_copy['moving_avg_5'] = df_copy['close'].rolling(window=5).mean()
            df_copy['moving_avg_10'] = df_copy['close'].rolling(window=10).mean()
            df_copy['moving_avg_20'] = df_copy['close'].rolling(window=20).mean()
            
            # 计算波动率
            df_copy['volatility_5'] = df_copy['close'].rolling(window=5).std()
            df_copy['volatility_10'] = df_copy['close'].rolling(window=10).std()
            df_copy['volatility_20'] = df_copy['close'].rolling(window=20).std()
            
            # 计算RSI
            delta = df_copy['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            df_copy['rsi'] = 100 - (100 / (1 + rs))
            
            # 计算MACD
            exp1 = df_copy['close'].ewm(span=12, adjust=False).mean()
            exp2 = df_copy['close'].ewm(span=26, adjust=False).mean()
            df_copy['macd'] = exp1 - exp2
            df_copy['macd_signal'] = df_copy['macd'].ewm(span=9, adjust=False).mean()
            df_copy['macd_hist'] = df_copy['macd'] - df_copy['macd_signal']
            
            # 计算布林带
            df_copy['bollinger_mid'] = df_copy['close'].rolling(window=20).mean()
            df_copy['bollinger_std'] = df_copy['close'].rolling(window=20).std()
            df_copy['bollinger_upper'] = df_copy['bollinger_mid'] + (df_copy['bollinger_std'] * 2)
            df_copy['bollinger_lower'] = df_copy['bollinger_mid'] - (df_copy['bollinger_std'] * 2)
            
            # 丢弃临时列
            df_copy.drop(columns=['bollinger_mid', 'bollinger_std'], inplace=True, errors='ignore')
            
            # 删除NaN值
            # df_copy.dropna(inplace=True)
            
            return df_copy
        
        except Exception as e:
            logger.error(f"计算技术指标时出错: {str(e)}")
            return df
    
    @classmethod
    async def _get_on_chain_data(cls, token: str, days: int) -> pd.DataFrame:
        """
        获取链上数据
        
        Args:
            token: 代币符号 (ETH/BTC)
            days: 历史数据天数
            
        Returns:
            pd.DataFrame: 链上数据
        """
        try:
            if token == 'ETH':
                chain = 'ethereum'
                # 获取以太坊的链上数据，如Gas价格、交易计数等
                gas_prices = []
                tx_counts = []
                
                # 获取最近几天的数据
                for day in range(days):
                    date = datetime.now() - timedelta(days=day)
                    block_number = await cls._get_closest_block_number(chain, date)
                    
                    # 获取Gas价格
                    gas_data = await DataIntegrationService.fetch_ankr_data(
                        chain=chain,
                        method="eth_gasPrice",
                        params=[]
                    )
                    gas_price = int(gas_data, 16) / 1e9  # 转换为Gwei
                    gas_prices.append((date, gas_price))
                    
                    # 获取区块信息包括交易数
                    block_data = await DataIntegrationService.fetch_ankr_data(
                        chain=chain,
                        method="eth_getBlockByNumber",
                        params=[hex(block_number), False]
                    )
                    tx_count = len(block_data.get("transactions", []))
                    tx_counts.append((date, tx_count))
                    
                    # 等待一下，以避免API速率限制
                    await asyncio.sleep(0.2)
                
                # 创建DataFrame
                gas_df = pd.DataFrame(gas_prices, columns=['date', 'gas_price'])
                gas_df.set_index('date', inplace=True)
                
                tx_df = pd.DataFrame(tx_counts, columns=['date', 'tx_count'])
                tx_df.set_index('date', inplace=True)
                
                # 合并数据
                result_df = pd.concat([gas_df, tx_df], axis=1)
                
            elif token == 'BTC':
                chain = 'bitcoin'
                # 获取比特币的链上数据，如难度、交易计数等
                difficulties = []
                tx_counts = []
                
                # 获取最近几天的数据
                for day in range(days):
                    date = datetime.now() - timedelta(days=day)
                    block_number = await cls._get_closest_block_number(chain, date)
                    
                    # 获取区块信息
                    block_data = await DataIntegrationService.fetch_ankr_data(
                        chain=chain,
                        method="getblock",
                        params=[str(block_number)]
                    )
                    
                    difficulties.append((date, block_data.get("difficulty", 0)))
                    tx_counts.append((date, len(block_data.get("tx", []))))
                    
                    # 等待一下，以避免API速率限制
                    await asyncio.sleep(0.2)
                
                # 创建DataFrame
                diff_df = pd.DataFrame(difficulties, columns=['date', 'difficulty'])
                diff_df.set_index('date', inplace=True)
                
                tx_df = pd.DataFrame(tx_counts, columns=['date', 'tx_count'])
                tx_df.set_index('date', inplace=True)
                
                # 合并数据
                result_df = pd.concat([diff_df, tx_df], axis=1)
                
            else:
                logger.warning(f"不支持的代币类型: {token}")
                return pd.DataFrame()
            
            return result_df
            
        except Exception as e:
            logger.error(f"获取链上数据时出错: {str(e)}")
            return pd.DataFrame()
    
    @classmethod
    async def _get_closest_block_number(cls, chain: str, target_date: datetime) -> int:
        """
        获取最接近指定日期的区块号
        
        Args:
            chain: 区块链名称
            target_date: 目标日期
            
        Returns:
            int: 区块号
        """
        try:
            if chain == 'ethereum':
                # 使用binary search找到接近目标时间的区块
                # 这里简化为估算，实际项目中可以使用二分查找优化
                timestamp = int(target_date.timestamp())
                
                # 获取当前区块
                current_block_data = await DataIntegrationService.fetch_ankr_data(
                    chain='ethereum',
                    method="eth_blockNumber",
                    params=[]
                )
                current_block = int(current_block_data, 16)
                
                # 获取当前区块的时间戳
                current_block_info = await DataIntegrationService.fetch_ankr_data(
                    chain='ethereum',
                    method="eth_getBlockByNumber",
                    params=[hex(current_block), False]
                )
                current_timestamp = int(current_block_info["timestamp"], 16)
                
                # 估算目标区块
                # 以太坊平均出块时间约为13秒
                seconds_diff = current_timestamp - timestamp
                blocks_diff = seconds_diff // 13
                
                estimated_block = max(1, current_block - blocks_diff)
                return estimated_block
                
            elif chain == 'bitcoin':
                # 比特币平均出块时间约为10分钟
                timestamp = int(target_date.timestamp())
                
                # 获取当前区块高度
                current_height = await DataIntegrationService.fetch_ankr_data(
                    chain='bitcoin',
                    method="getblockcount",
                    params=[]
                )
                
                # 获取当前区块信息
                current_block = await DataIntegrationService.fetch_ankr_data(
                    chain='bitcoin',
                    method="getblockhash",
                    params=[current_height]
                )
                
                current_block_info = await DataIntegrationService.fetch_ankr_data(
                    chain='bitcoin',
                    method="getblock",
                    params=[current_block]
                )
                
                current_timestamp = current_block_info["time"]
                
                # 估算目标区块
                seconds_diff = current_timestamp - timestamp
                blocks_diff = seconds_diff // 600  # 10分钟 = 600秒
                
                estimated_height = max(1, current_height - blocks_diff)
                return estimated_height
            
            else:
                raise ValueError(f"不支持的区块链: {chain}")
                
        except Exception as e:
            logger.error(f"估算区块号时出错: {str(e)}")
            # 返回一个默认值
            return 1
    
    @classmethod
    async def _get_sentiment_data(cls, symbol: str, days: int) -> pd.DataFrame:
        """
        获取情绪数据
        
        Args:
            symbol: 交易对符号
            days: 历史数据天数
            
        Returns:
            pd.DataFrame: 情绪数据
        """
        # 在实际项目中，这里应该调用情绪分析API或服务
        # 这里我们生成一些模拟数据用于演示
        
        try:
            token = symbol.split('/')[0]
            
            # 生成日期序列
            dates = []
            sentiment_scores = []
            social_volumes = []
            
            for day in range(days):
                date = datetime.now() - timedelta(days=day)
                dates.append(date)
                
                # 生成-1到1之间的随机情绪分数
                sentiment_scores.append(np.random.uniform(-1, 1))
                
                # 生成随机社交媒体提及量
                social_volumes.append(np.random.randint(100, 10000))
            
            # 创建DataFrame
            df = pd.DataFrame({
                'date': dates,
                'sentiment_score': sentiment_scores,
                'social_volume': social_volumes
            })
            
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"获取情绪数据时出错: {str(e)}")
            return pd.DataFrame()
    
    @classmethod
    async def _get_exchange_reserve_data(cls, token: str, days: int) -> pd.DataFrame:
        """
        获取交易所存量数据
        
        Args:
            token: 代币符号
            days: 历史数据天数
            
        Returns:
            pd.DataFrame: 交易所存量数据
        """
        # 在实际项目中，这里应该调用相关API获取交易所存量数据
        # 这里我们生成一些模拟数据用于演示
        
        try:
            dates = []
            reserves = []
            
            base_reserve = 1000000  # 基础存量值
            if token == 'BTC':
                base_reserve = 100000
            elif token == 'ETH':
                base_reserve = 1000000
            
            for day in range(days):
                date = datetime.now() - timedelta(days=day)
                dates.append(date)
                
                # 生成随机波动的存量
                daily_change = np.random.normal(0, 0.02)  # 均值0，标准差0.02的正态分布
                reserve = base_reserve * (1 + daily_change)
                reserves.append(reserve)
                
                # 更新基础值，模拟趋势
                base_reserve = reserve
            
            # 创建DataFrame
            df = pd.DataFrame({
                'date': dates,
                'reserve': reserves
            })
            
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"获取交易所存量数据时出错: {str(e)}")
            return pd.DataFrame() 