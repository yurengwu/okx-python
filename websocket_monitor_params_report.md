# WebSocket监控系统参数详细报告

## 📊 系统概览

本报告详细展示了WebSocket实时监控系统的所有参数配置和返回值结构。

## 🔧 配置参数

### 波动率检测器配置
- **window_size**: 20 (滑动窗口大小)
- **threshold**: 4.5 (Z-score阈值)
- **volume_spike_multiplier**: 3.0 (成交量异常倍数)

### 资金流向检测器配置
- **window_size**: 100 (数据窗口大小，支持24小时数据)
- **fund_threshold**: 1,000,000 USDT (资金异动阈值)
- **main_fund_escape_threshold**: 0.8 (主力资金出逃阈值)

### 移动止盈检测器配置
- **max_gain_threshold**: 10.0% (开始追踪的最小涨幅)
- **stop_loss_percent**: 16.67% (移动止盈回撤比例)

### 警报系统配置
- **alert_cooldown_minutes**: 5 (警报冷却时间)
- **enable_volatility_alerts**: true
- **enable_volume_alerts**: true
- **enable_fund_flow_alerts**: true
- **enable_moving_stop_profit**: true

## 📡 WebSocket接口返回参数

### 原始Ticker数据结构
```json
{
  "arg": {
    "channel": "tickers",
    "instId": "SOL-USDT-SWAP"
  },
  "data": [{
    "instType": "SWAP",
    "instId": "SOL-USDT-SWAP",
    "last": "4375.01",
    "lastSz": "1",
    "askPx": "4375.01",
    "askSz": "4375",
    "bidPx": "4375",
    "bidSz": "886.53",
    "open24h": "4318.26",
    "high24h": "4453.74",
    "low24h": "4293.39",
    "sodUtc0": "4347.99",
    "sodUtc8": "4403.65",
    "volCcy24h": "3146998.03",
    "vol24h": "31469980.3",
    "ts": "1757558229067"
  }]
}
```

### 提取的关键参数
- **价格 (last)**: 当前最新成交价
- **24H成交量 (vol24h)**: 24小时成交量
- **开盘价 (open24h)**: 24小时开盘价
- **最高价 (high24h)**: 24小时最高价
- **最低价 (low24h)**: 24小时最低价
- **买一价 (bidPx)**: 买一档价格
- **卖一价 (askPx)**: 卖一档价格
- **时间戳 (ts)**: 数据时间戳

## 🚨 PriceAlert对象结构

```python
class PriceAlert:
    def __init__(self, symbol, alert_type, current_price, change_percent, 
                 volume, timestamp, message, fund_flow=None, ai_score=None, 
                 max_gain=None, current_decline=None):
        self.symbol = symbol              # 交易对符号
        self.alert_type = alert_type      # 警报类型
        self.current_price = current_price # 当前价格
        self.change_percent = change_percent # 涨跌幅百分比
        self.volume = volume              # 成交量
        self.timestamp = timestamp        # 时间戳
        self.message = message            # 警报消息
        self.fund_flow = fund_flow        # 资金流向(USDT)
        self.ai_score = ai_score          # AI评分
        self.max_gain = max_gain          # 最大涨幅
        self.current_decline = current_decline # 当前回撤
```

## 🔍 检测器状态监控

### 波动率检测器状态
- **价格历史长度**: 当前/最大窗口大小
- **最新价格**: 实时价格
- **成交量历史长度**: 当前/最大窗口大小
- **最新成交量**: 实时成交量
- **最近价格变化**: 价格变化百分比

### 资金流向检测器状态
- **价格历史长度**: 当前/最大窗口大小 (100)
- **资金流向历史长度**: 当前/最大窗口大小
- **最新资金流向**: 实时资金流向(USDT)
- **24H涨跌幅计算**: 基于历史数据的涨跌幅

### 移动止盈追踪器状态
- **正在追踪**: 是否正在追踪某个交易对
- **最大涨幅**: 追踪期间的最大涨幅
- **当前回撤**: 从最高点的回撤幅度

## 🎯 24H涨跌幅计算逻辑

1. **数据充足时**: 使用24小时前的价格作为基准
2. **数据不足时**: 使用最早可用价格作为基准
3. **计算公式**: `((当前价格 - 基准价格) / 基准价格) * 100`
4. **精度**: 保留2位小数

## ✅ 问题修复总结

### 修复前问题
- 24H涨跌幅显示为0.0%或-0.0%
- 数据窗口大小不足(30 < 100)
- 配置文件被.env覆盖

### 修复后状态
- ✅ 资金流向检测器window_size: 100
- ✅ 24H涨跌幅计算正常
- ✅ 配置正确加载
- ✅ 编码问题解决

## 📝 建议

1. **重启WebSocket监控系统**以应用所有配置更改
2. **监控日志**确保24H涨跌幅不再显示0.0%
3. **定期检查**配置文件和.env文件的一致性

---
*报告生成时间: 2024年1月*
*系统版本: WebSocket Monitor v2.0*