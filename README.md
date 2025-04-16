# 加密货币数据中继服务

本项目实现了一个加密货币数据的中继服务，用于解决网络限制问题，允许前端通过Netlify函数访问各种加密货币相关的API和数据源。

## 主要功能

- 加密货币市场数据获取和中继
- 区块链和Web3数据接口
- 钱包功能辅助（地址验证、交易构建等）
- 交易手续费计算
- NFT数据访问
- 行情预测分析

## 技术栈

- Node.js
- Express.js
- Netlify Functions
- Serverless架构
- CCXT库（加密货币交易所接口）
- ethers.js（区块链交互）

## 本地开发

### 前提条件

- Node.js 16+
- npm 或 yarn

### 安装

```bash
# 安装依赖
npm install

# 或使用yarn
yarn install
```

### 本地运行

```bash
# 启动本地开发服务器
npm run dev

# 或使用yarn
yarn dev
```

服务器将在 http://localhost:8888 上运行，Netlify函数将在 http://localhost:8888/.netlify/functions/api 上可用。

## 部署到Netlify

### 方法1：通过Netlify CLI

```bash
# 安装Netlify CLI（如果尚未安装）
npm install -g netlify-cli

# 登录Netlify
netlify login

# 部署到Netlify
netlify deploy --prod
```

### 方法2：通过GitHub仓库

1. 将代码推送到GitHub仓库
2. 在Netlify仪表板上创建新站点
3. 选择"从Git导入"
4. 选择您的GitHub仓库
5. 配置构建设置（使用默认设置即可）
6. 点击"部署站点"

## 环境变量配置

在Netlify仪表板中，您需要配置以下环境变量：

- `ANKR_API_KEY`: Ankr API密钥
- `RESERVOIR_API_KEY`: Reservoir API密钥
- `ONEINCH_API_KEY`: 1inch API密钥

## 许可证

MIT 