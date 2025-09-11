import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from loguru import logger
import talib

class EnhancedTechnicalIndicators:
    """增强技术指标计算类"""
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> Dict:
        """计算所有技术指标"""
        try:
            if df.empty or len(df) < 50:
                logger.warning("数据不足，无法计算技术指标")
                return {}
            
            indicators = {}
            
            # 基础价格数据
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            volume = df['volume'].values
            
            # 移动平均线
            indicators.update(EnhancedTechnicalIndicators.calculate_moving_averages(close))
            
            # RSI
            indicators.update(EnhancedTechnicalIndicators.calculate_rsi(close))
            
            # MACD
            indicators.update(EnhancedTechnicalIndicators.calculate_macd(close))
            
            # 布林带
            indicators.update(EnhancedTechnicalIndicators.calculate_bollinger_bands(close))
            
            # KDJ指标
            indicators.update(EnhancedTechnicalIndicators.calculate_kdj(high, low, close))
            
            # 威廉指标
            indicators.update(EnhancedTechnicalIndicators.calculate_williams_r(high, low, close))
            
            # CCI指标
            indicators.update(EnhancedTechnicalIndicators.calculate_cci(high, low, close))
            
            # ATR
            indicators.update(EnhancedTechnicalIndicators.calculate_atr(high, low, close))
            
            # 成交量指标
            indicators.update(EnhancedTechnicalIndicators.calculate_volume_indicators(close, volume))
            
            # 波动率
            indicators.update(EnhancedTechnicalIndicators.calculate_volatility(close))
            
            # 动量指标
            indicators.update(EnhancedTechnicalIndicators.calculate_momentum_indicators(close))
            
            # 趋势强度指标
            indicators.update(EnhancedTechnicalIndicators.calculate_trend_indicators(high, low, close))
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}
    
    @staticmethod
    def calculate_moving_averages(close: np.ndarray) -> Dict:
        """计算移动平均线"""
        try:
            return {
                'sma_5': talib.SMA(close, timeperiod=5)[-1] if len(close) >= 5 else None,
                'sma_10': talib.SMA(close, timeperiod=10)[-1] if len(close) >= 10 else None,
                'sma_20': talib.SMA(close, timeperiod=20)[-1] if len(close) >= 20 else None,
                'sma_50': talib.SMA(close, timeperiod=50)[-1] if len(close) >= 50 else None,
                'sma_200': talib.SMA(close, timeperiod=200)[-1] if len(close) >= 200 else None,
                'ema_12': talib.EMA(close, timeperiod=12)[-1] if len(close) >= 12 else None,
                'ema_26': talib.EMA(close, timeperiod=26)[-1] if len(close) >= 26 else None,
                'ema_50': talib.EMA(close, timeperiod=50)[-1] if len(close) >= 50 else None,
            }
        except Exception as e:
            logger.error(f"计算移动平均线失败: {e}")
            return {}
    
    @staticmethod
    def calculate_rsi(close: np.ndarray) -> Dict:
        """计算RSI指标"""
        try:
            return {
                'rsi_14': talib.RSI(close, timeperiod=14)[-1] if len(close) >= 14 else None,
                'rsi_21': talib.RSI(close, timeperiod=21)[-1] if len(close) >= 21 else None,
            }
        except Exception as e:
            logger.error(f"计算RSI失败: {e}")
            return {}
    
    @staticmethod
    def calculate_macd(close: np.ndarray) -> Dict:
        """计算MACD指标"""
        try:
            if len(close) < 26:
                return {'macd': None, 'macd_signal': None, 'macd_histogram': None}
            
            macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            
            return {
                'macd': macd[-1] if not np.isnan(macd[-1]) else None,
                'macd_signal': macd_signal[-1] if not np.isnan(macd_signal[-1]) else None,
                'macd_histogram': macd_hist[-1] if not np.isnan(macd_hist[-1]) else None,
            }
        except Exception as e:
            logger.error(f"计算MACD失败: {e}")
            return {'macd': None, 'macd_signal': None, 'macd_histogram': None}
    
    @staticmethod
    def calculate_bollinger_bands(close: np.ndarray, period: int = 20, std_dev: int = 2) -> Dict:
        """计算布林带"""
        try:
            if len(close) < period:
                return {'bb_upper': None, 'bb_middle': None, 'bb_lower': None, 'bb_width': None}
            
            bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev)
            
            upper = bb_upper[-1] if not np.isnan(bb_upper[-1]) else None
            middle = bb_middle[-1] if not np.isnan(bb_middle[-1]) else None
            lower = bb_lower[-1] if not np.isnan(bb_lower[-1]) else None
            
            # 计算布林带宽度
            width = None
            if upper and lower and middle:
                width = (upper - lower) / middle * 100
            
            return {
                'bb_upper': upper,
                'bb_middle': middle,
                'bb_lower': lower,
                'bb_width': width,
            }
        except Exception as e:
            logger.error(f"计算布林带失败: {e}")
            return {'bb_upper': None, 'bb_middle': None, 'bb_lower': None, 'bb_width': None}
    
    @staticmethod
    def calculate_kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 9) -> Dict:
        """计算KDJ指标"""
        try:
            if len(close) < period:
                return {'kdj_k': None, 'kdj_d': None, 'kdj_j': None}
            
            # 计算K值
            lowest_low = talib.MIN(low, timeperiod=period)
            highest_high = talib.MAX(high, timeperiod=period)
            
            rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
            
            # 使用简单移动平均计算K和D
            k_values = []
            d_values = []
            
            k = 50  # 初始K值
            d = 50  # 初始D值
            
            for i in range(len(rsv)):
                if not np.isnan(rsv[i]):
                    k = (2/3) * k + (1/3) * rsv[i]
                    d = (2/3) * d + (1/3) * k
                k_values.append(k)
                d_values.append(d)
            
            # J = 3K - 2D
            j = 3 * k_values[-1] - 2 * d_values[-1] if k_values and d_values else None
            
            return {
                'kdj_k': k_values[-1] if k_values else None,
                'kdj_d': d_values[-1] if d_values else None,
                'kdj_j': j,
            }
        except Exception as e:
            logger.error(f"计算KDJ失败: {e}")
            return {'kdj_k': None, 'kdj_d': None, 'kdj_j': None}
    
    @staticmethod
    def calculate_williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Dict:
        """计算威廉指标"""
        try:
            if len(close) < period:
                return {'williams_r': None}
            
            williams_r = talib.WILLR(high, low, close, timeperiod=period)
            
            return {
                'williams_r': williams_r[-1] if not np.isnan(williams_r[-1]) else None,
            }
        except Exception as e:
            logger.error(f"计算威廉指标失败: {e}")
            return {'williams_r': None}
    
    @staticmethod
    def calculate_cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Dict:
        """计算CCI指标"""
        try:
            if len(close) < period:
                return {'cci': None}
            
            cci = talib.CCI(high, low, close, timeperiod=period)
            
            return {
                'cci': cci[-1] if not np.isnan(cci[-1]) else None,
            }
        except Exception as e:
            logger.error(f"计算CCI失败: {e}")
            return {'cci': None}
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Dict:
        """计算ATR指标"""
        try:
            if len(close) < period:
                return {'atr': None, 'atr_percent': None}
            
            atr = talib.ATR(high, low, close, timeperiod=period)
            atr_value = atr[-1] if not np.isnan(atr[-1]) else None
            
            # ATR百分比
            atr_percent = None
            if atr_value and close[-1] > 0:
                atr_percent = (atr_value / close[-1]) * 100
            
            return {
                'atr': atr_value,
                'atr_percent': atr_percent,
            }
        except Exception as e:
            logger.error(f"计算ATR失败: {e}")
            return {'atr': None, 'atr_percent': None}
    
    @staticmethod
    def calculate_volume_indicators(close: np.ndarray, volume: np.ndarray) -> Dict:
        """计算成交量指标"""
        try:
            if len(volume) < 20:
                return {'volume_sma': None, 'volume_ratio': None, 'obv': None}
            
            # 成交量移动平均
            volume_sma = talib.SMA(volume, timeperiod=20)[-1] if len(volume) >= 20 else None
            
            # 成交量比率
            volume_ratio = None
            if volume_sma and volume_sma > 0:
                volume_ratio = volume[-1] / volume_sma
            
            # OBV指标
            obv = talib.OBV(close, volume)[-1] if len(close) >= 1 else None
            
            return {
                'volume_sma': volume_sma,
                'volume_ratio': volume_ratio,
                'obv': obv,
            }
        except Exception as e:
            logger.error(f"计算成交量指标失败: {e}")
            return {'volume_sma': None, 'volume_ratio': None, 'obv': None}
    
    @staticmethod
    def calculate_volatility(close: np.ndarray, period: int = 20) -> Dict:
        """计算波动率指标"""
        try:
            if len(close) < period:
                return {'volatility': None, 'volatility_percentile': None}
            
            # 计算收益率
            returns = np.diff(np.log(close))
            
            # 波动率（标准差）
            volatility = np.std(returns[-period:]) * np.sqrt(24 * 365) if len(returns) >= period else None
            
            # 波动率百分位数（相对于历史波动率的位置）
            volatility_percentile = None
            if len(returns) >= 100:
                historical_vol = [np.std(returns[i:i+period]) for i in range(len(returns)-period+1)]
                if volatility and historical_vol:
                    volatility_percentile = (np.sum(np.array(historical_vol) <= volatility) / len(historical_vol)) * 100
            
            return {
                'volatility': volatility,
                'volatility_percentile': volatility_percentile,
            }
        except Exception as e:
            logger.error(f"计算波动率失败: {e}")
            return {'volatility': None, 'volatility_percentile': None}
    
    @staticmethod
    def calculate_momentum_indicators(close: np.ndarray) -> Dict:
        """计算动量指标"""
        try:
            indicators = {}
            
            # ROC (Rate of Change)
            if len(close) >= 10:
                roc = talib.ROC(close, timeperiod=10)
                indicators['roc_10'] = roc[-1] if not np.isnan(roc[-1]) else None
            
            # 动量指标
            if len(close) >= 10:
                momentum = talib.MOM(close, timeperiod=10)
                indicators['momentum_10'] = momentum[-1] if not np.isnan(momentum[-1]) else None
            
            # TRIX指标
            if len(close) >= 30:
                trix = talib.TRIX(close, timeperiod=14)
                indicators['trix'] = trix[-1] if not np.isnan(trix[-1]) else None
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算动量指标失败: {e}")
            return {}
    
    @staticmethod
    def calculate_trend_indicators(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Dict:
        """计算趋势指标"""
        try:
            indicators = {}
            
            # ADX (平均趋向指数)
            if len(close) >= 14:
                adx = talib.ADX(high, low, close, timeperiod=14)
                indicators['adx'] = adx[-1] if not np.isnan(adx[-1]) else None
            
            # 抛物线SAR
            if len(close) >= 2:
                sar = talib.SAR(high, low, acceleration=0.02, maximum=0.2)
                indicators['sar'] = sar[-1] if not np.isnan(sar[-1]) else None
            
            # Aroon指标
            if len(close) >= 14:
                aroon_down, aroon_up = talib.AROON(high, low, timeperiod=14)
                indicators['aroon_up'] = aroon_up[-1] if not np.isnan(aroon_up[-1]) else None
                indicators['aroon_down'] = aroon_down[-1] if not np.isnan(aroon_down[-1]) else None
            
            return indicators
            
        except Exception as e:
            logger.error(f"计算趋势指标失败: {e}")
            return {}
    
    @staticmethod
    def get_signal_strength(indicators: Dict) -> Dict:
        """根据技术指标计算信号强度"""
        try:
            signals = {
                'bullish_signals': 0,
                'bearish_signals': 0,
                'neutral_signals': 0,
                'signal_strength': 0,
                'signal_details': []
            }
            
            # RSI信号
            rsi = indicators.get('rsi_14')
            if rsi:
                if rsi < 30:
                    signals['bullish_signals'] += 1
                    signals['signal_details'].append('RSI超卖')
                elif rsi > 70:
                    signals['bearish_signals'] += 1
                    signals['signal_details'].append('RSI超买')
                else:
                    signals['neutral_signals'] += 1
            
            # MACD信号
            macd = indicators.get('macd')
            macd_signal = indicators.get('macd_signal')
            if macd and macd_signal:
                if macd > macd_signal:
                    signals['bullish_signals'] += 1
                    signals['signal_details'].append('MACD金叉')
                else:
                    signals['bearish_signals'] += 1
                    signals['signal_details'].append('MACD死叉')
            
            # 布林带信号
            bb_upper = indicators.get('bb_upper')
            bb_lower = indicators.get('bb_lower')
            if bb_upper and bb_lower:
                # 这里需要当前价格来判断，暂时跳过
                pass
            
            # KDJ信号
            kdj_k = indicators.get('kdj_k')
            kdj_d = indicators.get('kdj_d')
            if kdj_k and kdj_d:
                if kdj_k < 20 and kdj_d < 20:
                    signals['bullish_signals'] += 1
                    signals['signal_details'].append('KDJ超卖')
                elif kdj_k > 80 and kdj_d > 80:
                    signals['bearish_signals'] += 1
                    signals['signal_details'].append('KDJ超买')
                else:
                    signals['neutral_signals'] += 1
            
            # 计算总体信号强度
            total_signals = signals['bullish_signals'] + signals['bearish_signals'] + signals['neutral_signals']
            if total_signals > 0:
                signals['signal_strength'] = (signals['bullish_signals'] - signals['bearish_signals']) / total_signals
            
            return signals
            
        except Exception as e:
            logger.error(f"计算信号强度失败: {e}")
            return {}