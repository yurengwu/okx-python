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

from core.config import Config
from monitoring.serverchan_notifier import ServerChanNotifier
from core.database import TradingDatabase
from trading.okx_client import OKXClient

@dataclass
class PriceAlert:
    """价格警报数据类"""
    symbol: str
    alert_type: str  # 'volatility', 'volume_spike', 'fund_inflow', 'fund_outflow', 'main_fund_escape', 'moving_stop_profit'
    current_price: float
    change_percent: float
    volume: float
    timestamp: datetime
    message: str
    # 新增字段
    fund_flow: Optional[float] = None  # 资金流向（正数为流入，负数为流出）
    ai_score: Optional[int] = None  # AI评分
    max_gain: Optional[float] = None  # 最大涨幅
    current_decline: Optional[float] = None  # 当前跌幅

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

class FundFlowDetector:
    """资金流向检测器"""
    
    def __init__(self, window_size: int = 100, fund_threshold: float = 1000000, escape_threshold: float = 0.8):
        self.window_size = window_size
        self.fund_threshold = fund_threshold  # 资金异动阈值
        self.escape_threshold = escape_threshold  # 主力资金出逃阈值
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.fund_flow_history: Dict[str, deque] = {}
        self.tracking_symbols: Dict[str, dict] = {}  # 追踪中的交易对
        self.ticker_data: Dict[str, dict] = {}  # 存储ticker数据
        
    def add_market_data(self, symbol: str, price: float, volume: float, 
                       buy_volume: float = None, sell_volume: float = None) -> Optional[PriceAlert]:
        """添加市场数据并检测资金异动"""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.window_size)
            self.volume_history[symbol] = deque(maxlen=self.window_size)
            self.fund_flow_history[symbol] = deque(maxlen=self.window_size)
            
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)
        
        # 计算资金流向（简化计算：买入量-卖出量，如果没有具体数据则根据价格变化估算）
        fund_flow = self._calculate_fund_flow(symbol, price, volume, buy_volume, sell_volume)
        self.fund_flow_history[symbol].append(fund_flow)
        
        # 检测各种资金异动
        alerts = []
        
        # 检测资金流入异常
        inflow_alert = self._detect_fund_inflow(symbol, price, volume, fund_flow)
        if inflow_alert:
            alerts.append(inflow_alert)
            
        # 检测主力资金出逃
        escape_alert = self._detect_main_fund_escape(symbol, price, volume, fund_flow)
        if escape_alert:
            alerts.append(escape_alert)
            
        # 检测移动止盈
        stop_profit_alert = self._detect_moving_stop_profit(symbol, price)
        if stop_profit_alert:
            alerts.append(stop_profit_alert)
            
        return alerts[0] if alerts else None
        
    def _calculate_fund_flow(self, symbol: str, price: float, volume: float, 
                           buy_volume: float = None, sell_volume: float = None) -> float:
        """计算资金流向"""
        if buy_volume is not None and sell_volume is not None:
            # 如果有具体的买卖量数据
            return (buy_volume - sell_volume) * price
        else:
            # 简化计算：根据价格变化和成交量估算
            if len(self.price_history[symbol]) >= 2:
                prev_price = list(self.price_history[symbol])[-2]  # 获取前一个价格
                price_change = (price - prev_price) / prev_price
                # 价格上涨且成交量大，认为是资金流入
                return price_change * volume * price
            return 0
            
    def _detect_fund_inflow(self, symbol: str, price: float, volume: float, fund_flow: float) -> Optional[PriceAlert]:
        """检测资金流入异常"""
        if len(self.fund_flow_history[symbol]) < 10:
            return None
            
        # 计算平均资金流向
        avg_fund_flow = statistics.mean(list(self.fund_flow_history[symbol])[:-1])
        
        # 检测资金大量流入
        if fund_flow > self.fund_threshold and fund_flow > avg_fund_flow * 3:
            # 开始追踪这个交易对
            self.tracking_symbols[symbol] = {
                'start_price': price,
                'start_time': datetime.now(),
                'max_price': price,
                'type': 'fund_inflow'
            }
            
            return PriceAlert(
                symbol=symbol,
                alert_type='fund_inflow',
                current_price=price,
                change_percent=self._get_24h_change(symbol),
                volume=volume,
                timestamp=datetime.now(),
                message=f"{symbol} 合约资金持续流入，24H涨跌幅{self._get_24h_change(symbol):.1f}%，现报${price:.2f}，可能出现上涨行情，但需注意风险",
                fund_flow=fund_flow,
                ai_score=80
            )
            
        return None
        
    def _detect_main_fund_escape(self, symbol: str, price: float, volume: float, fund_flow: float) -> Optional[PriceAlert]:
        """检测主力资金出逃"""
        if len(self.fund_flow_history[symbol]) < 10:
            return None
            
        # 检测连续资金流出
        recent_flows = list(self.fund_flow_history[symbol])[-5:]
        if all(flow < 0 for flow in recent_flows) and abs(sum(recent_flows)) > self.fund_threshold:
            return PriceAlert(
                symbol=symbol,
                alert_type='main_fund_escape',
                current_price=price,
                change_percent=self._get_24h_change(symbol),
                volume=volume,
                timestamp=datetime.now(),
                message=f"{symbol} 疑似主力资金已出逃，资金异动监控结束，现报${price:.2f}，24H涨跌幅{self._get_24h_change(symbol):.2f}%，注意市场风险。",
                fund_flow=sum(recent_flows)
            )
            
        return None
    
    def _get_24h_change(self, symbol: str) -> float:
        """获取24小时价格变化百分比"""
        # 优先使用ticker数据中的open24h字段
        if symbol in self.ticker_data:
            ticker = self.ticker_data[symbol]
            if 'open24h' in ticker and ticker['open24h']:
                try:
                    current_price = float(ticker['last'])
                    open_24h = float(ticker['open24h'])
                    if open_24h > 0:
                        return (current_price - open_24h) / open_24h * 100
                except (ValueError, KeyError):
                    pass
         
        # 如果ticker数据不可用，回退到历史价格计算
        if symbol not in self.price_history or len(self.price_history[symbol]) < 2:
            return 0.0
            
        prices = list(self.price_history[symbol])
        current_price = prices[-1]
        
        # 由于WebSocket数据是实时的，我们使用可用的历史数据来估算24小时变化
        # 如果数据点不足，我们使用最早的价格作为基准
        if len(prices) >= 24:
            price_24h_ago = prices[-24]
        else:
            # 数据不足24小时时，使用最早的价格
            price_24h_ago = prices[0]
            
        # 避免除零错误
        if price_24h_ago == 0:
            return 0.0
            
        change_percent = (current_price - price_24h_ago) / price_24h_ago * 100
        
        # 如果计算结果为0或接近0，可能是因为数据不足或价格变化很小
        # 在这种情况下，我们可以使用更短期的价格变化来估算
        if abs(change_percent) < 0.01 and len(prices) >= 5:
            # 使用最近5个数据点的变化趋势来估算
            recent_prices = prices[-5:]
            if len(recent_prices) >= 2:
                short_term_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
                # 将短期变化扩展到24小时（粗略估算）
                return short_term_change * (24 / len(recent_prices))
            
        return change_percent
        
    def _detect_moving_stop_profit(self, symbol: str, price: float) -> Optional[PriceAlert]:
        """检测移动止盈"""
        if symbol not in self.tracking_symbols:
            return None
            
        tracking_info = self.tracking_symbols[symbol]
        start_price = tracking_info['start_price']
        max_price = max(tracking_info['max_price'], price)
        tracking_info['max_price'] = max_price
        
        # 计算最大涨幅和当前跌幅
        max_gain = (max_price - start_price) / start_price * 100
        current_decline = (max_price - price) / max_price * 100
        
        # 如果达到最大涨幅后跌幅超过16.67%，触发移动止盈
        if max_gain > 10 and current_decline > 16.67:
            # 移除追踪
            del self.tracking_symbols[symbol]
            
            return PriceAlert(
                symbol=symbol,
                alert_type='moving_stop_profit',
                current_price=price,
                change_percent=self._get_24h_change(symbol),
                volume=0,
                timestamp=datetime.now(),
                message=f"{symbol} 追踪达到最大涨幅后，跌幅超过16.67%，移动止盈以保护利润AI 追踪后上涨，达到最大涨幅后下跌，跌幅超过16.67%，现报${price:.2f}，注意移动止盈以保护利润",
                max_gain=max_gain,
                current_decline=current_decline,
                ai_score=80
            )
            
        return None
        


