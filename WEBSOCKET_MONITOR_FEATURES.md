# WebSocket监控系统新功能说明

## 概述

WebSocket监控系统已成功扩展，新增了资金流向检测、主力资金监控和移动止盈追踪等高级功能。这些功能可以帮助您更好地监控市场动态，及时发现交易机会和风险。

## 新增功能

### 1. 资金流向检测 (Fund Flow Detection)

**功能描述：**
- 实时监控大额资金流入流出
- 基于价格变化和成交量计算资金流向
- 当资金流入超过阈值时触发警报

**触发条件：**
- 资金流入量 > 配置阈值（默认1M USDT）
- 资金流入量 > 历史平均值的3倍
- 需要至少10个历史数据点

**警报示例：**
```
💰 BTC/USDT:USDT 资金流入异常
BTC 合约资金持续流入，24H涨跌幅2.0%，现报$51000.00，可能出现上涨行情，但需注意风险
资金流向: 2888.5M USDT
```

### 2. 主力资金监控 (Main Fund Escape Detection)

**功能描述：**
- 检测主力资金出逃行为
- 监控连续资金流出模式
- 及时发现市场风险信号

**触发条件：**
- 最近5次交易全部为资金流出
- 累计流出金额 > 配置阈值
- 需要至少10个历史数据点

**警报示例：**
```
⚠️ BTC/USDT:USDT 主力资金出逃
BTC 疑似主力资金已出逃，资金异动监控结束，现报$50500.00，24H涨跌幅0.91%，注意市场风险。
```

### 3. 移动止盈追踪 (Moving Stop Profit Tracking)

**功能描述：**
- 自动追踪涨幅较大的交易对
- 在价格回撤时触发止盈保护
- 最大化利润保护，降低回撤风险

**工作流程：**
1. 当检测到资金流入异常时，自动开始追踪
2. 记录最高价格和最大涨幅
3. 当价格回撤超过设定比例时触发止盈

**触发条件：**
- 涨幅达到阈值（默认10%）后开始追踪
- 从最高点回撤超过设定比例（默认16.67%）时触发

**警报示例：**
```
📈 ETH/USDT:USDT 移动止盈触发
ETH 追踪结束：达到最大涨幅16.7%后回撤15.0%，触发移动止盈，现报$2975.00
最大涨幅: 16.7%, 当前回撤: 15.0%
```

## 配置参数

### 环境变量配置 (.env)

```bash
# Server酱通知配置（支持多token群发）
SERVERCHAN_SENDKEY=your_main_sendkey_here
SERVERCHAN_SENDKEYS=token1,token2,token3,token4  # 多个token用逗号分隔
```

### 资金流向监控配置
```python
# 启用资金流向警报
ENABLE_FUND_FLOW_ALERTS = True

# 资金异动阈值（USDT）
FUND_FLOW_THRESHOLD = 1000000  # 1M USDT

# 资金流向检测窗口大小
FUND_FLOW_WINDOW_SIZE = 30

# 主力资金出逃阈值（比例）
MAIN_FUND_ESCAPE_THRESHOLD = 0.8
```

### 移动止盈配置
```python
# 启用移动止盈
ENABLE_MOVING_STOP_PROFIT = True

# 开始追踪的涨幅阈值（%）
MAX_GAIN_THRESHOLD = 10.0

# 触发止盈的回撤比例（%）
STOP_LOSS_PERCENT = 16.67
```

## 使用方法

### 1. 启动监控
```python
from monitoring.websocket_monitor import WebSocketMonitor

# 创建监控实例（自动支持多token群发）
monitor = WebSocketMonitor()

# 启动监控
await monitor.start_monitoring()
```

### 多Token群发功能

系统支持向多个微信账号同时发送通知：

1. **配置多个Token**：在 `.env` 文件中配置多个Server酱token
2. **自动群发**：系统会自动向所有配置的token发送通知
3. **发送状态**：日志会显示每个token的发送状态
4. **容错机制**：单个token发送失败不影响其他token

**配置示例**：
```bash
# 主要token
SERVERCHAN_SENDKEY=SCT123456T...
# 额外的token（用逗号分隔）
SERVERCHAN_SENDKEYS=SCT789012T...,SCT345678T...,SCT901234T...
```

**日志输出示例**：
```
初始化Server酱通知器，配置了 4 个token
发送通知到token 1/4: SCT123456T...
Token 1 发送成功
发送通知到token 2/4: SCT789012T...
Token 2 发送成功
群发完成: 4/4 个token发送成功
```

