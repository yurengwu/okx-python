import sqlite3
import json
from datetime import datetime

def check_database_detailed():
    """详细检查数据库内容"""
    db_path = "trading_data.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("=== 详细数据库检查 ===")
            
            # 检查trading_signals表的具体内容
            print("\n=== trading_signals表内容 ===")
            cursor.execute("SELECT * FROM trading_signals ORDER BY signal_time DESC LIMIT 5")
            signals = cursor.fetchall()
            
            if signals:
                # 获取列名
                cursor.execute("PRAGMA table_info(trading_signals)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"列名: {columns}")
                
                for signal in signals:
                    print(f"信号: {dict(zip(columns, signal))}")
            else:
                print("trading_signals表为空")
            
            # 检查analysis_results表的具体内容
            print("\n=== analysis_results表内容 ===")
            cursor.execute("SELECT * FROM analysis_results ORDER BY timestamp DESC LIMIT 5")
            results = cursor.fetchall()
            
            if results:
                cursor.execute("PRAGMA table_info(analysis_results)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"列名: {columns}")
                
                for result in results:
                    print(f"分析结果: {dict(zip(columns, result))}")
            else:
                print("analysis_results表为空")
            
            # 检查win_rate_stats表的具体内容
            print("\n=== win_rate_stats表内容 ===")
            cursor.execute("SELECT * FROM win_rate_stats ORDER BY last_updated DESC LIMIT 5")
            stats = cursor.fetchall()
            
            if stats:
                cursor.execute("PRAGMA table_info(win_rate_stats)")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"列名: {columns}")
                
                for stat in stats:
                    print(f"胜率统计: {dict(zip(columns, stat))}")
            else:
                print("win_rate_stats表为空")
            
            # 检查最新的技术指标
            print("\n=== 最新技术指标 ===")
            cursor.execute("SELECT symbol, timestamp FROM technical_indicators ORDER BY timestamp DESC LIMIT 5")
            indicators = cursor.fetchall()
            for indicator in indicators:
                print(f"技术指标: {indicator[0]} - {indicator[1]}")
            
            # 检查最新的K线数据
            print("\n=== 最新K线数据 ===")
            cursor.execute("SELECT symbol, timestamp FROM kline_data ORDER BY timestamp DESC LIMIT 5")
            klines = cursor.fetchall()
            for kline in klines:
                print(f"K线数据: {kline[0]} - {kline[1]}")
                
    except Exception as e:
        print(f"数据库检查失败: {e}")

if __name__ == "__main__":
    check_database_detailed()