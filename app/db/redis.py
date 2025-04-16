import redis
from redis.exceptions import ConnectionError, RedisError
from app.core.config import settings
import logging
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis客户端模拟类"""
    
    @staticmethod
    def get(key: str) -> str:
        """获取缓存数据"""
        return None
    
    @staticmethod
    def set(key: str, value: str, ex: int = None) -> bool:
        """设置缓存数据"""
        return True

    _client = None

    @classmethod
    def get_client(cls) -> redis.Redis:
        """获取Redis客户端连接"""
        if cls._client is None:
            try:
                cls._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_DB,
                    decode_responses=True,  # 自动将字节解码为字符串
                    socket_timeout=5,  # 连接超时时间(秒)
                )
                # 测试连接
                cls._client.ping()
                logger.info("Redis连接成功")
            except ConnectionError as e:
                logger.error(f"Redis连接失败: {str(e)}")
                raise
            except RedisError as e:
                logger.error(f"Redis操作错误: {str(e)}")
                raise
        return cls._client

    @classmethod
    def close(cls):
        """关闭Redis连接"""
        if cls._client:
            cls._client.close()
            cls._client = None
            logger.info("Redis连接已关闭")

    @classmethod
    def set(cls, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值
            ex: 过期时间(秒)
            
        Returns:
            bool: 操作是否成功
        """
        client = cls.get_client()
        try:
            return client.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Redis set操作错误 [key={key}]: {str(e)}")
            return False

    @classmethod
    def get(cls, key: str) -> Union[str, None]:
        """
        获取键值
        
        Args:
            key: 键名
            
        Returns:
            Union[str, None]: 键值,不存在时返回None
        """
        client = cls.get_client()
        try:
            return client.get(key)
        except RedisError as e:
            logger.error(f"Redis get操作错误 [key={key}]: {str(e)}")
            return None

    @classmethod
    def delete(cls, key: str) -> bool:
        """
        删除键
        
        Args:
            key: 键名
            
        Returns:
            bool: 操作是否成功
        """
        client = cls.get_client()
        try:
            return bool(client.delete(key))
        except RedisError as e:
            logger.error(f"Redis delete操作错误 [key={key}]: {str(e)}")
            return False

    @classmethod
    def exists(cls, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键名
            
        Returns:
            bool: 键是否存在
        """
        client = cls.get_client()
        try:
            return bool(client.exists(key))
        except RedisError as e:
            logger.error(f"Redis exists操作错误 [key={key}]: {str(e)}")
            return False 