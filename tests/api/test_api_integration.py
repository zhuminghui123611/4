"""
API接口集成测试
包含功能测试、边界值测试、异常测试、网络环境模拟、性能测试、安全性测试和接口间调用关系测试
"""

import unittest
import asyncio
import time
import httpx
import pytest
import logging
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

from app.services.data_integration_service import DataIntegrationService
from app.models.market_data import DataSourceType
from app.core.exceptions import ExternalAPIException

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API基础URL - 这应该指向您的实际API端点
BASE_URL = "http://localhost:8000/api/v1"

# 测试数据
TEST_DATA = {
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "chains": ["ethereum", "bsc", "solana"],
    "addresses": {
        "ethereum": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "bsc": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "solana": "9W5JeKsL8AZVh9XeFJ3JQaEx3ZCnfTK4uVVwXAXaMNFQ"
    },
    "tokens": {
        "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
        "bsc": "0x55d398326f99059ff775485246999027b3197955",  # USDT
    },
    "collections": {
        "ethereum": "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",  # BAYC
        "solana": "9W5JeKsL8AZVh9XeFJ3JQaEx3ZCnfTK4uVVwXAXaMNFQ"
    }
}

class TestAPIIntegration(unittest.TestCase):
    """API接口集成测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.http_client = httpx.AsyncClient(timeout=30.0)
    
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cls.http_client.aclose())
    
    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        expected_status: int = 200,
        check_error: bool = True
    ) -> Dict[str, Any]:
        """发送API请求并验证结果"""
        url = f"{BASE_URL}/{endpoint}"
        logger.info(f"发送 {method} 请求到 {url}")
        start_time = time.time()
        
        response = await self.http_client.request(
            method=method,
            url=url,
            params=params,
            json=json_data
        )
        
        elapsed = time.time() - start_time
        logger.info(f"请求耗时: {elapsed:.2f}秒")
        
        # 验证状态码
        self.assertEqual(
            response.status_code, 
            expected_status, 
            f"意外的状态码: {response.status_code}, 预期: {expected_status}, 响应: {response.text}"
        )
        
        # 解析响应
        try:
            result = response.json()
        except Exception as e:
            raise AssertionError(f"无法解析JSON响应: {response.text}, 错误: {str(e)}")
        
        # 检查错误
        if check_error and expected_status >= 400:
            self.assertIn("error", result, "错误响应应该包含'error'字段")
            self.assertIn("message", result["error"], "错误对象应该包含'message'字段")
        
        return result
    
    #--------------------------------------------------------------------------------
    # 1. 功能测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """测试健康检查端点"""
        result = await self.make_request("GET", "health")
        self.assertIn("status", result)
        self.assertEqual(result["status"], "ok")
    
    @pytest.mark.asyncio
    async def test_get_available_symbols(self):
        """测试获取可用交易对列表"""
        result = await self.make_request("GET", "predictions/symbols")
        self.assertIn("symbols", result)
        self.assertIsInstance(result["symbols"], list)
        self.assertTrue(len(result["symbols"]) > 0, "应该返回至少一个交易对")
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self):
        """测试获取历史数据"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 100
        }
        result = await self.make_request("GET", "predictions/historical-data", params=params)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertTrue(len(result["data"]) > 0, "应该返回历史数据记录")
        
        # 验证数据结构
        first_record = result["data"][0]
        for field in ["timestamp", "open", "high", "low", "close", "volume"]:
            self.assertIn(field, first_record, f"历史数据记录应包含 {field} 字段")
    
    @pytest.mark.asyncio
    async def test_sync_historical_data(self):
        """测试同步历史数据"""
        data = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2023-01-01T00:00:00Z"
        }
        result = await self.make_request("POST", "predictions/sync-historical-data", json_data=data)
        self.assertIn("success", result)
        self.assertTrue(result["success"], "同步操作应该成功")
        self.assertIn("records_count", result)
    
    @pytest.mark.asyncio
    async def test_process_features(self):
        """测试处理特征数据"""
        data = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "feature_type": "technical"
        }
        result = await self.make_request("POST", "predictions/process-features", json_data=data)
        self.assertIn("success", result)
        self.assertTrue(result["success"], "特征处理应该成功")
    
    @pytest.mark.asyncio
    async def test_get_feature_data(self):
        """测试获取特征数据"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "feature_type": "technical",
            "limit": 50
        }
        result = await self.make_request("GET", "predictions/feature-data", params=params)
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
    
    @pytest.mark.asyncio
    async def test_train_model(self):
        """测试训练模型"""
        data = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "model_type": "lightgbm",
            "train_size": 0.8
        }
        result = await self.make_request("POST", "predictions/train-model", json_data=data)
        self.assertIn("success", result)
        self.assertTrue(result["success"], "模型训练应该成功")
        self.assertIn("model_id", result)
    
    @pytest.mark.asyncio
    async def test_get_prediction(self):
        """测试获取预测结果"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h"
        }
        result = await self.make_request("GET", "predictions/predict", params=params)
        self.assertIn("prediction", result)
        self.assertIn("timestamp", result)
    
    #--------------------------------------------------------------------------------
    # 2. 边界值测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_historical_data_max_limit(self):
        """测试获取历史数据时使用最大限制值"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 10000  # 非常大的限制值
        }
        result = await self.make_request("GET", "predictions/historical-data", params=params)
        self.assertIn("data", result)
        # 验证API是否正确处理了大限制值（应该有一个内部最大限制）
        self.assertTrue(len(result["data"]) <= 10000)
    
    @pytest.mark.asyncio
    async def test_get_historical_data_min_limit(self):
        """测试获取历史数据时使用最小限制值"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 1
        }
        result = await self.make_request("GET", "predictions/historical-data", params=params)
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 1, "应该只返回一条记录")
    
    @pytest.mark.asyncio
    async def test_get_historical_data_zero_limit(self):
        """测试获取历史数据时限制值为零"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 0
        }
        # 应该返回错误或默认限制的数据
        result = await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400 if API_TREATS_ZERO_AS_ERROR else 200
        )
        if API_TREATS_ZERO_AS_ERROR:
            self.assertIn("error", result)
        else:
            self.assertIn("data", result)
    
    #--------------------------------------------------------------------------------
    # 3. 异常输入测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_historical_data_invalid_symbol(self):
        """测试使用无效的交易对"""
        params = {
            "symbol": "INVALID/PAIR",
            "timeframe": "1h",
            "limit": 10
        }
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=404
        )
    
    @pytest.mark.asyncio
    async def test_get_historical_data_invalid_timeframe(self):
        """测试使用无效的时间周期"""
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "invalid",
            "limit": 10
        }
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400
        )
    
    @pytest.mark.asyncio
    async def test_get_historical_data_missing_params(self):
        """测试缺少必填参数"""
        # 缺少symbol参数
        params = {
            "timeframe": "1h",
            "limit": 10
        }
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400
        )
        
        # 缺少timeframe参数
        params = {
            "symbol": "BTC/USDT",
            "limit": 10
        }
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400
        )
    
    @pytest.mark.asyncio
    async def test_train_model_invalid_parameters(self):
        """测试使用无效的模型参数"""
        data = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "model_type": "invalid_model",  # 无效的模型类型
            "train_size": 0.8
        }
        await self.make_request(
            "POST", 
            "predictions/train-model", 
            json_data=data,
            expected_status=400
        )
        
        data = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "model_type": "lightgbm",
            "train_size": 2.0  # 超出合法范围
        }
        await self.make_request(
            "POST", 
            "predictions/train-model", 
            json_data=data,
            expected_status=400
        )
    
    #--------------------------------------------------------------------------------
    # 4. 网络环境测试
    #--------------------------------------------------------------------------------
    @patch('httpx.AsyncClient.request')
    @pytest.mark.asyncio
    async def test_request_timeout(self, mock_request):
        """测试请求超时情况"""
        # 模拟超时异常
        mock_request.side_effect = httpx.TimeoutException("Request timed out")
        
        with self.assertRaises(httpx.TimeoutException):
            await self.make_request("GET", "predictions/symbols")
    
    @patch.object(DataIntegrationService, '_make_api_request')
    @pytest.mark.asyncio
    async def test_external_api_failure(self, mock_api_request):
        """测试外部API失败场景"""
        # 模拟外部API失败
        mock_api_request.side_effect = ExternalAPIException(
            status_code=503,
            message="外部服务暂时不可用"
        )
        
        # 测试系统是如何处理外部API失败的
        params = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "limit": 10
        }
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=503
        )
    
    #--------------------------------------------------------------------------------
    # 5. 性能测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_response_time(self):
        """测试响应时间"""
        start_time = time.time()
        await self.make_request("GET", "predictions/symbols")
        elapsed = time.time() - start_time
        
        logger.info(f"响应时间: {elapsed:.2f}秒")
        self.assertLess(elapsed, 2.0, "API响应时间应小于2秒")
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求"""
        async def make_concurrent_request():
            return await self.make_request("GET", "predictions/symbols")
        
        # 创建10个并发请求
        start_time = time.time()
        tasks = [make_concurrent_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        logger.info(f"10个并发请求耗时: {elapsed:.2f}秒")
        
        # 验证所有请求都成功
        for result in results:
            self.assertIn("symbols", result)
        
        # 验证平均响应时间
        avg_time = elapsed / 10
        logger.info(f"平均响应时间: {avg_time:.2f}秒")
        self.assertLess(avg_time, 5.0, "并发请求的平均响应时间应小于5秒")
    
    #--------------------------------------------------------------------------------
    # 6. 安全性测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self):
        """测试SQL注入尝试"""
        # 尝试一个简单的SQL注入
        params = {
            "symbol": "' OR 1=1; --",
            "timeframe": "1h",
            "limit": 10
        }
        # 应该返回错误，而不是执行SQL注入
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400
        )
    
    @pytest.mark.asyncio
    async def test_xss_attempt(self):
        """测试XSS攻击尝试"""
        # 尝试一个简单的XSS攻击
        params = {
            "symbol": "<script>alert('XSS')</script>",
            "timeframe": "1h",
            "limit": 10
        }
        # 应该返回错误，而不是执行XSS
        await self.make_request(
            "GET", 
            "predictions/historical-data", 
            params=params,
            expected_status=400
        )
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self):
        """测试未授权访问"""
        # 如果API需要授权，测试未授权访问的情况
        # 注意：这需要根据您的API授权机制进行调整
        
        # 移除授权头
        original_headers = self.http_client.headers.copy()
        if "Authorization" in self.http_client.headers:
            self.http_client.headers.pop("Authorization")
        
        try:
            # 尝试访问需要授权的端点
            await self.make_request(
                "GET", 
                "predictions/admin/models",  # 假设这是一个受保护的管理端点
                expected_status=401
            )
        finally:
            # 恢复原始头
            self.http_client.headers = original_headers
    
    #--------------------------------------------------------------------------------
    # 7. 接口间调用关系测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_data_flow_consistency(self):
        """测试数据在不同接口之间的一致性"""
        # 步骤1: 同步历史数据
        sync_data = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "start_date": "2023-03-01T00:00:00Z"
        }
        sync_result = await self.make_request("POST", "predictions/sync-historical-data", json_data=sync_data)
        self.assertTrue(sync_result["success"])
        
        # 步骤2: 获取历史数据
        hist_params = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "limit": 20
        }
        hist_result = await self.make_request("GET", "predictions/historical-data", params=hist_params)
        self.assertIn("data", hist_result)
        self.assertTrue(len(hist_result["data"]) > 0)
        
        # 步骤3: 处理特征
        feature_data = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "feature_type": "technical"
        }
        feature_result = await self.make_request("POST", "predictions/process-features", json_data=feature_data)
        self.assertTrue(feature_result["success"])
        
        # 步骤4: 获取特征数据
        feature_params = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "feature_type": "technical",
            "limit": 20
        }
        feature_data_result = await self.make_request("GET", "predictions/feature-data", params=feature_params)
        self.assertIn("data", feature_data_result)
        
        # 步骤5: 训练模型
        train_data = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "model_type": "lightgbm",
            "train_size": 0.8
        }
        train_result = await self.make_request("POST", "predictions/train-model", json_data=train_data)
        self.assertTrue(train_result["success"])
        model_id = train_result["model_id"]
        
        # 步骤6: 获取预测
        predict_params = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "model_id": model_id
        }
        predict_result = await self.make_request("GET", "predictions/predict", params=predict_params)
        self.assertIn("prediction", predict_result)
        
        # 步骤7: 评估模型
        eval_data = {
            "model_id": model_id
        }
        eval_result = await self.make_request("POST", "predictions/evaluate-model", json_data=eval_data)
        self.assertIn("metrics", eval_result)
        
        # 验证数据一致性
        # 1. 历史数据和特征数据的时间戳应该对应
        hist_timestamps = [record["timestamp"] for record in hist_result["data"]]
        feature_timestamps = [record["timestamp"] for record in feature_data_result["data"]]
        for timestamp in feature_timestamps:
            self.assertIn(timestamp, hist_timestamps, "特征数据时间戳应存在于历史数据中")

# 配置常量和标记
API_TREATS_ZERO_AS_ERROR = True  # 根据实际API行为调整

# 运行测试
if __name__ == "__main__":
    pytest.main(["-v", "test_api_integration.py"]) 