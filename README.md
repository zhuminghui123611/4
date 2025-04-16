# 加密货币数据中继服务

一个基于Netlify Functions的加密货币数据中继服务，用于解决区域网络限制问题，提供对多个交易所API的访问。

## 功能特点

- 基于CCXT库，支持100多个加密货币交易所
- 无需服务器，使用Netlify Functions作为无服务器函数
- 纯静态部署，简单易用
- 内置缓存和错误处理机制
- 完整的API文档

## API端点

- `/api/v1/ccxt/exchanges` - 获取所有支持的交易所列表
- `/api/v1/ccxt/exchanges/:exchangeId` - 获取交易所详细信息
- `/api/v1/ccxt/ticker/:exchangeId/:symbol` - 获取特定交易对的价格信息
- `/api/v1/ccxt/ohlcv/:exchangeId/:symbol` - 获取K线数据

## 部署方法

1. Fork本仓库
2. 在Netlify上创建新站点
3. 连接到你的GitHub仓库
4. 部署设置：
   - 构建命令：留空
   - 发布目录：`public`
   - 环境变量：无需额外设置

## 本地开发

```bash
# 安装依赖
npm install

# 本地开发服务器
npm run dev
```

## 注意事项

- 本服务仅作为中继，不存储任何用户数据
- API调用限制取决于目标交易所的限制策略
- 请勿用于非法用途

## 许可证

MIT 