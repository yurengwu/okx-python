#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试实时WebSocket监控中的24小时涨跌幅计算

这个脚本模拟实际WebSocket监控环境，测试24小时涨跌幅计算的准确性
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.websocket_monitor import FundFlowDetector
from datetime import datetime
import time

def test_realtime_24h_change():
    """测试实时环境下的24小时涨跌幅计算"""
    print("=== 测试实时WebSocket监控24小时涨跌幅计算 ===")
    
    # 创建资金流向检测器（使用实际配置）
    detector = FundFlowDetector(window_size=100, fund_threshold=1000000)
    
    symbol = "ETH-USDT-SWAP"
    base_price = 4362.33
    
    print(f"\n1. 模拟实时数据积累过程...")
    print(f"   基准价格: ${base_price}")
    
    # 模拟数据不足的情况（少于24个数据点）
    print("\n2. 测试数据不足情况（10个数据点）:")
    for i in range(10):
        price = base_price + (i * 0.5)  # 价格缓慢上涨
        volume = 1000000
        detector.add_market_data(symbol, price, volume)
        
        change = detector._get_24h_change(symbol)
        print(f"   数据点 {i+1}: 价格=${price:.2f}, 24H涨跌幅={change:+.2f}%")
    
    # 模拟有足够数据的情况（30个数据点）
    print("\n3. 测试数据充足情况（30个数据点）:")
    for i in range(10, 30):
        price = base_price + (i * 0.3)  # 继续上涨
        volume = 1000000
        detector.add_market_data(symbol, price, volume)
    
    change = detector._get_24h_change(symbol)
    current_price = base_price + (29 * 0.3)
    print(f"   最终价格: ${current_price:.2f}")
    print(f"   24H涨跌幅: {change:+.2f}%")
    print(f"   预期涨跌幅: {((current_price - base_price) / base_price * 100):+.2f}%")
    
    # 测试价格横盘情况
    print("\n4. 测试价格横盘情况:")
    detector2 = FundFlowDetector(window_size=100, fund_threshold=1000000)
    symbol2 = "BTC-USDT-SWAP"
    flat_price = 50000.0
    
    # 添加相同价格的数据
    for i in range(15):
        detector2.add_market_data(symbol2, flat_price, 1000000)
    
    change = detector2._get_24h_change(symbol2)
    print(f"   横盘价格: ${flat_price:.2f}")
    print(f"   24H涨跌幅: {change:+.2f}%")
    
    # 测试价格下跌情况
    print("\n5. 测试价格下跌情况:")
    detector3 = FundFlowDetector(window_size=100, fund_threshold=1000000)
    symbol3 = "SOL-USDT-SWAP"
    start_price = 200.0
    
    for i in range(20):
        price = start_price - (i * 1.0)  # 价格下跌
        volume = 1000000
        detector3.add_market_data(symbol3, price, volume)
    
    change = detector3._get_24h_change(symbol3)
    final_price = start_price - (19 * 1.0)
    print(f"   起始价格: ${start_price:.2f}")
    print(f"   最终价格: ${final_price:.2f}")
    print(f"   24H涨跌幅: {change:+.2f}%")
    print(f"   预期涨跌幅: {((final_price - start_price) / start_price * 100):+.2f}%")
    
    # 测试资金流入警报中的24H涨跌幅
    print("\n6. 测试资金流入警报中的24H涨跌幅:")
    detector4 = FundFlowDetector(window_size=100, fund_threshold=50000)  # 降低阈值便于测试
    symbol4 = "ETH-USDT-SWAP"
    
    # 先添加一些基础数据
    for i in range(15):
        price = 4362.33 + (i * 2.0)  # 价格上涨
        volume = 500000
        detector4.add_market_data(symbol4, price, volume)
    
    # 触发资金流入警报
    trigger_price = 4362.33 + (15 * 2.0)
    trigger_volume = 5000000  # 大成交量
    alert = detector4.add_market_data(symbol4, trigger_price, trigger_volume)
    
    if alert and alert.alert_type == 'fund_inflow':
        print(f"   ✅ 资金流入警报触发")
        print(f"   当前价格: ${alert.current_price:.2f}")
        print(f"   24H涨跌幅: {alert.change_percent:+.2f}%")
        print(f"   警报消息: {alert.message}")
    else:
        print(f"   ❌ 未触发资金流入警报")
        change = detector4._get_24h_change(symbol4)
        print(f"   当前24H涨跌幅: {change:+.2f}%")
    
    print("\n=== 测试完成 ===")
    print("\n修复说明:")
    print("1. 增加了window_size到100，确保有足够的历史数据")
    print("2. 改进了24小时涨跌幅计算逻辑，处理数据不足的情况")
    print("3. 添加了短期趋势估算，避免涨跌幅显示为0")
    print("4. 移除了随机变化生成，使用真实的价格计算")

if __name__ == "__main__":
    test_realtime_24h_change()