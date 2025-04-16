#!/usr/bin/env python3
"""
API健康检查脚本
定期检查API服务的健康状态，生成健康报告
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
from typing import Dict, List, Any, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('api_health_check.log')
    ]
)
logger = logging.getLogger(__name__)

class APIHealthChecker:
    """API健康检查类"""
    
    def __init__(self, 
                 base_url: str,
                 check_interval: int = 60,
                 timeout: float = 10.0,
                 history_size: int = 100,
                 report_file: str = "api_health_report.json"):
        """
        初始化API健康检查器
        
        Args:
            base_url: API基础URL
            check_interval: 检查间隔(秒)
            timeout: 请求超时时间(秒)
            history_size: 保留的历史记录数量
            report_file: 健康报告文件路径
        """
        self.base_url = base_url.rstrip('/')
        self.check_interval = check_interval
        self.timeout = timeout
        self.history_size = history_size
        self.report_file = report_file
        
        # 端点列表及其预期响应
        self.endpoints = {
            # 基础端点
            "/api/v1/health": {"method": "GET", "expected_status": 200},
            
            # 预测API端点
            "/api/v1/predictions/symbols": {"method": "GET", "expected_status": 200},
            "/api/v1/predictions/historical-data": {
                "method": "GET", 
                "params": {"symbol": "BTC/USDT", "timeframe": "1h", "limit": 5},
                "expected_status": 200
            },
            "/api/v1/predictions/feature-data": {
                "method": "GET", 
                "params": {"symbol": "BTC/USDT", "timeframe": "1h", "feature_type": "technical", "limit": 5},
                "expected_status": 200
            }
        }
        
        # 健康历史记录
        self.health_history = []
        
        # 加载已有的健康报告
        self.load_health_report()
    
    def load_health_report(self):
        """加载已有的健康报告"""
        if os.path.exists(self.report_file):
            try:
                with open(self.report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                    if "history" in report_data:
                        self.health_history = report_data["history"]
                        logger.info(f"加载了 {len(self.health_history)} 条历史健康记录")
            except Exception as e:
                logger.error(f"加载健康报告失败: {str(e)}")
    
    def save_health_report(self):
        """保存健康报告"""
        # 限制历史记录大小
        if len(self.health_history) > self.history_size:
            self.health_history = self.health_history[-self.history_size:]
        
        # 计算当前健康状态
        current_status = "健康" if self.calculate_overall_health() >= 0.9 else "不健康"
        uptime = self.calculate_uptime()
        
        report = {
            "last_update": datetime.datetime.now().isoformat(),
            "status": current_status,
            "uptime": uptime,
            "endpoints": self.calculate_endpoint_health(),
            "history": self.health_history
        }
        
        try:
            with open(self.report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"健康报告已保存到 {self.report_file}")
        except Exception as e:
            logger.error(f"保存健康报告失败: {str(e)}")
    
    def calculate_overall_health(self) -> float:
        """计算整体健康度(0.0-1.0)"""
        if not self.health_history:
            return 1.0
        
        # 获取最近的检查记录
        recent_checks = self.health_history[-10:] if len(self.health_history) >= 10 else self.health_history
        
        # 计算成功率
        total_checks = sum(len(check["results"]) for check in recent_checks)
        successful_checks = sum(
            sum(1 for result in check["results"] if result["status"] == "成功")
            for check in recent_checks
        )
        
        if total_checks == 0:
            return 1.0
            
        return successful_checks / total_checks
    
    def calculate_uptime(self) -> Dict[str, Any]:
        """计算API运行时间统计"""
        if not self.health_history:
            return {"percentage": 100.0, "since": datetime.datetime.now().isoformat()}
        
        # 计算检查开始时间
        first_check_time = datetime.datetime.fromisoformat(self.health_history[0]["timestamp"])
        
        # 计算总检查次数和成功次数
        total_health_checks = len(self.health_history)
        successful_health_checks = sum(
            1 for check in self.health_history 
            if any(result["status"] == "成功" for result in check["results"])
        )
        
        uptime_percentage = (successful_health_checks / total_health_checks * 100) if total_health_checks > 0 else 100.0
        
        return {
            "percentage": round(uptime_percentage, 2),
            "since": first_check_time.isoformat(),
            "total_checks": total_health_checks,
            "successful_checks": successful_health_checks
        }
    
    def calculate_endpoint_health(self) -> Dict[str, Dict[str, Any]]:
        """计算各端点的健康状态"""
        endpoint_stats = {}
        
        for endpoint in self.endpoints:
            endpoint_checks = 0
            endpoint_successes = 0
            response_times = []
            
            for check in self.health_history:
                for result in check["results"]:
                    if result["endpoint"] == endpoint:
                        endpoint_checks += 1
                        if result["status"] == "成功":
                            endpoint_successes += 1
                            response_times.append(result["response_time"])
            
            success_rate = (endpoint_successes / endpoint_checks * 100) if endpoint_checks > 0 else 100.0
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            endpoint_stats[endpoint] = {
                "success_rate": round(success_rate, 2),
                "average_response_time": round(avg_response_time, 3),
                "checks": endpoint_checks,
                "status": "健康" if success_rate >= 90 else "不健康"
            }
        
        return endpoint_stats
    
    async def check_endpoint(self, session: aiohttp.ClientSession, 
                            endpoint: str, 
                            config: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查单个API端点的健康状态
        
        Args:
            session: aiohttp会话
            endpoint: API端点
            config: 端点配置
            
        Returns:
            检查结果
        """
        method = config.get("method", "GET")
        params = config.get("params", {})
        data = config.get("data", None)
        expected_status = config.get("expected_status", 200)
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method == "GET":
                async with session.get(url, params=params, timeout=self.timeout) as response:
                    elapsed = time.time() - start_time
                    response_status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
            elif method == "POST":
                async with session.post(url, json=data, params=params, timeout=self.timeout) as response:
                    elapsed = time.time() - start_time
                    response_status = response.status
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
            else:
                return {
                    "endpoint": endpoint,
                    "status": "失败",
                    "error": f"不支持的HTTP方法: {method}",
                    "response_time": 0,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            
            # 检查响应状态
            if response_status == expected_status:
                logger.info(f"端点 {endpoint} 健康检查通过 ({response_status}, {elapsed:.3f}秒)")
                return {
                    "endpoint": endpoint,
                    "status": "成功",
                    "response_status": response_status,
                    "response_time": elapsed,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            else:
                logger.warning(f"端点 {endpoint} 返回意外状态码: {response_status}, 预期: {expected_status}")
                return {
                    "endpoint": endpoint,
                    "status": "失败",
                    "response_status": response_status,
                    "error": f"意外的状态码: {response_status}",
                    "response_time": elapsed,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"端点 {endpoint} 请求超时 ({elapsed:.3f}秒)")
            return {
                "endpoint": endpoint,
                "status": "失败",
                "error": "请求超时",
                "response_time": elapsed,
                "timestamp": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"端点 {endpoint} 请求异常: {str(e)}")
            return {
                "endpoint": endpoint,
                "status": "失败",
                "error": str(e),
                "response_time": elapsed,
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    async def check_health(self):
        """检查所有端点的健康状态"""
        async with aiohttp.ClientSession() as session:
            check_results = []
            
            # 并行检查所有端点
            tasks = []
            for endpoint, config in self.endpoints.items():
                task = asyncio.create_task(
                    self.check_endpoint(session, endpoint, config)
                )
                tasks.append(task)
            
            check_results = await asyncio.gather(*tasks)
            
            # 记录健康检查结果
            check_record = {
                "timestamp": datetime.datetime.now().isoformat(),
                "results": check_results
            }
            self.health_history.append(check_record)
            
            # 保存健康报告
            self.save_health_report()
            
            # 计算并输出总体健康状态
            overall_health = self.calculate_overall_health()
            logger.info(f"总体健康度: {overall_health:.2%}")
            
            return check_results
    
    async def run(self):
        """运行健康检查循环"""
        logger.info(f"开始API健康检查，间隔: {self.check_interval}秒")
        
        try:
            while True:
                logger.info(f"执行健康检查 - {datetime.datetime.now().isoformat()}")
                await self.check_health()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("健康检查被取消")
        except Exception as e:
            logger.error(f"健康检查异常: {str(e)}")

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="API健康检查工具")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="API基础URL")
    parser.add_argument("--interval", type=int, default=60, help="检查间隔(秒)")
    parser.add_argument("--timeout", type=float, default=10.0, help="请求超时时间(秒)")
    parser.add_argument("--report-file", type=str, default="api_health_report.json", help="健康报告文件路径")
    args = parser.parse_args()
    
    checker = APIHealthChecker(
        base_url=args.base_url,
        check_interval=args.interval,
        timeout=args.timeout,
        report_file=args.report_file
    )
    
    try:
        await checker.run()
    except KeyboardInterrupt:
        logger.info("健康检查被用户中断")
    
    logger.info("API健康检查完成")

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main()) 