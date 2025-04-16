#!/usr/bin/env python3
"""
测试自动转账API的脚本
使用方法：
    python test_auto_transfer_api.py [admin_key]
"""

import sys
import requests
import json
from pprint import pprint

# 基础URL，根据实际部署环境修改
BASE_URL = "http://localhost:8080/api/v1"

def test_get_auto_transfer_settings(admin_key):
    """测试获取自动转账设置"""
    url = f"{BASE_URL}/settlements/auto-transfer-settings?admin_key={admin_key}"
    print(f"\n[测试] 获取自动转账设置: GET {url}")
    
    try:
        response = requests.get(url)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            pprint(data)
            return data
        else:
            print(f"错误: {response.text}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def test_update_auto_transfer_settings(admin_key, enabled=True, receiver_address="0x1234567890abcdef1234567890abcdef12345678", threshold=5.0):
    """测试更新自动转账设置"""
    url = f"{BASE_URL}/settlements/auto-transfer-settings?admin_key={admin_key}"
    payload = {
        "enabled": enabled,
        "receiver_address": receiver_address,
        "threshold": threshold
    }
    
    print(f"\n[测试] 更新自动转账设置: PUT {url}")
    print(f"请求数据:")
    pprint(payload)
    
    try:
        response = requests.put(url, json=payload)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            pprint(data)
            return data
        else:
            print(f"错误: {response.text}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def test_fee_balances(admin_key):
    """测试获取费用余额"""
    url = f"{BASE_URL}/settlements/balances?admin_key={admin_key}"
    print(f"\n[测试] 获取费用余额: GET {url}")
    
    try:
        response = requests.get(url)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            pprint(data)
            return data
        else:
            print(f"错误: {response.text}")
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def test_complete_flow(admin_key):
    """测试完整流程"""
    print("\n======== 测试自动转账API ========")
    
    # 1. 获取当前设置
    current_settings = test_get_auto_transfer_settings(admin_key)
    if not current_settings:
        print("获取当前设置失败，退出测试")
        return False
        
    # 2. 更新设置（启用自动转账）
    updated_settings = test_update_auto_transfer_settings(
        admin_key,
        enabled=True,
        receiver_address="0x1234567890abcdef1234567890abcdef12345678",
        threshold=8.5
    )
    if not updated_settings:
        print("更新设置失败，退出测试")
        return False
        
    # 3. 再次获取设置确认更新成功
    confirmed_settings = test_get_auto_transfer_settings(admin_key)
    if not confirmed_settings:
        print("确认设置更新失败，退出测试")
        return False
        
    # 4. 获取费用余额（查看自动转账模式下的余额展示）
    balances = test_fee_balances(admin_key)
    if not balances:
        print("获取费用余额失败，退出测试")
        return False
        
    # 5. 恢复原设置（禁用自动转账）
    restore_settings = test_update_auto_transfer_settings(
        admin_key,
        enabled=False,
        receiver_address="",
        threshold=10.0
    )
    if not restore_settings:
        print("恢复设置失败，退出测试")
        return False
        
    print("\n✅ 测试完成！所有API调用成功。")
    return True

if __name__ == "__main__":
    # 从命令行获取admin_key，或使用默认值
    admin_key = sys.argv[1] if len(sys.argv) > 1 else "admin-test-key"
    
    # 运行测试
    test_complete_flow(admin_key) 