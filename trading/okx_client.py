import ccxt
import pandas as pd
from typing import List, Dict, Optional
from loguru import logger
from core.config import Config
import time

class OKXClient:
    def __init__(self):
        """初始化OKX客户端"""
        self.exchange = ccxt.okx({
            'apiKey': Config.OKX_API_KEY,
            'secret': Config.OKX_SECRET_KEY,
            'password': Config.OKX_PASSPHRASE,
            'sandbox': Config.OKX_SANDBOX,
            'enableRateLimit': True,
            'timeout': 30000,  # 30秒超时
            'proxies': {
                'http': 'http://127.0.0.1:7890',
                'https': 'http://127.0.0.1:7890'
            },
            'options': {
                'defaultType': 'swap',  # 设置默认为永续合约
            }
        })
        
    def get_usdt_swap_symbols(self) -> List[str]:
        """获取所有USDT结算的永续合约交易对"""
        try:
            markets = self.exchange.load_markets()
            usdt_swaps = []
            
            for symbol, market in markets.items():
                # 检查是否为永续合约且以USDT结算
                if (market.get('type') == 'swap' and 
                    market.get('settle') == 'USDT' and 
                    market.get('active', False)):
                    usdt_swaps.append(symbol)
            
            logger.info(f"找到 {len(usdt_swaps)} 个USDT永续合约交易对")
            return usdt_swaps
            
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            return []
    
    def get_kline_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"获取 {symbol} K线数据成功，共 {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取 {symbol} K线数据失败: {e}")
            return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """获取实时价格信息"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last_price': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'volume_24h': ticker.get('baseVolume', 0),
                'change_24h': ticker.get('change'),
                'percentage_24h': ticker.get('percentage')
            }
        except Exception as e:
            logger.error(f"获取 {symbol} 价格信息失败: {e}")
            return None
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """获取订单簿数据"""
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit)
            return {
                'symbol': symbol,
                'bids': order_book['bids'][:limit],
                'asks': order_book['asks'][:limit],
                'timestamp': order_book['timestamp']
            }
        except Exception as e:
            logger.error(f"获取 {symbol} 订单簿失败: {e}")
            return None
    
    def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """获取资金费率"""
        try:
            funding_rate = self.exchange.fetch_funding_rate(symbol)
            return {
                'symbol': symbol,
                'funding_rate': funding_rate.get('fundingRate'),
                'next_funding_time': funding_rate.get('fundingDatetime')
            }
        except Exception as e:
            logger.error(f"获取 {symbol} 资金费率失败: {e}")
            return None
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        """获取多个交易对的市场数据"""
        market_data = {}
        
        for symbol in symbols:
            try:
                # 获取K线数据
                kline_data = self.get_kline_data(symbol, Config.TIMEFRAME, Config.KLINE_LIMIT)
                
                # 获取实时价格
                ticker_data = self.get_ticker(symbol)
                
                # 获取资金费率
                funding_data = self.get_funding_rate(symbol)
                
                if kline_data is not None:
                    market_data[symbol] = {
                        'kline': kline_data,
                        'ticker': ticker_data,
                        'funding': funding_data
                    }
                    
            except Exception as e:
                logger.error(f"获取 {symbol} 市场数据失败: {e}")
                continue
        
        return market_data
    
    def test_connection(self) -> bool:
        """测试API连接是否正常"""
        try:
            # 测试获取服务器时间 - 使用公共API，不需要认证
            logger.info("正在测试OKX API连接...")
            
            # 尝试加载市场数据来测试连接
            markets = self.exchange.load_markets()
            if markets:
                logger.info(f"OKX API连接正常，加载了 {len(markets)} 个市场")
                return True
            return False
        except ccxt.NetworkError as e:
            logger.error(f"网络连接错误: {e}")
            return False
        except ccxt.ExchangeError as e:
            logger.error(f"交易所API错误: {e}")
            return False
        except Exception as e:
            logger.error(f"OKX API连接测试失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            return False
    
    def validate_symbol(self, symbol: str) -> bool:
        """验证交易对是否有效"""
        try:
            markets = self.exchange.load_markets()
            return symbol in markets and markets[symbol].get('active', False)
        except Exception as e:
            logger.error(f"验证交易对 {symbol} 失败: {e}")
            return False
    
    def get_instruments(self, inst_type: str = 'SWAP') -> List[Dict]:
        """获取交易工具信息"""
        try:
            # 使用OKX的公共API获取交易工具信息
            response = self.exchange.public_get_public_instruments({
                'instType': inst_type
            })
            
            if response.get('code') == '0':
                return response.get('data', [])
            else:
                logger.error(f"获取交易工具失败: {response.get('msg', 'Unknown error')}")
                return []
                
        except Exception as e:
            logger.error(f"获取交易工具信息失败: {e}")
            # 备用方法：使用ccxt的load_markets
            try:
                markets = self.exchange.load_markets()
                instruments = []
                for symbol, market in markets.items():
                    if market.get('type') == inst_type.lower():
                        instruments.append({
                            'instId': symbol,
                            'instType': inst_type,
                            'baseCcy': market.get('base'),
                            'quoteCcy': market.get('quote'),
                            'settleCcy': market.get('settle'),
                            'state': 'live' if market.get('active') else 'suspend'
                        })
                return instruments
            except Exception as e2:
                logger.error(f"备用方法也失败: {e2}")
                return []
    
    def get_exchange_info(self) -> Dict:
        """获取交易所基本信息"""
        try:
            return {
                'name': self.exchange.name,
                'id': self.exchange.id,
                'has_fetch_ohlcv': self.exchange.has['fetchOHLCV'],
                'has_fetch_ticker': self.exchange.has['fetchTicker'],
                'has_fetch_funding_rate': self.exchange.has.get('fetchFundingRate', False),
                'rate_limit': self.exchange.rateLimit,
                'sandbox': self.exchange.sandbox
            }
        except Exception as e:
            logger.error(f"获取交易所信息失败: {e}")
            return {}