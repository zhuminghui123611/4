# 加密货币API中继服务

这个仓库包含部署在Netlify上的API中继服务，用于解决网络限制问题，允许从限制区域访问某些加密货币API。

## 功能

- 使用Netlify Functions作为API中继
- 支持访问Ankr、Reservoir、1inch等API
- 通过安全地存储API密钥，避免在客户端暴露敏感信息

## 部署

该服务部署在Netlify上，通过以下URL访问：

```
https://[your-netlify-site].netlify.app/.netlify/functions/api
```

## 使用方法

本地Python后端可以通过HTTP请求调用此中继服务：

```python
import requests

NETLIFY_API_URL = "https://[your-netlify-site].netlify.app/.netlify/functions/api"

# 示例请求
response = requests.get(f"{NETLIFY_API_URL}/ankr/endpoint", params={"key": "value"})
data = response.json()
```

## 环境变量

在Netlify部署时需要设置以下环境变量：

- `ANKR_API_KEY`: Ankr API密钥
- `RESERVOIR_API_KEY`: Reservoir API密钥
- `ONEINCH_API_KEY`: 1inch API密钥 