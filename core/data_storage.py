import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
from .database import TradingDatabase
from analysis.enhanced_indicators import EnhancedTechnicalIndicators

class DataStorageManager:
    """数据存储管理器"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db = TradingDatabase(db_path)
        self.indicators_calculator = EnhancedTechnicalIndicators()
    
    def store_kline_data(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """存储K线数据"""
        try:
            if df.empty:
                logger.warning(f"K线数据为空，跳过存储: {symbol}")
                return False
            
            # 处理DataFrame格式：如果timestamp是索引，重置为列
            if df.index.name == 'timestamp' or 'timestamp' not in df.columns:
                df_copy = df.reset_index()
                if 'timestamp' not in df_copy.columns and df_copy.index.name is None:
                    df_copy['timestamp'] = df.index
            else:
                df_copy = df.copy()
            
            # 确保数据格式正确
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df_copy.columns for col in required_columns):
                logger.error(f"K线数据缺少必要列: {symbol}, 现有列: {list(df_copy.columns)}")
                return False
            
            # 使用数据库的批量保存方法
            success = self.db.save_kline_data(symbol, df_copy, timeframe)
            
            if success:
                logger.info(f"成功存储K线数据: {symbol}, 共 {len(df_copy)} 条")
            else:
                logger.error(f"存储K线数据失败: {symbol}")
            
            return success
            
        except Exception as e:
            logger.error(f"存储K线数据失败 {symbol}: {e}")
            return False
    
    def store_technical_indicators(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """计算并存储技术指标"""
        try:
            if df.empty or len(df) < 50:
                logger.warning(f"数据不足，无法计算技术指标: {symbol}")
                return False
            
            # 处理DataFrame格式：如果timestamp是索引，重置为列
            if df.index.name == 'timestamp' or 'timestamp' not in df.columns:
                df_copy = df.reset_index()
                if 'timestamp' not in df_copy.columns and df_copy.index.name is None:
                    df_copy['timestamp'] = df.index
            else:
                df_copy = df.copy()
            
            # 计算技术指标
            indicators = self.indicators_calculator.calculate_all_indicators(df_copy)
            
            if not indicators:
                logger.warning(f"技术指标计算失败: {symbol}")
                return False
            
            # 获取最新时间戳
            if 'timestamp' in df_copy.columns:
                latest_timestamp = df_copy['timestamp'].iloc[-1]
            else:
                latest_timestamp = df_copy.index[-1]
            
            # 确保时间戳是datetime对象
            if not isinstance(latest_timestamp, pd.Timestamp):
                latest_timestamp = pd.to_datetime(latest_timestamp)
            
            # 存储技术指标
            success = self.db.save_technical_indicators(
                symbol=symbol,
                indicators=indicators,
                timestamp=latest_timestamp.to_pydatetime(),
                timeframe=timeframe
            )
            
            if success:
                logger.info(f"成功存储技术指标: {symbol}")
            else:
                logger.error(f"存储技术指标失败: {symbol}")
            
            return success
            
        except Exception as e:
            logger.error(f"计算并存储技术指标失败 {symbol}: {e}")
            return False
    
    def get_historical_data(self, symbol: str, timeframe: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取历史数据"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            data = self.db.get_kline_data(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time
            )
            
            if data:
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                logger.info(f"获取到 {len(df)} 条历史数据: {symbol}")
                return df
            else:
                logger.warning(f"未找到历史数据: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"获取历史数据失败 {symbol}: {e}")
            return None
    
    def get_latest_indicators(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """获取最新技术指标"""
        try:
            indicators = self.db.get_technical_indicators(
                symbol=symbol,
                timeframe=timeframe,
                limit=1
            )
            
            if indicators:
                return indicators[0]
            else:
                logger.warning(f"未找到技术指标数据: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"获取技术指标失败 {symbol}: {e}")
            return None
    
    def store_analysis_result(self, symbol: str, analysis_result: Dict) -> bool:
        """存储分析结果"""
        try:
            success = self.db.save_analysis_result(
                symbol=symbol,
                analysis=analysis_result
            )
            
            if success:
                logger.info(f"成功存储分析结果: {symbol}")
            else:
                logger.error(f"存储分析结果失败: {symbol}")
            
            return success
            
        except Exception as e:
            logger.error(f"存储分析结果失败 {symbol}: {e}")
            return False
    
    def get_analysis_history(self, symbol: str, days: int = 7) -> List[Dict]:
        """获取分析历史"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # 这里需要在database.py中添加相应方法
            # 暂时返回空列表
            return []
            
        except Exception as e:
            logger.error(f"获取分析历史失败 {symbol}: {e}")
            return []
    
    def update_data_for_symbol(self, symbol: str, timeframe: str = "1h") -> bool:
        """更新指定交易对的数据"""
        try:
            from okx_client import OKXClient
            from config import Config
            
            # 初始化OKX客户端
            config = Config()
            okx_client = OKXClient(config)
            
            # 获取最新K线数据
            df = okx_client.get_kline_data(symbol, timeframe, limit=200)
            
            if df is None or df.empty:
                logger.error(f"获取K线数据失败: {symbol}")
                return False
            
            # 存储K线数据
            kline_success = self.store_kline_data(symbol, timeframe, df)
            
            # 计算并存储技术指标
            indicators_success = self.store_technical_indicators(symbol, timeframe, df)
            
            return kline_success and indicators_success
            
        except Exception as e:
            logger.error(f"更新数据失败 {symbol}: {e}")
            return False
    
    def batch_update_data(self, symbols: List[str], timeframe: str = "1h") -> Dict[str, bool]:
        """批量更新数据"""
        results = {}
        
        for symbol in symbols:
            try:
                logger.info(f"正在更新数据: {symbol}")
                results[symbol] = self.update_data_for_symbol(symbol, timeframe)
                
                # 避免请求过于频繁
                import time
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"批量更新数据失败 {symbol}: {e}")
                results[symbol] = False
        
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"批量更新完成: {success_count}/{len(symbols)} 成功")
        
        return results
    
    def get_data_statistics(self) -> Dict:
        """获取数据统计信息"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # K线数据统计
            cursor.execute("SELECT COUNT(*) FROM kline_data")
            stats['total_kline_records'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM kline_data")
            stats['unique_symbols'] = cursor.fetchone()[0]
            
            # 技术指标统计
            cursor.execute("SELECT COUNT(*) FROM technical_indicators")
            stats['total_indicator_records'] = cursor.fetchone()[0]
            
            # 分析结果统计
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            stats['total_analysis_records'] = cursor.fetchone()[0]
            
            # 最新数据时间
            cursor.execute("SELECT MAX(timestamp) FROM kline_data")
            latest_data = cursor.fetchone()[0]
            if latest_data:
                stats['latest_data_time'] = latest_data
            
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """清理旧数据"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # 删除旧的K线数据
            cursor.execute(
                "DELETE FROM kline_data WHERE timestamp < ?",
                (cutoff_time,)
            )
            kline_deleted = cursor.rowcount
            
            # 删除旧的技术指标数据
            cursor.execute(
                "DELETE FROM technical_indicators WHERE timestamp < ?",
                (cutoff_time,)
            )
            indicators_deleted = cursor.rowcount
            
            # 删除旧的分析结果
            cursor.execute(
                "DELETE FROM analysis_results WHERE created_at < ?",
                (cutoff_time,)
            )
            analysis_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"清理完成 - K线: {kline_deleted}, 指标: {indicators_deleted}, 分析: {analysis_deleted}")
            return True
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            return False