// 简单CCXT API函数 - 无需Express
const ccxt = require('ccxt');

// 函数处理器
exports.handler = async function(event, context) {
  // 设置CORS头
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };
  
  // 解析请求路径
  const path = event.path.replace('/.netlify/functions/ccxt-simple', '');
  const segments = path.split('/').filter(segment => segment);
  
  try {
    // 健康检查
    if (path === '' || path === '/') {
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          status: 'ok',
          message: 'CCXT API运行正常',
          version: ccxt.version,
          timestamp: new Date().toISOString()
        })
      };
    }
    
    // 交易所列表
    if (path === '/exchanges') {
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          exchanges: ccxt.exchanges,
          count: ccxt.exchanges.length,
          timestamp: new Date().toISOString()
        })
      };
    }
    
    // 获取特定交易所行情 - /exchange/:id/ticker/:symbol
    if (segments.length === 4 && segments[0] === 'exchange' && segments[2] === 'ticker') {
      const exchangeId = segments[1];
      const symbol = decodeURIComponent(segments[3]);
      
      // 检查交易所是否支持
      if (!ccxt.exchanges.includes(exchangeId)) {
        return {
          statusCode: 404,
          headers,
          body: JSON.stringify({
            error: `不支持的交易所: ${exchangeId}`,
            supported: ccxt.exchanges.slice(0, 10) // 列出前10个支持的交易所
          })
        };
      }
      
      // 创建交易所实例
      const exchange = new ccxt[exchangeId]();
      
      // 获取行情数据
      const ticker = await exchange.fetchTicker(symbol);
      
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          exchange: exchangeId,
          symbol: symbol,
          price: ticker.last,
          change: ticker.percentage,
          high: ticker.high,
          low: ticker.low,
          volume: ticker.baseVolume,
          timestamp: new Date(ticker.timestamp).toISOString(),
          raw: ticker
        })
      };
    }
    
    // 处理Gate.io BTC/USDT特定请求
    if (path === '/gateio/btc-usdt') {
      const exchange = new ccxt.gateio();
      const ticker = await exchange.fetchTicker('BTC/USDT');
      
      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          exchange: 'Gate.io',
          symbol: 'BTC/USDT',
          price: ticker.last,
          change: ticker.percentage,
          high: ticker.high,
          low: ticker.low,
          volume: ticker.baseVolume,
          timestamp: new Date(ticker.timestamp).toISOString()
        })
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
          '/exchange/:id/ticker/:symbol',
          '/gateio/btc-usdt'
        ]
      })
    };
    
  } catch (error) {
    console.error('CCXT API错误:', error);
    
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({
        error: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
      })
    };
  }
}; 