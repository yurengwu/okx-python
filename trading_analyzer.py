import pandas as pd
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime
import json
import os

from okx_client import OKXClient
from deepseek_analyzer import DeepSeekAnalyzer
from data_storage import DataStorageManager
from win_rate_analyzer import WinRateAnalyzer
from serverchan_notifier import ServerChanNotifier
from config import Config

class TradingAnalyzer:
    def __init__(self):
        """初始化交易分析器"""
        self.okx_client = OKXClient()
        self.deepseek_analyzer = DeepSeekAnalyzer()
        self.data_storage = DataStorageManager()
        self.win_rate_analyzer = WinRateAnalyzer()
        self.results_dir = "analysis_results"
        
        # 初始化Server酱通知器
        self.serverchan_notifier = None
        if Config.ENABLE_SERVERCHAN_NOTIFICATION and Config.SERVERCHAN_SENDKEY:
            self.serverchan_notifier = ServerChanNotifier(Config.SERVERCHAN_SENDKEY)
            logger.info("Server酱通知功能已启用")
        
        # 创建结果目录
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def run_analysis(self, symbols: Optional[List[str]] = None) -> Dict:
        """运行完整的交易分析"""
        try:
            # 使用配置中的交易对或传入的交易对
            if symbols is None:
                symbols = Config.TRADING_PAIRS
            
            logger.info(f"开始分析 {len(symbols)} 个交易对")
            
            # 1. 获取市场数据
            logger.info("正在获取市场数据...")
            market_data = self.okx_client.get_market_data(symbols)
            
            if not market_data:
                logger.error("未能获取到市场数据")
                return {"error": "未能获取到市场数据"}
            
            logger.info(f"成功获取 {len(market_data)} 个交易对的市场数据")
            
            # 2. 使用DeepSeek进行分析
            logger.info("正在进行AI分析...")
            analysis_result = self.deepseek_analyzer.analyze_market_data(market_data)
            
            if not analysis_result:
                logger.error("AI分析失败")
                return {"error": "AI分析失败"}
            
            # 3. 保存分析结果
            self.save_analysis_result(analysis_result)
            
            # 4. 格式化输出
            formatted_output = self.deepseek_analyzer.format_analysis_output(analysis_result)
            
            # 5. 发送Server酱通知
            if self.serverchan_notifier:
                try:
                    notification_result = self.serverchan_notifier.send_analysis_notification(analysis_result)
                    if notification_result.get('success'):
                        logger.info("Server酱通知发送成功")
                    else:
                        logger.warning(f"Server酱通知发送失败: {notification_result.get('error')}")
                except Exception as e:
                    logger.error(f"发送Server酱通知时出错: {e}")
            
            logger.info("分析完成")
            
            return {
                "success": True,
                "analysis_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "analyzed_pairs": list(market_data.keys()),
                "analysis_result": analysis_result,
                "formatted_output": formatted_output
            }
            
        except Exception as e:
            logger.error(f"分析过程中发生错误: {e}")
            return {"error": str(e)}
    
    def save_analysis_result(self, analysis_result: Dict):
        """保存分析结果到文件和数据库"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 保存JSON格式到文件
            json_filename = f"{self.results_dir}/analysis_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            
            # 保存可读格式到文件
            txt_filename = f"{self.results_dir}/analysis_{timestamp}.txt"
            formatted_output = self.deepseek_analyzer.format_analysis_output(analysis_result)
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            
            logger.info(f"分析结果已保存到文件: {json_filename}, {txt_filename}")
            
            # 保存到数据库
            if 'recommendations' in analysis_result:
                for symbol, recommendation in analysis_result['recommendations'].items():
                    try:
                        # 保存分析结果到analysis_results表
                        success = self.data_storage.store_analysis_result(symbol, recommendation)
                        if success:
                            logger.info(f"成功保存 {symbol} 分析结果到数据库")
                        else:
                            logger.error(f"保存 {symbol} 分析结果到数据库失败")
                        
                        # 保存交易信号到trading_signals表
                        if recommendation.get('action') and recommendation.get('action').upper() in ['BUY', 'SELL']:
                            signal_success = self.data_storage.db.save_trading_signal(symbol, recommendation)
                            if signal_success:
                                logger.info(f"成功保存 {symbol} 交易信号到数据库")
                            else:
                                logger.error(f"保存 {symbol} 交易信号到数据库失败")
                        
                    except Exception as db_error:
                        logger.error(f"保存 {symbol} 分析结果到数据库时出错: {db_error}")
            
            # 执行胜率分析并保存统计
            try:
                self.analyze_and_save_win_rates()
                
                # 更新trading_signals表中的空字段
                self.win_rate_analyzer.update_trading_signals_with_results()
            except Exception as wr_error:
                logger.error(f"胜率分析失败: {wr_error}")
            
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
    
    def analyze_and_save_win_rates(self):
        """分析并保存胜率统计"""
        try:
            # 获取最新的分析结果
            analysis_results = self.data_storage.db.get_analysis_results(limit=500)
            
            if not analysis_results:
                logger.info("暂无分析结果，跳过胜率分析")
                return
            
            # 提取交易信号
            signals = self.win_rate_analyzer.extract_signals_from_analysis(analysis_results)
            
            if not signals:
                logger.info("暂无有效交易信号，跳过胜率分析")
                return
            
            # 按交易对分组分析
            symbols = list(set([signal.symbol for signal in signals]))
            
            for symbol in symbols:
                try:
                    # 获取该交易对的K线数据用于胜率分析
                    kline_data = self.data_storage.db.get_kline_data(symbol, limit=2000)
                    
                    if kline_data is None or kline_data.empty:
                        logger.warning(f"无法获取 {symbol} 的K线数据，跳过胜率分析")
                        continue
                    
                    # kline_data已经是DataFrame格式，直接使用
                    df = kline_data.reset_index()  # 将timestamp从索引转为列
                    if 'timestamp' not in df.columns:
                        df['timestamp'] = df.index
                    
                    # 获取该交易对的信号
                    symbol_signals = [s for s in signals if s.symbol == symbol]
                    
                    # 评估信号表现
                    signal_results = []
                    for signal in symbol_signals:
                        result = self.win_rate_analyzer.evaluate_signal_performance(signal, df)
                        signal_results.append(result)
                    
                    # 计算胜率统计
                    stats = self.win_rate_analyzer.calculate_win_rate_stats(signal_results)
                    
                    if stats and stats.get('total_signals', 0) > 0:
                        # 保存胜率统计
                        success = self.win_rate_analyzer.save_win_rate_stats(symbol, stats)
                        if success:
                            logger.info(f"成功保存 {symbol} 胜率统计: 胜率 {stats.get('win_rate', 0):.2f}%")
                        else:
                            logger.error(f"保存 {symbol} 胜率统计失败")
                    
                except Exception as symbol_error:
                    logger.error(f"分析 {symbol} 胜率失败: {symbol_error}")
            
        except Exception as e:
            logger.error(f"胜率分析过程失败: {e}")
    
    def get_latest_analysis(self) -> Optional[Dict]:
        """获取最新的分析结果"""
        try:
            json_files = [f for f in os.listdir(self.results_dir) if f.endswith('.json')]
            if not json_files:
                return None
            
            # 按时间排序，获取最新的
            latest_file = sorted(json_files)[-1]
            filepath = os.path.join(self.results_dir, latest_file)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"读取最新分析结果失败: {e}")
            return None
    
    def get_analysis_history(self, days: int = 7) -> List[Dict]:
        """获取历史分析结果"""
        try:
            json_files = [f for f in os.listdir(self.results_dir) if f.endswith('.json')]
            
            # 按时间过滤和排序
            cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
            recent_files = []
            
            for filename in json_files:
                filepath = os.path.join(self.results_dir, filename)
                file_time = os.path.getmtime(filepath)
                if file_time > cutoff_time:
                    recent_files.append((filepath, file_time))
            
            # 按时间排序
            recent_files.sort(key=lambda x: x[1], reverse=True)
            
            # 读取文件内容
            history = []
            for filepath, _ in recent_files:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        history.append(data)
                except Exception as e:
                    logger.warning(f"读取文件 {filepath} 失败: {e}")
                    continue
            
            return history
            
        except Exception as e:
            logger.error(f"获取分析历史失败: {e}")
            return []
    
    def generate_summary_report(self) -> str:
        """生成汇总报告"""
        try:
            latest_analysis = self.get_latest_analysis()
            if not latest_analysis:
                return "暂无分析数据"
            
            report = []
            report.append("=== 交易分析汇总报告 ===")
            report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            if 'recommendations' in latest_analysis:
                recommendations = latest_analysis['recommendations']
                
                # 统计建议分布
                actions = {}
                risk_levels = []
                confidence_levels = []
                
                for symbol, rec in recommendations.items():
                    action = rec.get('action', '观望')
                    actions[action] = actions.get(action, 0) + 1
                    
                    if 'risk_level' in rec:
                        risk_levels.append(rec['risk_level'])
                    if 'confidence' in rec:
                        confidence_levels.append(rec['confidence'])
                
                report.append("\n操作建议分布:")
                for action, count in actions.items():
                    report.append(f"  {action}: {count} 个交易对")
                
                if risk_levels:
                    avg_risk = sum(risk_levels) / len(risk_levels)
                    report.append(f"\n平均风险等级: {avg_risk:.1f}/5")
                
                if confidence_levels:
                    avg_confidence = sum(confidence_levels) / len(confidence_levels)
                    report.append(f"平均信心度: {avg_confidence:.1f}/10")
                
                # 高信心度推荐
                high_confidence = [(symbol, rec) for symbol, rec in recommendations.items() 
                                 if rec.get('confidence', 0) >= 7]
                
                if high_confidence:
                    report.append("\n高信心度推荐 (≥7):")
                    for symbol, rec in high_confidence:
                        report.append(f"  {symbol}: {rec.get('action', 'N/A')} - 入场: {rec.get('entry_price', 'N/A')}")
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"生成汇总报告失败: {e}")
            return f"生成报告失败: {e}"
    
    def test_serverchan_notification(self) -> Dict:
        """
        测试Server酱通知功能
        
        Returns:
            Dict: 测试结果
        """
        if not self.serverchan_notifier:
            return {
                "success": False,
                "error": "Server酱通知功能未启用或SendKey未配置"
            }
        
        try:
            result = self.serverchan_notifier.test_connection()
            return result
        except Exception as e:
            logger.error(f"测试Server酱通知失败: {e}")
            return {"success": False, "error": str(e)}
    
    def validate_configuration(self) -> Dict[str, bool]:
        """
        验证系统配置
        
        Returns:
            Dict[str, bool]: 配置验证结果
        """
        validation = {
            'okx_api_configured': bool(Config.OKX_API_KEY and Config.OKX_SECRET_KEY and Config.OKX_PASSPHRASE),
            'deepseek_api_configured': bool(Config.DEEPSEEK_API_KEY),
            'serverchan_configured': bool(Config.SERVERCHAN_SENDKEY) if Config.ENABLE_SERVERCHAN_NOTIFICATION else True,
            'okx_connection': False
        }
        
        # 测试OKX连接
        if validation['okx_api_configured']:
            try:
                test_data = self.okx_client.get_market_data(['BTC-USDT-SWAP'])
                validation['okx_connection'] = bool(test_data)
            except Exception:
                validation['okx_connection'] = False
        
        return validation