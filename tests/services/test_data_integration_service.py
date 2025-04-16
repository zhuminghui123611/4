"""
数据集成服务单元测试
测试与中继服务的交互功能
"""

import unittest
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import httpx

from app.services.data_integration_service import DataIntegrationService, with_retry, with_cache, APIRateLimiter
from app.models.market_data import DataSourceType
from app.core.exceptions import ExternalAPIException

class TestDataIntegrationService(unittest.TestCase):
    """数据集成服务单元测试类"""
    
    #--------------------------------------------------------------------------------
    # 功能测试
    #--------------------------------------------------------------------------------
    @patch("app.services.data_integration_service.httpx.AsyncClient.request")
    @pytest.mark.asyncio
    async def test_make_api_request(self, mock_request):
        """测试基本API请求功能"""
        # 配置Mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "测试数据"}
        mock_request.return_value = mock_response
        
        # 测试API请求
        result = await DataIntegrationService._make_api_request(
            data_source=DataSourceType.ANKR,
            method="GET",
            endpoint="test-endpoint",
            params={"param": "value"}
        )
        
        # 验证结果
        self.assertEqual(result, {"data": "测试数据"})
        
        # 验证调用
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(kwargs["method"], "GET")
        self.assertTrue(DataIntegrationService._base_urls[DataSourceType.ANKR] in kwargs["url"])
        self.assertEqual(kwargs["params"], {"param": "value"})
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_fetch_ankr_data(self, mock_api_request):
        """测试获取Ankr数据"""
        # 配置Mock
        mock_api_request.return_value = {"result": {"balance": "1000000000000000000"}}
        
        # 测试获取Ankr数据
        result = await DataIntegrationService.fetch_ankr_data(
            chain="ethereum",
            method="eth_getBalance",
            params=["0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "latest"]
        )
        
        # 验证结果
        self.assertEqual(result, {"balance": "1000000000000000000"})
        
        # 验证调用
        mock_api_request.assert_called_once()
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_fetch_reservoir_data(self, mock_api_request):
        """测试获取Reservoir数据"""
        # 配置Mock
        mock_api_request.return_value = {"collections": [{"id": "bayc", "name": "Bored Ape Yacht Club"}]}
        
        # 测试获取Reservoir数据
        result = await DataIntegrationService.fetch_reservoir_data(
            endpoint="bayc",
            params={"limit": 1}
        )
        
        # 验证结果
        self.assertEqual(result, {"collections": [{"id": "bayc", "name": "Bored Ape Yacht Club"}]})
        
        # 验证调用
        mock_api_request.assert_called_once()
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_fetch_okx_p2p_data(self, mock_api_request):
        """测试获取OKX P2P数据"""
        # 配置Mock
        mock_api_request.return_value = {"data": [{"id": "123", "price": "20000", "currency": "CNY"}]}
        
        # 测试获取OKX P2P数据
        result = await DataIntegrationService.fetch_okx_p2p_data(
            endpoint="",
            params={"quoteCcy": "CNY", "baseCcy": "BTC"}
        )
        
        # 验证结果
        self.assertEqual(result, {"data": [{"id": "123", "price": "20000", "currency": "CNY"}]})
        
        # 验证调用
        mock_api_request.assert_called_once()
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_fetch_oneinch_data(self, mock_api_request):
        """测试获取1inch数据"""
        # 配置Mock
        mock_api_request.return_value = {"tokens": {"0x123": {"symbol": "USDT", "decimals": 6}}}
        
        # 测试获取1inch数据
        result = await DataIntegrationService.fetch_oneinch_data(
            chain_id=1,
            endpoint="",
            params={}
        )
        
        # 验证结果
        self.assertEqual(result, {"tokens": {"0x123": {"symbol": "USDT", "decimals": 6}}})
        
        # 验证调用
        mock_api_request.assert_called_once()
    
    #--------------------------------------------------------------------------------
    # 异常测试
    #--------------------------------------------------------------------------------
    @patch("app.services.data_integration_service.httpx.AsyncClient.request")
    @pytest.mark.asyncio
    async def test_api_request_error(self, mock_request):
        """测试API请求错误处理"""
        # 配置Mock返回错误响应
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_request.return_value = mock_response
        
        # 测试API请求错误
        with self.assertRaises(ExternalAPIException) as context:
            await DataIntegrationService._make_api_request(
                data_source=DataSourceType.ANKR,
                method="GET",
                endpoint="test-endpoint"
            )
        
        # 验证异常
        self.assertEqual(context.exception.status_code, 400)
        self.assertTrue("API请求失败" in str(context.exception))
    
    @patch("app.services.data_integration_service.httpx.AsyncClient.request")
    @pytest.mark.asyncio
    async def test_network_error(self, mock_request):
        """测试网络错误处理"""
        # 配置Mock抛出网络异常
        mock_request.side_effect = httpx.RequestError("网络错误")
        
        # 测试网络错误
        with self.assertRaises(ExternalAPIException) as context:
            await DataIntegrationService._make_api_request(
                data_source=DataSourceType.ANKR,
                method="GET",
                endpoint="test-endpoint"
            )
        
        # 验证异常
        self.assertEqual(context.exception.status_code, 500)
        self.assertTrue("API请求异常" in str(context.exception))
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_ankr_api_error(self, mock_api_request):
        """测试Ankr API错误处理"""
        # 配置Mock返回错误响应
        mock_api_request.return_value = {"error": {"code": -32000, "message": "执行错误"}}
        
        # 测试Ankr API错误
        with self.assertRaises(ExternalAPIException) as context:
            await DataIntegrationService.fetch_ankr_data(
                chain="ethereum",
                method="eth_getBalance",
                params=["0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "latest"]
            )
        
        # 验证异常
        self.assertTrue("Ankr API错误" in str(context.exception))
    
    #--------------------------------------------------------------------------------
    # 边界值和异常输入测试
    #--------------------------------------------------------------------------------
    @patch("app.services.data_integration_service.httpx.AsyncClient.request")
    @pytest.mark.asyncio
    async def test_empty_response(self, mock_request):
        """测试空响应处理"""
        # 配置Mock返回空响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_response.text = ""
        mock_request.return_value = mock_response
        
        # 测试空响应
        result = await DataIntegrationService._make_api_request(
            data_source=DataSourceType.ANKR,
            method="GET",
            endpoint="test-endpoint"
        )
        
        # 验证结果包含原始文本
        self.assertEqual(result, {"raw_text": ""})
    
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_invalid_data_source(self, mock_api_request):
        """测试无效数据源处理"""
        # 测试无效数据源
        with self.assertRaises(ExternalAPIException) as context:
            await DataIntegrationService._make_api_request(
                data_source="invalid_source",
                method="GET",
                endpoint="test-endpoint"
            )
        
        # 验证异常
        self.assertEqual(context.exception.status_code, 500)
        self.assertTrue("未知的数据源类型" in str(context.exception))
        
        # 验证未调用API请求
        mock_api_request.assert_not_called()
    
    #--------------------------------------------------------------------------------
    # 测试工具类和装饰器
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_api_rate_limiter(self):
        """测试API速率限制器"""
        # 创建速率限制器
        rate_limiter = APIRateLimiter(calls_limit=3, time_period=1)
        
        # 测试正常情况下的调用
        start_time = asyncio.get_event_loop().time()
        
        for _ in range(3):
            await rate_limiter.wait_if_needed()
        
        # 第四次调用应该触发等待
        await rate_limiter.wait_if_needed()
        
        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time
        
        # 验证至少等待了预期的时间
        self.assertGreaterEqual(elapsed, 1.0)
    
    @patch("app.services.data_integration_service.httpx.AsyncClient.request")
    @pytest.mark.asyncio
    async def test_retry_decorator(self, mock_request):
        """测试重试装饰器"""
        # 配置Mock前两次失败，第三次成功
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.text = "Internal Server Error"
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": "测试数据"}
        
        mock_request.side_effect = [
            mock_response_error,  # 第一次调用失败
            mock_response_error,  # 第二次调用失败
            mock_response_success  # 第三次调用成功
        ]
        
        # 定义测试函数
        @with_retry(max_retries=3, retry_delay=0.1)
        async def test_func():
            return await DataIntegrationService._make_api_request(
                data_source=DataSourceType.ANKR,
                method="GET",
                endpoint="test-endpoint"
            )
        
        # 测试重试功能
        start_time = asyncio.get_event_loop().time()
        result = await test_func()
        end_time = asyncio.get_event_loop().time()
        
        # 验证结果
        self.assertEqual(result, {"data": "测试数据"})
        
        # 验证重试次数
        self.assertEqual(mock_request.call_count, 3)
        
        # 验证至少等待了预期的时间
        elapsed = end_time - start_time
        self.assertGreaterEqual(elapsed, 0.1 + 0.1 * 2)  # 初始延迟 + 第二次延迟
    
    @patch("app.services.data_integration_service.RedisClient")
    @patch("app.services.data_integration_service.DataIntegrationService._make_api_request")
    @pytest.mark.asyncio
    async def test_cache_decorator(self, mock_api_request, mock_redis):
        """测试缓存装饰器"""
        # 配置API请求Mock
        mock_api_request.return_value = {"data": "测试数据"}
        
        # 配置Redis Mock - 第一次未命中缓存，第二次命中缓存
        mock_redis.get.side_effect = [None, json.dumps({"data": "缓存数据"})]
        
        # 定义测试函数
        @with_cache(ttl=300, cache_key_prefix="test_cache")
        async def test_func(param):
            return await DataIntegrationService._make_api_request(
                data_source=DataSourceType.ANKR,
                method="GET",
                endpoint="test-endpoint",
                params={"param": param}
            )
        
        # 测试缓存未命中情况
        result1 = await test_func("value1")
        
        # 验证结果
        self.assertEqual(result1, {"data": "测试数据"})
        
        # 验证API请求被调用
        mock_api_request.assert_called_once()
        
        # 验证数据被保存到缓存
        mock_redis.set.assert_called_once()
        
        # 重置Mock
        mock_api_request.reset_mock()
        
        # 测试缓存命中情况
        result2 = await test_func("value2")
        
        # 验证结果
        self.assertEqual(result2, {"data": "缓存数据"})
        
        # 验证API请求未被调用
        mock_api_request.assert_not_called()
    
    #--------------------------------------------------------------------------------
    # 优雅降级测试
    #--------------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_handle_data_source_exception(self):
        """测试数据源异常处理和优雅降级"""
        # 定义一个总是抛出异常的异步函数
        async def failing_func():
            raise ExternalAPIException(status_code=500, message="测试异常")
        
        # 测试带有回退值的异常处理
        result = await DataIntegrationService.handle_data_source_exception(
            source=DataSourceType.ANKR,
            func=failing_func,
            fallback_value={"fallback": "数据"}
        )
        
        # 验证结果是回退值
        self.assertEqual(result, {"fallback": "数据"})
        
        # 测试无回退值的异常处理
        result = await DataIntegrationService.handle_data_source_exception(
            source=DataSourceType.ANKR,
            func=failing_func,
            log_error=False
        )
        
        # 验证结果是None
        self.assertIsNone(result)

# 运行测试
if __name__ == "__main__":
    pytest.main(["-v", "test_data_integration_service.py"]) 