# Qlib高级预测功能数据库模型和服务

## 概述

为支持qlib高级预测功能，我们已创建了完整的数据管理系统，包括历史数据获取、特征工程、模型训练和预测服务。该系统与MongoDB集成，提供了高效可靠的数据存储和检索功能。

## 数据库模型

我们设计了五个主要的数据模型来支持qlib高级预测功能：

1. **HistoricalData**: 存储原始市场数据，包括OHLCV数据和其他相关信息。
2. **FeatureData**: 存储从原始数据中提取的特征，用于模型训练和预测。
3. **TrainedModel**: 存储训练完成的模型信息，包括模型参数、性能指标和文件路径。
4. **ModelPerformance**: 存储模型评估结果，包括各种性能指标和样本预测。
5. **DataSource**: 存储数据源信息，用于管理多个数据提供者。

## 服务组件

系统包含三个主要服务组件：

### 1. 历史数据服务 (HistoricalDataService)

负责从各种数据源获取、同步和管理历史市场数据。主要功能包括：

- 获取可用交易对列表
- 同步历史数据
- 评估数据质量
- 查询历史数据
- 管理数据源

### 2. 特征数据服务 (FeatureDataService)

负责从历史数据中提取、处理和管理特征数据。主要功能包括：

- 提供基础特征处理（收益率、波动率等）
- 提供技术指标特征（移动平均线、RSI、MACD等）
- 提供高级特征（价格动量、市场状态等）
- 查询特征数据

### 3. 模型服务 (ModelService)

负责模型训练、评估和预测功能。主要功能包括：

- 训练新模型（支持多种模型类型）
- 评估模型性能
- 使用模型进行预测
- 管理模型状态（激活/停用）

## 数据流程

整个系统的数据流程如下：

1. **数据获取**: 通过HistoricalDataService从各种数据源获取原始市场数据。
2. **数据处理**: 通过FeatureDataService从原始数据中提取和处理特征。
3. **模型训练**: 使用处理后的特征数据训练预测模型。
4. **模型评估**: 评估模型性能并记录结果。
5. **预测**: 使用训练好的模型进行实时预测。

## 使用示例

### 获取历史数据

```python
from app.services.historical_data_service import HistoricalDataService

# 创建并初始化服务
service = HistoricalDataService()
await service.initialize()

# 同步历史数据
result = await service.sync_historical_data(
    symbol="BTC/USDT",
    start_date="2023-01-01T00:00:00.000Z",
    end_date="2023-06-30T23:59:59.999Z"
)

# 获取历史数据
data = await service.get_historical_data(
    symbol="BTC/USDT",
    start_date="2023-06-01T00:00:00.000Z",
    limit=100
)
```

### 处理特征数据

```python
from app.services.feature_data_service import FeatureDataService

# 创建并初始化服务
service = FeatureDataService()
await service.initialize()

# 处理特征数据
result = await service.process_features(
    symbol="BTC/USDT",
    timeframe="1d",
    feature_types=["basic", "technical"],
    start_date="2023-01-01T00:00:00.000Z",
    refresh=True
)

# 获取特征数据
data = await service.get_feature_data(
    symbol="BTC/USDT",
    timeframe="1d",
    start_date="2023-06-01T00:00:00.000Z",
    limit=100
)
```

### 训练和使用模型

```python
from app.services.model_service import ModelService

# 创建并初始化服务
service = ModelService()
await service.initialize()

# 训练模型
train_result = await service.train_model({
    "symbol": "BTC/USDT",
    "model_name": "价格方向预测模型",
    "model_type": "random_forest",
    "timeframe": "1d",
    "features": ["return_1d", "return_5d", "volatility_10d", "rsi_14"],
    "target": "price_direction",
    "target_horizon": 5
})

# 使用模型进行预测
prediction = await service.predict({
    "model_id": train_result["model_id"],
    "latest": True
})

# 评估模型
evaluation = await service.evaluate_model(
    model_id=train_result["model_id"],
    evaluation_period={
        "start": "2023-05-01T00:00:00.000Z",
        "end": "2023-06-30T23:59:59.999Z"
    }
)
```

## 测试

提供了测试脚本 `scripts/test_historical_data.py` 用于测试系统各个组件的功能。

使用方法：

```bash
./scripts/test_historical_data.py
```

## 依赖项

该系统依赖以下主要组件：

- MongoDB: 用于数据存储
- Python 3.8+
- pandas: 用于数据处理
- numpy: 用于数学计算
- scikit-learn: 用于模型训练和评估
- pymongo: 用于MongoDB连接

## 注意事项

- 确保MongoDB服务已启动并可访问
- 模型文件保存在项目的`app/models`目录下
- 默认支持的模型类型包括：linear、random_forest、xgboost和lstm