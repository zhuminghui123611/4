const express = require('express');
const serverless = require('serverless-http');
const cors = require('cors');
const RateLimit = require('express-rate-limit');
const morgan = require('morgan');
const compression = require('compression');
const helmet = require('helmet');

const { ApiError } = require('./lib/api-client');
const { 
  CcxtAdapter, 
  AnkrAdapter, 
  ReservoirAdapter, 
  OneInchAdapter,
  OkxAdapter,
  DataSourceMonitor
} = require('./lib/data-sources');

// 新服务模块
const BroadcastService = require('./lib/broadcast-service');
const WalletService = require('./lib/wallet-service');
const HistoryService = require('./lib/history-service');
const PredictionService = require('./lib/prediction-service');
const FeeService = require('./lib/fee-service');

// 创建Express应用
const app = express();

// 安全和性能中间件
app.use(helmet());
app.use(compression());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// 启用CORS
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS || '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'x-api-key'],
  maxAge: 86400 // 预检请求缓存1天
}));

// 请求日志
app.use(morgan(':remote-addr - :method :url :status :res[content-length] - :response-time ms'));

// 限流保护
const limiter = RateLimit({
  windowMs: 1 * 60 * 1000, // 1分钟
  max: 60, // 每个IP每分钟最多60个请求
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    status: 429,
    message: '请求过于频繁，请稍后再试',
  }
});
app.use(limiter);

// 健康检查端点
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    version: '1.0.0'
  });
});

// 数据源状态端点
app.get('/status', async (req, res, next) => {
  try {
    const results = await DataSourceMonitor.checkAllSources();
    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      sources: results
    });
  } catch (error) {
    next(error);
  }
});

