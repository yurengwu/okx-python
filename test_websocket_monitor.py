#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试WebSocket监控系统的新功能
包括资金流向检测、主力资金监控、移动止盈等功能
"""

import asyncio
import json
from datetime import datetime
from monitoring.websocket_monitor import WebSocketMonitor, FundFlowDetector, MovingStopProfitTracker, PriceAlert
from loguru import logger

def test_fund_flow_detector():
    """测试资金流向检测器"""
    print("\n=== 测试资金流向检测器 ===")
    
    # 使用更低的阈值进行测试
    detector = FundFlowDetector(window_size=10, fund_threshold=50000, escape_threshold=0.6)
    
    # 模拟正常交易数据
    symbol = "BTC/USDT:USDT"
    base_price = 50000
    
    print("1. 添加正常交易数据...")
    # 先添加足够的历史数据
    for i in range(12):
        price = base_price + (i * 5)  # 价格缓慢上涨
        volume = 500000 + (i * 10000)  # 成交量逐渐增加
        alert = detector.add_market_data(symbol, price, volume)
        if alert:
            print(f"   警报: {alert.alert_type} - {alert.message}")
    
    print("\n2. 模拟大量资金流入...")
    # 模拟资金大量流入 - 价格大幅上涨 + 成交量激增
    price = base_price + 1000  # 价格大幅上涨2%
    volume = 3000000  # 成交量激增
    alert = detector.add_market_data(symbol, price, volume)
    if alert:
        print(f"   ✅ 资金流入警报: {alert.message}")
        print(f"   资金流向: {alert.fund_flow/1000000:.1f}M USDT")
    else:
        print("   ❌ 未检测到资金流入警报")
        # 显示调试信息
        fund_flow = detector._calculate_fund_flow(symbol, price, volume)
        print(f"   调试: 计算的资金流向 = {fund_flow/1000000:.1f}M USDT, 阈值 = {detector.fund_threshold/1000000:.1f}M USDT")
    
    print("\n3. 模拟主力资金出逃...")
    # 模拟连续资金流出
    for i in range(8):
        price = base_price + 1000 - (i * 100)  # 价格持续下跌
        volume = 1500000  # 保持高成交量
        alert = detector.add_market_data(symbol, price, volume)
        if alert and alert.alert_type == 'main_fund_escape':
            print(f"   ✅ 主力资金出逃警报: {alert.message}")
            break
        elif alert:
            print(f"   其他警报: {alert.alert_type} - {alert.message}")
    else:
        print("   ❌ 未检测到主力资金出逃警报")
        # 显示调试信息
        outflow_count = sum(1 for flow in list(detector.fund_flow_history[symbol])[-5:] if flow < 0)
        print(f"   调试: 最近5次中有{outflow_count}次资金流出, 出逃阈值 = {detector.escape_threshold}")

def test_moving_stop_profit_tracker():
    """测试移动止盈追踪器"""
    print("\n=== 测试移动止盈追踪器 ===")
    
    tracker = MovingStopProfitTracker(max_gain_threshold=10.0, stop_loss_percent=15.0)
    
    symbol = "ETH/USDT:USDT"
    entry_price = 3000
    
    print(f"1. 开始追踪 {symbol}，入场价格: ${entry_price}")
    tracker.start_tracking(symbol, entry_price, "资金流入异常")
    
    print("\n2. 模拟价格上涨...")
    # 模拟价格上涨超过10%
    prices = [3100, 3200, 3300, 3400, 3500]  # 涨幅达到16.67%
    for price in prices:
        gain = (price - entry_price) / entry_price * 100
        print(f"   价格: ${price}, 涨幅: {gain:.1f}%")
        alert = tracker.update_price(symbol, price)
        if alert:
            print(f"   警报: {alert.message}")
    
    print("\n3. 模拟价格回撤触发止盈...")
    # 模拟价格回撤超过15%
    max_price = 3500
    decline_price = 2975  # 从最高点回撤15%
    decline = (max_price - decline_price) / max_price * 100
    print(f"   价格回撤到: ${decline_price}, 回撤幅度: {decline:.1f}%")
    
    alert = tracker.update_price(symbol, decline_price)
    if alert and alert.alert_type == 'moving_stop_profit':
        print(f"   ✅ 移动止盈触发: {alert.message}")
        print(f"   最大涨幅: {alert.max_gain:.1f}%, 当前回撤: {alert.current_decline:.1f}%")
    else:
        print("   ❌ 未触发移动止盈")

def test_price_alert_formats():
    """测试新的警报消息格式"""
    print("\n=== 测试警报消息格式 ===")
    
    # 测试资金流入警报
    fund_inflow_alert = PriceAlert(
        symbol="OG/USDT:USDT",
        alert_type="fund_inflow",
        current_price=24.33,
        change_percent=23.9,
        volume=5000000,
        timestamp=datetime.now(),
        message="OG 合约资金持续流入，24H涨跌幅23.9%，现报$24.33，可能出现上涨行情，但需注意风险",
        fund_flow=2500000,
        ai_score=80
    )
    
    print("1. 资金流入警报格式:")
    print(f"   标题: 💰 {fund_inflow_alert.symbol} 资金流入异常")
    print(f"   消息: {fund_inflow_alert.message}")
    
    # 测试主力资金出逃警报
    escape_alert = PriceAlert(
        symbol="OG/USDT:USDT",
        alert_type="main_fund_escape",
        current_price=22.44,
        change_percent=0.99,
        volume=3000000,
        timestamp=datetime.now(),
        message="OG 疑似主力资金已出逃，资金异动监控结束，现报$22.44，24H涨跌幅0.99%，注意市场风险。",
        fund_flow=-1800000
    )
    
    print("\n2. 主力资金出逃警报格式:")
    print(f"   标题: ⚠️ {escape_alert.symbol} 主力资金出逃")
    print(f"   消息: {escape_alert.message}")
    
    # 测试移动止盈警报
    stop_profit_alert = PriceAlert(
        symbol="OG/USDT:USDT",
        alert_type="moving_stop_profit",
        current_price=22.44,
        change_percent=-8.5,
        volume=0,
        timestamp=datetime.now(),
        message="OG 追踪达到最大涨幅后，跌幅超过16.67%，移动止盈以保护利润",
        max_gain=25.2,
        current_decline=16.8,
        ai_score=80
    )
    
    print("\n3. 移动止盈警报格式:")
    print(f"   标题: 📈 {stop_profit_alert.symbol} 移动止盈触发")
    print(f"   消息: {stop_profit_alert.message}")
    print(f"   最大涨幅: {stop_profit_alert.max_gain}%, 当前回撤: {stop_profit_alert.current_decline}%")

async def test_websocket_monitor_integration():
    """测试WebSocket监控系统集成"""
    print("\n=== 测试WebSocket监控系统集成 ===")
    
    try:
        monitor = WebSocketMonitor()
        print("✅ WebSocket监控系统初始化成功")
        print(f"   - 波动率检测器: 已启用")
        print(f"   - 资金流向检测器: 已启用")
        print(f"   - 移动止盈追踪器: 已启用")
        print(f"   - 监控交易对数量: {len(monitor.symbols)}")
        
        # 测试配置参数
        print(f"\n配置参数:")
        print(f"   - 资金异动阈值: {monitor.config.FUND_FLOW_THRESHOLD/1000000:.1f}M USDT")
        print(f"   - 移动止盈涨幅阈值: {monitor.config.MAX_GAIN_THRESHOLD}%")
        print(f"   - 移动止盈回撤比例: {monitor.config.STOP_LOSS_PERCENT}%")
        print(f"   - 警报冷却时间: {monitor.config.ALERT_COOLDOWN_MINUTES}分钟")
        
    except Exception as e:
        print(f"❌ WebSocket监控系统初始化失败: {e}")

def main():
    """主测试函数"""
    print("🚀 开始测试WebSocket监控系统新功能")
    print("=" * 50)
    
    # 测试各个组件
    test_fund_flow_detector()
    test_moving_stop_profit_tracker()
    test_price_alert_formats()
    
    # 测试系统集成
    asyncio.run(test_websocket_monitor_integration())
    
    print("\n" + "=" * 50)
    print("✅ 所有测试完成！")
    print("\n📋 新功能说明:")
    print("1. 资金流向检测 - 监控大额资金流入流出")
    print("2. 主力资金监控 - 检测主力资金出逃")
    print("3. 移动止盈追踪 - 自动追踪涨幅并在回撤时止盈")
    print("4. 智能警报系统 - 多种警报类型和格式")
    print("5. 可配置参数 - 通过环境变量灵活配置")

if __name__ == "__main__":
    main()