import logging
import os
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException
from app.services.data_processing_service import DataProcessingService

logger = logging.getLogger(__name__)

# 检查qlib是否可用
try:
    import qlib
    from qlib.contrib.model.pytorch_lstm import LSTMModel
    from qlib.contrib.model.pytorch_gru import GRUModel
    from qlib.contrib.model.gbdt import LGBModel
    from qlib.utils import init_instance_by_config
    from qlib.workflow import R
    from qlib.workflow.record_temp import SignalRecord, SigAnaRecord
    from qlib.rl.order_execution.simulator import SingleAssetOrderExecutionSimulator
    
    QLIB_AVAILABLE = True
    
    # 初始化qlib
    try:
        qlib_initialized = False
        
        def ensure_qlib_initialized():
            """确保qlib已初始化"""
            global qlib_initialized
            if not qlib_initialized:
                qlib_path = settings.QLIB_MODEL_PATH
                if not qlib_path:
                    qlib_path = str(Path.home() / "qlib_data")
                
                # 如果路径不存在，尝试创建
                if not os.path.exists(qlib_path):
                    os.makedirs(qlib_path, exist_ok=True)
                
                qlib.init(provider_uri=qlib_path, auto_mount=False)
                qlib_initialized = True
                logger.info(f"Qlib已初始化，使用数据路径: {qlib_path}")
    
    except Exception as e:
        logger.error(f"Qlib初始化失败: {str(e)}")
        QLIB_AVAILABLE = False
        
except ImportError:
    QLIB_AVAILABLE = False
    logger.warning("Qlib库不可用，预测功能将受限")

