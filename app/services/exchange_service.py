import ccxt
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import time
import json
from decimal import Decimal
import httpx

from app.models.market_data import (
    MarketDataType, 
    OHLCVData, 
    TickerData, 
    OrderBookData, 
    TradeData, 
    DataSourceType,
    TimeFrame,
    OrderBookItem
)
from app.models.trading import (
    OrderSide, 
    OrderType, 
    OrderStatus, 
    CreateOrderRequest, 
    OrderResponse,
    TradingPlatform
)
from app.db.redis import RedisClient
from app.core.exceptions import ExternalAPIException, BadRequestException
from app.core.config import settings

logger = logging.getLogger(__name__)

class ExchangeService:
    """交易所服务，处理与CCXT库的交互"""
    
    # 交易所实例缓存
    _exchange_instances: Dict[str, ccxt.Exchange] = {}
    
    # 支持的交易所列表
    _supported_exchanges = [
        'binance', 'okx', 'kucoin', 'huobi', 'gate', 'bybit',
        'coinbase', 'kraken', 'bitfinex', 'bitstamp', 'ftx'
    ]
    
    # CCXT状态码到自定义OrderStatus的映射
    _status_mapping = {
        'open': OrderStatus.OPEN,
        'closed': OrderStatus.FILLED,
        'canceled': OrderStatus.CANCELED,
        'expired': OrderStatus.EXPIRED,
        'rejected': OrderStatus.REJECTED,
        'pending': OrderStatus.PENDING,
    }
    
    # 中继服务API基础URL
    _relay_api_base_url = "https://calm-twilight-b880c5.netlify.app/api/v1/ccxt"
    
    # 是否使用中继服务
    _use_relay_service = True
    
    @classmethod
    def get_supported_exchanges(cls) -> List[str]:
        """获取支持的交易所列表"""
        return cls._supported_exchanges
    
    @classmethod
    def get_exchange_instance(cls, exchange_id: str) -> ccxt.Exchange:
        """
        获取交易所实例，如果不存在则创建新实例
        
        Args:
            exchange_id: 交易所ID
            
        Returns:
            ccxt.Exchange: 交易所实例
            
        Raises:
            BadRequestException: 如果交易所不支持
        """
        if exchange_id not in cls._supported_exchanges:
            raise BadRequestException(f"不支持的交易所: {exchange_id}")
        
        if exchange_id not in cls._exchange_instances:
            try:
                # 获取交易所类
                exchange_class = getattr(ccxt, exchange_id)
                
                # 创建交易所实例
                cls._exchange_instances[exchange_id] = exchange_class({
                    'enableRateLimit': True,  # 启用请求频率限制
                })
                logger.info(f"已创建交易所实例 {exchange_id}")
            except (AttributeError, TypeError) as e:
                logger.error(f"创建交易所实例失败 {exchange_id}: {str(e)}")
                raise ExternalAPIException(f"创建交易所连接失败: {str(e)}")
        
        return cls._exchange_instances[exchange_id]
    
    @classmethod
    async def _get_from_relay_service(cls, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        从中继服务获取数据
        
        Args:
            endpoint: API端点路径
            params: 查询参数
            
        Returns:
            Dict[str, Any]: API响应数据
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        url = f"{cls._relay_api_base_url}/{endpoint}"
        logger.debug(f"从中继服务获取数据: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code >= 400:
                    error_message = f"中继服务请求失败: [{response.status_code}] - {response.text}"
                    logger.error(error_message)
                    raise ExternalAPIException(
                        status_code=response.status_code,
                        message=error_message
                    )
                
                return response.json()
        except httpx.RequestError as e:
            error_message = f"中继服务连接异常: {str(e)}"
            logger.error(error_message)
            raise ExternalAPIException(
                status_code=500,
                message=error_message
            )
    
    @classmethod
    async def get_ticker(cls, exchange_id: str, symbol: str) -> TickerData:
        """
        获取交易对的当前行情
        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对符号
            
        Returns:
            TickerData: 行情数据
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        # 生成缓存键
        cache_key = f"ticker:{exchange_id}:{symbol}"
        
        # 尝试从缓存获取数据
        cached_data = RedisClient.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        try:
            # 尝试使用中继服务
            if cls._use_relay_service:
                try:
                    ticker_data = await cls._get_from_relay_service(f"ticker/{exchange_id}/{symbol}")
                    
                    # 构建响应数据
                    ticker = TickerData(
                        symbol=symbol,
                        exchange=exchange_id,
                        timestamp=ticker_data['timestamp'],
                        datetime=datetime.fromtimestamp(ticker_data['timestamp'] / 1000),
                        bid=ticker_data.get('bid'),
                        ask=ticker_data.get('ask'),
                        last=ticker_data['last'],
                        high=ticker_data.get('high'),
                        low=ticker_data.get('low'),
                        volume=ticker_data.get('volume'),
                        change=ticker_data.get('change'),
                        percentage=ticker_data.get('percentage'),
                        source=DataSourceType.EXCHANGE
                    )
                    
                    # 缓存数据，10秒过期
                    RedisClient.set(cache_key, json.dumps(ticker_data), ex=10)
                    
                    return ticker
                except ExternalAPIException as e:
                    logger.warning(f"中继服务获取ticker失败，尝试直接连接: {str(e)}")
            
            # 如果中继服务失败或未启用，尝试直接连接
            exchange = cls.get_exchange_instance(exchange_id)
            ticker = exchange.fetch_ticker(symbol)
            
            # 构建响应数据
            ticker_data = TickerData(
                symbol=symbol,
                exchange=exchange_id,
                timestamp=ticker['timestamp'],
                datetime=datetime.fromtimestamp(ticker['timestamp'] / 1000),
                bid=ticker.get('bid'),
                ask=ticker.get('ask'),
                last=ticker['last'],
                high=ticker.get('high'),
                low=ticker.get('low'),
                volume=ticker.get('volume'),
                change=ticker.get('change'),
                percentage=ticker.get('percentage'),
                source=DataSourceType.EXCHANGE
            )
            
            # 缓存数据，10秒过期
            RedisClient.set(cache_key, ticker_data.json(), ex=10)
            
            return ticker_data
        except ccxt.NetworkError as e:
            logger.error(f"获取ticker时网络错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"获取ticker时交易所错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"获取ticker时发生未知错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"获取数据失败: {str(e)}")
    
    @classmethod
    async def get_ohlcv(
        cls, 
        exchange_id: str, 
        symbol: str, 
        timeframe: str = '1d', 
        limit: int = 100,
        since: Optional[int] = None
    ) -> List[OHLCVData]:
        """
        获取K线数据
        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对符号
            timeframe: 时间周期
            limit: 获取数量限制
            since: 开始时间戳 (毫秒)
            
        Returns:
            List[OHLCVData]: K线数据列表
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        # 生成缓存键
        cache_key = f"ohlcv:{exchange_id}:{symbol}:{timeframe}:{limit}:{since or 0}"
        
        # 尝试从缓存获取数据
        cached_data = RedisClient.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        try:
            # 尝试使用中继服务
            if cls._use_relay_service:
                try:
                    params = {
                        'timeframe': timeframe,
                        'limit': limit
                    }
                    if since:
                        params['since'] = since
                        
                    ohlcv_data = await cls._get_from_relay_service(
                        f"ohlcv/{exchange_id}/{symbol}", 
                        params=params
                    )
                    
                    # 转换为响应数据
                    result = []
                    for candle in ohlcv_data:
                        timestamp, open_price, high, low, close, volume = candle
                        result.append(OHLCVData(
                            symbol=symbol,
                            exchange=exchange_id,
                            timestamp=timestamp,
                            datetime=datetime.fromtimestamp(timestamp / 1000),
                            timeframe=timeframe,
                            open=open_price,
                            high=high,
                            low=low,
                            close=close,
                            volume=volume,
                            source=DataSourceType.EXCHANGE
                        ))
                    
                    # 缓存数据
                    # 根据时间周期设置不同的过期时间
                    if timeframe in ['1m', '5m', '15m']:
                        cache_ttl = 60  # 1分钟
                    elif timeframe in ['30m', '1h', '2h', '4h']:
                        cache_ttl = 300  # 5分钟
                    else:
                        cache_ttl = 1800  # 30分钟
                        
                    RedisClient.set(cache_key, json.dumps([c.dict() for c in result]), ex=cache_ttl)
                    
                    return result
                except ExternalAPIException as e:
                    logger.warning(f"中继服务获取OHLCV失败，尝试直接连接: {str(e)}")
            
            # 如果中继服务失败或未启用，尝试直接连接
            exchange = cls.get_exchange_instance(exchange_id)
            
            # 检查交易所是否支持所请求的时间周期
            if not hasattr(exchange, 'timeframes') or timeframe not in exchange.timeframes:
                raise BadRequestException(f"交易所 {exchange_id} 不支持 {timeframe} 时间周期")
            
            # 获取K线数据
            ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            
            # 转换为响应数据
            result = []
            for candle in ohlcv_data:
                timestamp, open_price, high, low, close, volume = candle
                result.append(OHLCVData(
                    symbol=symbol,
                    exchange=exchange_id,
                    timestamp=timestamp,
                    datetime=datetime.fromtimestamp(timestamp / 1000),
                    timeframe=timeframe,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    source=DataSourceType.EXCHANGE
                ))
            
            # 缓存数据
            # 根据时间周期设置不同的过期时间
            if timeframe in ['1m', '5m', '15m']:
                cache_ttl = 60  # 1分钟
            elif timeframe in ['30m', '1h', '2h', '4h']:
                cache_ttl = 300  # 5分钟
            else:
                cache_ttl = 1800  # 30分钟
                
            RedisClient.set(cache_key, json.dumps([c.dict() for c in result]), ex=cache_ttl)
            
            return result
        except ccxt.NetworkError as e:
            logger.error(f"获取OHLCV时网络错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"获取OHLCV时交易所错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"获取OHLCV时发生未知错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"获取数据失败: {str(e)}")
    
    @classmethod
    async def get_order_book(cls, exchange_id: str, symbol: str, limit: int = 20) -> OrderBookData:
        """
        获取订单簿数据
        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对符号
            limit: 深度限制
            
        Returns:
            OrderBookData: 订单簿数据
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        # 生成缓存键
        cache_key = f"orderbook:{exchange_id}:{symbol}:{limit}"
        
        # 尝试从缓存获取数据
        cached_data = RedisClient.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # 如果缓存中没有，则从交易所获取
        try:
            exchange = cls.get_exchange_instance(exchange_id)
            order_book = exchange.fetch_order_book(symbol, limit)
            
            # 构建订单簿项目
            bids = [OrderBookItem(price=bid[0], amount=bid[1]) for bid in order_book['bids']]
            asks = [OrderBookItem(price=ask[0], amount=ask[1]) for ask in order_book['asks']]
            
            # 构建响应数据
            result = OrderBookData(
                symbol=symbol,
                exchange=exchange_id,
                timestamp=order_book['timestamp'] or int(time.time() * 1000),
                datetime=datetime.fromtimestamp((order_book['timestamp'] or int(time.time() * 1000)) / 1000),
                bids=bids,
                asks=asks,
                nonce=order_book.get('nonce'),
                source=DataSourceType.EXCHANGE
            )
            
            # 缓存数据，5秒过期
            RedisClient.set(cache_key, result.json(), ex=5)
            
            return result
        except ccxt.NetworkError as e:
            logger.error(f"获取订单簿时网络错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"获取订单簿时交易所错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"获取订单簿时发生未知错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"获取数据失败: {str(e)}")
    
    @classmethod
    async def get_trades(
        cls, 
        exchange_id: str, 
        symbol: str, 
        limit: int = 100,
        since: Optional[int] = None
    ) -> List[TradeData]:
        """
        获取最近成交记录
        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对符号
            limit: 获取数量限制
            since: 开始时间戳 (毫秒)
            
        Returns:
            List[TradeData]: 成交记录列表
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        # 生成缓存键
        cache_key = f"trades:{exchange_id}:{symbol}:{limit}:{since or 0}"
        
        # 尝试从缓存获取数据
        cached_data = RedisClient.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # 如果缓存中没有，则从交易所获取
        try:
            exchange = cls.get_exchange_instance(exchange_id)
            trades = exchange.fetch_trades(symbol, since, limit)
            
            # 转换为响应数据
            result = []
            for trade in trades:
                result.append(TradeData(
                    symbol=symbol,
                    exchange=exchange_id,
                    timestamp=trade['timestamp'],
                    datetime=datetime.fromtimestamp(trade['timestamp'] / 1000),
                    id=trade.get('id'),
                    order=trade.get('order'),
                    type=trade.get('type'),
                    side=trade['side'],
                    price=trade['price'],
                    amount=trade['amount'],
                    cost=trade.get('cost'),
                    fee=trade.get('fee'),
                    source=DataSourceType.EXCHANGE
                ))
            
            # 缓存数据，30秒过期
            RedisClient.set(cache_key, json.dumps([item.dict() for item in result]), ex=30)
            
            return result
        except ccxt.NetworkError as e:
            logger.error(f"获取成交记录时网络错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"获取成交记录时交易所错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"获取成交记录时发生未知错误 {exchange_id}:{symbol} - {str(e)}")
            raise ExternalAPIException(f"获取数据失败: {str(e)}")
    
    @classmethod
    async def create_order(cls, request: CreateOrderRequest) -> OrderResponse:
        """
        创建订单
        
        Args:
            request: 创建订单请求
            
        Returns:
            OrderResponse: 订单响应
            
        Raises:
            ExternalAPIException: 如果API调用失败
            BadRequestException: 如果请求参数无效
        """
        if request.platform != TradingPlatform.CENTRALIZED:
            raise BadRequestException("当前仅支持中心化交易所下单")
        
        exchange_id = request.exchange
        
        try:
            exchange = cls.get_exchange_instance(exchange_id)
            
            # 检查交易所是否已经初始化认证信息
            if not exchange.apiKey or not exchange.secret:
                raise BadRequestException(f"交易所 {exchange_id} 未配置API密钥")
            
            # 根据订单类型准备参数
            order_type = request.type.value
            
            params = {}
            if request.custom_parameters:
                params.update(request.custom_parameters)
            
            if request.client_order_id:
                params['clientOrderId'] = request.client_order_id
            
            # 创建订单
            if order_type == OrderType.MARKET.value:
                # 市价单
                order = exchange.create_order(
                    symbol=request.symbol,
                    type=order_type,
                    side=request.side.value,
                    amount=float(request.amount),
                    params=params
                )
            elif order_type == OrderType.LIMIT.value:
                # 限价单
                if not request.price:
                    raise BadRequestException("限价单必须指定价格")
                
                order = exchange.create_order(
                    symbol=request.symbol,
                    type=order_type,
                    side=request.side.value,
                    amount=float(request.amount),
                    price=float(request.price),
                    params=params
                )
            elif order_type in [OrderType.STOP_LIMIT.value, OrderType.STOP_MARKET.value]:
                # 止损单
                if not request.stop_price:
                    raise BadRequestException("止损单必须指定止损价格")
                
                if order_type == OrderType.STOP_LIMIT.value and not request.price:
                    raise BadRequestException("止损限价单必须指定价格")
                
                # 不同交易所的止损单参数可能不同，这里使用通用方式
                params['stopPrice'] = float(request.stop_price)
                
                order = exchange.create_order(
                    symbol=request.symbol,
                    type=order_type,
                    side=request.side.value,
                    amount=float(request.amount),
                    price=float(request.price) if request.price else None,
                    params=params
                )
            
            # 构建响应
            status = cls._status_mapping.get(order.get('status', 'open'), OrderStatus.OPEN)
            
            return OrderResponse(
                order_id=order['id'],
                client_order_id=order.get('clientOrderId') or request.client_order_id,
                status=status,
                symbol=request.symbol,
                side=request.side,
                type=request.type,
                price=Decimal(str(order.get('price', 0))) if order.get('price') else None,
                amount=Decimal(str(order['amount'])),
                filled=Decimal(str(order.get('filled', 0))),
                remaining=Decimal(str(order.get('remaining', order['amount']))),
                cost=Decimal(str(order.get('cost', 0))) if order.get('cost') else None,
                fee=order.get('fee'),
                created_at=datetime.fromtimestamp(order['timestamp'] / 1000) if order.get('timestamp') else datetime.now(),
                updated_at=None,
                platform=TradingPlatform.CENTRALIZED,
                exchange=exchange_id,
                raw_response=order
            )
        except ccxt.NetworkError as e:
            logger.error(f"创建订单时网络错误 {exchange_id}:{request.symbol} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"创建订单时交易所错误 {exchange_id}:{request.symbol} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"创建订单时发生未知错误 {exchange_id}:{request.symbol} - {str(e)}")
            raise ExternalAPIException(f"下单失败: {str(e)}")
    
    @classmethod
    async def get_markets(cls, exchange_id: str, reload: bool = False) -> Dict[str, Any]:
        """
        获取交易所支持的市场数据
        
        Args:
            exchange_id: 交易所ID
            reload: 是否强制重新加载市场数据
            
        Returns:
            Dict[str, Any]: 市场数据
            
        Raises:
            ExternalAPIException: 如果API调用失败
        """
        # 生成缓存键
        cache_key = f"markets:{exchange_id}"
        
        # 如果不强制重新加载，尝试从缓存获取
        if not reload:
            cached_data = RedisClient.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        
        try:
            # 尝试使用中继服务
            if cls._use_relay_service:
                try:
                    exchange_info = await cls._get_from_relay_service(f"exchanges/{exchange_id}")
                    markets = {}
                    # 这里假设中继服务返回的交易所信息中包含markets字段
                    # 如果不包含，需要额外调用市场数据API
                    if 'markets' in exchange_info:
                        markets = exchange_info['markets']
                    
                    # 缓存数据，1小时过期
                    RedisClient.set(cache_key, json.dumps(markets), ex=3600)
                    return markets
                except ExternalAPIException as e:
                    logger.warning(f"中继服务获取市场数据失败，尝试直接连接: {str(e)}")
            
            # 如果中继服务失败或未启用，尝试直接连接
            exchange = cls.get_exchange_instance(exchange_id)
            markets = exchange.load_markets(reload=reload)
            
            # 缓存数据，1小时过期
            RedisClient.set(cache_key, json.dumps(markets), ex=3600)
            
            return markets
        except ccxt.NetworkError as e:
            logger.error(f"获取市场数据时网络错误 {exchange_id} - {str(e)}")
            raise ExternalAPIException(f"网络连接失败: {str(e)}")
        except ccxt.ExchangeError as e:
            logger.error(f"获取市场数据时交易所错误 {exchange_id} - {str(e)}")
            raise ExternalAPIException(f"交易所返回错误: {str(e)}")
        except Exception as e:
            logger.error(f"获取市场数据时发生未知错误 {exchange_id} - {str(e)}")
            raise ExternalAPIException(f"获取数据失败: {str(e)}")
    
    @classmethod
    def close_exchange_connections(cls):
        """关闭所有交易所连接"""
        for exchange_id, exchange in cls._exchange_instances.items():
            try:
                if hasattr(exchange, 'close') and callable(exchange.close):
                    exchange.close()
                    logger.info(f"关闭交易所连接 {exchange_id}")
            except Exception as e:
                logger.error(f"关闭交易所连接失败 {exchange_id}: {str(e)}")
        
        cls._exchange_instances = {} 