import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger
import json
from pathlib import Path

class TradingDatabase:
    """交易数据库管理类"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        """初始化数据库连接"""
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """初始化数据库表结构"""
        try:
            # 确保数据库文件目录存在
            import os
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # K线数据表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kline_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL,
                        timeframe TEXT NOT NULL DEFAULT '1h',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timestamp, timeframe)
                    )
                """)
                
                # 技术指标数据表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS technical_indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        timeframe TEXT NOT NULL DEFAULT '1h',
                        rsi_14 REAL,
                        sma_20 REAL,
                        sma_50 REAL,
                        ema_12 REAL,
                        ema_26 REAL,
                        macd REAL,
                        macd_signal REAL,
                        macd_histogram REAL,
                        bb_upper REAL,
                        bb_middle REAL,
                        bb_lower REAL,
                        bb_width REAL,
                        kdj_k REAL,
                        kdj_d REAL,
                        kdj_j REAL,
                        williams_r REAL,
                        cci REAL,
                        atr REAL,
                        volatility REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timestamp, timeframe)
                    )
                """)
                
                # 分析结果表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        action TEXT NOT NULL,
                        entry_price REAL,
                        stop_loss REAL,
                        take_profit REAL,
                        risk_level INTEGER,
                        confidence INTEGER,
                        support_levels TEXT,
                        resistance_levels TEXT,
                        analysis_text TEXT,
                        market_data TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 交易信号历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trading_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        signal_time DATETIME NOT NULL,
                        signal_type TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        stop_loss REAL,
                        take_profit REAL,
                        actual_exit_price REAL,
                        exit_time DATETIME,
                        profit_loss REAL,
                        win_flag BOOLEAN,
                        holding_hours REAL,
                        max_drawdown REAL,
                        max_profit REAL,
                        status TEXT DEFAULT 'open',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 胜率统计表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS win_rate_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL DEFAULT '1h',
                        signal_type TEXT NOT NULL,
                        total_signals INTEGER DEFAULT 0,
                        winning_signals INTEGER DEFAULT 0,
                        win_rate REAL DEFAULT 0.0,
                        avg_profit REAL DEFAULT 0.0,
                        avg_loss REAL DEFAULT 0.0,
                        profit_factor REAL DEFAULT 0.0,
                        max_consecutive_wins INTEGER DEFAULT 0,
                        max_consecutive_losses INTEGER DEFAULT 0,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timeframe, signal_type)
                    )
                """)
                
                # 创建索引提高查询性能
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_kline_symbol_time ON kline_data(symbol, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_indicators_symbol_time ON technical_indicators(symbol, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_symbol_time ON analysis_results(symbol, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON trading_signals(symbol, signal_time)")
                
                conn.commit()
                logger.info("数据库初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_kline_data(self, symbol: str, df: pd.DataFrame, timeframe: str = '1h') -> bool:
        """保存K线数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 准备数据
                data_to_insert = []
                for idx, row in df.iterrows():
                    # 处理时间戳：优先使用timestamp列，否则使用索引
                    if 'timestamp' in row and pd.notna(row['timestamp']):
                        timestamp = pd.to_datetime(row['timestamp'])
                    elif hasattr(idx, 'strftime'):  # 索引是时间戳
                        timestamp = pd.to_datetime(idx)
                    else:  # 索引是整数，使用timestamp列
                        timestamp = pd.to_datetime(row['timestamp'])
                    
                    data_to_insert.append((
                        symbol,
                        timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        float(row['volume']),
                        timeframe
                    ))
                
                # 使用INSERT OR IGNORE实现追加模式，避免重复数据但不覆盖
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR IGNORE INTO kline_data 
                    (symbol, timestamp, open, high, low, close, volume, timeframe)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, data_to_insert)
                
                conn.commit()
                logger.info(f"保存 {symbol} K线数据 {len(data_to_insert)} 条")
                return True
                
        except Exception as e:
            logger.error(f"保存K线数据失败: {e}")
            return False
    
    def save_technical_indicators(self, symbol: str, indicators: Dict, timestamp: datetime, timeframe: str = '1h') -> bool:
        """保存技术指标数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO technical_indicators 
                    (symbol, timestamp, timeframe, rsi_14, sma_20, sma_50, ema_12, ema_26,
                     macd, macd_signal, macd_histogram, bb_upper, bb_middle, bb_lower, bb_width,
                     kdj_k, kdj_d, kdj_j, williams_r, cci, atr, volatility)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    timeframe,
                    indicators.get('rsi_14'),
                    indicators.get('sma_20'),
                    indicators.get('sma_50'),
                    indicators.get('ema_12'),
                    indicators.get('ema_26'),
                    indicators.get('macd'),
                    indicators.get('macd_signal'),
                    indicators.get('macd_histogram'),
                    indicators.get('bb_upper'),
                    indicators.get('bb_middle'),
                    indicators.get('bb_lower'),
                    indicators.get('bb_width'),
                    indicators.get('kdj_k'),
                    indicators.get('kdj_d'),
                    indicators.get('kdj_j'),
                    indicators.get('williams_r'),
                    indicators.get('cci'),
                    indicators.get('atr'),
                    indicators.get('volatility')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存技术指标失败: {e}")
            return False
    
    def save_analysis_result(self, symbol: str, analysis: Dict) -> bool:
        """保存分析结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 处理take_profit数据类型
                take_profit = analysis.get('take_profit')
                if isinstance(take_profit, list) and take_profit:
                    # 如果是列表，取第一个目标价格
                    take_profit_value = take_profit[0]
                elif isinstance(take_profit, (int, float)):
                    take_profit_value = take_profit
                else:
                    take_profit_value = None
                
                # 处理confidence数据类型（转换为整数百分比）
                confidence = analysis.get('confidence')
                if isinstance(confidence, float):
                    confidence_value = int(confidence * 100)  # 转换为百分比整数
                elif isinstance(confidence, int):
                    confidence_value = confidence
                else:
                    confidence_value = None
                
                cursor.execute("""
                    INSERT INTO analysis_results 
                    (symbol, timestamp, action, entry_price, stop_loss, take_profit,
                     risk_level, confidence, support_levels, resistance_levels, 
                     analysis_text, market_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    analysis.get('action'),
                    analysis.get('entry_price'),
                    analysis.get('stop_loss'),
                    take_profit_value,
                    analysis.get('risk_level'),
                    confidence_value,
                    json.dumps(analysis.get('support_levels', [])),
                    json.dumps(analysis.get('resistance_levels', [])),
                    analysis.get('analysis'),
                    json.dumps(analysis.get('market_data', {}))
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
            return False
    
    def get_analysis_results(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """获取分析结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if symbol:
                    cursor.execute("""
                        SELECT * FROM analysis_results 
                        WHERE symbol = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (symbol, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM analysis_results 
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (limit,))
                
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                analysis_list = []
                for row in results:
                    result_dict = dict(zip(columns, row))
                    # 构造与WinRateAnalyzer期望的格式兼容的数据结构
                    formatted_result = {
                        'id': result_dict['id'],
                        'symbol': result_dict['symbol'],
                        'created_at': result_dict['timestamp'],
                        'analysis_result': {
                            'action': result_dict['action'],
                            'entry_point': result_dict['entry_price'],
                            'stop_loss': result_dict['stop_loss'],
                            'take_profit': result_dict['take_profit'],
                            'confidence': result_dict['confidence'],
                            'technical_analysis': json.loads(result_dict['market_data']) if result_dict['market_data'] else {}
                        }
                    }
                    analysis_list.append(formatted_result)
                
                return analysis_list
                
        except Exception as e:
            logger.error(f"获取分析结果失败: {e}")
            return []
    
    def get_kline_data(self, symbol: str, timeframe: str = '1h', limit: int = 1000) -> Optional[pd.DataFrame]:
        """获取K线数据 - 智能取样：不足1000条按最大数量取，大于1000条取最近1000条，等于1000条取1000条"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 首先查询总数量
                count_query = """
                    SELECT COUNT(*) FROM kline_data 
                    WHERE symbol = ? AND timeframe = ?
                """
                cursor = conn.cursor()
                cursor.execute(count_query, (symbol, timeframe))
                total_count = cursor.fetchone()[0]
                
                if total_count == 0:
                    return None
                
                # 根据总数量决定取样策略
                if total_count <= 1000:
                    # 不足或等于1000条，取全部
                    actual_limit = total_count
                    logger.info(f"数据库中{symbol}共{total_count}条数据，取全部")
                else:
                    # 超过1000条，取最近1000条
                    actual_limit = 1000
                    logger.info(f"数据库中{symbol}共{total_count}条数据，取最近1000条")
                
                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM kline_data 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                
                df = pd.read_sql_query(query, conn, params=(symbol, timeframe, actual_limit))
                
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    df = df.sort_index()  # 按时间正序排列
                    return df
                
                return None
                
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None
    
    def get_latest_timestamp(self, symbol: str, timeframe: str = '1h') -> Optional[datetime]:
        """获取最新数据时间戳"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(timestamp) FROM kline_data 
                    WHERE symbol = ? AND timeframe = ?
                """, (symbol, timeframe))
                
                result = cursor.fetchone()
                if result[0]:
                    return datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                
                return None
                
        except Exception as e:
            logger.error(f"获取最新时间戳失败: {e}")
            return None
    
    def save_win_rate_stats(self, symbol: str, stats: Dict) -> bool:
        """保存胜率统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO win_rate_stats 
                    (symbol, timeframe, signal_type, total_signals, winning_signals, 
                     win_rate, avg_profit, avg_loss, profit_factor, 
                     max_consecutive_wins, max_consecutive_losses, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    stats.get('timeframe', '1h'),
                    stats.get('signal_type', 'all'),
                    stats.get('total_signals', 0),
                    stats.get('winning_signals', 0),
                    stats.get('win_rate', 0.0),
                    stats.get('avg_profit', 0.0),
                    stats.get('avg_loss', 0.0),
                    stats.get('profit_factor', 0.0),
                    stats.get('max_consecutive_wins', 0),
                    stats.get('max_consecutive_losses', 0),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存胜率统计失败: {e}")
            return False
    
    def save_trading_signal(self, symbol: str, signal: Dict) -> bool:
        """保存交易信号"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 处理take_profit数据类型
                take_profit = signal.get('take_profit', 0)
                if isinstance(take_profit, list) and take_profit:
                    # 如果是列表，取第一个目标价格
                    take_profit_value = take_profit[0]
                elif isinstance(take_profit, (int, float)):
                    take_profit_value = take_profit
                else:
                    take_profit_value = 0
                
                cursor.execute("""
                    INSERT INTO trading_signals 
                    (symbol, signal_time, signal_type, entry_price, stop_loss, 
                     take_profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    signal.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    signal.get('action', 'HOLD').lower(),
                    signal.get('entry_price', 0),
                    signal.get('stop_loss', 0),
                    take_profit_value,
                    'open'
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存交易信号失败: {e}")
            return False
    
    def update_trading_signal_result(self, signal_id: int, exit_time: datetime, 
                                   actual_exit_price: float, profit_loss: float, 
                                   win_flag: bool, holding_hours: float, 
                                   max_drawdown: float, max_profit: float) -> bool:
        """更新交易信号结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE trading_signals 
                    SET exit_time = ?, actual_exit_price = ?, profit_loss = ?, 
                        win_flag = ?, holding_hours = ?, max_drawdown = ?, 
                        max_profit = ?, status = 'closed'
                    WHERE id = ?
                """, (
                    exit_time.strftime('%Y-%m-%d %H:%M:%S'),
                    actual_exit_price,
                    profit_loss,
                    win_flag,
                    holding_hours,
                    max_drawdown,
                    max_profit,
                    signal_id
                ))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"更新交易信号结果失败: {e}")
            return False
    
    def get_open_trading_signals(self, symbol: str = None) -> List[Dict]:
        """获取未完成的交易信号"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if symbol:
                    query = """
                        SELECT * FROM trading_signals 
                        WHERE status = 'open' AND symbol = ?
                        ORDER BY signal_time DESC
                    """
                    df = pd.read_sql_query(query, conn, params=(symbol,))
                else:
                    query = """
                        SELECT * FROM trading_signals 
                        WHERE status = 'open'
                        ORDER BY signal_time DESC
                    """
                    df = pd.read_sql_query(query, conn)
                
                return df.to_dict('records') if not df.empty else []
                
        except Exception as e:
            logger.error(f"获取未完成交易信号失败: {e}")
            return []
    
    def get_win_rate_stats(self, symbol: str, signal_type: str = None) -> Dict:
        """获取胜率统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if signal_type:
                    cursor.execute("""
                        SELECT * FROM win_rate_stats 
                        WHERE symbol = ? AND signal_type = ?
                    """, (symbol, signal_type))
                else:
                    cursor.execute("""
                        SELECT * FROM win_rate_stats 
                        WHERE symbol = ?
                    """, (symbol,))
                
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                stats = []
                for row in results:
                    stats.append(dict(zip(columns, row)))
                
                return {'symbol': symbol, 'stats': stats}
                
        except Exception as e:
            logger.error(f"获取胜率统计失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        pass  # SQLite连接在with语句中自动关闭