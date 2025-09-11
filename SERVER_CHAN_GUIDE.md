# Server酱通知功能使用指南

## 📱 功能介绍

Server酱通知功能可以将OKX交易分析结果实时推送到您的微信，让您随时随地接收交易建议。

## 🔧 配置步骤

### 1. 获取SendKey
1. 访问 [Server酱官网](https://sct.ftqq.com/)
2. 使用微信扫码登录
3. 复制您的SendKey（格式如：SCT161736T...hRwS）

### 2. 配置环境变量
在 `.env` 文件中添加以下配置：
```
# Server酱通知配置
SERVERCHAN_SENDKEY=your_sendkey_here
# 多个token群发配置（逗号分隔，可选）
SERVERCHAN_SENDKEYS=token2,token3,token4
ENABLE_SERVERCHAN_NOTIFICATION=true
```

**多token群发说明：**
- `SERVERCHAN_SENDKEY`：主要token，必填
- `SERVERCHAN_SENDKEYS`：额外的token列表，用逗号分隔，可选
- 系统会自动向所有配置的token发送通知，实现群发功能
- 只要有一个token发送成功，就认为通知发送成功

## 🚀 使用方法

### 测试通知
```bash
# 命令行测试
python main.py --test-serverchan

# 交互模式测试
python main.py
# 选择选项 9
```

### 自动通知
每次执行分析时会自动发送通知：
```bash
# 单次分析（会自动发送通知）
python main.py --analyze

# 定时调度（每次分析都会发送通知）
python main.py --schedule
```

## 📋 通知内容

通知消息包含：
- 📊 **分析概览**：分析时间、交易对数量
- 💡 **操作建议**：BUY/SELL/HOLD 分布统计
- 📈 **关键指标**：平均风险等级、信心度
- 🎯 **具体建议**：每个交易对的详细分析
- ⚠️ **风险提示**：投资风险警告

## 🔍 故障排除

### 通知发送失败
1. 检查SendKey是否正确配置
2. 确认网络连接正常
3. 验证Server酱服务状态

### 配置检查
```bash
python main.py --check
```
查看配置状态，确保 `serverchan_configured: True`

## 📝 注意事项

1. **消息限制**：Server酱有日推送限制，请合理使用
2. **内容长度**：消息内容会自动截取，确保重要信息优先显示
3. **隐私安全**：SendKey请妥善保管，不要泄露给他人
4. **网络要求**：需要稳定的网络连接才能正常发送通知

## 🎉 成功示例

当看到以下日志时，说明通知发送成功：
```
✅ 测试通知发送成功！
   请检查您的微信是否收到测试消息
```

或在分析日志中看到：
```
INFO | Server酱通知发送成功: 🚀 交易分析报告 - 2025-09-09 12:46:18
```

---

💡 **提示**：首次使用建议先执行测试命令，确认通知功能正常后再启用自动分析。