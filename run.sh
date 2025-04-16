#!/bin/bash

# 激活虚拟环境
. venv/bin/activate

# 检查依赖是否安装
pip list | grep fastapi > /dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# 运行应用
echo "Starting the API server..."
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 退出虚拟环境
deactivate 