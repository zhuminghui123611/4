#!/bin/bash

# 这个脚本用于Netlify部署

# 显示环境和版本信息
echo "============================================="
echo "当前环境信息:"
echo "Node.js版本: $(node -v)"
echo "NPM版本: $(npm -v)"
echo "============================================="

echo "这是一个纯JavaScript项目，不需要Python"
echo "开始部署JS函数..."

# 确保public目录存在
mkdir -p public

# 确保公共文件夹有内容
if [ ! -f public/index.html ]; then
  echo '<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>加密货币数据中继服务</title>
</head>
<body>
  <h1>加密货币数据中继服务</h1>
  <p>API访问路径: /api/v1/</p>
  <p>服务状态: <a href="/.netlify/functions/api/health">查看健康状态</a></p>
  <p>测试端点: <a href="/.netlify/functions/api/api/v1/test">测试API</a></p>
</body>
</html>' > public/index.html
fi

# 清除不需要的文件
echo "清理Python相关文件..."
rm -f requirements.txt || true
rm -rf __pycache__ || true
rm -rf .pytest_cache || true

echo "部署准备完成!"
exit 0 