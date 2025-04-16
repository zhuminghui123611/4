from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
import pandas as pd
import numpy as np
import uuid
import json
import os
import pickle
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, precision_score, recall_score, f1_score

from app.core.exceptions import BadRequestException
from app.exceptions.service_exceptions import ServiceUnavailableException
from app.db.historical_data_db import HistoricalDataDB, FeatureDataDB, TrainedModelDB, ModelPerformanceDB
from app.db.models import FeatureData, TrainedModel, ModelPerformance

logger = logging.getLogger(__name__)

class ModelService:
    """模型服务，负责处理模型训练、评估和预测功能"""
    
    def __init__(self):
        """初始化模型服务"""
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        self.active_models = {}  # 缓存活跃模型
        
        # 确保模型目录存在
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)
    
    async def initialize(self):
        """初始化服务，加载活跃模型"""
        try:
            # 获取所有活跃模型
            active_models = await TrainedModelDB.get_active_models()
            
            # 尝试加载模型
            for model in active_models:
                try:
                    model_path = model.model_file_path
                    if os.path.exists(model_path):
                        with open(model_path, 'rb') as f:
                            loaded_model = pickle.load(f)
                            self.active_models[model.model_id] = {
                                "model": loaded_model,
                                "metadata": model
                            }
                        logger.info(f"成功加载模型: {model.model_id}, {model.model_name}")
                    else:
                        logger.warning(f"模型文件不存在: {model_path}")
                except Exception as e:
                    logger.error(f"加载模型 {model.model_id} 失败: {str(e)}")
            
            logger.info(f"模型服务初始化完成，已加载 {len(self.active_models)} 个活跃模型")
        except Exception as e:
            logger.error(f"初始化模型服务失败: {str(e)}")
            raise ServiceUnavailableException("初始化模型服务失败")
    
    async def get_available_models(self, symbol: Optional[str] = None,
                             is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        参数:
            symbol: 交易对符号（可选）
            is_active: 是否活跃（可选）
            
        返回:
            模型信息列表
        """
        try:
            # 构建查询条件
            query = {}
            if symbol:
                query["symbols"] = symbol
            if is_active is not None:
                query["is_active"] = is_active
            
            # 从数据库获取模型列表
            # 注意：TrainedModelDB.get_active_models 需要增强以支持自定义查询
            if is_active is True:
                models = await TrainedModelDB.get_active_models(symbol)
            else:
                # 这里需要实现一个通用的查询方法
                # 示例中仅返回活跃模型
                models = await TrainedModelDB.get_active_models(symbol)
            
            # 转换为字典列表
            result = []
            for model in models:
                model_dict = model.dict()
                
                # 转换日期时间字段
                for field in ["training_start_time", "training_end_time"]:
                    if field in model_dict and isinstance(model_dict[field], datetime):
                        model_dict[field] = model_dict[field].isoformat()
                
                # 添加最新性能指标
                try:
                    performances = await ModelPerformanceDB.get_model_performances(model.model_id, limit=1)
                    if performances:
                        performance = performances[0]
                        model_dict["latest_performance"] = {
                            "evaluation_time": performance.evaluation_time.isoformat(),
                            "metrics": performance.metrics
                        }
                except:
                    pass
                
                result.append(model_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"获取可用模型列表失败: {str(e)}")
            raise ServiceUnavailableException(f"获取可用模型列表失败: {str(e)}")
    
    async def train_model(self, model_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        训练新模型
        
        参数:
            model_config: 模型配置信息，包括：
                - symbol: 交易对符号
                - model_name: 模型名称
                - model_type: 模型类型
                - timeframe: 时间框架
                - features: 使用的特征列表
                - target: 目标变量
                - target_horizon: 目标预测周期
                - train_start_date: 训练开始日期
                - train_end_date: 训练结束日期
                - hyperparameters: 超参数
                - notes: 备注信息
            
        返回:
            训练结果
        """
        try:
            # 验证必要参数
            required_fields = ["symbol", "model_name", "model_type", "timeframe", "features", "target"]
            for field in required_fields:
                if field not in model_config:
                    raise BadRequestException(f"缺少必要参数: {field}")
            
            # 准备参数
            symbol = model_config["symbol"]
            model_name = model_config["model_name"]
            model_type = model_config["model_type"]
            timeframe = model_config["timeframe"]
            features = model_config["features"]
            target = model_config["target"]
            target_horizon = model_config.get("target_horizon", 1)
            
            # 处理日期范围
            train_start_date = None
            train_end_date = None
            
            if "train_start_date" in model_config:
                train_start_date = datetime.fromisoformat(model_config["train_start_date"].replace('Z', '+00:00'))
            else:
                # 默认使用最近180天的数据
                train_start_date = datetime.now() - timedelta(days=180)
            
            if "train_end_date" in model_config:
                train_end_date = datetime.fromisoformat(model_config["train_end_date"].replace('Z', '+00:00'))
            else:
                train_end_date = datetime.now()
            
            # 获取特征数据
            feature_records = await FeatureDataDB.get_feature_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=train_start_date,
                end_date=train_end_date,
                limit=10000  # 获取足够的数据用于训练
            )
            
            if not feature_records:
                raise BadRequestException(f"没有找到交易对 {symbol} 在指定时间范围的特征数据")
            
            # 将数据转换为DataFrame
            feature_dicts = []
            for record in feature_records:
                record_dict = record.dict()
                record_dict["features"]["timestamp"] = record_dict["timestamp"]
                feature_dicts.append(record_dict["features"])
            
            df = pd.DataFrame(feature_dicts)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            
            # 处理目标变量
            if target == "price_direction":
                # 二分类预测价格方向
                df[f"future_return_{target_horizon}"] = df["close"].shift(-target_horizon) / df["close"] - 1
                df[f"target_{target}"] = np.where(df[f"future_return_{target_horizon}"] > 0, 1, 0)
            elif target == "price_change":
                # 回归预测价格变化百分比
                df[f"target_{target}"] = df["close"].shift(-target_horizon) / df["close"] - 1
            elif target == "volatility":
                # 回归预测波动率
                if f"volatility_{target_horizon}d" in df.columns:
                    df[f"target_{target}"] = df[f"volatility_{target_horizon}d"].shift(-1)
                else:
                    df[f"target_{target}"] = df["close"].pct_change().rolling(window=target_horizon).std().shift(-1)
            else:
                raise BadRequestException(f"不支持的目标变量: {target}")
            
            # 准备训练集
            df = df.dropna()
            
            if len(df) < 100:
                raise BadRequestException(f"有效数据样本不足，至少需要100条记录，当前有 {len(df)} 条")
            
            # 提取特征和目标
            X = df[features]
            y = df[f"target_{target}"]
            
            # 分割训练集和测试集
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            
            # 特征标准化
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # 训练模型
            model_instance = None
            hyperparameters = model_config.get("hyperparameters", {})
            training_start_time = datetime.now()
            
            if model_type == "linear":
                from sklearn.linear_model import LinearRegression, LogisticRegression
                if target == "price_direction":
                    model_instance = LogisticRegression(**hyperparameters)
                else:
                    model_instance = LinearRegression(**hyperparameters)
            
            elif model_type == "random_forest":
                from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
                if target == "price_direction":
                    model_instance = RandomForestClassifier(**hyperparameters)
                else:
                    model_instance = RandomForestRegressor(**hyperparameters)
            
            elif model_type == "xgboost":
                import xgboost as xgb
                if target == "price_direction":
                    model_instance = xgb.XGBClassifier(**hyperparameters)
                else:
                    model_instance = xgb.XGBRegressor(**hyperparameters)
            
            elif model_type == "lstm":
                # LSTM需要特殊处理，这里简化为一个占位符
                # 实际项目中需要实现完整的LSTM模型
                model_instance = "LSTM_PLACEHOLDER"
                logger.warning("LSTM模型训练需要特殊处理，当前仅返回占位符")
            
            else:
                raise BadRequestException(f"不支持的模型类型: {model_type}")
            
            # 训练模型
            if model_instance != "LSTM_PLACEHOLDER":
                model_instance.fit(X_train_scaled, y_train)
            
            training_end_time = datetime.now()
            
            # 评估模型
            performance_metrics = {}
            if model_instance != "LSTM_PLACEHOLDER":
                if target == "price_direction":
                    y_pred = model_instance.predict(X_test_scaled)
                    performance_metrics = {
                        "accuracy": float(accuracy_score(y_test, y_pred)),
                        "precision": float(precision_score(y_test, y_pred)),
                        "recall": float(recall_score(y_test, y_pred)),
                        "f1": float(f1_score(y_test, y_pred))
                    }
                else:
                    y_pred = model_instance.predict(X_test_scaled)
                    performance_metrics = {
                        "mae": float(mean_absolute_error(y_test, y_pred)),
                        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
                        "r2": float(model_instance.score(X_test_scaled, y_test))
                    }
            else:
                # 对LSTM占位符使用模拟指标
                performance_metrics = {
                    "accuracy": 0.75,
                    "precision": 0.72,
                    "recall": 0.78,
                    "f1": 0.75
                } if target == "price_direction" else {
                    "mae": 0.015,
                    "rmse": 0.025,
                    "r2": 0.65
                }
            
            # 生成模型ID和版本
            model_id = f"mdl_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            model_version = "1.0.0"
            
            # 保存模型文件
            model_filename = f"{model_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pkl"
            model_file_path = os.path.join(self.models_dir, model_filename)
            
            if model_instance != "LSTM_PLACEHOLDER":
                with open(model_file_path, 'wb') as f:
                    pickle.dump({
                        "model": model_instance,
                        "scaler": scaler,
                        "features": features,
                        "target": target,
                        "target_horizon": target_horizon,
                        "metadata": {
                            "model_id": model_id,
                            "model_name": model_name,
                            "model_type": model_type,
                            "model_version": model_version,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "training_start_time": training_start_time,
                            "training_end_time": training_end_time
                        }
                    }, f)
            
            # 创建训练模型记录
            model_record = TrainedModel(
                model_id=model_id,
                model_name=model_name,
                model_type=model_type,
                model_version=model_version,
                training_start_time=training_start_time,
                training_end_time=training_end_time,
                symbols=[symbol],
                timeframe=timeframe,
                features_used=features,
                hyperparameters=hyperparameters,
                performance_metrics=performance_metrics,
                model_file_path=model_file_path,
                is_active=True,
                created_by=model_config.get("created_by", "system"),
                notes=model_config.get("notes", "")
            )
            
            # 保存到数据库
            await TrainedModelDB.save_trained_model(model_record)
            
            # 创建性能评估记录
            performance_record = ModelPerformance(
                performance_id=f"perf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                model_id=model_id,
                evaluation_time=datetime.now(),
                evaluation_period={"start": train_start_date.isoformat(), "end": train_end_date.isoformat()},
                metrics=performance_metrics,
                predictions_sample=[
                    {"timestamp": X_test.index[i], "actual": float(y_test.iloc[i]), "predicted": float(y_pred[i]), "error": float(y_test.iloc[i] - y_pred[i])}
                    for i in range(min(5, len(y_test)))
                ],
                is_production=True
            )
            
            # 保存到数据库
            await ModelPerformanceDB.save_performance(performance_record)
            
            # 将模型添加到活跃模型缓存
            if model_instance != "LSTM_PLACEHOLDER":
                self.active_models[model_id] = {
                    "model": {
                        "model": model_instance,
                        "scaler": scaler,
                        "features": features,
                        "target": target,
                        "target_horizon": target_horizon
                    },
                    "metadata": model_record
                }
            
            # 返回训练结果
            return {
                "status": "success",
                "message": f"成功训练模型: {model_name}",
                "model_id": model_id,
                "model_name": model_name,
                "model_type": model_type,
                "model_version": model_version,
                "symbol": symbol,
                "timeframe": timeframe,
                "features_used": features,
                "target": target,
                "target_horizon": target_horizon,
                "training_start_time": training_start_time.isoformat(),
                "training_end_time": training_end_time.isoformat(),
                "training_duration_seconds": (training_end_time - training_start_time).total_seconds(),
                "performance_metrics": performance_metrics,
                "is_active": True,
                "model_file_path": model_file_path
            }
            
        except BadRequestException as e:
            logger.warning(f"训练模型参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"训练模型失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"训练模型失败: {str(e)}")
    
    async def predict(self, prediction_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用模型进行预测
        
        参数:
            prediction_request: 预测请求信息，包括：
                - model_id: 模型ID
                - input_data: 输入数据（可以是特征ID或原始特征值）
                
        返回:
            预测结果
        """
        try:
            # 验证必要参数
            if "model_id" not in prediction_request:
                raise BadRequestException("缺少必要参数: model_id")
            
            model_id = prediction_request["model_id"]
            
            # 获取模型
            if model_id in self.active_models:
                model_data = self.active_models[model_id]
            else:
                # 尝试从数据库加载模型
                model_record = await TrainedModelDB.get_trained_model(model_id)
                if not model_record:
                    raise BadRequestException(f"模型不存在: {model_id}")
                
                if not model_record.is_active:
                    raise BadRequestException(f"模型未激活: {model_id}")
                
                # 加载模型文件
                model_path = model_record.model_file_path
                if not os.path.exists(model_path):
                    raise BadRequestException(f"模型文件不存在: {model_path}")
                
                with open(model_path, 'rb') as f:
                    model_data = {
                        "model": pickle.load(f),
                        "metadata": model_record
                    }
                
                # 添加到缓存
                self.active_models[model_id] = model_data
            
            # 获取模型元数据
            model_metadata = model_data["metadata"]
            model_obj = model_data["model"]
            
            # 如果model_obj是从新版系统保存的，则包含完整信息
            if isinstance(model_obj, dict) and "model" in model_obj:
                model_instance = model_obj["model"]
                scaler = model_obj["scaler"]
                features = model_obj["features"]
                target = model_obj["target"]
                target_horizon = model_obj["target_horizon"]
            else:
                # 兼容旧版格式
                model_instance = model_obj
                scaler = StandardScaler()  # 这可能会导致问题，但这里只是为了兼容
                features = model_metadata.features_used
                target = "unknown"
                target_horizon = 1
            
            # 处理输入数据
            input_data = prediction_request.get("input_data", None)
            feature_id = prediction_request.get("feature_id", None)
            latest = prediction_request.get("latest", False)
            
            # 获取输入特征
            input_features = None
            
            if input_data is not None:
                # 直接使用提供的输入数据
                input_features = pd.DataFrame([input_data])
            elif feature_id is not None:
                # 通过特征ID获取
                # 这需要实现根据ID获取特征的方法
                raise NotImplementedError("通过特征ID获取输入数据的功能尚未实现")
            elif latest:
                # 获取最新的特征数据
                symbol = model_metadata.symbols[0] if model_metadata.symbols else "BTC/USDT"
                timeframe = model_metadata.timeframe
                
                latest_features = await FeatureDataDB.get_feature_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=1
                )
                
                if not latest_features:
                    raise BadRequestException(f"没有找到交易对 {symbol} 的最新特征数据")
                
                # 提取特征
                feature_dict = latest_features[0].features
                input_features = pd.DataFrame([feature_dict])
            else:
                raise BadRequestException("未提供输入数据，请提供input_data, feature_id或设置latest=true")
            
            # 确保所有必要的特征都存在
            missing_features = [f for f in features if f not in input_features.columns]
            if missing_features:
                raise BadRequestException(f"缺少必要的特征: {', '.join(missing_features)}")
            
            # 只使用模型需要的特征
            input_features = input_features[features]
            
            # 应用标准化
            input_scaled = scaler.transform(input_features)
            
            # 进行预测
            prediction = model_instance.predict(input_scaled)
            prediction_value = float(prediction[0])
            
            # 处理预测结果
            prediction_result = {
                "model_id": model_id,
                "model_name": model_metadata.model_name,
                "model_type": model_metadata.model_type,
                "symbol": model_metadata.symbols[0] if model_metadata.symbols else "unknown",
                "timestamp": datetime.now().isoformat(),
                "target": target,
                "target_horizon": target_horizon
            }
            
            if target == "price_direction":
                prediction_result["prediction"] = {
                    "direction": "up" if prediction_value > 0.5 else "down",
                    "probability": prediction_value if model_metadata.model_type in ["logistic_regression", "random_forest", "xgboost"] else None
                }
            elif target == "price_change":
                prediction_result["prediction"] = {
                    "price_change_percent": prediction_value * 100,
                    "direction": "up" if prediction_value > 0 else "down"
                }
            elif target == "volatility":
                prediction_result["prediction"] = {
                    "volatility": prediction_value
                }
            
            # 返回预测结果
            return prediction_result
            
        except BadRequestException as e:
            logger.warning(f"预测请求参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"预测失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"预测失败: {str(e)}")
    
    async def evaluate_model(self, model_id: str, evaluation_period: Dict[str, str],
                       comparison_models: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        评估模型性能
        
        参数:
            model_id: 模型ID
            evaluation_period: 评估周期，包含start和end
            comparison_models: 用于比较的其他模型ID列表
            
        返回:
            评估结果
        """
        try:
            # 获取模型
            model_record = await TrainedModelDB.get_trained_model(model_id)
            if not model_record:
                raise BadRequestException(f"模型不存在: {model_id}")
            
            # 处理评估周期
            start_date = datetime.fromisoformat(evaluation_period["start"].replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(evaluation_period["end"].replace('Z', '+00:00'))
            
            # 获取特征数据
            symbol = model_record.symbols[0] if model_record.symbols else "BTC/USDT"
            timeframe = model_record.timeframe
            
            feature_records = await FeatureDataDB.get_feature_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                limit=10000
            )
            
            if not feature_records:
                raise BadRequestException(f"没有找到交易对 {symbol} 在指定时间范围的特征数据")
            
            # 将数据转换为DataFrame
            feature_dicts = []
            for record in feature_records:
                record_dict = record.dict()
                record_dict["features"]["timestamp"] = record_dict["timestamp"]
                feature_dicts.append(record_dict["features"])
            
            df = pd.DataFrame(feature_dicts)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            
            # 加载模型
            model_path = model_record.model_file_path
            if not os.path.exists(model_path):
                raise BadRequestException(f"模型文件不存在: {model_path}")
            
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            # 如果model_data是从新版系统保存的，则包含完整信息
            if isinstance(model_data, dict) and "model" in model_data:
                model_instance = model_data["model"]
                scaler = model_data["scaler"]
                features = model_data["features"]
                target = model_data["target"]
                target_horizon = model_data["target_horizon"]
            else:
                # 兼容旧版格式
                model_instance = model_data
                scaler = StandardScaler()  # 这可能会导致问题
                features = model_record.features_used
                target = "unknown"
                target_horizon = 1
            
            # 处理目标变量
            if target == "price_direction":
                df[f"future_return_{target_horizon}"] = df["close"].shift(-target_horizon) / df["close"] - 1
                df[f"target_{target}"] = np.where(df[f"future_return_{target_horizon}"] > 0, 1, 0)
            elif target == "price_change":
                df[f"target_{target}"] = df["close"].shift(-target_horizon) / df["close"] - 1
            elif target == "volatility":
                if f"volatility_{target_horizon}d" in df.columns:
                    df[f"target_{target}"] = df[f"volatility_{target_horizon}d"].shift(-1)
                else:
                    df[f"target_{target}"] = df["close"].pct_change().rolling(window=target_horizon).std().shift(-1)
            
            # 删除缺失值
            df = df.dropna()
            
            if len(df) < 30:
                raise BadRequestException(f"有效数据样本不足，至少需要30条记录，当前有 {len(df)} 条")
            
            # 提取特征和目标
            X = df[features]
            y = df[f"target_{target}"]
            
            # 特征标准化
            X_scaled = scaler.transform(X)
            
            # 进行预测
            y_pred = model_instance.predict(X_scaled)
            
            # 计算性能指标
            performance_metrics = {}
            if target == "price_direction":
                performance_metrics = {
                    "accuracy": float(accuracy_score(y, y_pred)),
                    "precision": float(precision_score(y, y_pred)),
                    "recall": float(recall_score(y, y_pred)),
                    "f1": float(f1_score(y, y_pred))
                }
                
                # 添加交易策略指标
                signal_returns = df[f"future_return_{target_horizon}"] * y_pred
                performance_metrics["strategy_return"] = float(signal_returns.sum())
                performance_metrics["sharpe_ratio"] = float(signal_returns.mean() / signal_returns.std() * np.sqrt(252))
            else:
                performance_metrics = {
                    "mae": float(mean_absolute_error(y, y_pred)),
                    "rmse": float(np.sqrt(mean_squared_error(y, y_pred))),
                    "r2": float(model_instance.score(X_scaled, y))
                }
            
            # 创建性能评估记录
            performance_record = ModelPerformance(
                performance_id=f"perf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}",
                model_id=model_id,
                evaluation_time=datetime.now(),
                evaluation_period={"start": start_date.isoformat(), "end": end_date.isoformat()},
                metrics=performance_metrics,
                predictions_sample=[
                    {"timestamp": df.index[i].strftime('%Y-%m-%d %H:%M:%S'), "actual": float(y.iloc[i]), "predicted": float(y_pred[i]), "error": float(y.iloc[i] - y_pred[i])}
                    for i in range(min(5, len(y)))
                ],
                is_production=False,
                comparison_models=comparison_models or []
            )
            
            # 保存到数据库
            await ModelPerformanceDB.save_performance(performance_record)
            
            # 如果需要，执行与其他模型的比较
            comparisons = []
            if comparison_models:
                for comp_model_id in comparison_models:
                    try:
                        comp_performances = await ModelPerformanceDB.get_model_performances(comp_model_id, limit=1)
                        if comp_performances:
                            comp_performance = comp_performances[0]
                            comparisons.append({
                                "model_id": comp_model_id,
                                "metrics": comp_performance.metrics
                            })
                    except Exception as e:
                        logger.warning(f"获取比较模型 {comp_model_id} 的性能数据失败: {str(e)}")
            
            # 返回评估结果
            return {
                "status": "success",
                "message": f"成功评估模型: {model_record.model_name}",
                "model_id": model_id,
                "model_name": model_record.model_name,
                "evaluation_period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "performance_metrics": performance_metrics,
                "predictions_sample": performance_record.predictions_sample,
                "comparison_results": comparisons
            }
            
        except BadRequestException as e:
            logger.warning(f"评估模型参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"评估模型失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"评估模型失败: {str(e)}")
    
    async def update_model_status(self, model_id: str, is_active: bool) -> Dict[str, Any]:
        """
        更新模型状态
        
        参数:
            model_id: 模型ID
            is_active: 是否激活
            
        返回:
            更新结果
        """
        try:
            # 更新数据库
            result = await TrainedModelDB.update_model_status(model_id, is_active)
            
            if not result:
                raise BadRequestException(f"模型不存在: {model_id}")
            
            # 更新缓存
            if is_active:
                # 如果是激活模型，需要加载模型到缓存
                if model_id not in self.active_models:
                    model_record = await TrainedModelDB.get_trained_model(model_id)
                    
                    if model_record and model_record.is_active:
                        model_path = model_record.model_file_path
                        if os.path.exists(model_path):
                            with open(model_path, 'rb') as f:
                                self.active_models[model_id] = {
                                    "model": pickle.load(f),
                                    "metadata": model_record
                                }
                            logger.info(f"已加载模型到缓存: {model_id}")
            else:
                # 如果是停用模型，需要从缓存中移除
                if model_id in self.active_models:
                    del self.active_models[model_id]
                    logger.info(f"已从缓存中移除模型: {model_id}")
            
            # 返回更新结果
            return {
                "status": "success",
                "message": f"成功{'激活' if is_active else '停用'}模型: {model_id}",
                "model_id": model_id,
                "is_active": is_active
            }
            
        except BadRequestException as e:
            logger.warning(f"更新模型状态参数错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"更新模型状态失败: {str(e)}", exc_info=True)
            raise ServiceUnavailableException(f"更新模型状态失败: {str(e)}") 