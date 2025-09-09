import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from database import TradingDatabase
from dataclasses import dataclass
from enum import Enum

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class TradingSignal:
    symbol: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timestamp: datetime
    indicators: Dict
    analysis_id: str

@dataclass
class SignalResult:
    signal: TradingSignal
    actual_outcome: str  # 'win', 'loss', 'pending'
    max_profit: float
    max_loss: float
    exit_price: Optional[float]
    exit_time: Optional[datetime]
    holding_period: Optional[timedelta]
    profit_loss: float

class WinRateAnalyzer:
    """胜率分析器"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db = TradingDatabase(db_path)
    
    def extract_signals_from_analysis(self, analysis_results: List[Dict]) -> List[TradingSignal]:
        """从分析结果中提取交易信号"""
        signals = []
        
        try:
            for result in analysis_results:
                if not result.get('analysis_result'):
                    continue
                
                analysis = result['analysis_result']
                if isinstance(analysis, str):
                    import json
                    analysis = json.loads(analysis)
                
                # 提取信号信息
                action = analysis.get('action', 'HOLD').upper()
                if action not in ['BUY', 'SELL']:
                    continue
                
                signal = TradingSignal(
                    symbol=result['symbol'],
                    signal_type=SignalType.BUY if action == 'BUY' else SignalType.SELL,
                    entry_price=float(analysis.get('entry_point', 0)),
                    stop_loss=float(analysis.get('stop_loss', 0)),
                    take_profit=float(analysis.get('take_profit', 0)),
                    confidence=float(analysis.get('confidence', 0)),
                    timestamp=datetime.fromisoformat(result['created_at'].replace('Z', '+00:00')),
                    indicators=analysis.get('technical_analysis', {}),
                    analysis_id=str(result.get('id', ''))
                )
                
                signals.append(signal)
                
        except Exception as e:
            logger.error(f"提取交易信号失败: {e}")
        
        return signals
    
    def evaluate_signal_performance(self, signal: TradingSignal, price_data: pd.DataFrame) -> SignalResult:
        """评估信号表现"""
        try:
            # 筛选信号时间之后的价格数据
            future_data = price_data[price_data['timestamp'] > signal.timestamp].copy()
            
            future_data = future_data.sort_values('timestamp')
            entry_price = signal.entry_price
            
            max_profit = 0
            max_loss = 0
            exit_price = None
            exit_time = None
            outcome = 'pending'
            
            for _, row in future_data.iterrows():
                current_price = row['close']
                current_time = row['timestamp']
                
                if signal.signal_type == SignalType.BUY:
                    # 买入信号评估
                    profit_loss = (current_price - entry_price) / entry_price * 100
                    
                    # 更新最大盈利和亏损
                    max_profit = max(max_profit, profit_loss)
                    max_loss = min(max_loss, profit_loss)
                    
                    # 检查止损和止盈
                    if signal.stop_loss > 0 and current_price <= signal.stop_loss:
                        exit_price = signal.stop_loss
                        exit_time = current_time
                        outcome = 'loss'
                        break
                    elif signal.take_profit > 0 and current_price >= signal.take_profit:
                        exit_price = signal.take_profit
                        exit_time = current_time
                        outcome = 'win'
                        break
                
                elif signal.signal_type == SignalType.SELL:
                    # 卖出信号评估
                    profit_loss = (entry_price - current_price) / entry_price * 100
                    
                    # 更新最大盈利和亏损
                    max_profit = max(max_profit, profit_loss)
                    max_loss = min(max_loss, profit_loss)
                    
                    # 检查止损和止盈
                    if signal.stop_loss > 0 and current_price >= signal.stop_loss:
                        exit_price = signal.stop_loss
                        exit_time = current_time
                        outcome = 'loss'
                        break
                    elif signal.take_profit > 0 and current_price <= signal.take_profit:
                        exit_price = signal.take_profit
                        exit_time = current_time
                        outcome = 'win'
                        break
            
            # 如果没有触发止损或止盈，检查是否有足够的数据进行评估
            if outcome == 'pending':
                if not future_data.empty:
                    # 有未来数据，使用最后价格
                    last_row = future_data.iloc[-1]
                    exit_price = last_row['close']
                    exit_time = last_row['timestamp']
                    
                    if signal.signal_type == SignalType.BUY:
                        final_profit_loss = (exit_price - entry_price) / entry_price * 100
                    else:
                        final_profit_loss = (entry_price - exit_price) / entry_price * 100
                    
                    outcome = 'win' if final_profit_loss > 0 else 'loss'
                else:
                    # 没有未来数据，使用当前最新价格进行评估
                    if not price_data.empty:
                        last_row = price_data.iloc[-1]
                        current_price = last_row['close']
                        current_time = last_row['timestamp']
                        
                        # 检查信号时间与最新数据时间的关系
                        time_diff = signal.timestamp - current_time
                        # 如果信号时间在数据时间之后，说明信号是最近生成的，使用最新价格评估
                        if time_diff.total_seconds() <= 86400:  # 24小时内的信号都可以评估
                            exit_price = current_price
                            exit_time = current_time
                            
                            if signal.signal_type == SignalType.BUY:
                                final_profit_loss = (exit_price - entry_price) / entry_price * 100
                            else:
                                final_profit_loss = (entry_price - exit_price) / entry_price * 100
                            
                            outcome = 'win' if final_profit_loss > 0 else 'loss'
                            
                            # 更新最大盈利和亏损
                            max_profit = max(max_profit, final_profit_loss if final_profit_loss > 0 else 0)
                            max_loss = min(max_loss, final_profit_loss if final_profit_loss < 0 else 0)
            
            # 计算持仓时间
            holding_period = None
            if exit_time:
                holding_period = exit_time - signal.timestamp
            
            # 计算最终盈亏（如果还没有计算过）
            if 'final_profit_loss' not in locals():
                final_profit_loss = 0
                if exit_price:
                    if signal.signal_type == SignalType.BUY:
                        final_profit_loss = (exit_price - entry_price) / entry_price * 100
                    else:
                        final_profit_loss = (entry_price - exit_price) / entry_price * 100
            
            return SignalResult(
                signal=signal,
                actual_outcome=outcome,
                max_profit=max_profit,
                max_loss=max_loss,
                exit_price=exit_price,
                exit_time=exit_time,
                holding_period=holding_period,
                profit_loss=final_profit_loss
            )
            
        except Exception as e:
            logger.error(f"评估信号表现失败: {e}")
            return SignalResult(
                signal=signal,
                actual_outcome='error',
                max_profit=0,
                max_loss=0,
                exit_price=None,
                exit_time=None,
                holding_period=None,
                profit_loss=0
            )
    
    def calculate_win_rate_stats(self, signal_results: List[SignalResult]) -> Dict:
        """计算胜率统计"""
        try:
            if not signal_results:
                return {}
            
            # 过滤掉pending和error的结果
            completed_results = [r for r in signal_results if r.actual_outcome in ['win', 'loss']]
            
            if not completed_results:
                return {'total_signals': len(signal_results), 'completed_signals': 0}
            
            # 基础统计
            total_signals = len(signal_results)
            completed_signals = len(completed_results)
            wins = len([r for r in completed_results if r.actual_outcome == 'win'])
            losses = len([r for r in completed_results if r.actual_outcome == 'loss'])
            
            win_rate = wins / completed_signals * 100 if completed_signals > 0 else 0
            
            # 盈亏统计
            profits = [r.profit_loss for r in completed_results if r.actual_outcome == 'win']
            losses_pnl = [r.profit_loss for r in completed_results if r.actual_outcome == 'loss']
            
            avg_profit = np.mean(profits) if profits else 0
            avg_loss = np.mean(losses_pnl) if losses_pnl else 0
            max_profit = max(profits) if profits else 0
            max_loss = min(losses_pnl) if losses_pnl else 0
            
            # 风险收益比
            risk_reward_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0
            
            # 按信心度分组统计
            confidence_stats = {}
            for confidence_range in [(0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.0)]:
                range_results = [
                    r for r in completed_results 
                    if confidence_range[0] <= r.signal.confidence < confidence_range[1]
                ]
                
                if range_results:
                    range_wins = len([r for r in range_results if r.actual_outcome == 'win'])
                    range_win_rate = range_wins / len(range_results) * 100
                    
                    confidence_stats[f"{confidence_range[0]}-{confidence_range[1]}"] = {
                        'count': len(range_results),
                        'win_rate': range_win_rate,
                        'avg_profit_loss': np.mean([r.profit_loss for r in range_results])
                    }
            
            # 按交易对分组统计
            symbol_stats = {}
            symbols = list(set([r.signal.symbol for r in completed_results]))
            
            for symbol in symbols:
                symbol_results = [r for r in completed_results if r.signal.symbol == symbol]
                symbol_wins = len([r for r in symbol_results if r.actual_outcome == 'win'])
                symbol_win_rate = symbol_wins / len(symbol_results) * 100
                
                symbol_stats[symbol] = {
                    'count': len(symbol_results),
                    'win_rate': symbol_win_rate,
                    'avg_profit_loss': np.mean([r.profit_loss for r in symbol_results])
                }
            
            # 计算连续胜负统计
            max_consecutive_wins = 0
            max_consecutive_losses = 0
            current_consecutive_wins = 0
            current_consecutive_losses = 0
            
            # 按时间排序结果
            sorted_results = sorted(completed_results, key=lambda x: x.signal.timestamp)
            
            for result in sorted_results:
                if result.actual_outcome == 'win':
                    current_consecutive_wins += 1
                    current_consecutive_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, current_consecutive_wins)
                else:
                    current_consecutive_losses += 1
                    current_consecutive_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
            
            # 计算盈利因子 (总盈利/总亏损的绝对值)
            total_profits = sum([r.profit_loss for r in completed_results if r.profit_loss > 0])
            total_losses = abs(sum([r.profit_loss for r in completed_results if r.profit_loss < 0]))
            profit_factor = total_profits / total_losses if total_losses > 0 else 0
            
            # 按信号类型统计
            buy_results = [r for r in completed_results if r.signal.signal_type == SignalType.BUY]
            sell_results = [r for r in completed_results if r.signal.signal_type == SignalType.SELL]
            
            buy_win_rate = 0
            sell_win_rate = 0
            
            if buy_results:
                buy_wins = len([r for r in buy_results if r.actual_outcome == 'win'])
                buy_win_rate = buy_wins / len(buy_results) * 100
            
            if sell_results:
                sell_wins = len([r for r in sell_results if r.actual_outcome == 'win'])
                sell_win_rate = sell_wins / len(sell_results) * 100
            
            return {
                'total_signals': total_signals,
                'completed_signals': completed_signals,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'risk_reward_ratio': risk_reward_ratio,
                'profit_factor': profit_factor,
                'max_consecutive_wins': max_consecutive_wins,
                'max_consecutive_losses': max_consecutive_losses,
                'buy_win_rate': buy_win_rate,
                'sell_win_rate': sell_win_rate,
                'confidence_stats': confidence_stats,
                'symbol_stats': symbol_stats,
                'total_profit_loss': sum([r.profit_loss for r in completed_results])
            }
            
        except Exception as e:
            logger.error(f"计算胜率统计失败: {e}")
            return {}
    
    def analyze_symbol_win_rate(self, symbol: str, days: int = 30) -> Dict:
        """分析特定交易对的胜率"""
        try:
            # 获取历史分析结果
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # 这里需要从数据库获取分析结果
            # 暂时返回模拟数据
            return {
                'symbol': symbol,
                'period_days': days,
                'total_signals': 0,
                'win_rate': 0,
                'avg_profit_loss': 0,
                'best_confidence_range': None,
                'recommendation': 'insufficient_data'
            }
            
        except Exception as e:
            logger.error(f"分析交易对胜率失败 {symbol}: {e}")
            return {}
    
    def get_win_rate_prediction(self, symbol: str, current_indicators: Dict, confidence: float) -> Dict:
        """基于历史数据预测胜率"""
        try:
            # 获取历史相似信号的表现
            historical_stats = self.analyze_symbol_win_rate(symbol, days=90)
            
            # 基于信心度调整预测
            base_win_rate = historical_stats.get('win_rate', 50)
            
            # 信心度调整因子
            confidence_factor = 1.0
            if confidence >= 0.85:
                confidence_factor = 1.2
            elif confidence >= 0.7:
                confidence_factor = 1.1
            elif confidence < 0.5:
                confidence_factor = 0.8
            
            predicted_win_rate = min(base_win_rate * confidence_factor, 95)
            
            # 风险等级评估
            risk_level = 'medium'
            if predicted_win_rate >= 70:
                risk_level = 'low'
            elif predicted_win_rate < 45:
                risk_level = 'high'
            
            return {
                'predicted_win_rate': predicted_win_rate,
                'confidence_factor': confidence_factor,
                'risk_level': risk_level,
                'historical_win_rate': base_win_rate,
                'sample_size': historical_stats.get('total_signals', 0),
                'reliability': 'high' if historical_stats.get('total_signals', 0) >= 20 else 'low'
            }
            
        except Exception as e:
            logger.error(f"预测胜率失败 {symbol}: {e}")
            return {
                'predicted_win_rate': 50,
                'confidence_factor': 1.0,
                'risk_level': 'medium',
                'reliability': 'low'
            }
    
    def save_win_rate_stats(self, symbol: str, stats: Dict, signal_type: str = 'all') -> bool:
        """保存胜率统计到数据库"""
        try:
            # 构建符合database.py期望格式的stats字典
            formatted_stats = {
                'timeframe': '1h',
                'signal_type': signal_type,
                'total_signals': stats.get('total_signals', 0),
                'winning_signals': stats.get('wins', 0),
                'win_rate': stats.get('win_rate', 0),
                'avg_profit': stats.get('avg_profit', 0),
                'avg_loss': abs(stats.get('avg_loss', 0)),
                'profit_factor': stats.get('profit_factor', 0),
                'max_consecutive_wins': stats.get('max_consecutive_wins', 0),
                'max_consecutive_losses': stats.get('max_consecutive_losses', 0)
            }
            
            return self.db.save_win_rate_stats(symbol=symbol, stats=formatted_stats)
        except Exception as e:
            logger.error(f"保存胜率统计失败: {e}")
            return False
    
    def update_trading_signals_with_results(self) -> bool:
        """更新trading_signals表中的空字段"""
        try:
            # 获取所有未完成的交易信号
            open_signals = self.db.get_open_trading_signals()
            
            if not open_signals:
                logger.info("没有未完成的交易信号需要更新")
                return True
            
            updated_count = 0
            
            for signal_data in open_signals:
                try:
                    symbol = signal_data['symbol']
                    signal_id = signal_data['id']
                    signal_time = datetime.fromisoformat(signal_data['signal_time'])
                    entry_price = signal_data['entry_price']
                    stop_loss = signal_data['stop_loss']
                    take_profit = signal_data['take_profit']
                    signal_type_str = signal_data['signal_type']
                    
                    # 转换信号类型
                    signal_type = SignalType.BUY if signal_type_str.upper() == 'BUY' else SignalType.SELL
                    
                    # 创建TradingSignal对象
                    trading_signal = TradingSignal(
                        symbol=symbol,
                        signal_type=signal_type,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=0.5,  # 默认值
                        timestamp=signal_time,
                        indicators={},
                        analysis_id=str(signal_id)
                    )
                    
                    # 获取K线数据
                    kline_data = self.db.get_kline_data(symbol, limit=1000)
                    
                    if kline_data is None or kline_data.empty:
                        logger.warning(f"无法获取 {symbol} 的K线数据，跳过信号 {signal_id}")
                        continue
                    
                    # 将索引转为列
                    df = kline_data.reset_index()
                    if 'timestamp' not in df.columns:
                        df['timestamp'] = df.index
                    
                    # 评估信号表现
                    result = self.evaluate_signal_performance(trading_signal, df)
                    
                    # 如果信号已完成，更新数据库
                    if result.exit_time and result.exit_price:
                        holding_hours = result.holding_period.total_seconds() / 3600 if result.holding_period else 0
                        win_flag = result.actual_outcome == 'win'
                        
                        success = self.db.update_trading_signal_result(
                            signal_id=signal_id,
                            exit_time=result.exit_time,
                            actual_exit_price=result.exit_price,
                            profit_loss=result.profit_loss,
                            win_flag=win_flag,
                            holding_hours=holding_hours,
                            max_drawdown=abs(result.max_loss),
                            max_profit=result.max_profit
                        )
                        
                        if success:
                            updated_count += 1
                            logger.info(f"更新信号 {signal_id} ({symbol}): {result.actual_outcome}, 盈亏: {result.profit_loss:.2f}%")
                        else:
                            logger.error(f"更新信号 {signal_id} 失败")
                    
                except Exception as signal_error:
                    logger.error(f"处理信号 {signal_data.get('id', 'unknown')} 失败: {signal_error}")
                    continue
            
            logger.info(f"成功更新 {updated_count} 个交易信号")
            return True
            
        except Exception as e:
            logger.error(f"更新交易信号失败: {e}")
            return False
    
    def get_overall_performance_report(self, days: int = 30) -> Dict:
        """获取整体表现报告"""
        try:
            # 这里应该从数据库获取所有交易对的统计数据
            # 暂时返回模拟报告
            return {
                'period_days': days,
                'total_symbols_analyzed': 0,
                'overall_win_rate': 0,
                'total_signals': 0,
                'best_performing_symbols': [],
                'worst_performing_symbols': [],
                'avg_confidence': 0,
                'high_confidence_win_rate': 0,
                'low_confidence_win_rate': 0,
                'recommendations': []
            }
            
        except Exception as e:
            logger.error(f"获取整体表现报告失败: {e}")
            return {}