class MovingStopProfitTracker:
    """移动止盈追踪器"""
    
    def __init__(self, max_gain_threshold: float = 10.0, stop_loss_percent: float = 16.67):
        self.max_gain_threshold = max_gain_threshold
        self.stop_loss_percent = stop_loss_percent
        self.tracking_positions: Dict[str, dict] = {}
        
    def start_tracking(self, symbol: str, entry_price: float, reason: str = "资金流入"):
        """开始追踪交易对"""
        self.tracking_positions[symbol] = {
            'entry_price': entry_price,
            'max_price': entry_price,
            'start_time': datetime.now(),
            'reason': reason
        }
        logger.info(f"开始追踪 {symbol}，入场价格: ${entry_price:.4f}，原因: {reason}")
        
    def update_price(self, symbol: str, current_price: float) -> Optional[PriceAlert]:
        """更新价格并检查是否触发止盈"""
        if symbol not in self.tracking_positions:
            return None
            
        position = self.tracking_positions[symbol]
        entry_price = position['entry_price']
        
        # 更新最高价格
        position['max_price'] = max(position['max_price'], current_price)
        max_price = position['max_price']
        
        # 计算收益和回撤
        max_gain = (max_price - entry_price) / entry_price * 100
        current_drawdown = (max_price - current_price) / max_price * 100
        
        # 检查是否触发移动止盈
        if max_gain >= self.max_gain_threshold and current_drawdown >= self.stop_loss_percent:
            # 停止追踪
            del self.tracking_positions[symbol]
            
            return PriceAlert(
                symbol=symbol,
                alert_type='moving_stop_profit',
                current_price=current_price,
                change_percent=(current_price - entry_price) / entry_price * 100,
                volume=0,
                timestamp=datetime.now(),
                message=f"{symbol} 追踪结束：达到最大涨幅{max_gain:.1f}%后回撤{current_drawdown:.1f}%，触发移动止盈，现报${current_price:.2f}",
                max_gain=max_gain,
                current_decline=current_drawdown,
                ai_score=80
            )
            
        return None
        
    def stop_tracking(self, symbol: str, reason: str = "手动停止"):
        """停止追踪"""
        if symbol in self.tracking_positions:
            del self.tracking_positions[symbol]
            logger.info(f"停止追踪 {symbol}，原因: {reason}")

