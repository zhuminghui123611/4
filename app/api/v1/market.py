from fastapi import APIRouter, Query, Path, Depends, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.market_data import (
    MarketDataResponse, 
    MarketDataType, 
    DataSourceType,
    TimeFrame
)
from app.services.exchange_service import ExchangeService
from app.core.exceptions import BadRequestException, ExternalAPIException

router = APIRouter()


@router.get("/exchanges", response_model=List[str])
async def get_supported_exchanges():
    """
    获取支持的交易所列表
    
    返回系统支持的所有交易所列表。
    """
    try:
        exchanges = ExchangeService.get_supported_exchanges()
        return exchanges
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{exchange}/{symbol}", response_model=MarketDataResponse)
async def get_ticker(
    exchange: str = Path(..., description="交易所ID"),
    symbol: str = Path(..., description="交易对符号，例如BTC/USDT")
):
    """
    获取交易对的当前行情
    
    返回指定交易所和交易对的最新行情数据。
    """
    try:
        ticker_data = await ExchangeService.get_ticker(exchange, symbol)
        
        return MarketDataResponse(
            success=True,
            data_type=MarketDataType.TICKER,
            data=ticker_data,
            source=DataSourceType.EXCHANGE
        )
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ohlcv/{exchange}/{symbol}", response_model=MarketDataResponse)
async def get_ohlcv(
    exchange: str = Path(..., description="交易所ID"),
    symbol: str = Path(..., description="交易对符号，例如BTC/USDT"),
    timeframe: str = Query("1d", description="时间周期: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M"),
    limit: int = Query(100, description="获取数量限制", ge=1, le=1000),
    since: Optional[int] = Query(None, description="开始时间戳(毫秒)")
):
    """
    获取K线数据
    
    返回指定交易所和交易对的K线(蜡烛图)数据。
    """
    try:
        ohlcv_data = await ExchangeService.get_ohlcv(exchange, symbol, timeframe, limit, since)
        
        return MarketDataResponse(
            success=True,
            data_type=MarketDataType.OHLCV,
            data=ohlcv_data,
            source=DataSourceType.EXCHANGE
        )
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{exchange}/{symbol}", response_model=MarketDataResponse)
async def get_order_book(
    exchange: str = Path(..., description="交易所ID"),
    symbol: str = Path(..., description="交易对符号，例如BTC/USDT"),
    limit: int = Query(20, description="深度限制", ge=1, le=100)
):
    """
    获取订单簿数据
    
    返回指定交易所和交易对的订单簿数据。
    """
    try:
        order_book_data = await ExchangeService.get_order_book(exchange, symbol, limit)
        
        return MarketDataResponse(
            success=True,
            data_type=MarketDataType.ORDER_BOOK,
            data=order_book_data,
            source=DataSourceType.EXCHANGE
        )
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{exchange}/{symbol}", response_model=MarketDataResponse)
async def get_trades(
    exchange: str = Path(..., description="交易所ID"),
    symbol: str = Path(..., description="交易对符号，例如BTC/USDT"),
    limit: int = Query(100, description="获取数量限制", ge=1, le=1000),
    since: Optional[int] = Query(None, description="开始时间戳(毫秒)")
):
    """
    获取最近成交记录
    
    返回指定交易所和交易对的最近成交记录。
    """
    try:
        trades_data = await ExchangeService.get_trades(exchange, symbol, limit, since)
        
        return MarketDataResponse(
            success=True,
            data_type=MarketDataType.TRADE,
            data=trades_data,
            source=DataSourceType.EXCHANGE
        )
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/markets/{exchange}", response_model=Dict[str, Any])
async def get_markets(
    exchange: str = Path(..., description="交易所ID"),
    reload: bool = Query(False, description="是否强制重新加载")
):
    """
    获取交易所市场数据
    
    返回指定交易所支持的所有市场数据。
    """
    try:
        markets = await ExchangeService.load_markets(exchange, reload)
        
        return {
            "success": True,
            "exchange": exchange,
            "markets": markets
        }
    except BadRequestException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ExternalAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 