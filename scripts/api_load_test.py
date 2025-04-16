#!/usr/bin/env python3
"""
API负载测试脚本
测试API接口的性能和并发处理能力
"""

import asyncio
import aiohttp
import time
import datetime
import argparse
import logging
import json
import sys
import os
import random
import statistics
from typing import Dict, List, Any, Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('api_load_test.log')
    ]
)
logger = logging.getLogger(__name__)

class APILoadTester:
    """API负载测试类"""
    
    def __init__(self, 
                 base_url: str,
                 concurrency: int = 10,
                 total_requests: int = 1000,
                 ramp_up_time: int = 5,
                 timeout: float = 30.0,
                 report_file: str = "api_load_test_report.json"):
        """
        初始化API负载测试器
        
        Args:
            base_url: API基础URL
            concurrency: 并发用户数
            total_requests: 总请求数
            ramp_up_time: 爬坡时间(秒)，即达到目标并发数所需的时间
            timeout: 请求超时时间(秒)
            report_file: 测试报告文件路径
        """
        self.base_url = base_url.rstrip('/')
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.ramp_up_time = ramp_up_time
        self.timeout = timeout
        self.report_file = report_file
        
        # 测试场景配置
        self.test_scenarios = {
            "健康检查": {
                "weight": 10,  # 权重，决定被选中的概率
                "endpoint": "/api/v1/health",
                "method": "GET",
                "params": {}
            },
            "获取交易对": {
                "weight": 15,
                "endpoint": "/api/v1/predictions/symbols",
                "method": "GET",
                "params": {}
            },
            "获取历史数据": {
                "weight": 25,
                "endpoint": "/api/v1/predictions/historical-data",
                "method": "GET",
                "params": {
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "limit": 100
                }
            },
            "获取特征数据": {
                "weight": 20,
                "endpoint": "/api/v1/predictions/feature-data",
                "method": "GET",
                "params": {
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "feature_type": "technical",
                    "limit": 50
                }
            },
            "获取预测结果": {
                "weight": 30,
                "endpoint": "/api/v1/predictions/predict",
                "method": "GET",
                "params": {
                    "symbol": "BTC/USDT",
                    "timeframe": "1h"
                }
            }
        }
        
        # 计算权重总和
        self.total_weight = sum(scenario["weight"] for scenario in self.test_scenarios.values())
        
        # 结果统计
        self.results = []
        self.start_time = None
        self.end_time = None
        self.completed_requests = 0
        self.failed_requests = 0
        
        # 并发控制
        self.request_semaphore = asyncio.Semaphore(concurrency)
        
        # 测试参数变量
        self.test_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"]
        self.test_timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.test_feature_types = ["technical", "fundamental", "sentiment"]
    
    def _select_scenario(self) -> Tuple[str, Dict[str, Any]]:
        """
        根据权重随机选择测试场景
        
        Returns:
            场景名称和配置
        """
        r = random.uniform(0, self.total_weight)
        cumulative_weight = 0
        
        for name, scenario in self.test_scenarios.items():
            cumulative_weight += scenario["weight"]
            if r <= cumulative_weight:
                return name, scenario
        
        # 默认返回第一个场景
        name = list(self.test_scenarios.keys())[0]
        return name, self.test_scenarios[name]
    
    def _randomize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        随机化请求参数，增加测试多样性
        
        Args:
            params: 原始参数
            
        Returns:
            随机化后的参数
        """
        randomized = params.copy()
        
        # 随机化交易对
        if "symbol" in randomized:
            randomized["symbol"] = random.choice(self.test_symbols)
        
        # 随机化时间周期
        if "timeframe" in randomized:
            randomized["timeframe"] = random.choice(self.test_timeframes)
        
        # 随机化特征类型
        if "feature_type" in randomized:
            randomized["feature_type"] = random.choice(self.test_feature_types)
        
        # 随机化限制数量
        if "limit" in randomized:
            # 在原始值的50%-150%范围内随机
            original_limit = randomized["limit"]
            min_limit = max(1, int(original_limit * 0.5))
            max_limit = int(original_limit * 1.5)
            randomized["limit"] = random.randint(min_limit, max_limit)
        
        return randomized
    
    async def _make_request(self, session: aiohttp.ClientSession, scenario_name: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送API请求并记录结果
        
        Args:
            session: aiohttp会话
            scenario_name: 场景名称
            scenario: 场景配置
            
        Returns:
            请求结果
        """
        # 获取场景配置
        method = scenario["method"]
        endpoint = scenario["endpoint"]
        params = self._randomize_params(scenario["params"])
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        result = {
            "scenario": scenario_name,
            "method": method,
            "endpoint": endpoint,
            "params": params,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 获取并发控制信号量
        async with self.request_semaphore:
            try:
                if method == "GET":
                    async with session.get(url, params=params, timeout=self.timeout) as response:
                        elapsed = time.time() - start_time
                        status = response.status
                        try:
                            # 只读取响应，不关心内容
                            await response.read()
                        except:
                            pass
                elif method == "POST":
                    async with session.post(url, json=params, timeout=self.timeout) as response:
                        elapsed = time.time() - start_time
                        status = response.status
                        try:
                            # 只读取响应，不关心内容
                            await response.read()
                        except:
                            pass
                else:
                    self.failed_requests += 1
                    return {
                        **result,
                        "success": False,
                        "error": f"不支持的HTTP方法: {method}",
                        "response_time": 0
                    }
                
                # 记录结果
                self.completed_requests += 1
                result.update({
                    "success": 200 <= status < 400,
                    "status": status,
                    "response_time": elapsed
                })
                
                if not result["success"]:
                    self.failed_requests += 1
                
                return result
                
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                self.failed_requests += 1
                return {
                    **result,
                    "success": False,
                    "error": "请求超时",
                    "response_time": elapsed
                }
            except Exception as e:
                elapsed = time.time() - start_time
                self.failed_requests += 1
                return {
                    **result,
                    "success": False,
                    "error": str(e),
                    "response_time": elapsed
                }
    
    async def run_load_test(self):
        """运行负载测试"""
        logger.info(f"开始API负载测试，并发用户数: {self.concurrency}，总请求数: {self.total_requests}")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            # 创建请求任务
            for i in range(self.total_requests):
                # 计算延迟启动时间，实现爬坡
                if self.ramp_up_time > 0:
                    delay = self.ramp_up_time * (i / self.total_requests)
                else:
                    delay = 0
                
                # 选择测试场景
                scenario_name, scenario = self._select_scenario()
                
                # 创建并发任务
                task = asyncio.create_task(self._delayed_request(session, scenario_name, scenario, delay))
                tasks.append(task)
                
                # 定期输出进度
                if (i + 1) % 100 == 0 or i + 1 == self.total_requests:
                    logger.info(f"已创建 {i + 1}/{self.total_requests} 个请求任务")
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks)
            self.results.extend(results)
            
            self.end_time = time.time()
            
            # 生成测试报告
            self.generate_report()
            
            logger.info(f"负载测试完成，总耗时: {self.end_time - self.start_time:.2f}秒")
    
    async def _delayed_request(self, session: aiohttp.ClientSession, scenario_name: str, scenario: Dict[str, Any], delay: float):
        """带延迟的请求，用于实现爬坡"""
        if delay > 0:
            await asyncio.sleep(delay)
        return await self._make_request(session, scenario_name, scenario)
    
    def generate_report(self):
        """生成测试报告"""
        # 计算总体统计
        total_time = self.end_time - self.start_time
        request_rate = self.total_requests / total_time
        success_rate = (self.completed_requests - self.failed_requests) / self.total_requests * 100 if self.total_requests > 0 else 0
        
        # 提取响应时间
        response_times = [r["response_time"] for r in self.results if "response_time" in r]
        
        # 计算响应时间统计
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = np.percentile(response_times, 95)
            p99_response_time = np.percentile(response_times, 99)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
        else:
            avg_response_time = median_response_time = min_response_time = max_response_time = p95_response_time = p99_response_time = std_dev = 0
        
        # 按场景分组统计
        scenario_stats = {}
        for scenario_name in self.test_scenarios.keys():
            scenario_results = [r for r in self.results if r.get("scenario") == scenario_name]
            scenario_times = [r["response_time"] for r in scenario_results if "response_time" in r]
            
            if scenario_times:
                scenario_stats[scenario_name] = {
                    "requests": len(scenario_results),
                    "success_rate": sum(1 for r in scenario_results if r.get("success", False)) / len(scenario_results) * 100,
                    "avg_response_time": statistics.mean(scenario_times),
                    "median_response_time": statistics.median(scenario_times),
                    "min_response_time": min(scenario_times),
                    "max_response_time": max(scenario_times),
                    "p95_response_time": np.percentile(scenario_times, 95),
                    "std_dev": statistics.stdev(scenario_times) if len(scenario_times) > 1 else 0
                }
        
        # 构建报告
        report = {
            "summary": {
                "test_start": datetime.datetime.fromtimestamp(self.start_time).isoformat(),
                "test_end": datetime.datetime.fromtimestamp(self.end_time).isoformat(),
                "total_time_seconds": total_time,
                "total_requests": self.total_requests,
                "completed_requests": self.completed_requests,
                "failed_requests": self.failed_requests,
                "requests_per_second": request_rate,
                "success_rate": success_rate,
                "concurrency": self.concurrency
            },
            "response_time": {
                "average": avg_response_time,
                "median": median_response_time,
                "min": min_response_time,
                "max": max_response_time,
                "p95": p95_response_time,
                "p99": p99_response_time,
                "std_dev": std_dev
            },
            "scenarios": scenario_stats,
            "test_config": {
                "base_url": self.base_url,
                "concurrency": self.concurrency,
                "total_requests": self.total_requests,
                "ramp_up_time": self.ramp_up_time,
                "timeout": self.timeout
            }
        }
        
        # 保存报告
        try:
            with open(self.report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"测试报告已保存到 {self.report_file}")
        except Exception as e:
            logger.error(f"保存测试报告失败: {str(e)}")
        
        # 输出摘要
        logger.info("-" * 80)
        logger.info("API负载测试摘要:")
        logger.info(f"总请求数: {self.total_requests}")
        logger.info(f"完成请求数: {self.completed_requests}")
        logger.info(f"失败请求数: {self.failed_requests}")
        logger.info(f"成功率: {success_rate:.2f}%")
        logger.info(f"总测试时间: {total_time:.2f}秒")
        logger.info(f"请求速率: {request_rate:.2f}请求/秒")
        logger.info(f"平均响应时间: {avg_response_time:.3f}秒")
        logger.info(f"中位响应时间: {median_response_time:.3f}秒")
        logger.info(f"95%响应时间: {p95_response_time:.3f}秒")
        logger.info(f"99%响应时间: {p99_response_time:.3f}秒")
        logger.info("-" * 80)
        
        # 生成图表
        self.generate_charts()
    
    def generate_charts(self):
        """生成测试结果图表"""
        try:
            # 创建图表目录
            charts_dir = "load_test_charts"
            os.makedirs(charts_dir, exist_ok=True)
            
            # 提取响应时间和时间戳
            response_times = [r["response_time"] for r in self.results if "response_time" in r]
            timestamps = [time.mktime(datetime.datetime.fromisoformat(r["timestamp"]).timetuple()) - self.start_time for r in self.results if "timestamp" in r]
            success = [1 if r.get("success", False) else 0 for r in self.results]
            
            # 按场景分组的响应时间
            scenario_times = {}
            for scenario in self.test_scenarios.keys():
                scenario_times[scenario] = [r["response_time"] for r in self.results if r.get("scenario") == scenario and "response_time" in r]
            
            # 图1: 响应时间分布直方图
            plt.figure(figsize=(10, 6))
            plt.hist(response_times, bins=50, alpha=0.75)
            plt.title('响应时间分布')
            plt.xlabel('响应时间 (秒)')
            plt.ylabel('请求数')
            plt.grid(True, alpha=0.3)
            plt.savefig(os.path.join(charts_dir, 'response_time_distribution.png'))
            plt.close()
            
            # 图2: 响应时间随时间变化的散点图
            plt.figure(figsize=(12, 6))
            plt.scatter(timestamps, response_times, c=success, cmap='viridis', alpha=0.5)
            plt.colorbar(label='成功 (1) / 失败 (0)')
            plt.title('响应时间随时间变化')
            plt.xlabel('测试时间 (秒)')
            plt.ylabel('响应时间 (秒)')
            plt.grid(True, alpha=0.3)
            plt.savefig(os.path.join(charts_dir, 'response_time_vs_time.png'))
            plt.close()
            
            # 图3: 不同场景的响应时间箱线图
            plt.figure(figsize=(12, 8))
            data = [times for scenario, times in scenario_times.items() if times]
            labels = [scenario for scenario, times in scenario_times.items() if times]
            plt.boxplot(data, labels=labels, showmeans=True)
            plt.title('各场景响应时间对比')
            plt.xlabel('测试场景')
            plt.ylabel('响应时间 (秒)')
            plt.xticks(rotation=45, ha='right')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(charts_dir, 'scenario_comparison.png'))
            plt.close()
            
            # 图4: 成功率饼图
            success_count = sum(success)
            failure_count = len(success) - success_count
            plt.figure(figsize=(8, 8))
            plt.pie([success_count, failure_count], 
                   labels=['成功', '失败'], 
                   autopct='%1.1f%%',
                   colors=['#4CAF50', '#F44336'],
                   startangle=90)
            plt.title('请求成功率')
            plt.savefig(os.path.join(charts_dir, 'success_rate.png'))
            plt.close()
            
            logger.info(f"已生成测试图表，保存在 {charts_dir} 目录")
            
        except Exception as e:
            logger.error(f"生成图表失败: {str(e)}")

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="API负载测试工具")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="API基础URL")
    parser.add_argument("--concurrency", type=int, default=10, help="并发用户数")
    parser.add_argument("--requests", type=int, default=1000, help="总请求数")
    parser.add_argument("--ramp-up", type=int, default=5, help="爬坡时间(秒)")
    parser.add_argument("--timeout", type=float, default=30.0, help="请求超时时间(秒)")
    parser.add_argument("--report-file", type=str, default="api_load_test_report.json", help="测试报告文件路径")
    args = parser.parse_args()
    
    tester = APILoadTester(
        base_url=args.base_url,
        concurrency=args.concurrency,
        total_requests=args.requests,
        ramp_up_time=args.ramp_up,
        timeout=args.timeout,
        report_file=args.report_file
    )
    
    try:
        await tester.run_load_test()
    except KeyboardInterrupt:
        logger.info("负载测试被用户中断")
    except Exception as e:
        logger.error(f"负载测试过程中发生错误: {str(e)}")
    
    logger.info("API负载测试完成")

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 