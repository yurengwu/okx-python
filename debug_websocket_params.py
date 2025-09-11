#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试WebSocket监控系统参数
查看实际接口返回的参数，进行颗粒化核对
"""

import asyncio
import json
import websockets
from datetime import datetime
from loguru import logger
from pprint import pprint
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import Config
from monitoring.websocket_monitor import WebSocketMonitor, PriceAlert
from trading.okx_client import OKXClient

class WebSocketDebugger:
    """WebSocket参数调试器"""
    
    def __init__(self):
        self.config = Config()
        self.okx_client = OKXClient()
        self.ws_url = self.config.WEBSOCKET_URL
        self.monitor = WebSocketMonitor()
        
        # 获取交易对列表
        self.symbols = self._get_debug_symbols()
        logger.info(f"调试交易对: {self.symbols}")
        
    def _get_debug_symbols(self):
        """获取用于调试的交易对"""
        try:
            # 获取热门交易对进行调试
            instruments = self.okx_client.get_instruments('SWAP')
            if instruments:
                usdt_swaps = [inst['instId'] for inst in instruments 
                            if inst['instId'].endswith('-USDT-SWAP')][:5]  # 只取前5个
                return usdt_swaps
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            
        # 备用交易对
        return ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'BNB-USDT-SWAP']
    
    async def debug_websocket_data(self):
        """调试WebSocket数据"""
        logger.info("开始调试WebSocket数据...")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # 订阅ticker数据
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [
                        {
                            "channel": "tickers",
                            "instId": symbol
                        } for symbol in self.symbols
                    ]
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                logger.info(f"已订阅 {len(self.symbols)} 个交易对的ticker数据")
                
                # 接收并调试数据
                message_count = 0
                while message_count < 20:  # 只处理前20条消息
                    try:
                        message = await websocket.recv()
                        message_count += 1
                        
                        print(f"\n{'='*80}")
                        print(f"消息 #{message_count} - 时间: {datetime.now().strftime('%H:%M:%S')}")
                        print(f"{'='*80}")
                        
                        # 解析原始消息
                        data = json.loads(message)
                        print("\n📡 原始WebSocket消息:")
                        pprint(data, width=120)
                        
                        # 处理ticker数据
                        if 'data' in data and data.get('arg', {}).get('channel') == 'tickers':
                            await self._debug_ticker_processing(data['data'])
                        
                    except Exception as e:
                        logger.error(f"处理消息失败: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
    
    async def _debug_ticker_processing(self, tickers):
        """调试ticker数据处理"""
        for ticker in tickers:
            symbol = ticker['instId']
            
            print(f"\n🔍 处理交易对: {symbol}")
            print("-" * 60)
            
            # 1. 原始ticker数据
            print("\n📊 原始Ticker数据:")
            for key, value in ticker.items():
                print(f"  {key:15}: {value}")
            
            # 2. 提取的关键参数
            try:
                price = float(ticker['last'])
                volume = float(ticker['vol24h'])
                
                print(f"\n💰 提取的关键参数:")
                print(f"  价格 (last):     {price}")
                print(f"  24H成交量:       {volume}")
                print(f"  开盘价 (open):   {ticker.get('open', 'N/A')}")
                print(f"  最高价 (high):   {ticker.get('high', 'N/A')}")
                print(f"  最低价 (low):    {ticker.get('low', 'N/A')}")
                print(f"  买一价 (bidPx):  {ticker.get('bidPx', 'N/A')}")
                print(f"  卖一价 (askPx):  {ticker.get('askPx', 'N/A')}")
                print(f"  时间戳 (ts):     {ticker.get('ts', 'N/A')}")
                
                # 3. 存储ticker数据供24H涨跌幅计算使用
                if not hasattr(self.monitor, 'ticker_data'):
                    self.monitor.ticker_data = {}
                self.monitor.ticker_data[symbol] = ticker
                
                # 存储到fund_flow_detector中
                if not hasattr(self.monitor.fund_flow_detector, 'ticker_data'):
                    self.monitor.fund_flow_detector.ticker_data = {}
                self.monitor.fund_flow_detector.ticker_data[symbol] = ticker
                
                # 4. 调用各个检测器并查看返回值
                print(f"\n🔬 检测器处理结果:")
                
                # 波动率检测
                volatility_alert = self.monitor.volatility_detector.add_price_data(symbol, price, volume)
                print(f"\n  📈 波动率检测器:")
                if volatility_alert:
                    print(f"    ✅ 触发警报: {volatility_alert.alert_type}")
                    self._print_alert_details(volatility_alert)
                else:
                    print(f"    ❌ 无警报")
                
                # 资金流向检测
                fund_flow_alert = self.monitor.fund_flow_detector.add_market_data(symbol, price, volume)
                print(f"\n  💰 资金流向检测器:")
                if fund_flow_alert:
                    print(f"    ✅ 触发警报: {fund_flow_alert.alert_type}")
                    self._print_alert_details(fund_flow_alert)
                else:
                    print(f"    ❌ 无警报")
                
                # 移动止盈检测
                stop_profit_alert = self.monitor.stop_profit_tracker.update_price(symbol, price)
                print(f"\n  🛡️ 移动止盈检测器:")
                if stop_profit_alert:
                    print(f"    ✅ 触发警报: {stop_profit_alert.alert_type}")
                    self._print_alert_details(stop_profit_alert)
                else:
                    print(f"    ❌ 无警报")
                
                # 5. 内部状态检查
                print(f"\n📋 检测器内部状态:")
                self._debug_detector_states(symbol)
                
            except Exception as e:
                logger.error(f"处理ticker数据失败: {e}")
    
    def _print_alert_details(self, alert: PriceAlert):
        """打印警报详细信息"""
        print(f"      类型: {alert.alert_type}")
        print(f"      交易对: {alert.symbol}")
        print(f"      当前价格: ${alert.current_price:.4f}")
        print(f"      24H涨跌幅: {alert.change_percent:+.2f}%")
        print(f"      成交量: {alert.volume:.0f}")
        print(f"      时间: {alert.timestamp.strftime('%H:%M:%S')}")
        print(f"      消息: {alert.message}")
        
        if alert.fund_flow is not None:
            print(f"      资金流向: {alert.fund_flow/1000000:.2f}M USDT")
        if alert.ai_score is not None:
            print(f"      AI评分: {alert.ai_score}")
        if alert.max_gain is not None:
            print(f"      最大涨幅: {alert.max_gain:.2f}%")
        if alert.current_decline is not None:
            print(f"      当前跌幅: {alert.current_decline:.2f}%")
    
    def _debug_detector_states(self, symbol: str):
        """调试检测器内部状态"""
        # 检测器配置参数
        print(f"\n    🔧 检测器配置参数:")
        print(f"      波动率检测器 window_size: {self.monitor.volatility_detector.window_size}")
        print(f"      波动率检测器 threshold: {self.monitor.volatility_detector.volatility_threshold}")
        print(f"      资金流向检测器 window_size: {self.monitor.fund_flow_detector.window_size}")
        print(f"      资金流向检测器 fund_threshold: {self.monitor.fund_flow_detector.fund_threshold/1000000:.1f}M USDT")
        print(f"      移动止盈检测器 max_gain_threshold: {self.monitor.stop_profit_tracker.max_gain_threshold}%")
        print(f"      移动止盈检测器 stop_loss_percent: {self.monitor.stop_profit_tracker.stop_loss_percent}%")
        
        # 波动率检测器状态
        if symbol in self.monitor.volatility_detector.price_history:
            price_hist = list(self.monitor.volatility_detector.price_history[symbol])
            volume_hist = list(self.monitor.volatility_detector.volume_history[symbol])
            print(f"\n    📈 波动率检测器状态:")
            print(f"      价格历史长度: {len(price_hist)}/{self.monitor.volatility_detector.window_size}")
            print(f"      最新价格: {price_hist[-1] if price_hist else 'N/A'}")
            print(f"      成交量历史长度: {len(volume_hist)}/{self.monitor.volatility_detector.window_size}")
            print(f"      最新成交量: {volume_hist[-1] if volume_hist else 'N/A'}")
            if len(price_hist) >= 2:
                recent_change = (price_hist[-1] - price_hist[-2]) / price_hist[-2] * 100
                print(f"      最近价格变化: {recent_change:+.2f}%")
        
        # 资金流向检测器状态
        if symbol in self.monitor.fund_flow_detector.price_history:
            price_hist = list(self.monitor.fund_flow_detector.price_history[symbol])
            fund_hist = list(self.monitor.fund_flow_detector.fund_flow_history[symbol])
            print(f"\n    💰 资金流向检测器状态:")
            print(f"      价格历史长度: {len(price_hist)}/{self.monitor.fund_flow_detector.window_size}")
            print(f"      资金流向历史长度: {len(fund_hist)}/{self.monitor.fund_flow_detector.window_size}")
            if fund_hist:
                print(f"      最新资金流向: {fund_hist[-1]/1000000:.2f}M USDT")
                if len(fund_hist) >= 10:
                    avg_fund_flow = sum(fund_hist[:-1]) / (len(fund_hist) - 1)
                    print(f"      平均资金流向: {avg_fund_flow/1000000:.2f}M USDT")
                    print(f"      流入检测阈值: {self.monitor.fund_flow_detector.fund_threshold/1000000:.1f}M USDT")
                    print(f"      是否超过阈值: {'是' if fund_hist[-1] > self.monitor.fund_flow_detector.fund_threshold else '否'}")
                    print(f"      是否超过3倍平均值: {'是' if fund_hist[-1] > avg_fund_flow * 3 else '否'}")
            
            # 24H涨跌幅计算详情
            change_24h = self.monitor.fund_flow_detector._get_24h_change(symbol)
            print(f"\n    📊 24H涨跌幅计算详情:")
            print(f"      计算结果: {change_24h:+.2f}%")
            
            # 检查ticker数据是否可用
            if hasattr(self.monitor.fund_flow_detector, 'ticker_data') and symbol in self.monitor.fund_flow_detector.ticker_data:
                ticker_data = self.monitor.fund_flow_detector.ticker_data[symbol]
                print(f"      Ticker数据可用: 是")
                print(f"      open24h: {ticker_data.get('open24h', 'N/A')}")
                print(f"      last: {ticker_data.get('last', 'N/A')}")
                if ticker_data.get('open24h') and ticker_data.get('last'):
                    try:
                        current = float(ticker_data['last'])
                        open24h = float(ticker_data['open24h'])
                        ticker_change = (current - open24h) / open24h * 100
                        print(f"      基于ticker数据计算: {ticker_change:+.2f}%")
                    except (ValueError, ZeroDivisionError):
                        print(f"      ticker数据计算失败")
            else:
                print(f"      Ticker数据可用: 否")
            if len(price_hist) >= 2:
                current_price = price_hist[-1]
                if len(price_hist) >= 24:
                    price_24h_ago = price_hist[-24]
                    print(f"      使用24小时前价格: ${price_24h_ago:.4f}")
                else:
                    price_24h_ago = price_hist[0]
                    print(f"      数据不足24小时，使用最早价格: ${price_24h_ago:.4f}")
                print(f"      当前价格: ${current_price:.4f}")
                if price_24h_ago > 0:
                    manual_calc = (current_price - price_24h_ago) / price_24h_ago * 100
                    print(f"      手动计算结果: {manual_calc:+.2f}%")
        
        # 移动止盈追踪器状态
        print(f"\n    🛡️ 移动止盈追踪器状态:")
        if symbol in self.monitor.stop_profit_tracker.tracking_positions:
            position = self.monitor.stop_profit_tracker.tracking_positions[symbol]
            print(f"      正在追踪: 是")
            print(f"      入场价格: ${position['entry_price']:.4f}")
            print(f"      最高价格: ${position['max_price']:.4f}")
            print(f"      入场原因: {position.get('reason', 'N/A')}")
        else:
            print(f"      正在追踪: 否")

async def main():
    """主函数"""
    debugger = WebSocketDebugger()
    
    print("\n" + "="*100)
    print("🔍 WebSocket监控系统参数调试工具")
    print("="*100)
    
    # 打印配置信息
    print(f"\n📋 当前配置:")
    print(f"  WebSocket URL: {debugger.config.WEBSOCKET_URL}")
    print(f"  波动率窗口大小: {debugger.config.VOLATILITY_WINDOW_SIZE}")
    print(f"  波动率阈值: {debugger.config.VOLATILITY_THRESHOLD}")
    print(f"  资金流向窗口大小: {debugger.config.FUND_FLOW_WINDOW_SIZE}")
    print(f"  资金流向阈值: {debugger.config.FUND_FLOW_THRESHOLD/1000000:.1f}M USDT")
    print(f"  成交量激增倍数: {debugger.config.VOLUME_SPIKE_MULTIPLIER}")
    
    try:
        await debugger.debug_websocket_data()
    except KeyboardInterrupt:
        print("\n\n🛑 调试已停止")
    except Exception as e:
        logger.error(f"调试过程中发生错误: {e}")
    
    print("\n" + "="*100)
    print("🏁 调试完成")
    print("="*100)

if __name__ == "__main__":
    asyncio.run(main())