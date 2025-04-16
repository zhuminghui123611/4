const express = require('express');
const serverless = require('serverless-http');
const cors = require('cors');
const axios = require('axios');
const ccxt = require('ccxt');

// 创建Express应用
const app = express();

// 基本中间件
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());

// 定义API版本和基础路径
const API_V1_BASE = '/api/v1';

// 硬编码API密钥（替换为您自己的密钥）
const ANKR_API_KEY = 'ce9c9f46eac0e045692e0d041fb543747122fb07b9b50f705f70f1004d841840'; // Ankr API密钥
const RESERVOIR_API_KEY = 'd1d6d023-5e2f-5561-8184-6417a48c2f01'; // Reservoir API密钥
const ONEINCH_API_KEY = 'BFmmhv1wAlc12w1jd6xy8YMy5y0sxLPh'; // 1inch API密钥
const WALLETCONNECT_PROJECT_ID = '64b6a6cc7a2296ccb0b97b887b6dee1a';

// API基础URLs
const ANKR_BASE_URL = 'https://api.ankr.com/v2';
const RESERVOIR_BASE_URL = 'https://api.reservoir.tools';
const ONEINCH_BASE_URL = 'https://api.1inch.io/v5.0';

// 健康检查端点
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    version: '1.0.0'
  });
});

// 简单测试端点
app.get(`${API_V1_BASE}/test`, (req, res) => {
  res.json({
    message: '服务正常运行',
    timestamp: new Date().toISOString()
  });
});

// WalletConnect配置端点
app.get(`${API_V1_BASE}/wallet/connect-info`, (req, res) => {
  res.json({
    projectId: WALLETCONNECT_PROJECT_ID,
    supportedChains: ['ethereum', 'polygon', 'binance-smart-chain'],
    message: 'WalletConnect配置信息'
  });
});

// API服务状态检查
app.get(`${API_V1_BASE}/status`, async (req, res) => {
  try {
    const services = [
      { name: 'Ankr API', configured: true },
      { name: 'Reservoir API', configured: true },
      { name: '1inch API', configured: true },
      { name: 'WalletConnect', configured: true },
      { name: 'CCXT', configured: true }
    ];
    
    res.json({
      status: 'operational',
      services,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '服务状态检查失败',
        details: error.message
      }
    });
  }
});

// Ankr简化端点
app.get(`${API_V1_BASE}/ankr/info`, (req, res) => {
  res.json({
    service: 'Ankr API',
    status: 'configured',
    supportedChains: ['ethereum', 'polygon', 'bsc', 'avalanche', 'arbitrum'],
    timestamp: new Date().toISOString()
  });
});

// Reservoir简化端点
app.get(`${API_V1_BASE}/reservoir/info`, (req, res) => {
  res.json({
    service: 'Reservoir API',
    status: 'configured',
    supportedChains: ['ethereum', 'polygon', 'arbitrum', 'optimism'],
    timestamp: new Date().toISOString()
  });
});

// 1inch简化端点
app.get(`${API_V1_BASE}/1inch/info`, (req, res) => {
  res.json({
    service: '1inch API',
    status: 'configured',
    supportedChains: ['ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism'],
    timestamp: new Date().toISOString()
  });
});

// CCXT简化端点
app.get(`${API_V1_BASE}/ccxt/info`, (req, res) => {
  res.json({
    service: 'CCXT API',
    status: 'configured',
    supportedExchanges: ccxt.exchanges.length,
    timestamp: new Date().toISOString()
  });
});

// 简化版Ankr原生代币余额查询
app.get(`${API_V1_BASE}/native-balance/:chain/:address`, async (req, res) => {
  try {
    const { chain, address } = req.params;
    
    const response = await axios.post(
      ANKR_BASE_URL,
      {
        jsonrpc: '2.0',
        method: 'ankr_getAccountBalance',
        params: {
          blockchain: chain,
          walletAddress: address
        },
        id: 1
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': ANKR_API_KEY
        }
      }
    );
    
    res.json(response.data);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取原生代币余额失败',
        details: error.message
      }
    });
  }
});

// 简化版Reservoir NFT集合信息
app.get(`${API_V1_BASE}/collections/:collectionId`, async (req, res) => {
  try {
    const { collectionId } = req.params;
    const chain = req.query.chain || 'ethereum';
    
    const response = await axios.get(
      `${RESERVOIR_BASE_URL}/collections/v5?id=${collectionId}`,
      {
        headers: {
          'x-api-key': RESERVOIR_API_KEY
        }
      }
    );
    
    res.json(response.data);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取NFT集合信息失败',
        details: error.message
      }
    });
  }
});

