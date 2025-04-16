const express = require('express');
const serverless = require('serverless-http');
const cors = require('cors');
const CcxtAdapter = require('./ccxt-adapter');

// 创建Express应用
const app = express();

// 基本中间件
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());

// API版本和基础路径
const API_BASE = '/api';
const API_V1 = `${API_BASE}/v1`;

/**
 * 错误处理函数
 * @param {Error} error - 错误对象
 * @param {Object} res - Express响应对象
 */
function handleError(error, res) {
  console.error('API错误:', error);
  
  const status = error.status || 500;
  const message = error.message || '服务器内部错误';
  
  res.status(status).json({
    error: {
      status,
      message,
      timestamp: new Date().toISOString()
    }
  });
}

// 健康检查端点
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'ccxt-api',
    timestamp: new Date().toISOString(),
    version: '1.0.0'
  });
});

// CCXT版本信息
app.get(`${API_V1}/version`, (req, res) => {
  try {
    // 获取已安装的ccxt版本
    const ccxtVersion = require('ccxt/package.json').version;
    
    res.json({
      ccxt_version: ccxtVersion,
      api_version: '1.0.0',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 获取所有支持的交易所列表
app.get(`${API_V1}/exchanges`, async (req, res) => {
  try {
    const exchanges = await CcxtAdapter.getAllExchangeIds();
    
    res.json({
      count: exchanges.length,
      exchanges,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 获取交易所信息
app.get(`${API_V1}/exchanges/:exchangeId`, async (req, res) => {
  try {
    const { exchangeId } = req.params;
    const exchangeInfo = await CcxtAdapter.getExchangeInfo(exchangeId);
    
    res.json({
      ...exchangeInfo,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 获取交易对列表
app.get(`${API_V1}/exchanges/:exchangeId/markets`, async (req, res) => {
  try {
    const { exchangeId } = req.params;
    const markets = await CcxtAdapter.getMarkets(exchangeId);
    
    // 转换为更友好的格式
    const formattedMarkets = Object.keys(markets).map(symbol => ({
      symbol,
      base: markets[symbol].base,
      quote: markets[symbol].quote,
      active: markets[symbol].active
    }));
    
    res.json({
      exchange: exchangeId,
      count: formattedMarkets.length,
      markets: formattedMarkets,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 获取行情数据
app.get(`${API_V1}/exchanges/:exchangeId/ticker/:symbol`, async (req, res) => {
  try {
    const { exchangeId, symbol } = req.params;
    const ticker = await CcxtAdapter.getTicker(exchangeId, symbol);
    
    res.json({
      exchange: exchangeId,
      symbol,
      ticker,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 获取K线数据
app.get(`${API_V1}/exchanges/:exchangeId/ohlcv/:symbol`, async (req, res) => {
  try {
    const { exchangeId, symbol } = req.params;
    const { timeframe = '1h', limit = 100, since } = req.query;
    
    const parsedLimit = parseInt(limit, 10);
    const parsedSince = since ? parseInt(since, 10) : undefined;
    
    const ohlcv = await CcxtAdapter.getOHLCV(
      exchangeId, 
      symbol, 
      timeframe, 
      parsedLimit, 
      parsedSince
    );
    
    // 转换为更友好的格式
    const formattedData = ohlcv.map(candle => ({
      timestamp: candle[0],
      datetime: new Date(candle[0]).toISOString(),
      open: candle[1],
      high: candle[2],
      low: candle[3],
      close: candle[4],
      volume: candle[5]
    }));
    
    res.json({
      exchange: exchangeId,
      symbol,
      timeframe,
      count: formattedData.length,
      data: formattedData,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    handleError(error, res);
  }
});

// 404处理
app.use((req, res) => {
  res.status(404).json({
    error: {
      status: 404,
      message: '未找到请求的资源',
      path: req.path
    }
  });
});

// 错误处理中间件
app.use((err, req, res, next) => {
  handleError(err, res);
});

// 导出serverless函数处理器
const handler = serverless(app);

module.exports.handler = async (event, context) => {
  // 添加缓存控制头
  const result = await handler(event, context);
  
  // 对成功响应添加缓存控制
  if (result.statusCode >= 200 && result.statusCode < 400) {
    if (!result.headers['Cache-Control']) {
      // 默认缓存1分钟
      result.headers['Cache-Control'] = 'public, max-age=60';
    }
  }
  
  return result;
}; 