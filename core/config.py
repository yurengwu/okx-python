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
    # 默认交易对列表（作为备用）
    DEFAULT_TRADING_PAIRS = [
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
    ]
    
    # 动态交易对配置
    MAX_TRADING_PAIRS = int(os.getenv('MAX_TRADING_PAIRS', '20'))  # 最大分析交易对数量
    MIN_VOLUME_24H = float(os.getenv('MIN_VOLUME_24H', '1000000'))  # 最小24小时成交量（USDT）
    
    # 固定交易对配置（可通过环境变量配置，用逗号分隔）
    FIXED_TRADING_PAIRS = os.getenv('FIXED_TRADING_PAIRS', 'BTC-USDT-SWAP,ETH-USDT-SWAP').split(',') if os.getenv('FIXED_TRADING_PAIRS') else ['BTC-USDT-SWAP', 'ETH-USDT-SWAP']
    
    @classmethod
    def get_trading_pairs(cls, okx_client=None):
        """动态获取交易对列表"""
        if okx_client is None:
            # 如果没有提供OKX客户端，返回默认列表
            return cls.DEFAULT_TRADING_PAIRS
        
        try:
            # 获取所有USDT永续合约
            all_symbols = okx_client.get_usdt_swap_symbols()
            
            if not all_symbols:
                return cls.DEFAULT_TRADING_PAIRS
            
            # 使用可配置的固定交易对
            fixed_pairs = [pair.strip() for pair in cls.FIXED_TRADING_PAIRS if pair.strip()]
            final_pairs = []
            
            # 转换固定交易对格式：BTC-USDT-SWAP -> BTC/USDT:USDT
            def convert_swap_format(swap_symbol):
                if swap_symbol.endswith('-SWAP'):
                    base_quote = swap_symbol[:-5]  # 移除 '-SWAP'
                    if '-USDT' in base_quote:
                        base = base_quote.replace('-USDT', '')
                        return f"{base}/USDT:USDT"
                return swap_symbol
            
            # 添加固定的交易对（如果存在）
            for pair in fixed_pairs:
                converted_pair = convert_swap_format(pair)
                if converted_pair in all_symbols:
                    final_pairs.append(converted_pair)
            
            # 计算还需要多少个交易对来达到20个
            remaining_slots = cls.MAX_TRADING_PAIRS - len(final_pairs)
            
            if remaining_slots > 0:
                # 获取其他交易对的24小时成交量数据并排序
                volume_data = []
                for symbol in all_symbols[:50]:  # 限制查询数量以提高性能
                    # 跳过已经固定的交易对
                    if symbol in final_pairs:
                        continue
                        
                    try:
                        ticker = okx_client.get_ticker(symbol)
                        if ticker and ticker.get('volume_24h'):
                            volume_24h = float(ticker['volume_24h'])
                            if volume_24h >= cls.MIN_VOLUME_24H:
                                volume_data.append((symbol, volume_24h))
                    except Exception:
                        continue
                
                # 按成交量排序，取剩余槽位数量的活跃交易对
                volume_data.sort(key=lambda x: x[1], reverse=True)
                active_pairs = [pair[0] for pair in volume_data[:remaining_slots]]
                
                # 合并固定交易对和活跃交易对（确保不重复）
                for pair in active_pairs:
                    if pair not in final_pairs:
                        final_pairs.append(pair)
            
            return final_pairs if final_pairs else cls.DEFAULT_TRADING_PAIRS
            
        except Exception as e:
            print(f"动态获取交易对失败: {e}，使用默认列表")
            return cls.DEFAULT_TRADING_PAIRS
    
    # 保持向后兼容
    @property
    def TRADING_PAIRS(self):
        """向后兼容的交易对属性"""
        return self.DEFAULT_TRADING_PAIRS
    
    # 分析配置
    ANALYSIS_INTERVAL = 300  # 5分钟（秒）
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
    SERVERCHAN_SENDKEY = os.getenv('SERVERCHAN_SENDKEY', '')  # Server酱SendKey（主要token）
    SERVERCHAN_SENDKEYS = os.getenv('SERVERCHAN_SENDKEYS', '')  # Server酱多个SendKey（逗号分隔）
    ENABLE_SERVERCHAN_NOTIFICATION = os.getenv('ENABLE_SERVERCHAN_NOTIFICATION', 'False').lower() == 'true'
    
    @classmethod
    def get_serverchan_tokens(cls):
        """获取所有Server酱token列表"""
        tokens = []
        
        # 添加主要token
        if cls.SERVERCHAN_SENDKEY:
            tokens.append(cls.SERVERCHAN_SENDKEY)
        
        # 添加多个token
        if cls.SERVERCHAN_SENDKEYS:
            additional_tokens = [token.strip() for token in cls.SERVERCHAN_SENDKEYS.split(',') if token.strip()]
            tokens.extend(additional_tokens)
        
        # 去重
        return list(set(tokens))
    
    # WebSocket实时监控配置
    ENABLE_WEBSOCKET_MONITOR = os.getenv('ENABLE_WEBSOCKET_MONITOR', 'False').lower() == 'true'
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'wss://ws.okx.com:8443/ws/v5/public')
    
    # 波动率检测配置
    VOLATILITY_THRESHOLD = float(os.getenv('VOLATILITY_THRESHOLD', '2.5'))  # Z-score阈值
    VOLATILITY_WINDOW_SIZE = int(os.getenv('VOLATILITY_WINDOW_SIZE', '20'))  # 滑动窗口大小
    VOLUME_SPIKE_MULTIPLIER = float(os.getenv('VOLUME_SPIKE_MULTIPLIER', '3.0'))  # 成交量异常倍数
    
    # 实时警报配置
    ALERT_COOLDOWN_MINUTES = int(os.getenv('ALERT_COOLDOWN_MINUTES', '5'))  # 警报冷却时间（分钟）
    ENABLE_VOLATILITY_ALERTS = os.getenv('ENABLE_VOLATILITY_ALERTS', 'True').lower() == 'true'
    ENABLE_VOLUME_ALERTS = os.getenv('ENABLE_VOLUME_ALERTS', 'True').lower() == 'true'
    
    # 资金流向监控配置
    ENABLE_FUND_FLOW_ALERTS = os.getenv('ENABLE_FUND_FLOW_ALERTS', 'True').lower() == 'true'
    FUND_FLOW_THRESHOLD = float(os.getenv('FUND_FLOW_THRESHOLD', '1000000'))  # 资金异动阈值（USDT）
    FUND_FLOW_WINDOW_SIZE = int(os.getenv('FUND_FLOW_WINDOW_SIZE', '100'))  # 资金流向窗口大小（增加以支持24小时数据）
    
    # 移动止盈配置
    ENABLE_MOVING_STOP_PROFIT = os.getenv('ENABLE_MOVING_STOP_PROFIT', 'True').lower() == 'true'
    MAX_GAIN_THRESHOLD = float(os.getenv('MAX_GAIN_THRESHOLD', '10.0'))  # 开始追踪的最小涨幅（%）
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '16.67'))  # 移动止盈回撤比例（%）
    
    # 主力资金监控配置
    MAIN_FUND_ESCAPE_THRESHOLD = float(os.getenv('MAIN_FUND_ESCAPE_THRESHOLD', '0.8'))  # 主力资金出逃阈值