// 单一数据源状态检查
app.get('/status/:source', async (req, res, next) => {
  try {
    const result = await DataSourceMonitor.checkSource(req.params.source);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 定义API版本和基础路径
const API_V1_BASE = '/api/v1';

// CCXT路由
const ccxtRouter = express.Router();

// 获取所有交易所列表
ccxtRouter.get('/exchanges', (req, res, next) => {
  try {
    const exchanges = CcxtAdapter.getAllExchangeIds();
    res.json({
      count: exchanges.length,
      exchanges
    });
  } catch (error) {
    next(error);
  }
});

// 获取特定交易所信息
ccxtRouter.get('/exchanges/:exchangeId', async (req, res, next) => {
  try {
    const exchangeInfo = await CcxtAdapter.getExchangeInfo(req.params.exchangeId);
    res.json(exchangeInfo);
  } catch (error) {
    next(error);
  }
});

// 获取市场数据
ccxtRouter.get('/ticker/:exchangeId/:symbol', async (req, res, next) => {
  try {
    const { exchangeId, symbol } = req.params;
    const ticker = await CcxtAdapter.getTicker(exchangeId, symbol);
    res.json(ticker);
  } catch (error) {
    next(error);
  }
});

// 获取K线数据
ccxtRouter.get('/ohlcv/:exchangeId/:symbol', async (req, res, next) => {
  try {
    const { exchangeId, symbol } = req.params;
    const { timeframe = '1h', limit = 100 } = req.query;
    
    const ohlcv = await CcxtAdapter.getOHLCV(
      exchangeId, 
      symbol, 
      timeframe, 
      parseInt(limit)
    );
    
    res.json({
      exchange: exchangeId,
      symbol,
      timeframe,
      count: ohlcv.length,
      data: ohlcv
    });
  } catch (error) {
    next(error);
  }
});

// Ankr API路由
const ankrRouter = express.Router();

// 获取支持的区块链网络
ankrRouter.get('/chains', (req, res) => {
  const chains = AnkrAdapter.getSupportedChains();
  res.json({
    chains,
    count: chains.length
  });
});

// 获取账户余额
ankrRouter.get('/balance/:blockchain/:address', async (req, res, next) => {
  try {
    const { blockchain, address } = req.params;
    const balance = await AnkrAdapter.getAccountBalance(address, blockchain);
    res.json(balance);
  } catch (error) {
    next(error);
  }
});

// 获取Token价格
ankrRouter.get('/token-price/:blockchain/:contractAddress', async (req, res, next) => {
  try {
    const { blockchain, contractAddress } = req.params;
    const price = await AnkrAdapter.getTokenPrice(blockchain, contractAddress);
    res.json(price);
  } catch (error) {
    next(error);
  }
});

// 获取NFT元数据
ankrRouter.get('/nft/:blockchain/:contractAddress/:tokenId', async (req, res, next) => {
  try {
    const { blockchain, contractAddress, tokenId } = req.params;
    const metadata = await AnkrAdapter.getNftMetadata(blockchain, contractAddress, tokenId);
    res.json(metadata);
  } catch (error) {
    next(error);
  }
});

// 获取原生代币余额
ankrRouter.get('/native-balance/:chain/:address', async (req, res, next) => {
  try {
    const { chain, address } = req.params;
    const balance = await AnkrAdapter.getNativeBalance(chain, address);
    res.json(balance);
  } catch (error) {
    next(error);
  }
});

// 获取代币余额
ankrRouter.get('/token-balance/:chain/:address/:tokenAddress', async (req, res, next) => {
  try {
    const { chain, address, tokenAddress } = req.params;
    const balance = await AnkrAdapter.getTokenBalance(chain, address, tokenAddress);
    res.json(balance);
  } catch (error) {
    next(error);
  }
});

// 发送自定义RPC请求
ankrRouter.post('/rpc/:chain', async (req, res, next) => {
  try {
    const { chain } = req.params;
    const rpcRequest = req.body;
    
    if (!rpcRequest || !rpcRequest.method) {
      throw new ApiError('无效的RPC请求', 400, 'ANKR_RPC');
    }
    
    const result = await AnkrAdapter.sendRpcRequest(chain, rpcRequest);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// Reservoir API路由
const reservoirRouter = express.Router();

// 获取NFT集合信息
reservoirRouter.get('/collections/:collectionId', async (req, res, next) => {
  try {
    const { collectionId } = req.params;
    const { chain = 'ethereum' } = req.query;
    const collection = await ReservoirAdapter.getCollection(collectionId, chain);
    res.json(collection);
  } catch (error) {
    next(error);
  }
});

// 获取NFT销售历史
reservoirRouter.get('/sales/:collectionId', async (req, res, next) => {
  try {
    const { collectionId } = req.params;
    const { chain = 'ethereum', limit = 20 } = req.query;
    const sales = await ReservoirAdapter.getSales(collectionId, chain, parseInt(limit));
    res.json(sales);
  } catch (error) {
    next(error);
  }
});

// 获取NFT地板价
reservoirRouter.get('/floor-price/:collectionId', async (req, res, next) => {
  try {
    const { collectionId } = req.params;
    const { chain = 'ethereum' } = req.query;
    const floorPrice = await ReservoirAdapter.getCollectionFloorPrice(collectionId, chain);
    res.json(floorPrice);
  } catch (error) {
    next(error);
  }
});

// 1inch API路由
const oneInchRouter = express.Router();

// 获取支持的代币列表
oneInchRouter.get('/tokens/:chainId?', async (req, res, next) => {
  try {
    const { chainId = '1' } = req.params;
    const tokens = await OneInchAdapter.getTokens(chainId);
    res.json(tokens);
  } catch (error) {
    next(error);
  }
});

// 获取汇率报价
oneInchRouter.get('/quote/:chainId', async (req, res, next) => {
  try {
    const { chainId } = req.params;
    const { fromTokenAddress, toTokenAddress, amount } = req.query;
    
    if (!fromTokenAddress || !toTokenAddress || !amount) {
      throw new ApiError('缺少必要参数: fromTokenAddress, toTokenAddress, amount', 400, '1INCH_QUOTE');
    }
    
    const quote = await OneInchAdapter.getQuote(
      chainId,
      fromTokenAddress,
      toTokenAddress,
      amount
    );
    
    res.json(quote);
  } catch (error) {
    next(error);
  }
});

// 获取互换路由
oneInchRouter.get('/swap/:chainId', async (req, res, next) => {
  try {
    const { chainId } = req.params;
    const { fromTokenAddress, toTokenAddress, amount, fromAddress } = req.query;
    
    if (!fromTokenAddress || !toTokenAddress || !amount || !fromAddress) {
      throw new ApiError('缺少必要参数: fromTokenAddress, toTokenAddress, amount, fromAddress', 400, '1INCH_SWAP');
    }
    
    const swap = await OneInchAdapter.getSwap(
      chainId,
      fromTokenAddress,
      toTokenAddress,
      amount,
      fromAddress
    );
    
    res.json(swap);
  } catch (error) {
    next(error);
  }
});

// OKX P2P API路由
const okxRouter = express.Router();

// 获取P2P广告列表
okxRouter.get('/p2p', async (req, res, next) => {
  try {
    const { quoteCurrency = 'CNY', baseCurrency = 'USDT', side = 'buy', paymentMethod } = req.query;
    
    const adverts = await OkxAdapter.getP2PAdverts(
      quoteCurrency,
      baseCurrency,
      side,
      paymentMethod
    );
    
    res.json(adverts);
  } catch (error) {
    next(error);
  }
});

// 获取P2P支付方式
okxRouter.get('/p2p/payment-methods', async (req, res, next) => {
  try {
    const methods = await OkxAdapter.getP2PPaymentMethods();
    res.json(methods);
  } catch (error) {
    next(error);
  }
});

// 获取币种列表
okxRouter.get('/currencies', async (req, res, next) => {
  try {
    const currencies = await OkxAdapter.getCurrencies();
    res.json(currencies);
  } catch (error) {
    next(error);
  }
});

// 交易广播服务路由
const broadcastRouter = express.Router();

// 广播已签名的交易
broadcastRouter.post('/transaction', async (req, res, next) => {
  try {
    const { chain, signedTx } = req.body;
    
    if (!chain || !signedTx) {
      throw new ApiError('缺少必要参数: chain, signedTx', 400, 'BROADCAST');
    }
    
    const result = await BroadcastService.broadcastTransaction(chain, signedTx);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取交易状态
broadcastRouter.get('/transaction/:chain/:txHash', async (req, res, next) => {
  try {
    const { chain, txHash } = req.params;
    const result = await BroadcastService.getTransactionStatus(chain, txHash);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取Gas价格
broadcastRouter.get('/gas-price/:chain', async (req, res, next) => {
  try {
    const { chain } = req.params;
    const result = await BroadcastService.getGasPrice(chain);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 钱包辅助服务路由
const walletRouter = express.Router();

// 验证地址
walletRouter.get('/validate-address/:address', async (req, res, next) => {
  try {
    const { address } = req.params;
    const { chain = 'eth' } = req.query;
    const result = await WalletService.validateAddress(address, chain);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 解析ENS域名
walletRouter.get('/resolve-ens/:ensName', async (req, res, next) => {
  try {
    const { ensName } = req.params;
    const result = await WalletService.resolveEns(ensName);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取交易参数
walletRouter.post('/transaction-params', async (req, res, next) => {
  try {
    const { fromAddress, toAddress, chain, value, data, estimateGas } = req.body;
    
    if (!fromAddress || !toAddress) {
      throw new ApiError('缺少必要参数: fromAddress, toAddress', 400, 'WALLET');
    }
    
    const result = await WalletService.getTransactionParams(
      fromAddress, 
      toAddress, 
      chain, 
      { value, data, estimateGas }
    );
    
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 创建合约调用数据
walletRouter.post('/contract-data', async (req, res, next) => {
  try {
    const { contractAbi, methodName, params } = req.body;
    
    if (!contractAbi || !methodName) {
      throw new ApiError('缺少必要参数: contractAbi, methodName', 400, 'WALLET');
    }
    
    const result = WalletService.createContractData(contractAbi, methodName, params);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取代币余额
walletRouter.get('/balance/:chain/:address', async (req, res, next) => {
  try {
    const { chain, address } = req.params;
    const { tokenAddress } = req.query;
    
    const result = await WalletService.getTokenBalance(address, chain, tokenAddress);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 交易历史服务路由
const historyRouter = express.Router();

// 获取钱包交易历史
historyRouter.get('/wallet/:address', async (req, res, next) => {
  try {
    const { address } = req.params;
    const { 
      chains,
      page = 1, 
      limit = 50, 
      fromTimestamp, 
      toTimestamp,
      includeNFTs = true,
      includeERC20 = true,
      includeNative = true
    } = req.query;
    
    const chainsArray = chains ? chains.split(',') : [];
    
    const result = await HistoryService.getWalletHistory(
      address, 
      chainsArray, 
      {
        page: parseInt(page),
        limit: parseInt(limit),
        fromTimestamp: fromTimestamp ? parseInt(fromTimestamp) : 0,
        toTimestamp: toTimestamp ? parseInt(toTimestamp) : Math.floor(Date.now() / 1000),
        includeNFTs: includeNFTs === 'true',
        includeERC20: includeERC20 === 'true',
        includeNative: includeNative === 'true'
      }
    );
    
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取交易所交易历史
historyRouter.get('/exchange/:exchangeId/:symbol', async (req, res, next) => {
  try {
    const { exchangeId, symbol } = req.params;
    const { limit, since, until } = req.query;
    
    const result = await HistoryService.getExchangeTradeHistory(
      exchangeId, 
      symbol, 
      {
        limit: limit ? parseInt(limit) : 50,
        since: since ? parseInt(since) : undefined,
        until: until ? parseInt(until) : undefined
      }
    );
    
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 预测分析服务路由
const predictionRouter = express.Router();

// 生成预测
predictionRouter.post('/', async (req, res, next) => {
  try {
    const { 
      symbol,
      exchange, 
      predictionType, 
      timeHorizon,
      options
    } = req.body;
    
    if (!symbol || !exchange || !predictionType || !timeHorizon) {
      throw new ApiError('缺少必要参数: symbol, exchange, predictionType, timeHorizon', 400, 'PREDICTION');
    }
    
    const result = await PredictionService.generatePrediction(
      symbol,
      exchange,
      predictionType,
      timeHorizon,
      options || {}
    );
    
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// 获取支持的预测类型
predictionRouter.get('/types', (req, res) => {
  const types = PredictionService.getSupportedPredictionTypes();
  res.json({
    count: types.length,
    types
  });
});

// 获取支持的时间范围
predictionRouter.get('/horizons', (req, res) => {
  const horizons = PredictionService.getSupportedTimeHorizons();
  res.json({
    count: horizons.length,
    horizons
  });
});

// 费用服务路由
const feeRouter = express.Router();

// 计算交易费用
feeRouter.post('/calculate', async (req, res) => {
  try {
    const { symbol, amount, price, platformType, options } = req.body;
    
    // 验证必要参数
    if (!symbol || !amount || !price) {
      throw new ApiError('缺少必要参数：symbol, amount, price', 400, 'FEE');
    }
    
    // 调用费用服务计算费用
    const feeDetails = FeeService.calculateFees(
      symbol,
      parseFloat(amount),
      parseFloat(price),
      platformType || 'CEX',
      options || {}
    );
    
    return res.json({
      success: true,
      message: '费用计算成功',
      data: feeDetails
    });
  } catch (error) {
    return res.status(error.statusCode || 500).json({
      success: false,
      message: error.message,
      errorCode: error.code || 'UNKNOWN_ERROR'
    });
  }
});

// 应用费用到订单
feeRouter.post('/apply', async (req, res) => {
  try {
    const { order, feeDetails } = req.body;
    
    // 验证必要参数
    if (!order || !feeDetails) {
      throw new ApiError('缺少必要参数：order, feeDetails', 400, 'FEE');
    }
    
    // 应用费用到订单
    const orderWithFees = FeeService.applyFeesToOrder(order, feeDetails);
    
    return res.json({
      success: true,
      message: '费用应用成功',
      data: orderWithFees
    });
  } catch (error) {
    return res.status(error.statusCode || 500).json({
      success: false,
      message: error.message,
      errorCode: error.code || 'UNKNOWN_ERROR'
    });
  }
});

// 获取费率配置
feeRouter.get('/config', async (req, res) => {
  try {
    // 获取当前费用配置
    const feeConfig = FeeService.getFeeConfig();
    
    return res.json({
      success: true,
      message: '获取费用配置成功',
      data: feeConfig
    });
  } catch (error) {
    return res.status(error.statusCode || 500).json({
      success: false,
      message: error.message,
      errorCode: error.code || 'UNKNOWN_ERROR'
    });
  }
});

// 更新费率配置（需要认证保护）
feeRouter.post('/config', async (req, res) => {
  try {
    // 在实际生产环境中，这里应该添加身份验证和权限检查
    // 确保只有管理员可以更新费用配置
    
    const newConfig = req.body;
    
    // 验证请求体
    if (!newConfig || typeof newConfig !== 'object') {
      throw new ApiError('无效的配置参数', 400, 'FEE');
    }
    
    // 更新费用配置
    const updatedConfig = FeeService.updateFeeConfig(newConfig);
    
    return res.json({
      success: true,
      message: '费用配置更新成功',
      data: updatedConfig
    });
  } catch (error) {
    return res.status(error.statusCode || 500).json({
      success: false,
      message: error.message,
      errorCode: error.code || 'UNKNOWN_ERROR'
    });
  }
});

// 注册路由
app.use(`${API_V1_BASE}/ccxt`, ccxtRouter);
app.use(`${API_V1_BASE}/ankr`, ankrRouter);
app.use(`${API_V1_BASE}/reservoir`, reservoirRouter);
app.use(`${API_V1_BASE}/1inch`, oneInchRouter);
app.use(`${API_V1_BASE}/okx`, okxRouter);
app.use(`${API_V1_BASE}/broadcast`, broadcastRouter);
app.use(`${API_V1_BASE}/wallet`, walletRouter);
app.use(`${API_V1_BASE}/history`, historyRouter);
app.use(`${API_V1_BASE}/prediction`, predictionRouter);
app.use(`${API_V1_BASE}/fee`, feeRouter);

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
  
  const status = err instanceof ApiError ? err.statusCode : 500;
  const source = err instanceof ApiError ? err.source : 'SERVER';
  
  res.status(status).json({
    error: {
      status,
      message: err.message,
      source,
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