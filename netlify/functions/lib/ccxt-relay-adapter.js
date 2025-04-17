/**
 * CCXT中继适配器 - 用于Netlify Functions
 */

const ccxt = require('ccxt');
const axios = require('axios');

// 中继服务URL
const RELAY_URL = 'https://api.allorigins.win/raw?url=';

// 支持的交易所列表
const SUPPORTED_EXCHANGES = [
  'binance', 'gateio', 'kucoin', 'okx', 'huobi', 'bitget', 
  'mexc', 'bybit', 'coinex', 'bitfinex'
];

// API基础URL
const API_BASE_URLS = {
  binance: 'https://api.binance.com',
  gateio: 'https://api.gateio.ws',
  kucoin: 'https://api.kucoin.com',
  okx: 'https://www.okx.com',
  huobi: 'https://api.huobi.pro',
  bitget: 'https://api.bitget.com',
  mexc: 'https://api.mexc.com',
  bybit: 'https://api.bybit.com',
  coinex: 'https://api.coinex.com',
  bitfinex: 'https://api.bitfinex.com'
};

// 设置CORS响应头
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json'
};

/**
 * 通过中继服务发送API请求
 * @param {string} url - 完整的API URL
 * @returns {Promise<Object>} - API响应
 */
async function fetchViaRelay(url) {
  try {
    const relayUrl = `${RELAY_URL}${encodeURIComponent(url)}`;
    const response = await axios.get(relayUrl);
    return response.data;
  } catch (error) {
    console.error('中继请求失败:', error.message);
    throw new Error(`中继请求失败: ${error.message}`);
  }
}

/**
 * 获取交易所的API端点
 * @param {string} exchange - 交易所ID
 * @param {string} endpoint - API端点路径
 * @returns {string} - 完整的API URL
 */
function getExchangeEndpoint(exchange, endpoint) {
  const baseUrl = API_BASE_URLS[exchange.toLowerCase()];
  if (!baseUrl) {
    throw new Error(`不支持的交易所: ${exchange}`);
  }
  
  return `${baseUrl}${endpoint}`;
}

// 导出API函数
const adapter = {
  // 获取支持的交易所列表
  getExchanges: () => {
    return {
      exchanges: SUPPORTED_EXCHANGES,
      count: SUPPORTED_EXCHANGES.length,
      timestamp: new Date().toISOString()
    };
  },
  
  // 获取特定交易所的行情数据
  getTicker: async (exchange, symbol) => {
    if (!SUPPORTED_EXCHANGES.includes(exchange.toLowerCase())) {
      throw new Error(`不支持的交易所: ${exchange}`);
    }
    
    // 根据不同交易所构建API请求
    let url;
    const formattedSymbol = symbol.replace('/', '_').toUpperCase();
    
    switch (exchange.toLowerCase()) {
      case 'binance':
        url = getExchangeEndpoint('binance', `/api/v3/ticker/price?symbol=${symbol.replace('/', '')}`);
        break;
      case 'gateio':
        url = getExchangeEndpoint('gateio', `/api/v4/spot/tickers?currency_pair=${formattedSymbol}`);
        break;
      case 'kucoin':
        url = getExchangeEndpoint('kucoin', `/api/v1/market/orderbook/level1?symbol=${symbol}`);
        break;
      default:
        throw new Error(`暂不支持该交易所的行情获取: ${exchange}`);
    }
    
    // 通过中继服务发送请求
    const data = await fetchViaRelay(url);
    
    // 根据不同交易所处理响应
    let result;
    switch (exchange.toLowerCase()) {
      case 'binance':
        result = {
          exchange: 'Binance',
          symbol: symbol,
          price: parseFloat(data.price),
          timestamp: new Date().toISOString()
        };
        break;
      case 'gateio':
        result = {
          exchange: 'Gate.io',
          symbol: symbol,
          price: parseFloat(data[0].last),
          change: parseFloat(data[0].change_percentage),
          high: parseFloat(data[0].high_24h),
          low: parseFloat(data[0].low_24h),
          volume: parseFloat(data[0].base_volume),
          timestamp: new Date().toISOString()
        };
        break;
      case 'kucoin':
        result = {
          exchange: 'KuCoin',
          symbol: symbol,
          price: parseFloat(data.data.price),
          timestamp: new Date(data.data.time).toISOString()
        };
        break;
    }
    
    return result;
  },
  
  // 提供给Netlify函数使用的处理器
  createHandler: () => {
    return async (event, context) => {
      // 设置CORS头
      const headers = corsHeaders;
      
      // 处理路径
      const path = event.path || '';
      
      // 解析路径段
      const segments = path.split('/').filter(segment => segment);
      
      try {
        // 健康检查
        if (path === '' || path === '/') {
          return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
              status: 'ok',
              service: 'ccxt-relay-adapter',
              timestamp: new Date().toISOString(),
              supported_exchanges: SUPPORTED_EXCHANGES
            })
          };
        }
        
        // 获取交易所列表
        if (path === '/exchanges') {
          return {
            statusCode: 200,
            headers,
            body: JSON.stringify(adapter.getExchanges())
          };
        }
        
        // 获取特定交易所行情
        const tickerMatch = path.match(/^\/exchange\/([^\/]+)\/ticker\/([^\/]+)$/);
        if (tickerMatch) {
          const exchange = tickerMatch[1];
          const symbol = decodeURIComponent(tickerMatch[2]);
          const data = await adapter.getTicker(exchange, symbol);
          
          return {
            statusCode: 200,
            headers,
            body: JSON.stringify(data)
          };
        }
        
        // 找不到匹配的路径
        return {
          statusCode: 404,
          headers,
          body: JSON.stringify({
            error: '未找到请求的资源',
            path: path,
            available_endpoints: [
              '/',
              '/exchanges',
              '/exchange/:exchangeId/ticker/:symbol'
            ]
          })
        };
        
      } catch (error) {
        console.error('API错误:', error);
        
        return {
          statusCode: 500,
          headers,
          body: JSON.stringify({
            error: error.message
          })
        };
      }
    };
  }
};

// 导出适配器
module.exports = adapter; 