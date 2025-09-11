#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试固定交易对配置功能
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import Config
from trading.okx_client import OKXClient

def test_trading_pairs_config():
    """测试交易对配置功能"""
    print("=== 测试固定交易对配置功能 ===")
    
    # 测试默认配置
    print(f"\n1. 默认固定交易对: {Config.FIXED_TRADING_PAIRS}")
    print(f"   最大交易对数量: {Config.MAX_TRADING_PAIRS}")
    
    # 测试环境变量配置
    print("\n2. 测试环境变量配置:")
    
    # 设置不同的固定交易对
    test_configs = [
        "BTC-USDT-SWAP,ETH-USDT-SWAP",
        "BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP",
        "BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,DOGE-USDT-SWAP,XRP-USDT-SWAP"
    ]
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n   测试配置 {i}: {config}")
        
        # 临时设置环境变量
        original_value = os.environ.get('FIXED_TRADING_PAIRS')
        os.environ['FIXED_TRADING_PAIRS'] = config
        
        # 重新加载配置
        from importlib import reload
        import core.config
        reload(core.config)
        from core.config import Config as ReloadedConfig
        
        print(f"   解析后的固定交易对: {ReloadedConfig.FIXED_TRADING_PAIRS}")
        print(f"   固定交易对数量: {len(ReloadedConfig.FIXED_TRADING_PAIRS)}")
        
        # 恢复原始环境变量
        if original_value is not None:
            os.environ['FIXED_TRADING_PAIRS'] = original_value
        else:
            os.environ.pop('FIXED_TRADING_PAIRS', None)
    
    print("\n3. 测试动态获取逻辑:")
    try:
        # 创建OKX客户端
        okx_client = OKXClient()
        
        # 测试不同的固定交易对配置
        os.environ['FIXED_TRADING_PAIRS'] = 'BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP'
        reload(core.config)
        from core.config import Config as TestConfig
        
        print(f"   固定交易对: {TestConfig.FIXED_TRADING_PAIRS}")
        
        # 获取交易对
        trading_pairs = TestConfig.get_trading_pairs(okx_client)
        print(f"   获取到的交易对数量: {len(trading_pairs)}")
        print(f"   前10个交易对: {trading_pairs[:10]}")
        
        # 检查固定交易对是否包含在内
        fixed_in_result = [pair for pair in TestConfig.FIXED_TRADING_PAIRS if pair in trading_pairs]
        print(f"   固定交易对包含情况: {fixed_in_result}")
        
        # 检查是否有重复
        unique_pairs = list(set(trading_pairs))
        print(f"   是否有重复: {'否' if len(trading_pairs) == len(unique_pairs) else '是'}")
        
    except Exception as e:
        print(f"   动态获取测试失败: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_trading_pairs_config()