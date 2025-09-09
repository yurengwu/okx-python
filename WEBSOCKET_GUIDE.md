# WebSocket实时监控系统使用指南

## 功能概述

WebSocket实时监控系统可以实时监控OKX交易所**所有USDT永续合约交易对**的市场数据（目前约243个交易对），当检测到以下情况时会自动发送通知：

- **价格剧烈波动**：当价格变化超过设定阈值时
- **成交量异常**：当成交量出现异常放大时
- **重大事件**：大单交易、异常价格跳跃等

## 配置说明

### 1. 环境变量配置

在 `.env` 文件中添加以下配置：

```env
# WebSocket实时监控
ENABLE_WEBSOCKET_MONITOR=true
WEBSOCKET_URL=wss://ws.okx.com:8443/ws/v5/public

# 波动率检测
VOLATILITY_THRESHOLD=0.05
VOLATILITY_WINDOW_SIZE=20
VOLUME_SPIKE_MULTIPLIER=3.0

# 实时警报
REALTIME_ALERT_ENABLED=true
ALERT_COOLDOWN_MINUTES=5
MAX_ALERTS_PER_HOUR=10
```

### 2. 配置参数说明

- `ENABLE_WEBSOCKET_MONITOR`: 是否启用WebSocket监控
- `WEBSOCKET_URL`: OKX WebSocket API地址
- `VOLATILITY_THRESHOLD`: 波动率阈值（5%表示价格变化超过5%时触发警报）
- `VOLATILITY_WINDOW_SIZE`: 波动率计算窗口大小
- `VOLUME_SPIKE_MULTIPLIER`: 成交量异常倍数（3.0表示成交量超过平均值3倍时触发）
- `REALTIME_ALERT_ENABLED`: 是否启用实时警报
- `ALERT_COOLDOWN_MINUTES`: 警报冷却时间（分钟）
- `MAX_ALERTS_PER_HOUR`: 每小时最大警报数量

## 使用方法

### 1. 命令行启动

```bash
# 启动WebSocket实时监控
python main.py --websocket

# 测试WebSocket连接
python main.py --test-websocket
```

### 2. 交互模式

```bash
python main.py
```

然后选择：
- `10` - 启动WebSocket实时监控
- `11` - 测试WebSocket连接

## 监控数据

系统会自动获取并监控所有USDT永续合约交易对的以下数据：

1. **实时价格**：最新成交价格
2. **成交量**：24小时成交量
3. **价格变化**：价格波动幅度
4. **异常检测**：识别异常交易行为

**注意**：系统启动时会自动从OKX API获取最新的交易对列表，无需手动配置。如果API获取失败，会自动使用备用的主要交易对列表。

## 通知方式

当检测到异常情况时，系统会通过以下方式发送通知：

1. **Server酱推送**：发送到微信（需要配置SERVERCHAN_SENDKEY）
2. **控制台输出**：实时显示警报信息
3. **日志记录**：记录所有警报到日志文件

## 注意事项

1. **网络连接**：确保网络连接稳定，WebSocket需要持续连接
2. **API限制**：注意OKX API的连接限制和频率限制
3. **资源消耗**：长时间运行会消耗一定的CPU和内存资源
4. **通知配置**：建议配置Server酱通知，以便及时接收警报

## 故障排除

### 连接失败
- 检查网络连接
- 确认WebSocket URL是否正确
- 查看防火墙设置

### 无法接收通知
- 检查Server酱配置
- 确认SERVERCHAN_SENDKEY是否正确
- 查看通知发送日志

### 频繁断线
- 检查网络稳定性
- 适当调整重连间隔
- 查看错误日志

## 技术支持

如遇到问题，请查看：
1. 控制台输出信息
2. 日志文件（logs目录）
3. 配置文件是否正确