#!/usr/bin/env python3
"""
网络弹性测试脚本
模拟不同的网络环境，测试系统的网络恢复能力和错误处理机制
"""

import asyncio
import logging
import time
import random
import sys
import argparse
from typing import Dict, Any, List, Optional, Callable, Awaitable

# 添加项目根目录到Python路径
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.data_integration_service import DataIntegrationService
from app.models.market_data import DataSourceType
from app.core.exceptions import ExternalAPIException

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class NetworkResilienceTester:
    """网络弹性测试类"""
    
    def __init__(self, 
                 retry_count: int = 3,
                 failure_rate: float = 0.3,
                 max_latency: float = 2.0,
                 report_interval: int = 5):
        """
        初始化网络弹性测试器
        
        Args:
            retry_count: 最大重试次数
            failure_rate: 模拟网络故障率 (0.0-1.0)
            max_latency: 最大网络延迟(秒)
            report_interval: 测试报告间隔(秒)
        """
        self.retry_count = retry_count
        self.failure_rate = failure_rate
        self.max_latency = max_latency
        self.report_interval = report_interval
        
        # 测试统计
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retry_requests = 0
        self.last_report_time = time.time()
    
    async def simulate_network_condition(self):
        """模拟网络条件 - 延迟和故障"""
        # 模拟网络延迟
        delay = random.uniform(0, self.max_latency)
        await asyncio.sleep(delay)
        
        # 模拟网络故障
        if random.random() < self.failure_rate:
            raise ExternalAPIException(
                status_code=503,
                message="模拟网络故障 - 服务暂时不可用"
            )
    
    async def test_api_call(self, 
                           func: Callable[..., Awaitable[Any]], 
                           *args, **kwargs) -> Dict[str, Any]:
        """
        测试API调用，包含重试逻辑
        
        Args:
            func: 要测试的API调用函数
            *args, **kwargs: 传递给API函数的参数
            
        Returns:
            API响应或错误信息
        """
        self.total_requests += 1
        retry_count = 0
        start_time = time.time()
        
        while retry_count <= self.retry_count:
            try:
                # 模拟网络条件
                await self.simulate_network_condition()
                
                # 执行API调用
                result = await func(*args, **kwargs)
                
                # 成功处理
                elapsed = time.time() - start_time
                self.successful_requests += 1
                logger.info(f"API调用成功 (尝试次数: {retry_count + 1}, 耗时: {elapsed:.2f}秒)")
                
                # 定期输出报告
                await self.report_stats()
                
                return {
                    "success": True,
                    "data": result,
                    "retries": retry_count,
                    "elapsed": elapsed
                }
                
            except ExternalAPIException as e:
                retry_count += 1
                self.retry_requests += 1
                
                if retry_count <= self.retry_count:
                    backoff_time = 0.5 * (2 ** retry_count)  # 指数退避
                    logger.warning(f"API调用失败，将在 {backoff_time:.2f} 秒后重试 ({retry_count}/{self.retry_count}): {str(e)}")
                    await asyncio.sleep(backoff_time)
                else:
                    # 达到最大重试次数
                    elapsed = time.time() - start_time
                    self.failed_requests += 1
                    logger.error(f"API调用最终失败，达到最大重试次数 ({self.retry_count})，总耗时: {elapsed:.2f}秒: {str(e)}")
                    
                    # 定期输出报告
                    await self.report_stats()
                    
                    return {
                        "success": False,
                        "error": str(e),
                        "status_code": e.status_code,
                        "retries": retry_count,
                        "elapsed": elapsed
                    }
    
    async def report_stats(self, force: bool = False):
        """输出测试统计信息"""
        now = time.time()
        if force or (now - self.last_report_time >= self.report_interval):
            success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
            retry_rate = (self.retry_requests / self.total_requests * 100) if self.total_requests > 0 else 0
            
            logger.info("-" * 80)
            logger.info("网络弹性测试统计:")
            logger.info(f"总请求数: {self.total_requests}")
            logger.info(f"成功请求数: {self.successful_requests} ({success_rate:.2f}%)")
            logger.info(f"失败请求数: {self.failed_requests} ({100 - success_rate:.2f}%)")
            logger.info(f"重试请求数: {self.retry_requests} ({retry_rate:.2f}%)")
            logger.info(f"模拟故障率: {self.failure_rate * 100:.2f}%")
            logger.info(f"最大网络延迟: {self.max_latency:.2f} 秒")
            logger.info("-" * 80)
            
            self.last_report_time = now
    
    async def test_all_services(self, iterations: int = 10, interval: float = 1.0):
        """
        测试所有中继服务API
        
        Args:
            iterations: 每个API的测试迭代次数
            interval: 测试间隔(秒)
        """
        logger.info(f"开始网络弹性测试，模拟故障率: {self.failure_rate * 100:.2f}%, 最大延迟: {self.max_latency:.2f}秒")
        
        for i in range(iterations):
            logger.info(f"测试迭代 {i + 1}/{iterations}")
            
            # 测试Ankr API
            logger.info("测试 Ankr API...")
            await self.test_api_call(
                DataIntegrationService.fetch_ankr_data,
                chain="ethereum",
                method="eth_getBalance",
                params=["0x742d35Cc6634C0532925a3b844Bc454e4438f44e", "latest"]
            )
            await asyncio.sleep(interval)
            
            # 测试Reservoir API
            logger.info("测试 Reservoir API...")
            await self.test_api_call(
                DataIntegrationService.fetch_reservoir_data,
                endpoint="0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",  # BAYC收藏
                params={"limit": 1}
            )
            await asyncio.sleep(interval)
            
            # 测试OKX P2P API
            logger.info("测试 OKX P2P API...")
            await self.test_api_call(
                DataIntegrationService.fetch_okx_p2p_data,
                endpoint="",
                params={"quoteCcy": "CNY", "baseCcy": "BTC", "side": "buy"}
            )
            await asyncio.sleep(interval)
            
            # 测试1inch API
            logger.info("测试 1inch API...")
            await self.test_api_call(
                DataIntegrationService.fetch_oneinch_data,
                chain_id=1,
                endpoint="",
                params={"limit": 10}
            )
            await asyncio.sleep(interval)
        
        # 最终报告
        await self.report_stats(force=True)

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="网络弹性测试工具")
    parser.add_argument("--failure-rate", type=float, default=0.3, help="模拟网络故障率 (0.0-1.0)")
    parser.add_argument("--max-latency", type=float, default=2.0, help="最大网络延迟(秒)")
    parser.add_argument("--iterations", type=int, default=5, help="每个API的测试迭代次数")
    parser.add_argument("--interval", type=float, default=1.0, help="测试间隔(秒)")
    args = parser.parse_args()
    
    tester = NetworkResilienceTester(
        failure_rate=args.failure_rate,
        max_latency=args.max_latency
    )
    
    try:
        await tester.test_all_services(
            iterations=args.iterations,
            interval=args.interval
        )
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        await tester.report_stats(force=True)
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
    
    logger.info("网络弹性测试完成")

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 