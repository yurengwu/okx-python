#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试WebSocket监控系统的多token通知功能
"""

import asyncio
from datetime import datetime
from monitoring.websocket_monitor import WebSocketMonitor, PriceAlert
from loguru import logger

def test_multi_token_notification():
    """测试多token通知发送"""
    print("🚀 测试WebSocket监控系统多token通知功能")
    print("=" * 50)
    
    # 初始化监控系统
    monitor = WebSocketMonitor()
    
    if not monitor.notifier:
        print("❌ 通知器未初始化，请检查Server酱配置")
        return
    
    print(f"✅ 通知器初始化成功，配置了 {len(monitor.notifier.sendkeys)} 个token")
    
    # 创建测试警报
    test_alert = PriceAlert(
        symbol="BTC/USDT:USDT",
        alert_type="fund_inflow",
        current_price=51000.0,
        change_percent=2.5,
        volume=1500000,
        timestamp=datetime.now(),
        message="BTC 合约资金持续流入，24H涨跌幅2.5%，现报$51000.00，可能出现上涨行情，但需注意风险",
        fund_flow=2888500000,  # 2888.5M USDT
        ai_score=85
    )
    
    print("\n📤 发送测试通知...")
    
    # 异步发送通知
    async def send_test_notification():
        await monitor._send_alert(test_alert)
    
    # 运行异步函数
    asyncio.run(send_test_notification())
    
    print("\n✅ 测试完成！请检查微信是否收到通知")
    print("\n💡 提示：")
    print("   - 如果收到多条相同通知，说明多token群发功能正常")
    print("   - 每个配置的token都会收到一条通知")
    print("   - 检查日志可以看到每个token的发送状态")

if __name__ == "__main__":
    test_multi_token_notification()