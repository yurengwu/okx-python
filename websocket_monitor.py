import asyncio
import json
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from loguru import logger
from dataclasses import dataclass
import statistics
from collections import deque
import threading
import time

from config import Config
from serverchan_notifier import ServerChanNotifier
from database import TradingDatabase
from okx_client import OKXClient

@dataclass
class PriceAlert:
    """价格警报数据类"""
    symbol: str
    alert_type: str  # 'volatility', 'volume_spike', 'large_order'
    current_price: float
    change_percent: float
    volume: float
    timestamp: datetime
    message: str

class VolatilityDetector:
    """波动率检测器"""
    
    def __init__(self, window_size: int = 20, volatility_threshold: float = 3.0, volume_spike_multiplier: float = 3.0):
        self.window_size = window_size
        self.volatility_threshold = volatility_threshold
        self.volume_spike_multiplier = volume_spike_multiplier
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        
    def add_price_data(self, symbol: str, price: float, volume: float) -> Optional[PriceAlert]:
        """添加价格数据并检测异常波动"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.window_size)
            self.volume_history[symbol] = deque(maxlen=self.window_size)
            
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)
        
        # 需要足够的历史数据才能计算波动率
        if len(self.price_history[symbol]) < self.window_size:
            return None
            
        return self._detect_anomaly(symbol, price, volume)
        
    def _detect_anomaly(self, symbol: str, current_price: float, current_volume: float) -> Optional[PriceAlert]:
        """检测价格异常"""
        prices = list(self.price_history[symbol])
        volumes = list(self.volume_history[symbol])
        
        # 计算价格变化率
        if len(prices) >= 2:
            price_change = (current_price - prices[-2]) / prices[-2] * 100
            
            # 计算历史波动率
            price_changes = [(prices[i] - prices[i-1]) / prices[i-1] * 100 
                           for i in range(1, len(prices))]
            
            if len(price_changes) > 1:
                mean_change = statistics.mean(price_changes)
                std_change = statistics.stdev(price_changes)
                
                # Z-score检测异常波动
                if std_change > 0:
                    z_score = abs((price_change - mean_change) / std_change)
                    
                    # 添加最小变化幅度过滤：价格变化必须大于0.1%才考虑发送警报
                    min_change_threshold = 0.1  # 最小变化幅度0.1%
                    
                    if z_score > self.volatility_threshold and abs(price_change) > min_change_threshold:
                        return PriceAlert(
                            symbol=symbol,
                            alert_type='volatility',
                            current_price=current_price,
                            change_percent=price_change,
                            volume=current_volume,
                            timestamp=datetime.now(),
                            message=f"{symbol} 检测到异常波动: {price_change:.2f}% (Z-score: {z_score:.2f})"
                        )
        
        # 检测成交量异常
        if len(volumes) >= 10:
            avg_volume = statistics.mean(volumes[:-1])  # 排除当前成交量
            if avg_volume > 0 and current_volume > avg_volume * self.volume_spike_multiplier:  # 成交量超过平均值指定倍数
                return PriceAlert(
                    symbol=symbol,
                    alert_type='volume_spike',
                    current_price=current_price,
                    change_percent=0,
                    volume=current_volume,
                    timestamp=datetime.now(),
                    message=f"{symbol} 检测到成交量异常: 当前 {current_volume:.0f}, 平均 {avg_volume:.0f} (增长 {(current_volume/avg_volume-1)*100:.1f}%, 阈值: {self.volume_spike_multiplier}x)"
                )
                
        return None

class WebSocketMonitor:
    """WebSocket实时监控系统"""
    
    def __init__(self):
        self.config = Config()
        self.db = TradingDatabase()
        self.okx_client = OKXClient()
        
        # 初始化通知器（如果配置了sendkey）
        if hasattr(Config, 'SERVERCHAN_SENDKEY') and Config.SERVERCHAN_SENDKEY:
            self.notifier = ServerChanNotifier(Config.SERVERCHAN_SENDKEY)
        else:
            self.notifier = None
            
        self.volatility_detector = VolatilityDetector(
            window_size=self.config.VOLATILITY_WINDOW_SIZE,
            volatility_threshold=self.config.VOLATILITY_THRESHOLD,
            volume_spike_multiplier=self.config.VOLUME_SPIKE_MULTIPLIER
        )
        
        # WebSocket配置
        self.ws_url = self.config.WEBSOCKET_URL
        
        # 动态获取所有USDT永续合约交易对
        logger.info("正在获取所有USDT永续合约交易对...")
        self.symbols = self._get_usdt_swap_symbols()
        
        if not self.symbols:
            # 如果获取失败，使用备用的主要交易对
            logger.warning("获取交易对失败，使用备用交易对列表")
            self.symbols = [
                "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP",
                "DOGE-USDT-SWAP", "XRP-USDT-SWAP", "ADA-USDT-SWAP",
                "LINK-USDT-SWAP", "DOT-USDT-SWAP", "UNI-USDT-SWAP", "BNB-USDT-SWAP"
            ]
        
        # 运行状态
        self.is_running = False
        self.websocket = None
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=self.config.ALERT_COOLDOWN_MINUTES)
        
    def _get_usdt_swap_symbols(self) -> List[str]:
        """获取所有USDT永续合约交易对"""
        try:
            instruments = self.okx_client.get_instruments(inst_type='SWAP')
            
            if not instruments:
                logger.error("获取交易对数据为空")
                return []
                
            # 筛选USDT永续合约
            usdt_swaps = []
            for inst in instruments:
                inst_id = inst.get('instId', '')
                if inst_id.endswith('-USDT-SWAP'):
                    usdt_swaps.append(inst_id)
                    
            logger.info(f"成功获取 {len(usdt_swaps)} 个USDT永续合约交易对")
            
            # 按交易对名称排序
            usdt_swaps.sort()
            
            # 打印前20个交易对作为示例
            if usdt_swaps:
                logger.info(f"前20个交易对: {usdt_swaps[:20]}")
                
            return usdt_swaps
            
        except Exception as e:
            logger.error(f"获取USDT永续合约交易对失败: {e}")
            return []
        
    async def connect_websocket(self):
        """连接WebSocket"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info(f"WebSocket连接成功: {self.ws_url}")
            
            # 订阅ticker数据
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {"channel": "tickers", "instId": symbol} 
                    for symbol in self.symbols
                ]
            }
            
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"已订阅 {len(self.symbols)} 个交易对的实时数据")
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            return False
            
    async def handle_message(self, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            
            # 处理ticker数据
            if 'data' in data and data.get('arg', {}).get('channel') == 'tickers':
                for ticker in data['data']:
                    await self._process_ticker_data(ticker)
                    
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}")
            
    async def _process_ticker_data(self, ticker: dict):
        """处理ticker数据"""
        try:
            symbol = ticker['instId']
            price = float(ticker['last'])
            volume = float(ticker['vol24h'])
            
            # 检测异常波动
            alert = self.volatility_detector.add_price_data(symbol, price, volume)
            
            if alert and self._should_send_alert(symbol):
                # 检查警报类型是否启用
                if ((alert.alert_type == 'volatility' and self.config.ENABLE_VOLATILITY_ALERTS) or
                    (alert.alert_type == 'volume_spike' and self.config.ENABLE_VOLUME_ALERTS)):
                    await self._send_alert(alert)
                    self.last_alert_time[symbol] = datetime.now()
                
        except Exception as e:
            logger.error(f"处理ticker数据失败: {e}")
            
    def _should_send_alert(self, symbol: str) -> bool:
        """检查是否应该发送警报（冷却时间）"""
        if symbol not in self.last_alert_time:
            return True
            
        return datetime.now() - self.last_alert_time[symbol] > self.alert_cooldown
        
    async def _send_alert(self, alert: PriceAlert):
        """发送警报通知"""
        try:
            # 构建通知消息
            title = f"🚨 {alert.symbol} 市场异常"
            
            if alert.alert_type == 'volatility':
                content = f"""**价格异常波动检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
📈 **变化幅度**: {alert.change_percent:+.2f}%
📊 **成交量**: {alert.volume:.0f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ **警报原因**: 检测到异常价格波动

{alert.message}"""
            
            elif alert.alert_type == 'volume_spike':
                content = f"""**成交量异常检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
📊 **异常成交量**: {alert.volume:.0f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ **警报原因**: 检测到异常成交量激增

{alert.message}"""
            
            else:
                content = f"""**市场异常检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}"""
            
            # 发送Server酱通知（如果配置了）
            if self.notifier:
                success = self.notifier.send_notification(title, content)
                
                if success:
                    logger.info(f"实时警报发送成功: {alert.symbol} - {alert.alert_type}")
                else:
                    logger.error(f"实时警报发送失败: {alert.symbol} - {alert.alert_type}")
            else:
                logger.info(f"实时警报（仅控制台）: {alert.symbol} - {alert.alert_type}")
                print(f"\n🚨 {title}")
                print(content)
                
            # 保存警报到数据库
            self._save_alert_to_db(alert)
            
        except Exception as e:
            logger.error(f"发送警报失败: {e}")
            
    def _save_alert_to_db(self, alert: PriceAlert):
        """保存警报到数据库"""
        try:
            # 这里可以扩展保存警报历史的功能
            logger.info(f"警报记录: {alert.symbol} - {alert.alert_type} - {alert.message}")
        except Exception as e:
            logger.error(f"保存警报到数据库失败: {e}")
            
    async def start_monitoring(self):
        """开始监控"""
        self.is_running = True
        logger.info("启动WebSocket实时监控系统")
        
        while self.is_running:
            try:
                # 连接WebSocket
                if await self.connect_websocket():
                    # 监听消息
                    async for message in self.websocket:
                        if not self.is_running:
                            break
                        await self.handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket连接断开，尝试重连...")
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"WebSocket监控异常: {e}")
                await asyncio.sleep(10)
                
        # 安全关闭WebSocket连接
        await self.close_websocket()
        logger.info("WebSocket监控系统已停止")
        
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        
    async def close_websocket(self):
        """安全关闭WebSocket连接"""
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.close()
                logger.info("WebSocket连接已安全关闭")
            except Exception as e:
                logger.warning(f"关闭WebSocket连接时出现异常: {e}")
            
    def run_in_thread(self):
        """在线程中运行监控"""
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_monitoring())
            
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

if __name__ == "__main__":
    # 测试WebSocket监控
    monitor = WebSocketMonitor()
    
    async def main():
        try:
            await monitor.start_monitoring()
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭监控系统...")
            monitor.stop_monitoring()
            await monitor.close_websocket()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已安全退出")