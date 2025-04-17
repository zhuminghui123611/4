// CCXT中继服务 - Netlify函数
const adapter = require('./lib/ccxt-relay-adapter');

// 导出Netlify函数处理器
exports.handler = adapter.createHandler();
