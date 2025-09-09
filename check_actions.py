from database import TradingDatabase

db = TradingDatabase()
results = db.get_analysis_results(limit=10)

print('所有分析结果的action:')
action_count = {}
for r in results:
    action = r['analysis_result']['action']
    print(f"{r['symbol']}: {action}")
    action_count[action] = action_count.get(action, 0) + 1

print(f"\nAction统计: {action_count}")
print(f"总共 {len(results)} 条分析结果")

# 检查有多少BUY/SELL信号
buy_sell_count = action_count.get('BUY', 0) + action_count.get('SELL', 0)
print(f"BUY/SELL信号: {buy_sell_count} 条")
print(f"HOLD信号: {action_count.get('HOLD', 0)} 条")