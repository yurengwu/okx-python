# OKX加密货币交易分析系统

基于DeepSeek AI的智能交易分析系统，自动获取OKX USDT永续合约数据并提供专业的交易建议。

## 🚀 功能特性

- **自动数据获取**: 实时获取OKX USDT永续合约交易数据
- **AI智能分析**: 集成DeepSeek AI进行深度市场分析
- **定时执行**: 每小时自动执行分析并生成报告
- **多种操作模式**: 支持单次分析、定时调度、交互模式
- **详细建议**: 提供具体的买入/卖出点位和风险评估
- **历史记录**: 保存分析历史，支持回顾和对比
- **风险管理**: 内置止损止盈建议和风险等级评估

## 📋 系统要求

- Python 3.8+
- OKX API账户和密钥
- DeepSeek API密钥
- 稳定的网络连接

## 🛠️ 安装步骤

### 1. 克隆或下载项目

```bash
# 如果是从git克隆
git clone <repository-url>
cd okx-trading-analyzer

# 或者直接在当前目录使用
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置API密钥

复制环境变量模板文件：
```bash
copy .env.example .env
```

编辑 `.env` 文件，填入你的API密钥：

```env
# OKX API配置
OKX_API_KEY=your_okx_api_key_here
OKX_SECRET_KEY=your_okx_secret_key_here
OKX_PASSPHRASE=your_okx_passphrase_here
OKX_SANDBOX=False

# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## 🔑 API密钥获取

### OKX API密钥

1. 登录 [OKX官网](https://www.okx.com)
2. 进入 "API管理" 页面
3. 创建新的API密钥
4. 记录 API Key、Secret Key 和 Passphrase
5. 确保API权限包含 "读取" 权限

### DeepSeek API密钥

1. 访问 [DeepSeek官网](https://www.deepseek.com)
2. 注册并登录账户
3. 进入API管理页面
4. 创建新的API密钥
5. 复制API密钥

## 🎯 使用方法

### 命令行模式

```bash
# 检查配置
python main.py --check

# 执行单次分析
python main.py --analyze

# 启动定时调度器（每小时执行）
python main.py --schedule

# 查看最新分析结果
python main.py --latest

# 查看分析历史
python main.py --history

# 显示帮助
python main.py --help
```

### 交互模式

```bash
# 启动交互模式
python main.py
```

在交互模式中，你可以：
- 选择不同的操作
- 实时查看分析结果
- 管理定时任务

## 📊 分析结果说明

系统会为每个交易对提供以下信息：

### 交易建议
- **操作方向**: 做多/做空/观望
- **入场点位**: 建议的买入/卖出价格
- **止损点位**: 风险控制价格
- **止盈点位**: 获利了结价格
- **风险等级**: 1-5级风险评估
- **信心度**: 1-10级建议可信度

### 技术分析
- 价格趋势分析
- 支撑位和阻力位
- 技术指标解读
- 市场情绪判断

## 📁 项目结构

```
爬虫/
├── main.py                 # 主程序入口
├── config.py              # 配置文件
├── okx_client.py          # OKX API客户端
├── deepseek_analyzer.py   # DeepSeek分析器
├── trading_analyzer.py    # 交易分析器
├── scheduler.py           # 定时调度器
├── requirements.txt       # 依赖包列表
├── .env.example          # 环境变量模板
├── .env                  # 环境变量文件（需要创建）
├── README.md             # 使用说明
├── trading_analysis.log  # 日志文件
└── analysis_results/     # 分析结果目录
    ├── analysis_20240101_120000.json
    ├── analysis_20240101_120000.txt
    └── ...
```

## ⚙️ 配置说明

### 交易对配置

在 `config.py` 中可以修改要分析的交易对：

```python
TRADING_PAIRS = [
    'BTC-USDT-SWAP',
    'ETH-USDT-SWAP',
    'SOL-USDT-SWAP',
    'BNB-USDT-SWAP',
    'XRP-USDT-SWAP'
]
```

### 分析参数配置

```python
ANALYSIS_INTERVAL = 3600  # 分析间隔（秒）
KLINE_LIMIT = 100        # K线数据条数
TIMEFRAME = '1h'         # 时间周期
```

### 风险管理配置

```python
MAX_RISK_PERCENTAGE = 2.0      # 最大风险百分比
STOP_LOSS_PERCENTAGE = 1.5     # 止损百分比
TAKE_PROFIT_PERCENTAGE = 3.0   # 止盈百分比
```

## 📝 日志和结果

### 日志文件
- 位置: `trading_analysis.log`
- 自动轮转: 每天一个新文件
- 保留期: 30天

### 分析结果
- JSON格式: `analysis_results/analysis_YYYYMMDD_HHMMSS.json`
- 文本格式: `analysis_results/analysis_YYYYMMDD_HHMMSS.txt`

## 🚨 注意事项

### 风险提示
- **投资有风险**: 本系统仅提供分析建议，不构成投资建议
- **谨慎操作**: 请根据自己的风险承受能力进行交易
- **资金管理**: 建议使用小额资金进行测试
- **及时止损**: 严格执行止损策略

### 使用建议
- 首次使用建议先进行单次分析测试
- 定期检查API密钥的有效性
- 关注市场重大事件对分析结果的影响
- 结合其他分析工具进行综合判断

### 技术限制
- API调用频率限制
- 网络连接稳定性要求
- DeepSeek API使用配额限制

## 🔧 故障排除

### 常见问题

1. **API连接失败**
   - 检查网络连接
   - 验证API密钥正确性
   - 确认API权限设置

2. **分析结果异常**
   - 检查DeepSeek API配额
   - 验证市场数据获取是否正常
   - 查看日志文件获取详细错误信息

3. **定时任务不执行**
   - 确认程序正在运行
   - 检查系统时间设置
   - 查看日志文件排查问题

### 获取帮助

如果遇到问题，可以：
1. 查看日志文件 `trading_analysis.log`
2. 运行配置检查 `python main.py --check`
3. 检查API密钥和网络连接

## 📄 许可证

本项目仅供学习和研究使用。使用本系统进行实际交易的风险由用户自行承担。

## 🤝 贡献

欢迎提交问题报告和功能建议！

---

**免责声明**: 本系统提供的分析和建议仅供参考，不构成投资建议。加密货币交易存在高风险，可能导致资金损失。请在充分了解风险的情况下谨慎投资。