class WebSocketMonitor:
    """WebSocket实时监控系统"""
    
    def __init__(self):
        self.config = Config()
        self.db = TradingDatabase()
        self.okx_client = OKXClient()
        self.ticker_data = {}  # 存储ticker数据
        
        # 初始化通知器（支持多token群发）
        tokens = self.config.get_serverchan_tokens()
        if tokens:
            self.notifier = ServerChanNotifier(tokens)
            logger.info(f"初始化Server酱通知器，配置了 {len(tokens)} 个token")
        else:
            self.notifier = None
            logger.warning("未配置Server酱通知token")
            
        self.volatility_detector = VolatilityDetector(
            window_size=self.config.VOLATILITY_WINDOW_SIZE,
            volatility_threshold=self.config.VOLATILITY_THRESHOLD,
            volume_spike_multiplier=self.config.VOLUME_SPIKE_MULTIPLIER
        )
        
        # 初始化资金流向检测器
        self.fund_flow_detector = FundFlowDetector(
            window_size=self.config.FUND_FLOW_WINDOW_SIZE,
            fund_threshold=self.config.FUND_FLOW_THRESHOLD,
            escape_threshold=self.config.MAIN_FUND_ESCAPE_THRESHOLD
        )
        
        # 初始化移动止盈追踪器
        self.stop_profit_tracker = MovingStopProfitTracker(
            max_gain_threshold=self.config.MAX_GAIN_THRESHOLD,
            stop_loss_percent=self.config.STOP_LOSS_PERCENT
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
            
            # 打印原始ticker数据用于调试
            logger.debug(f"{symbol} 原始ticker数据: {json.dumps(ticker, indent=2)}")
            
            # 安全地转换价格和成交量，处理空字符串情况
            last_price = ticker.get('last', '')
            vol_24h = ticker.get('vol24h', '')
            
            if not last_price or last_price == '':
                logger.warning(f"{symbol} 价格数据为空，原始数据: last='{last_price}', 完整ticker: {ticker}")
                return
                
            if not vol_24h or vol_24h == '':
                logger.warning(f"{symbol} 成交量数据为空，原始数据: vol24h='{vol_24h}', 完整ticker: {ticker}")
                return
                
            try:
                price = float(last_price)
                volume = float(vol_24h)
            except (ValueError, TypeError) as e:
                logger.error(f"{symbol} 数据转换失败: last={last_price}, vol24h={vol_24h}, 错误: {e}")
                return
            
            # 存储ticker数据供24H涨跌幅计算使用
            if not hasattr(self, 'ticker_data'):
                self.ticker_data = {}
            self.ticker_data[symbol] = ticker
            
            # 检测异常波动
            volatility_alert = self.volatility_detector.add_price_data(symbol, price, volume)
            
            # 检测资金流向异常
            self.fund_flow_detector.ticker_data[symbol] = ticker
            fund_flow_alert = self.fund_flow_detector.add_market_data(symbol, price, volume)
            
            # 检测移动止盈
            stop_profit_alert = self.stop_profit_tracker.update_price(symbol, price)
            
            # 处理各种警报
            alerts = [alert for alert in [volatility_alert, fund_flow_alert, stop_profit_alert] if alert]
            
            for alert in alerts:
                if self._should_send_alert(symbol):
                    # 检查警报类型是否启用
                    should_send = False
                    if alert.alert_type == 'volatility' and self.config.ENABLE_VOLATILITY_ALERTS:
                        should_send = True
                    elif alert.alert_type == 'volume_spike' and self.config.ENABLE_VOLUME_ALERTS:
                        should_send = True
                    elif alert.alert_type == 'fund_inflow' and self.config.ENABLE_FUND_FLOW_ALERTS:
                        should_send = True
                    elif alert.alert_type == 'main_fund_escape' and self.config.ENABLE_FUND_FLOW_ALERTS:
                        should_send = True
                    elif alert.alert_type == 'moving_stop_profit' and self.config.ENABLE_MOVING_STOP_PROFIT:
                        should_send = True
                        
                    if should_send:
                        await self._send_alert(alert)
                        self.last_alert_time[symbol] = datetime.now()
                        
                        # 如果是资金流入警报，开始追踪
                        if alert.alert_type == 'fund_inflow':
                            self.stop_profit_tracker.start_tracking(symbol, price, "资金流入异常")
                
        except Exception as e:
            logger.error(f"处理ticker数据失败: {e}")
            
    def _should_send_alert(self, symbol: str) -> bool:
        """检查是否应该发送警报（冷却时间）"""
        if symbol not in self.last_alert_time:
            return True
            
        return datetime.now() - self.last_alert_time[symbol] > self.alert_cooldown
        
    async def _send_alert(self, alert: PriceAlert):
        """发送警报通知（异步非阻塞）"""
        try:
            # 构建通知消息
            if alert.alert_type == 'fund_inflow':
                title = f"💰 {alert.symbol} 资金流入异常"
                content = f"""**合约资金活跃异常检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.2f}
📈 **24H涨跌幅**: {alert.change_percent:+.1f}%
💵 **资金流入**: {alert.fund_flow/1000000:.1f}M USDT
🤖 **AI评分**: {alert.ai_score or 80}
⏰ **时间**: {alert.timestamp.strftime('%m/%d %H:%M')}

🚀 **警报**: {alert.message}"""
                
            elif alert.alert_type == 'main_fund_escape':
                title = f"⚠️ {alert.symbol} 主力资金出逃"
                content = f"""**主力资金异动监控**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.2f}
📉 **24H涨跌幅**: {alert.change_percent:+.2f}%
💸 **资金流出**: {abs(alert.fund_flow or 0)/1000000:.1f}M USDT
⏰ **时间**: {alert.timestamp.strftime('%m/%d %H:%M')}

🔴 **警报**: {alert.message}

📍 **追踪结束**"""
                
            elif alert.alert_type == 'moving_stop_profit':
                title = f"📈 {alert.symbol} 移动止盈触发"
                content = f"""**移动止盈保护**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.2f}
📈 **最大涨幅**: {alert.max_gain:.1f}%
📉 **当前回撤**: {alert.current_decline:.1f}%
🤖 **AI评分**: {alert.ai_score or 80}
⏰ **时间**: {alert.timestamp.strftime('%m/%d %H:%M')}

🛡️ **止盈**: {alert.message}

📍 **追踪结束**"""
                
            elif alert.alert_type == 'volatility':
                title = f"🚨 {alert.symbol} 价格异常波动"
                content = f"""**价格异常波动检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
📈 **变化幅度**: {alert.change_percent:+.2f}%
📊 **成交量**: {alert.volume:.0f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ **警报原因**: 检测到异常价格波动

{alert.message}"""
            
            elif alert.alert_type == 'volume_spike':
                title = f"📊 {alert.symbol} 成交量异常"
                content = f"""**成交量异常检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
📊 **异常成交量**: {alert.volume:.0f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

⚠️ **警报原因**: 检测到异常成交量激增

{alert.message}"""
            
            else:
                title = f"🚨 {alert.symbol} 市场异常"
                content = f"""**市场异常检测**

📊 **交易对**: {alert.symbol}
💰 **当前价格**: ${alert.current_price:.4f}
⏰ **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}"""
            
            # 异步发送Server酱通知（如果配置了）
            if self.notifier:
                # 使用asyncio.create_task实现真正的异步非阻塞发送
                asyncio.create_task(self._send_notification_async(title, content, alert.symbol, alert.alert_type))
                logger.info(f"实时警报已提交发送: {alert.symbol} - {alert.alert_type}")
            else:
                logger.info(f"实时警报（仅控制台）: {alert.symbol} - {alert.alert_type}")
                print(f"\n🚨 {title}")
                print(content)
                
            # 异步保存警报到数据库
            asyncio.create_task(self._save_alert_to_db_async(alert))
            
        except Exception as e:
            logger.error(f"发送警报失败: {e}")
            
    async def _send_notification_async(self, title: str, content: str, symbol: str, alert_type: str):
        """异步发送通知"""
        try:
            # 在线程池中执行同步的通知发送
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self.notifier.send_notification, title, content)
            
            if success:
                logger.info(f"实时警报发送成功: {symbol} - {alert_type}")
            else:
                logger.error(f"实时警报发送失败: {symbol} - {alert_type}")
        except Exception as e:
            logger.error(f"异步发送通知失败: {e}")
            
    async def _save_alert_to_db_async(self, alert: PriceAlert):
        """异步保存警报到数据库"""
        try:
            # 在线程池中执行数据库操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_alert_to_db, alert)
        except Exception as e:
            logger.error(f"异步保存警报到数据库失败: {e}")
            
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