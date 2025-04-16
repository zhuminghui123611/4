/**
 * CCXT适配器 - 用于访问加密货币交易所API
 * 纯JavaScript实现，适合Netlify Functions
 */

const ccxt = require('ccxt');
const crypto = require('crypto');

// 内存缓存
const cache = {
  exchanges: null,
  markets: {},
  tickers: {},
  ohlcv: {}
};

// 缓存TTL (毫秒)
const CACHE_TTL = {
  exchanges: 3600000, // 1小时
  markets: 300000,    // 5分钟
  tickers: 10000,     // 10秒
  ohlcv: 60000        // 1分钟
};

// 缓存时间戳
const cacheTimestamps = {
  exchanges: 0,
  markets: {},
  tickers: {},
  ohlcv: {}
};

/**
 * 生成缓存键
 * @param {string} type - 缓存类型
 * @param {Object} params - 参数
 * @returns {string} - 缓存键
 */
function generateCacheKey(type, params = {}) {
  const str = JSON.stringify(params);
  return `${type}_${crypto.createHash('md5').update(str).digest('hex')}`;
}

/**
 * 检查缓存是否有效
 * @param {string} type - 缓存类型
 * @param {string} key - 缓存键
 * @returns {boolean} - 缓存是否有效
 */
function isCacheValid(type, key) {
  const timestamp = type === 'exchanges' ? 
    cacheTimestamps.exchanges : 
    cacheTimestamps[type][key];
  
  if (!timestamp) return false;
  
  const now = Date.now();
  return now - timestamp < CACHE_TTL[type];
}

/**
 * 设置缓存
 * @param {string} type - 缓存类型
 * @param {string} key - 缓存键
 * @param {*} data - 要缓存的数据
 */
function setCache(type, key, data) {
  const now = Date.now();
  
  if (type === 'exchanges') {
    cache.exchanges = data;
    cacheTimestamps.exchanges = now;
  } else {
    cache[type][key] = data;
    cacheTimestamps[type][key] = now;
  }
}

/**
 * 获取缓存
 * @param {string} type - 缓存类型
 * @param {string} key - 缓存键
 * @returns {*} - 缓存的数据
 */
function getCache(type, key) {
  if (type === 'exchanges') {
    return cache.exchanges;
  }
  return cache[type][key];
}

/**
 * 创建交易所实例
 * @param {string} exchangeId - 交易所ID
 * @param {Object} params - 交易所参数
 * @returns {Object} - 交易所实例
 */
function createExchange(exchangeId, params = {}) {
  if (!ccxt.exchanges.includes(exchangeId)) {
    throw new Error(`不支持的交易所: ${exchangeId}`);
  }
  
  return new ccxt[exchangeId]({
    enableRateLimit: true,
    timeout: 30000,
    ...params
  });
}

// 导出CCXT适配器
const CcxtAdapter = {
  /**
   * 获取所有支持的交易所列表
   * @returns {Array} - 交易所列表
   */
  async getAllExchangeIds() {
    if (isCacheValid('exchanges')) {
      return getCache('exchanges');
    }
    
    const exchanges = ccxt.exchanges;
    setCache('exchanges', null, exchanges);
    return exchanges;
  },
  
  /**
   * 获取交易所信息
   * @param {string} exchangeId - 交易所ID
   * @returns {Object} - 交易所信息
   */
  async getExchangeInfo(exchangeId) {
    const cacheKey = generateCacheKey('markets', { exchangeId });
    
    if (isCacheValid('markets', cacheKey)) {
      return getCache('markets', cacheKey);
    }
    
    const exchange = createExchange(exchangeId);
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
    
    setCache('markets', cacheKey, exchangeInfo);
    return exchangeInfo;
  },
  
  /**
   * 获取行情数据
   * @param {string} exchangeId - 交易所ID
   * @param {string} symbol - 交易对符号
   * @returns {Object} - 行情数据
   */
  async getTicker(exchangeId, symbol) {
    const cacheKey = generateCacheKey('tickers', { exchangeId, symbol });
    
    if (isCacheValid('tickers', cacheKey)) {
      return getCache('tickers', cacheKey);
    }
    
    const exchange = createExchange(exchangeId);
    const ticker = await exchange.fetchTicker(symbol);
    
    setCache('tickers', cacheKey, ticker);
    return ticker;
  },
  
  /**
   * 获取K线数据
   * @param {string} exchangeId - 交易所ID
   * @param {string} symbol - 交易对符号
   * @param {string} timeframe - 时间周期
   * @param {number} limit - 限制数量
   * @param {number} since - 开始时间戳
   * @returns {Array} - K线数据
   */
  async getOHLCV(exchangeId, symbol, timeframe = '1h', limit = 100, since) {
    const cacheKey = generateCacheKey('ohlcv', { 
      exchangeId, symbol, timeframe, limit, since 
    });
    
    if (isCacheValid('ohlcv', cacheKey)) {
      return getCache('ohlcv', cacheKey);
    }
    
    const exchange = createExchange(exchangeId);
    
    if (!exchange.has.fetchOHLCV) {
      throw new Error(`交易所 ${exchangeId} 不支持获取K线数据`);
    }
    
    await exchange.loadMarkets();
    
    if (!exchange.timeframes || !(timeframe in exchange.timeframes)) {
      throw new Error(`交易所 ${exchangeId} 不支持时间周期 ${timeframe}`);
    }
    
    const ohlcv = await exchange.fetchOHLCV(symbol, timeframe, since, limit);
    
    setCache('ohlcv', cacheKey, ohlcv);
    return ohlcv;
  },
  
  /**
   * 获取可用市场(交易对)
   * @param {string} exchangeId - 交易所ID
   * @returns {Object} - 市场数据
   */
  async getMarkets(exchangeId) {
    const cacheKey = generateCacheKey('markets', { exchangeId, full: true });
    
    if (isCacheValid('markets', cacheKey)) {
      return getCache('markets', cacheKey);
    }
    
    const exchange = createExchange(exchangeId);
    const markets = await exchange.loadMarkets();
    
    setCache('markets', cacheKey, markets);
    return markets;
  }
};

module.exports = CcxtAdapter; 