class QlibIntegrationService:
    """Qlib集成服务，提供模型管理和预测功能"""
    
    # 支持的模型类型
    MODEL_TYPES = {
        "lstm": LSTMModel if QLIB_AVAILABLE else None,
        "gru": GRUModel if QLIB_AVAILABLE else None,
        "lgb": LGBModel if QLIB_AVAILABLE else None,
    }
    
    # 模型配置
    DEFAULT_MODEL_CONFIGS = {
        "lstm": {
            "class": "LSTMModel",
            "module_path": "qlib.contrib.model.pytorch_lstm",
            "kwargs": {
                "d_feat": 20,         # 特征维度
                "hidden_size": 64,    # LSTM隐藏层大小
                "num_layers": 2,      # LSTM层数
                "dropout": 0.0,       # dropout率
                "n_epochs": 100,      # 训练轮数
                "lr": 1e-3,           # 学习率
                "early_stop": 10,     # 早停轮数
                "batch_size": 16,     # 批量大小
                "metric": "loss",     # 评价指标
                "loss": "mse",        # 损失函数
                "GPU": 0,             # GPU ID，-1表示使用CPU
            },
        },
        "gru": {
            "class": "GRUModel",
            "module_path": "qlib.contrib.model.pytorch_gru",
            "kwargs": {
                "d_feat": 20,         # 特征维度
                "hidden_size": 64,    # GRU隐藏层大小
                "num_layers": 2,      # GRU层数
                "dropout": 0.0,       # dropout率
                "n_epochs": 100,      # 训练轮数
                "lr": 1e-3,           # 学习率
                "early_stop": 10,     # 早停轮数
                "batch_size": 16,     # 批量大小
                "metric": "loss",     # 评价指标
                "loss": "mse",        # 损失函数
                "GPU": 0,             # GPU ID，-1表示使用CPU
            },
        },
        "lgb": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",        # 损失函数
                "colsample_bytree": 0.8,  # 特征采样率
                "learning_rate": 0.1, # 学习率
                "subsample": 0.8,     # 样本采样率
                "lambda_l1": 0.1,     # L1正则化系数
                "lambda_l2": 0.1,     # L2正则化系数
                "max_depth": 5,       # 最大树深度
                "num_leaves": 31,     # 叶子节点数
                "num_threads": 4,     # 线程数
            },
        },
    }
    
    # 模型实例缓存
    _model_instances = {}
    
    @classmethod
    async def predict_with_qlib(
        cls,
        symbol: str,
        prediction_horizon: int = 1,
        historical_days: int = 90,
        model_type: str = "lstm",
        custom_model_path: Optional[str] = None,
        include_on_chain: bool = True,
        include_sentiment: bool = True,
    ) -> Dict[str, Any]:
        """
        使用qlib模型进行预测
        
        Args:
            symbol: 交易对符号，例如 "BTC/USDT"
            prediction_horizon: 预测周期（天）
            historical_days: 历史数据天数
            model_type: 模型类型，支持 "lstm", "gru", "lgb"
            custom_model_path: 自定义模型路径，如果提供则使用预训练模型
            include_on_chain: 是否包含链上数据
            include_sentiment: 是否包含情绪数据
            
        Returns:
            Dict[str, Any]: 预测结果
        """
        if not QLIB_AVAILABLE:
            raise ServiceUnavailableException("Qlib库不可用，无法进行预测")
        
        try:
            # 确保qlib已初始化
            ensure_qlib_initialized()
            
            # 准备qlib格式数据
            data_df = await DataProcessingService.prepare_qlib_format_data(
                symbol=symbol,
                days=historical_days,
                target_column='close',
                feature_columns=None  # 使用默认特征
            )
            
            if data_df.empty:
                raise ServiceUnavailableException(f"无法获取{symbol}的数据")
            
            # 分割特征和标签
            features = data_df.drop('label', axis=1)
            labels = data_df['label']
            
            # 拿出最后一行数据作为预测输入
            predict_features = features.iloc[[-1]]
            
            # 获取或创建模型
            model = await cls._get_model(model_type, custom_model_path)
            
            # 使用模型预测
            prediction = model.predict(predict_features)
            
            # 转换预测结果
            last_price = float(features.iloc[-1]['close'])
            predicted_price = float(prediction[0])
            predicted_change = (predicted_price - last_price) / last_price * 100
            
            # 准备返回结果
            result = {
                "symbol": symbol,
                "current_price": last_price,
                "predicted_price": predicted_price,
                "predicted_change": round(predicted_change, 2),
                "prediction_horizon": prediction_horizon,
                "model_type": model_type,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "features_used": list(features.columns),
                "data_points": len(data_df),
                "confidence": cls._calculate_prediction_confidence(data_df, model_type)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Qlib预测失败: {str(e)}")
            raise ServiceUnavailableException(f"预测失败: {str(e)}")
    
    @classmethod
    async def _get_model(cls, model_type: str, custom_model_path: Optional[str] = None):
        """
        获取或创建模型实例
        
        Args:
            model_type: 模型类型
            custom_model_path: 自定义模型路径
            
        Returns:
            模型实例
        """
        # 检查模型类型是否支持
        if model_type not in cls.MODEL_TYPES or cls.MODEL_TYPES[model_type] is None:
            raise ServiceUnavailableException(f"不支持的模型类型: {model_type}")
        
        # 生成模型缓存键
        model_key = f"{model_type}_{custom_model_path or 'default'}"
        
        # 检查是否已缓存
        if model_key in cls._model_instances:
            return cls._model_instances[model_key]
        
        try:
            if custom_model_path and os.path.exists(custom_model_path):
                # 加载自定义模型
                # 注意：实际项目中可能需要更复杂的模型加载逻辑
                raise NotImplementedError("自定义模型加载功能尚未实现")
            else:
                # 创建新模型实例
                model_config = cls.DEFAULT_MODEL_CONFIGS.get(model_type).copy()
                model_class = cls.MODEL_TYPES[model_type]
                model = model_class(**model_config["kwargs"])
                
                # 缓存模型实例
                cls._model_instances[model_key] = model
                
                return model
                
        except Exception as e:
            logger.error(f"获取模型实例失败: {str(e)}")
            raise ServiceUnavailableException(f"模型初始化失败: {str(e)}")
    
    @classmethod
    def _calculate_prediction_confidence(cls, data_df: pd.DataFrame, model_type: str) -> float:
        """
        计算预测置信度
        
        Args:
            data_df: 数据DataFrame
            model_type: 模型类型
            
        Returns:
            float: 置信度 (0-1)
        """
        # 简单策略：数据点越多，置信度越高，但有上限
        base_confidence = 0.5
        
        # 根据数据点数量调整
        data_factor = min(0.3, len(data_df) / 200 * 0.3)
        
        # 根据模型类型调整
        model_factor = {
            "lstm": 0.1,
            "gru": 0.1,
            "lgb": 0.05
        }.get(model_type, 0)
        
        # 合成最终置信度，限制在合理范围内
        confidence = base_confidence + data_factor + model_factor
        return min(0.9, max(0.3, confidence)) 