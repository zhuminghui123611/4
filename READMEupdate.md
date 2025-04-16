# API集成更新说明

## 已集成的API密钥

我们已将您提供的API密钥直接集成到代码中，无需通过环境变量配置：

1. **Ankr API**
   - API密钥: `ce9c9f46eac0e045692e0d041fb543747122fb07b9b50f705f70f1004d841840`
   - 已支持的区块链网络:
     - 以太坊 (eth)
     - Polygon (polygon)
     - Arbitrum (arbitrum)
     - Optimism (optimism)
     - Gnosis (gnosis)
     - Blast (blast)
     - Avalanche (avalanche)
     - Scroll (scroll)

2. **Reservoir API** (NFT交易聚合器)
   - API密钥: `d1d6d023-5e2f-5561-8184-6417a48c2f01`
   - WalletConnect项目ID: `64b6a6cc7a2296ccb0b97b887b6dee1a`

3. **1inch API**
   - API密钥: `BFmmhv1wAlc12w1jd6xy8YMy5y0sxLPh`

## 新增功能

### Ankr区块链API增强

我们扩展了Ankr API适配器的功能：

1. **多链支持**
   - 每个链都有独立的API客户端
   - 访问方式: `getAnkrClient(chainName)`

2. **原生代币余额查询**
   - 端点: `GET /api/v1/ankr/native-balance/:chain/:address`
   - 支持的链: eth, polygon, arbitrum, optimism, gnosis, blast, avalanche, scroll

3. **ERC20代币余额查询**
   - 端点: `GET /api/v1/ankr/token-balance/:chain/:address/:tokenAddress`

4. **自定义RPC请求**
   - 端点: `POST /api/v1/ankr/rpc/:chain`
   - 可发送任何标准JSON-RPC请求到指定区块链

### 状态监控增强

1. **多链状态监控**
   - 分别监控每个区块链网络的连接状态
   - 提供更细粒度的服务可用性信息

## 部署说明

这些更改已经直接集成到代码中，部署时无需进行额外配置。API密钥已经硬编码在服务中，可以直接部署到Netlify。

### 部署步骤

1. 登录Netlify
   ```bash
   netlify login
   ```

2. 初始化Netlify站点
   ```bash
   netlify init
   ```

3. 直接部署
   ```bash
   netlify deploy --prod
   ```

## 测试新API

部署完成后，可以使用以下示例来测试新的Ankr API功能：

1. 获取ETH区块链当前区块号
   ```
   curl -X POST https://your-netlify-app.netlify.app/api/v1/ankr/rpc/eth \
     -H "Content-Type: application/json" \
     -d '{"method":"eth_blockNumber","params":[]}'
   ```

2. 获取账户ETH余额
   ```
   curl https://your-netlify-app.netlify.app/api/v1/ankr/native-balance/eth/0x71C7656EC7ab88b098defB751B7401B5f6d8976F
   ```

3. 获取USDT代币余额 (Ethereum上的USDT合约)
   ```
   curl https://your-netlify-app.netlify.app/api/v1/ankr/token-balance/eth/0x71C7656EC7ab88b098defB751B7401B5f6d8976F/0xdAC17F958D2ee523a2206206994597C13D831ec7
   ``` 