from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
import logging
import ccxt
from app.services.exchange_service import ExchangeService
from app.core.exceptions import ExternalAPIException

router = APIRouter(prefix="/ccxt", tags=["ccxt"])
logger = logging.getLogger(__name__)

@router.get("/exchanges", summary="获取所有支持的交易所列表")
async def get_exchanges() -> List[str]:
    """
    返回CCXT库支持的所有交易所列表
    """
    try:
        # ccxt.exchanges是一个包含所有支持交易所ID的列表
        return ccxt.exchanges
    except Exception as e:
        logger.error(f"获取交易所列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取交易所列表失败: {str(e)}")

@router.get("/exchanges/{exchange_id}", summary="获取交易所信息")
async def get_exchange_info(exchange_id: str) -> Dict[str, Any]:
    """
    获取指定交易所的详细信息
    
    参数:
    - exchange_id: 交易所ID (如 'binance', 'huobi', 'okex')
    """
    try:
        if exchange_id not in ccxt.exchanges:
            raise HTTPException(status_code=404, detail=f"不支持的交易所: {exchange_id}")
        
        exchange = ExchangeService.get_exchange_instance(exchange_id)
        # 获取交易所的基本信息
        markets = await ExchangeService.get_markets(exchange_id)
        
        return {
            "id": exchange.id,
            "name": exchange.name,
            "markets_count": len(markets) if markets else 0,
            "timeframes": exchange.timeframes if hasattr(exchange, 'timeframes') else None,
            "has": exchange.has,
            "urls": exchange.urls,
            "version": exchange.version if hasattr(exchange, 'version') else None,
            "api": exchange.api if hasattr(exchange, 'api') else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易所信息失败: {exchange_id}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取交易所信息失败: {str(e)}")

@router.get("/ticker/{exchange_id}/{symbol}", summary="获取交易对的当前行情")
async def get_ticker(
    exchange_id: str,
    symbol: str,
) -> Dict[str, Any]:
    """
    获取指定交易所和交易对的当前行情
    
    参数:
    - exchange_id: 交易所ID (如 'binance', 'huobi', 'okex')
    - symbol: 交易对名称 (如 'BTC/USDT', 'ETH/USDT')
    """
    try:
        ticker = await ExchangeService.get_ticker(exchange_id, symbol)
        return ticker
    except ExternalAPIException as e:
        logger.error(f"获取行情失败: {exchange_id}/{symbol}, 错误: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"获取行情失败: {exchange_id}/{symbol}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取行情失败: {str(e)}")

@router.get("/ohlcv/{exchange_id}/{symbol}", summary="获取K线数据")
async def get_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str = Query("1h", description="时间周期 (如 '1m', '5m', '15m', '1h', '4h', '1d')"),
    limit: int = Query(100, description="返回的K线数量", ge=1, le=1000),
    since: Optional[int] = Query(None, description="开始时间戳 (毫秒)")
) -> List[List[float]]:
    """
    获取指定交易所和交易对的K线数据
    
    参数:
    - exchange_id: 交易所ID (如 'binance', 'huobi', 'okex')
    - symbol: 交易对名称 (如 'BTC/USDT', 'ETH/USDT')
    - timeframe: 时间周期
    - limit: 返回的K线数量
    - since: 开始时间戳 (毫秒)
    
    返回:
    K线数据数组，每个元素包含 [timestamp, open, high, low, close, volume]
    """
    try:
        ohlcv = await ExchangeService.get_ohlcv(
            exchange_id, symbol, timeframe, limit, since
        )
        return ohlcv
    except ExternalAPIException as e:
        logger.error(f"获取K线数据失败: {exchange_id}/{symbol}, 错误: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"获取K线数据失败: {exchange_id}/{symbol}, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取K线数据失败: {str(e)}") 