### 2. 在线程中运行
```python
# 在后台线程中运行
thread = monitor.run_in_thread()
```

### 3. 测试功能
```bash
# 运行测试脚本
python test_websocket_monitor.py
```

## 警报类型

| 警报类型 | 图标 | 描述 |
|---------|------|------|
| fund_inflow | 💰 | 资金流入异常 |
| main_fund_escape | ⚠️ | 主力资金出逃 |
| moving_stop_profit | 📈 | 移动止盈触发 |
| volatility | 🚨 | 价格波动异常 |
| volume_spike | 📊 | 成交量异常 |

## 技术实现

### 资金流向计算
```python
def _calculate_fund_flow(self, symbol: str, price: float, volume: float) -> float:
    """根据价格变化和成交量估算资金流向"""
    if len(self.price_history[symbol]) >= 2:
        prev_price = list(self.price_history[symbol])[-2]
        price_change = (price - prev_price) / prev_price
        return price_change * volume * price
    return 0
```

### 主力资金出逃检测
```python
def _detect_main_fund_escape(self, symbol: str, price: float, volume: float, fund_flow: float) -> Optional[PriceAlert]:
    """检测连续资金流出模式"""
    recent_flows = list(self.fund_flow_history[symbol])[-5:]
    if all(flow < 0 for flow in recent_flows) and abs(sum(recent_flows)) > self.fund_threshold:
        # 触发主力资金出逃警报
        return PriceAlert(...)
```

### 移动止盈追踪
```python
def update_price(self, symbol: str, current_price: float) -> Optional[PriceAlert]:
    """更新价格并检查是否触发止盈"""
    if symbol in self.tracking_positions:
        position = self.tracking_positions[symbol]
        # 计算当前涨幅和回撤
        current_gain = (current_price - position['entry_price']) / position['entry_price'] * 100
        decline_from_peak = (position['max_price'] - current_price) / position['max_price'] * 100
        
        if decline_from_peak >= self.stop_loss_percent:
            # 触发移动止盈
            return PriceAlert(...)
```

## 注意事项

1. **数据要求：** 资金流向检测需要至少10个历史数据点才能工作
2. **阈值设置：** 根据市场情况调整资金异动阈值，避免过多误报
3. **网络连接：** 确保WebSocket连接稳定，避免数据丢失
4. **通知配置：** 配置Server酱或其他通知方式以接收警报
5. **测试验证：** 在实际使用前运行测试脚本验证功能正常

## 故障排除

### 常见问题

1. **资金流向检测不触发**
   - 检查是否有足够的历史数据（至少10个数据点）
   - 确认阈值设置是否合理
   - 验证价格变化计算逻辑

2. **WebSocket连接错误**
   - 检查网络连接
   - 确认OKX API配置正确
   - 查看日志文件获取详细错误信息

3. **通知不发送**
   - 检查Server酱配置
   - 确认警报类型已启用
   - 验证冷却时间设置

### 调试模式

运行测试脚本可以看到详细的调试信息：
```bash
python test_websocket_monitor.py
```

测试脚本会显示：
- 资金流向计算结果
- 阈值比较
- 警报触发条件
- 系统配置参数

## 更新日志

### v2.2.0 (2025-01-11)
- ✅ 彻底修复实时WebSocket监控中24小时涨跌幅显示为0的问题
- ✅ 增加FundFlowDetector的window_size从30到100，确保足够历史数据
- ✅ 改进_get_24h_change方法，添加短期趋势估算逻辑
- ✅ 移除测试用的随机变化生成，使用真实价格计算
- ✅ 添加数据不足情况的智能处理机制
- ✅ 创建test_realtime_24h_change.py验证修复效果

### v2.1.0 (2025-01-11)
- ✅ 修复多Token群发功能
- ✅ 修复24小时涨跌幅计算问题
- ✅ 删除重复的方法定义
- ✅ 改进价格变化计算逻辑
- ✅ 添加测试脚本验证功能

### v2.0.0 (2025-01-11)
- ✅ 新增资金流向检测功能
- ✅ 新增主力资金监控功能  
- ✅ 新增移动止盈追踪功能
- ✅ 扩展警报消息格式
- ✅ 添加可配置参数
- ✅ 完善测试脚本
- ✅ 修复资金流向计算bug
- ✅ 优化警报触发逻辑

---

**开发者：** Trae AI Assistant  
**更新时间：** 2025年1月11日  
**版本：** v2.0.0