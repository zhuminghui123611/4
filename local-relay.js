// 本地简易中继服务器
const express = require('express');
const cors = require('cors');
const ccxt = require('ccxt');

const app = express();
const PORT = 3000;

// 启用CORS和JSON解析
app.use(cors());
app.use(express.json());

// 健康检查端点
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'local-ccxt-relay',
    timestamp: new Date().toISOString()
  });
});

// 获取交易所列表
app.get('/api/exchanges', async (req, res) => {
  try {
    res.json({
      exchanges: ccxt.exchanges,
      count: ccxt.exchanges.length,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('错误:', error);
    res.status(500).json({
      error: {
        message: error.message,
        status: 500
      }
    });
  }
});

// 获取Gate.io行情数据
app.get('/api/gateio/btcusdt', async (req, res) => {
  try {
    console.log('正在获取Gate.io BTC/USDT行情...');
    const gateio = new ccxt.gateio();
    const ticker = await gateio.fetchTicker('BTC/USDT');
    
    res.json({
      exchange: 'Gate.io',
      symbol: 'BTC/USDT',
      price: ticker.last,
      high: ticker.high,
      low: ticker.low,
      volume: ticker.baseVolume,
      timestamp: new Date(ticker.timestamp).toISOString(),
      raw: ticker
    });
  } catch (error) {
    console.error('获取Gate.io数据错误:', error);
    res.status(500).json({
      error: {
        message: error.message,
        status: 500
      }
    });
  }
});

// 通用交易所行情接口
app.get('/api/exchanges/:exchange/ticker/:symbol', async (req, res) => {
  try {
    const { exchange, symbol } = req.params;
    const decodedSymbol = decodeURIComponent(symbol);
    
    console.log(`正在获取${exchange}的${decodedSymbol}行情...`);
    
    if (!ccxt.exchanges.includes(exchange)) {
      return res.status(404).json({
        error: {
          message: `不支持的交易所: ${exchange}`,
          status: 404
        }
      });
    }
    
    const exchangeInstance = new ccxt[exchange]();
    const ticker = await exchangeInstance.fetchTicker(decodedSymbol);
    
    res.json({
      exchange,
      symbol: decodedSymbol,
      price: ticker.last,
      high: ticker.high,
      low: ticker.low,
      volume: ticker.baseVolume,
      timestamp: new Date(ticker.timestamp).toISOString(),
      raw: ticker
    });
  } catch (error) {
    console.error(`获取${req.params.exchange}数据错误:`, error);
    res.status(500).json({
      error: {
        message: error.message,
        status: 500
      }
    });
  }
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`中继服务已启动: http://localhost:${PORT}`);
  console.log(`健康检查: http://localhost:${PORT}/health`);
  console.log(`Gate.io BTC/USDT: http://localhost:${PORT}/api/gateio/btcusdt`);
}); 