import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # OKX API配置
    OKX_API_KEY = os.getenv('OKX_API_KEY', '')
    OKX_SECRET_KEY = os.getenv('OKX_SECRET_KEY', '')
    OKX_PASSPHRASE = os.getenv('OKX_PASSPHRASE', '')
    OKX_SANDBOX = os.getenv('OKX_SANDBOX', 'False').lower() == 'true'
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    
    # 交易对配置 (OKX永续合约格式)
    TRADING_PAIRS = [
        'BTC-USDT-SWAP',   # BTC永续合约
        'ETH-USDT-SWAP',   # ETH永续合约
        'SOL-USDT-SWAP',   # SOL永续合约
        'DOGE-USDT-SWAP',  # DOGE永续合约
        'OKB-USDT-SWAP',   # OKB永续合约
        'XRP-USDT-SWAP',   # XRP永续合约
        'LINEA-USDT-SWAP', # LINEA永续合约
        'TON-USDT-SWAP',   # TON永续合约
        'LINK-USDT-SWAP',  # LINK永续合约
        'ADA-USDT-SWAP'    # ADA永续合约
        # 注意：WLFL可能不是有效的OKX交易对，已排除
        # 如需添加其他币种，请确认其在OKX上的正确交易对格式
    ]
    
    # 分析配置
    ANALYSIS_INTERVAL = 3600  # 1小时（秒）
    KLINE_LIMIT = 300  # K线数据条数（公共接口限制）
    TIMEFRAME = '1h'  # 时间周期
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'trading_analysis.log'
    
    # 风险管理
    MAX_RISK_PERCENTAGE = 2.0  # 最大风险百分比
    STOP_LOSS_PERCENTAGE = 1.5  # 止损百分比
    TAKE_PROFIT_PERCENTAGE = 3.0  # 止盈百分比
    
    # Server酱通知配置
    SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', '')  # Server酱SendKey
    ENABLE_SERVERCHAN_NOTIFICATION = os.getenv('ENABLE_SERVERCHAN_NOTIFICATION', 'False').lower() == 'true'