// 简化版1inch代币列表
app.get(`${API_V1_BASE}/tokens/:chainId`, async (req, res) => {
  try {
    const { chainId } = req.params;
    
    const response = await axios.get(
      `${ONEINCH_BASE_URL}/${chainId}/tokens`,
      {
        headers: {
          'Accept': 'application/json',
          'Authorization': `Bearer ${ONEINCH_API_KEY}`
        }
      }
    );
    
    res.json(response.data);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取代币列表失败',
        details: error.message
      }
    });
  }
});

// CCXT - 获取所有支持的交易所列表
app.get(`${API_V1_BASE}/ccxt/exchanges`, (req, res) => {
  try {
    res.json(ccxt.exchanges);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取交易所列表失败',
        details: error.message
      }
    });
  }
});

// CCXT - 获取交易所信息
app.get(`${API_V1_BASE}/ccxt/exchanges/:exchangeId`, async (req, res) => {
  try {
    const { exchangeId } = req.params;
    
    if (!ccxt.exchanges.includes(exchangeId)) {
      return res.status(404).json({
        error: {
          status: 404,
          message: `不支持的交易所: ${exchangeId}`
        }
      });
    }
    
    // 创建交易所实例
    const exchange = new ccxt[exchangeId]({
      enableRateLimit: true
    });
    
    // 获取交易所信息
    await exchange.loadMarkets();
    
    const exchangeInfo = {
      id: exchange.id,
      name: exchange.name,
      markets_count: Object.keys(exchange.markets).length,
      timeframes: exchange.timeframes || {},
      has: exchange.has,
      urls: exchange.urls,
      version: exchange.version,
      countries: exchange.countries,
      supported_cryptos: Object.keys(exchange.currencies || {})
    };
    
    res.json(exchangeInfo);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取交易所信息失败',
        details: error.message
      }
    });
  }
});

// CCXT - 获取行情数据
app.get(`${API_V1_BASE}/ccxt/ticker/:exchangeId/:symbol`, async (req, res) => {
  try {
    const { exchangeId, symbol } = req.params;
    
    if (!ccxt.exchanges.includes(exchangeId)) {
      return res.status(404).json({
        error: {
          status: 404,
          message: `不支持的交易所: ${exchangeId}`
        }
      });
    }
    
    // 创建交易所实例
    const exchange = new ccxt[exchangeId]({
      enableRateLimit: true
    });
    
    // 获取ticker数据
    const ticker = await exchange.fetchTicker(symbol);
    
    res.json(ticker);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取行情数据失败',
        details: error.message
      }
    });
  }
});

// CCXT - 获取K线数据
app.get(`${API_V1_BASE}/ccxt/ohlcv/:exchangeId/:symbol`, async (req, res) => {
  try {
    const { exchangeId, symbol } = req.params;
    const timeframe = req.query.timeframe || '1h';
    const limit = parseInt(req.query.limit || '100', 10);
    const since = req.query.since ? parseInt(req.query.since, 10) : undefined;
    
    if (!ccxt.exchanges.includes(exchangeId)) {
      return res.status(404).json({
        error: {
          status: 404,
          message: `不支持的交易所: ${exchangeId}`
        }
      });
    }
    
    // 创建交易所实例
    const exchange = new ccxt[exchangeId]({
      enableRateLimit: true
    });
    
    // 检查交易所是否支持OHLCV
    if (!exchange.has.fetchOHLCV) {
      return res.status(400).json({
        error: {
          status: 400,
          message: `交易所 ${exchangeId} 不支持获取K线数据`
        }
      });
    }
    
    // 检查交易所是否支持请求的时间周期
    await exchange.loadMarkets();
    if (!exchange.timeframes || !(timeframe in exchange.timeframes)) {
      return res.status(400).json({
        error: {
          status: 400,
          message: `交易所 ${exchangeId} 不支持时间周期 ${timeframe}`
        }
      });
    }
    
    // 获取OHLCV数据
    const ohlcv = await exchange.fetchOHLCV(symbol, timeframe, since, limit);
    
    res.json(ohlcv);
  } catch (error) {
    res.status(500).json({
      error: {
        status: 500,
        message: '获取K线数据失败',
        details: error.message
      }
    });
  }
});

// 404处理
app.use((req, res) => {
  res.status(404).json({
    error: {
      status: 404,
      message: '未找到请求的资源'
    }
  });
});

// 错误处理中间件
app.use((err, req, res, next) => {
  console.error('错误:', err);
  
  res.status(500).json({
    error: {
      status: 500,
      message: err.message,
      timestamp: new Date().toISOString()
    }
  });
});

// 导出serverless函数处理器
const handler = serverless(app);
module.exports.handler = async (event, context) => {
  // 添加缓存控制头
  const result = await handler(event, context);
  
  // 如果没有错误，添加默认缓存控制
  if (result.statusCode >= 200 && result.statusCode < 400) {
    if (!result.headers['Cache-Control']) {
      result.headers['Cache-Control'] = 'public, max-age=60';
    }
  }
  
  return result;
}; 