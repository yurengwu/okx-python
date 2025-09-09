import json
from typing import Dict, List, Optional
from openai import OpenAI
from loguru import logger
from config import Config
import pandas as pd
from enhanced_indicators import EnhancedTechnicalIndicators
from data_storage import DataStorageManager
from win_rate_analyzer import WinRateAnalyzer
from prediction_model import TradingPredictionModel

class DeepSeekAnalyzer:
    def __init__(self):
        """初始化DeepSeek分析器"""
        self.client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL
        )
        self.indicators_calculator = EnhancedTechnicalIndicators()
        self.data_storage = DataStorageManager()
        self.win_rate_analyzer = WinRateAnalyzer()
        self.prediction_model = TradingPredictionModel()
    
    def prepare_market_data_for_analysis(self, market_data: Dict) -> str:
        """准备市场数据用于分析"""
        analysis_data = {}
        
        for symbol, data in market_data.items():
            if 'kline' in data and data['kline'] is not None:
                kline_df = data['kline']
                
                # 存储K线数据到数据库
                self.data_storage.store_kline_data(symbol, "1h", kline_df)
                
                # 计算增强技术指标
                enhanced_indicators = self.indicators_calculator.calculate_all_indicators(kline_df)
                
                # 存储技术指标到数据库
                self.data_storage.store_technical_indicators(symbol, "1h", kline_df)
                
                # 获取历史胜率数据
                win_rate_stats = self.win_rate_analyzer.analyze_symbol_win_rate(symbol, days=30)
                
                # 准备预测特征
                prediction_features = self._prepare_prediction_features(kline_df, enhanced_indicators, data)
                
                # 获取胜率预测
                win_rate_prediction = self.prediction_model.predict_success_probability(prediction_features)
                
                # 计算信号强度
                signal_strength = self.indicators_calculator.get_signal_strength(enhanced_indicators)
                
                latest_data = {
                    'symbol': symbol,
                    'current_price': float(kline_df['close'].iloc[-1]),
                    'price_change_24h': float(data['ticker']['percentage_24h']) if data['ticker'] else 0,
                    'volume_24h': float(data['ticker']['volume_24h']) if data['ticker'] else 0,
                    'funding_rate': float(data['funding']['funding_rate']) if data['funding'] else 0,
                    
                    # 价格统计
                    'high_24h': float(kline_df['high'].tail(24).max()),
                    'low_24h': float(kline_df['low'].tail(24).min()),
                    'avg_volume_7d': float(kline_df['volume'].tail(168).mean()),
                    
                    # 增强技术指标
                    'enhanced_indicators': enhanced_indicators,
                    
                    # 胜率分析
                    'historical_win_rate': win_rate_stats.get('win_rate', 50),
                    'win_rate_prediction': win_rate_prediction,
                    
                    # 信号强度
                    'signal_strength': signal_strength,
                    
                    # 最近价格趋势
                    'recent_prices': kline_df['close'].tail(10).tolist()
                }
                
                analysis_data[symbol] = latest_data
        
        return json.dumps(analysis_data, indent=2, ensure_ascii=False, default=str)
    
    def _prepare_prediction_features(self, kline_df: pd.DataFrame, indicators: Dict, market_data: Dict) -> Dict:
        """准备机器学习预测特征"""
        try:
            features = {}
            
            # 技术指标特征
            features.update({
                'rsi_14': indicators.get('rsi_14', 50),
                'macd': indicators.get('macd', 0),
                'macd_signal': indicators.get('macd_signal', 0),
                'bb_width': indicators.get('bb_width', 0),
                'kdj_k': indicators.get('kdj_k', 50),
                'kdj_d': indicators.get('kdj_d', 50),
                'williams_r': indicators.get('williams_r', -50),
                'cci': indicators.get('cci', 0),
                'atr_percent': indicators.get('atr_percent', 1),
                'volume_ratio': indicators.get('volume_ratio', 1),
                'volatility': indicators.get('volatility', 0.5),
                'adx': indicators.get('adx', 25),
            })
            
            # 价格变化特征
            if len(kline_df) >= 24:
                features['price_change_1h'] = (kline_df['close'].iloc[-1] - kline_df['close'].iloc[-2]) / kline_df['close'].iloc[-2] * 100
                features['price_change_4h'] = (kline_df['close'].iloc[-1] - kline_df['close'].iloc[-5]) / kline_df['close'].iloc[-5] * 100 if len(kline_df) >= 5 else 0
                features['price_change_24h'] = (kline_df['close'].iloc[-1] - kline_df['close'].iloc[-25]) / kline_df['close'].iloc[-25] * 100 if len(kline_df) >= 25 else 0
            
            # 市场特征
            ticker = market_data.get('ticker', {})
            features.update({
                'trading_volume_24h': float(ticker.get('volume_24h', 0)) if ticker else 0,
                'market_cap_rank': 50,  # 默认值，实际应从API获取
            })
            
            # 时间特征
            from datetime import datetime
            now = datetime.now()
            features.update({
                'hour_of_day': now.hour,
                'day_of_week': now.weekday(),
            })
            
            # 风险等级（基于波动率）
            volatility = features.get('volatility', 0.5)
            if volatility < 0.5:
                risk_level = 'low'
            elif volatility < 1.5:
                risk_level = 'medium'
            else:
                risk_level = 'high'
            
            features['risk_level'] = risk_level
            features['confidence'] = 0.7  # 默认信心度
            
            return features
            
        except Exception as e:
            logger.error(f"准备预测特征失败: {e}")
            return {}
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except:
            return 50.0
    
    def analyze_market_data(self, market_data: Dict) -> Optional[Dict]:
        """使用DeepSeek分析市场数据"""
        try:
            # 准备数据
            data_str = self.prepare_market_data_for_analysis(market_data)
            
            # 构建分析提示
            prompt = f"""
你是一个专业的加密货币交易分析师，拥有丰富的技术分析经验和机器学习辅助分析能力。请基于以下OKX USDT永续合约的增强市场数据进行深度分析，并为每个交易对提供具体的交易建议。

增强市场数据（包含30+技术指标、历史胜率、AI预测）：
{data_str}

请特别关注以下新增分析维度：

1. 增强技术分析：
   - 多重技术指标综合分析（RSI、MACD、布林带、KDJ、威廉指标、CCI、ATR等）
   - 趋势强度分析（ADX、SAR、Aroon）
   - 波动率和动量分析
   - 成交量指标分析（OBV、成交量比率）
   - 信号强度评估

2. 历史表现分析：
   - 历史胜率数据参考
   - AI模型预测概率
   - 风险收益比评估

3. 交易建议（基于数据驱动）：
   - 操作方向：BUY/SELL/HOLD
   - 建议入场点位（基于技术指标和支撑阻力）
   - 动态止损点位（基于ATR和波动率）
   - 分层止盈点位
   - 风险评估（1-5级，结合历史胜率）
   - 信心度（0.1-1.0，结合AI预测）

4. 市场情绪和预测：
   - 多维度市场情绪判断
   - 短期价格预期（基于技术指标和AI模型）
   - 关键技术位和催化因素

请确保分析客观、专业，充分利用提供的增强数据。对于每个交易对都要给出明确的数值建议和详细的技术分析依据。

请以JSON格式返回分析结果，格式如下：
{{
  "analysis_time": "分析时间",
  "market_overview": "整体市场概述（包含技术指标概况）",
  "recommendations": {{
    "交易对名称": {{
      "action": "BUY/SELL/HOLD",
      "entry_price": 建议入场价格,
      "stop_loss": 止损价格,
      "take_profit": 止盈价格,
      "risk_level": 风险等级(1-5),
      "confidence": 信心度(0.1-1.0),
      "predicted_win_rate": AI预测胜率,
      "technical_score": 技术指标综合评分,
      "analysis": "详细分析说明（包含关键技术指标解读）",
      "key_levels": {{
        "support": [支撑位数组],
        "resistance": [阻力位数组]
      }},
      "indicators_summary": {{
        "trend": "趋势方向",
        "momentum": "动量状态",
        "volatility": "波动率水平",
        "volume": "成交量状态"
      }}
    }}
  }}
}}
"""
            
            # 调用DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的加密货币交易分析师，擅长技术分析和风险管理。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            # 解析响应
            analysis_text = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_start = analysis_text.find('{')
                json_end = analysis_text.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = analysis_text[json_start:json_end]
                    analysis_result = json.loads(json_str)
                    
                    logger.info("DeepSeek分析完成")
                    return analysis_result
                else:
                    logger.warning("无法从响应中提取JSON格式")
                    return {
                        "analysis_time": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "market_overview": "分析格式解析失败",
                        "raw_analysis": analysis_text,
                        "recommendations": {}
                    }
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                return {
                    "analysis_time": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "market_overview": "JSON解析失败",
                    "raw_analysis": analysis_text,
                    "recommendations": {}
                }
                
        except Exception as e:
            logger.error(f"DeepSeek分析失败: {e}")
            return None
    
    def format_analysis_output(self, analysis: Dict) -> str:
        """格式化增强分析输出"""
        if not analysis or 'recommendations' not in analysis:
            return "分析失败或无有效数据"
        
        output = []
        output.append(f"\n=== 增强加密货币交易分析报告 ===")
        output.append(f"分析时间: {analysis.get('analysis_time', 'Unknown')}")
        output.append(f"市场概述: {analysis.get('market_overview', 'N/A')}")
        output.append("\n" + "="*50)
        
        for symbol, rec in analysis['recommendations'].items():
            output.append(f"\n【{symbol}】")
            output.append(f"操作建议: {rec.get('action', 'N/A')}")
            output.append(f"入场点位: {rec.get('entry_price', 'N/A')}")
            output.append(f"止损点位: {rec.get('stop_loss', 'N/A')}")
            output.append(f"止盈点位: {rec.get('take_profit', 'N/A')}")
            output.append(f"风险等级: {rec.get('risk_level', 'N/A')}/5")
            output.append(f"信心度: {rec.get('confidence', 'N/A'):.2f}" if isinstance(rec.get('confidence'), (int, float)) else f"信心度: {rec.get('confidence', 'N/A')}")
            
            # 新增AI预测和技术评分
            if 'predicted_win_rate' in rec:
                win_rate = rec['predicted_win_rate']
                if isinstance(win_rate, (int, float)):
                    output.append(f"AI预测胜率: {win_rate:.1%}")
                else:
                    output.append(f"AI预测胜率: {win_rate}")
            if 'technical_score' in rec:
                tech_score = rec['technical_score']
                if isinstance(tech_score, (int, float)):
                    output.append(f"技术指标评分: {tech_score:.2f}")
                else:
                    output.append(f"技术指标评分: {tech_score}")
            
            # 技术指标摘要
            indicators = rec.get('indicators_summary', {})
            if indicators:
                output.append(f"技术指标摘要:")
                output.append(f"  趋势: {indicators.get('trend', '未知')}")
                output.append(f"  动量: {indicators.get('momentum', '未知')}")
                output.append(f"  波动率: {indicators.get('volatility', '未知')}")
                output.append(f"  成交量: {indicators.get('volume', '未知')}")
            
            if 'key_levels' in rec:
                levels = rec['key_levels']
                if 'support' in levels:
                    output.append(f"支撑位: {levels['support']}")
                if 'resistance' in levels:
                    output.append(f"阻力位: {levels['resistance']}")
            
            output.append(f"分析说明: {rec.get('analysis', 'N/A')}")
            output.append("-" * 30)
        
        return "\n".join(output)