from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pymongo
from bson.objectid import ObjectId
import logging

from app.db.mongodb import get_collection, COLLECTION_HISTORICAL_DATA, COLLECTION_FEATURE_DATA, COLLECTION_TRAINED_MODELS, COLLECTION_MODEL_PERFORMANCES, COLLECTION_DATA_SOURCES
from app.db.models import HistoricalData, FeatureData, TrainedModel, ModelPerformance, DataSource, model_to_dict, dict_to_model

logger = logging.getLogger(__name__)

class HistoricalDataDB:
    """历史数据数据库服务，用于处理历史数据的存储和查询"""
    
    @staticmethod
    async def save_historical_data(data: Union[HistoricalData, List[HistoricalData]]) -> Union[str, List[str]]:
        """
        保存历史数据记录
        
        参数:
            data: 单个历史数据记录或记录列表
            
        返回:
            插入的记录ID或ID列表
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            
            # 处理单条记录
            if isinstance(data, HistoricalData):
                result = await collection.insert_one(model_to_dict(data))
                logger.info(f"历史数据已保存: {data.data_id}")
                return str(result.inserted_id)
            
            # 处理多条记录
            elif isinstance(data, list) and all(isinstance(item, HistoricalData) for item in data):
                data_dicts = [model_to_dict(item) for item in data]
                result = await collection.insert_many(data_dicts)
                logger.info(f"批量保存了 {len(result.inserted_ids)} 条历史数据")
                return [str(id) for id in result.inserted_ids]
            
            else:
                raise ValueError("无效的数据类型，必须是HistoricalData或其列表")
                
        except Exception as e:
            logger.error(f"保存历史数据失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_historical_data(
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source: Optional[str] = None,
        processed: Optional[bool] = None,
        limit: int = 1000,
        sort_order: int = pymongo.DESCENDING
    ) -> List[HistoricalData]:
        """
        获取历史数据记录
        
        参数:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源
            processed: 是否已处理
            limit: 返回记录的最大数量
            sort_order: 排序顺序 (pymongo.ASCENDING 或 pymongo.DESCENDING)
            
        返回:
            历史数据记录列表
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            
            # 构建查询条件
            query = {}
            if symbol:
                query["symbol"] = symbol
            if start_date:
                query["timestamp"] = {"$gte": start_date}
            if end_date:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = end_date
                else:
                    query["timestamp"] = {"$lte": end_date}
            if source:
                query["source"] = source
            if processed is not None:
                query["processed"] = processed
            
            # 执行查询
            cursor = collection.find(query).sort("timestamp", sort_order).limit(limit)
            
            # 转换为模型列表
            data = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                data.append(dict_to_model(HistoricalData, doc))
            
            return data
        except Exception as e:
            logger.error(f"获取历史数据失败: {str(e)}")
            raise
    
    @staticmethod
    async def update_historical_data_status(data_id: str, processed: bool = True, validated: bool = True, data_quality_score: Optional[float] = None) -> bool:
        """
        更新历史数据的处理状态
        
        参数:
            data_id: 数据记录ID
            processed: 是否已处理
            validated: 是否已验证
            data_quality_score: 数据质量评分
            
        返回:
            更新是否成功
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            
            # 构建更新内容
            update_data = {
                "processed": processed,
                "validated": validated
            }
            
            if data_quality_score is not None:
                update_data["data_quality_score"] = data_quality_score
            
            # 执行更新
            result = await collection.update_one(
                {"data_id": data_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"历史数据状态已更新: {data_id}")
                return True
            else:
                logger.warning(f"历史数据状态更新失败，未找到记录: {data_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新历史数据状态失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_symbols_with_data() -> List[str]:
        """
        获取有历史数据的所有交易对符号
        
        返回:
            交易对符号列表
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            symbols = await collection.distinct("symbol")
            return symbols
        except Exception as e:
            logger.error(f"获取交易对符号列表失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_data_date_range(symbol: str) -> Dict[str, datetime]:
        """
        获取指定交易对的数据日期范围
        
        参数:
            symbol: 交易对符号
            
        返回:
            包含最早和最晚日期的字典
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            
            # 获取最早的记录
            earliest = collection.find({"symbol": symbol}).sort("timestamp", pymongo.ASCENDING).limit(1)
            earliest_doc = await earliest.to_list(length=1)
            
            # 获取最晚的记录
            latest = collection.find({"symbol": symbol}).sort("timestamp", pymongo.DESCENDING).limit(1)
            latest_doc = await latest.to_list(length=1)
            
            result = {}
            
            if earliest_doc:
                result["earliest"] = earliest_doc[0]["timestamp"]
            
            if latest_doc:
                result["latest"] = latest_doc[0]["timestamp"]
            
            return result
        except Exception as e:
            logger.error(f"获取数据日期范围失败: {str(e)}")
            raise
    
    @staticmethod
    async def delete_historical_data(data_id: str) -> bool:
        """
        删除历史数据记录
        
        参数:
            data_id: 数据记录ID
            
        返回:
            删除是否成功
        """
        try:
            collection = get_collection(COLLECTION_HISTORICAL_DATA)
            result = await collection.delete_one({"data_id": data_id})
            
            if result.deleted_count > 0:
                logger.info(f"历史数据已删除: {data_id}")
                return True
            else:
                logger.warning(f"历史数据删除失败，未找到记录: {data_id}")
                return False
        except Exception as e:
            logger.error(f"删除历史数据失败: {str(e)}")
            raise


class FeatureDataDB:
    """特征数据数据库服务，用于处理预处理后的特征数据的存储和查询"""
    
    @staticmethod
    async def save_feature_data(data: Union[FeatureData, List[FeatureData]]) -> Union[str, List[str]]:
        """
        保存特征数据记录
        
        参数:
            data: 单个特征数据记录或记录列表
            
        返回:
            插入的记录ID或ID列表
        """
        try:
            collection = get_collection(COLLECTION_FEATURE_DATA)
            
            # 处理单条记录
            if isinstance(data, FeatureData):
                result = await collection.insert_one(model_to_dict(data))
                logger.info(f"特征数据已保存: {data.feature_id}")
                return str(result.inserted_id)
            
            # 处理多条记录
            elif isinstance(data, list) and all(isinstance(item, FeatureData) for item in data):
                data_dicts = [model_to_dict(item) for item in data]
                result = await collection.insert_many(data_dicts)
                logger.info(f"批量保存了 {len(result.inserted_ids)} 条特征数据")
                return [str(id) for id in result.inserted_ids]
            
            else:
                raise ValueError("无效的数据类型，必须是FeatureData或其列表")
                
        except Exception as e:
            logger.error(f"保存特征数据失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_feature_data(
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        timeframe: Optional[str] = None,
        feature_version: Optional[str] = None,
        limit: int = 1000,
        sort_order: int = pymongo.DESCENDING
    ) -> List[FeatureData]:
        """
        获取特征数据记录
        
        参数:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间框架
            feature_version: 特征版本
            limit: 返回记录的最大数量
            sort_order: 排序顺序
            
        返回:
            特征数据记录列表
        """
        try:
            collection = get_collection(COLLECTION_FEATURE_DATA)
            
            # 构建查询条件
            query = {}
            if symbol:
                query["symbol"] = symbol
            if start_date:
                query["timestamp"] = {"$gte": start_date}
            if end_date:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = end_date
                else:
                    query["timestamp"] = {"$lte": end_date}
            if timeframe:
                query["timeframe"] = timeframe
            if feature_version:
                query["feature_version"] = feature_version
            
            # 执行查询
            cursor = collection.find(query).sort("timestamp", sort_order).limit(limit)
            
            # 转换为模型列表
            features = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                features.append(dict_to_model(FeatureData, doc))
            
            return features
        except Exception as e:
            logger.error(f"获取特征数据失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_latest_feature_version() -> Optional[str]:
        """
        获取最新的特征版本
        
        返回:
            最新的特征版本，如果没有则返回None
        """
        try:
            collection = get_collection(COLLECTION_FEATURE_DATA)
            
            # 按创建时间降序排序并获取第一条记录
            latest = collection.find().sort("created_at", pymongo.DESCENDING).limit(1)
            latest_doc = await latest.to_list(length=1)
            
            if latest_doc:
                return latest_doc[0]["feature_version"]
            return None
            
        except Exception as e:
            logger.error(f"获取最新特征版本失败: {str(e)}")
            raise


class TrainedModelDB:
    """训练模型数据库服务，用于处理训练完成的模型信息的存储和查询"""
    
    @staticmethod
    async def save_trained_model(model: TrainedModel) -> str:
        """
        保存训练模型信息
        
        参数:
            model: 训练模型信息
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection(COLLECTION_TRAINED_MODELS)
            result = await collection.insert_one(model_to_dict(model))
            logger.info(f"训练模型信息已保存: {model.model_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存训练模型信息失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_trained_model(model_id: str) -> Optional[TrainedModel]:
        """
        获取训练模型信息
        
        参数:
            model_id: 模型ID
            
        返回:
            训练模型信息，如果不存在则返回None
        """
        try:
            collection = get_collection(COLLECTION_TRAINED_MODELS)
            doc = await collection.find_one({"model_id": model_id})
            
            if doc:
                return dict_to_model(TrainedModel, doc)
            return None
            
        except Exception as e:
            logger.error(f"获取训练模型信息失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_active_models(symbol: Optional[str] = None, model_type: Optional[str] = None) -> List[TrainedModel]:
        """
        获取激活状态的模型列表
        
        参数:
            symbol: 交易对符号(可选)
            model_type: 模型类型(可选)
            
        返回:
            激活状态的模型列表
        """
        try:
            collection = get_collection(COLLECTION_TRAINED_MODELS)
            
            # 构建查询条件
            query = {"is_active": True}
            if symbol:
                query["symbols"] = symbol
            if model_type:
                query["model_type"] = model_type
            
            # 执行查询
            cursor = collection.find(query)
            
            # 转换为模型列表
            models = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=100)  # 假设模型数量不会太多
            for doc in docs:
                models.append(dict_to_model(TrainedModel, doc))
            
            return models
            
        except Exception as e:
            logger.error(f"获取激活模型列表失败: {str(e)}")
            raise
    
    @staticmethod
    async def update_model_status(model_id: str, is_active: bool) -> bool:
        """
        更新模型激活状态
        
        参数:
            model_id: 模型ID
            is_active: 是否激活
            
        返回:
            更新是否成功
        """
        try:
            collection = get_collection(COLLECTION_TRAINED_MODELS)
            
            # 执行更新
            result = await collection.update_one(
                {"model_id": model_id},
                {"$set": {"is_active": is_active}}
            )
            
            if result.modified_count > 0:
                logger.info(f"模型状态已更新: {model_id}, is_active={is_active}")
                return True
            else:
                logger.warning(f"模型状态更新失败，未找到记录: {model_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新模型状态失败: {str(e)}")
            raise


class ModelPerformanceDB:
    """模型性能评估数据库服务，用于处理模型性能评估记录的存储和查询"""
    
    @staticmethod
    async def save_performance(performance: ModelPerformance) -> str:
        """
        保存模型性能评估记录
        
        参数:
            performance: 模型性能评估记录
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection(COLLECTION_MODEL_PERFORMANCES)
            result = await collection.insert_one(model_to_dict(performance))
            logger.info(f"模型性能评估记录已保存: {performance.performance_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存模型性能评估记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_model_performances(model_id: str, limit: int = 10) -> List[ModelPerformance]:
        """
        获取指定模型的性能评估记录列表
        
        参数:
            model_id: 模型ID
            limit: 返回记录的最大数量
            
        返回:
            性能评估记录列表
        """
        try:
            collection = get_collection(COLLECTION_MODEL_PERFORMANCES)
            
            # 执行查询
            cursor = collection.find({"model_id": model_id}).sort("evaluation_time", pymongo.DESCENDING).limit(limit)
            
            # 转换为模型列表
            performances = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                performances.append(dict_to_model(ModelPerformance, doc))
            
            return performances
            
        except Exception as e:
            logger.error(f"获取模型性能评估记录失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_best_performing_models(
        metrics: str = "accuracy",
        evaluation_period: Optional[Dict[str, str]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取表现最好的模型列表
        
        参数:
            metrics: 用于评估的指标名称
            evaluation_period: 评估周期
            limit: 返回记录的最大数量
            
        返回:
            包含模型ID和性能信息的字典列表
        """
        try:
            collection = get_collection(COLLECTION_MODEL_PERFORMANCES)
            
            # 构建查询条件
            query = {}
            if evaluation_period:
                query["evaluation_period"] = evaluation_period
            
            # 构建排序和查询字段
            sort_field = f"metrics.{metrics}"
            
            # 执行聚合查询，根据指定指标获取每个模型的最佳性能
            pipeline = [
                {"$match": query},
                {"$sort": {sort_field: -1}},  # 按指标降序排序
                {"$group": {
                    "_id": "$model_id",
                    "performance": {"$first": "$$ROOT"}
                }},
                {"$sort": {f"performance.metrics.{metrics}": -1}},  # 按指标降序排序
                {"$limit": limit}
            ]
            
            cursor = collection.aggregate(pipeline)
            
            # 提取结果
            result = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=limit)
            for doc in docs:
                performance = dict_to_model(ModelPerformance, doc["performance"])
                model = await TrainedModelDB.get_trained_model(performance.model_id)
                
                if model:
                    result.append({
                        "model_id": model.model_id,
                        "model_name": model.model_name,
                        "model_type": model.model_type,
                        "performance": {
                            "metrics": performance.metrics,
                            "evaluation_time": performance.evaluation_time,
                            "evaluation_period": performance.evaluation_period
                        }
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"获取最佳模型列表失败: {str(e)}")
            raise


class DataSourceDB:
    """数据源信息数据库服务，用于处理数据源信息记录的存储和查询"""
    
    @staticmethod
    async def save_data_source(source: DataSource) -> str:
        """
        保存数据源信息记录
        
        参数:
            source: 数据源信息记录
            
        返回:
            插入的记录ID
        """
        try:
            collection = get_collection(COLLECTION_DATA_SOURCES)
            result = await collection.insert_one(model_to_dict(source))
            logger.info(f"数据源信息已保存: {source.source_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"保存数据源信息失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_data_source(source_id: str) -> Optional[DataSource]:
        """
        获取数据源信息
        
        参数:
            source_id: 数据源ID
            
        返回:
            数据源信息，如果不存在则返回None
        """
        try:
            collection = get_collection(COLLECTION_DATA_SOURCES)
            doc = await collection.find_one({"source_id": source_id})
            
            if doc:
                return dict_to_model(DataSource, doc)
            return None
            
        except Exception as e:
            logger.error(f"获取数据源信息失败: {str(e)}")
            raise
    
    @staticmethod
    async def get_all_active_data_sources() -> List[DataSource]:
        """
        获取所有激活状态的数据源列表
        
        返回:
            激活状态的数据源列表
        """
        try:
            collection = get_collection(COLLECTION_DATA_SOURCES)
            
            # 执行查询
            cursor = collection.find({"status": "active"}).sort("priority", pymongo.ASCENDING)
            
            # 转换为模型列表
            sources = []
            # 使用 to_list 方法替代 async for
            docs = await cursor.to_list(length=100)  # 假设不会超过100个数据源
            for doc in docs:
                sources.append(dict_to_model(DataSource, doc))
            
            return sources
            
        except Exception as e:
            logger.error(f"获取激活数据源列表失败: {str(e)}")
            raise
    
    @staticmethod
    async def update_data_source_status(source_id: str, status: str) -> bool:
        """
        更新数据源状态
        
        参数:
            source_id: 数据源ID
            status: 新状态
            
        返回:
            更新是否成功
        """
        try:
            collection = get_collection(COLLECTION_DATA_SOURCES)
            
            # 执行更新
            result = await collection.update_one(
                {"source_id": source_id},
                {"$set": {"status": status}}
            )
            
            if result.modified_count > 0:
                logger.info(f"数据源状态已更新: {source_id}, status={status}")
                return True
            else:
                logger.warning(f"数据源状态更新失败，未找到记录: {source_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新数据源状态失败: {str(e)}")
            raise
    
    @staticmethod
    async def update_last_updated(source_id: str) -> bool:
        """
        更新数据源的最后更新时间
        
        参数:
            source_id: 数据源ID
            
        返回:
            更新是否成功
        """
        try:
            collection = get_collection(COLLECTION_DATA_SOURCES)
            
            # 执行更新
            result = await collection.update_one(
                {"source_id": source_id},
                {"$set": {"last_updated": datetime.now()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"数据源最后更新时间已更新: {source_id}")
                return True
            else:
                logger.warning(f"数据源最后更新时间更新失败，未找到记录: {source_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新数据源最后更新时间失败: {str(e)}")
            raise 