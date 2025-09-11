import sqlite3
import os

# 检查数据库文件是否存在
db_path = 'trading_data.db'
if not os.path.exists(db_path):
    print(f"数据库文件 {db_path} 不存在")
    exit(1)

print(f"数据库文件大小: {os.path.getsize(db_path)} bytes")

# 连接数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"\n数据库中的表: {[table[0] for table in tables]}")

# 检查关键表的数据量
key_tables = ['trading_signals', 'win_rate_stats', 'analysis_results', 'kline_data', 'technical_indicators']

print("\n=== 表数据统计 ===")
for table_name in key_tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"{table_name}: {count} 条记录")
        
        # 如果有数据，显示最新的几条记录
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            print(f"  最新3条记录: {len(rows)} 条")
            
    except sqlite3.OperationalError as e:
        print(f"{table_name}: 表不存在或查询错误 - {e}")

# 检查最近的分析结果
print("\n=== 最近的分析活动 ===")
try:
    cursor.execute("SELECT symbol, timestamp FROM trading_signals ORDER BY timestamp DESC LIMIT 5")
    recent_signals = cursor.fetchall()
    if recent_signals:
        print("最近的交易信号:")
        for signal in recent_signals:
            print(f"  {signal[0]}: {signal[1]}")
    else:
        print("没有交易信号记录")
except:
    print("无法查询交易信号")

try:
    cursor.execute("SELECT analysis_id, timestamp FROM analysis_results ORDER BY timestamp DESC LIMIT 5")
    recent_analysis = cursor.fetchall()
    if recent_analysis:
        print("最近的分析结果:")
        for analysis in recent_analysis:
            print(f"  {analysis[0]}: {analysis[1]}")
    else:
        print("没有分析结果记录")
except:
    print("无法查询分析结果")

conn.close()
print("\n数据库检查完成")