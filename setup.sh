#!/bin/bash

echo "正在初始化加密货币交易数据分析与执行后端服务..."

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
. venv/bin/activate

# 安装依赖
echo "安装依赖包..."
pip install --upgrade pip
pip install -r requirements.txt

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p logs
mkdir -p models/qlib_model

# 创建环境变量文件
if [ ! -f ".env" ]; then
    echo "创建环境变量文件..."
    cp .env.example .env
    echo "请编辑.env文件，设置必要的配置参数"
fi

echo "初始化完成！"
echo "使用以下命令运行服务："
echo "./run.sh"

# 退出虚拟环境
deactivate 