import ccxt
import pandas as pd
from typing import List, Dict, Optional
from loguru import logger
from core.config import Config
import time

class OKXClient:
    def __init__(self):
        """初始化OKX客户端"""
        # 基础配置
        config = {
            'apiKey': Config.OKX_API_KEY,
            'secret': Config.OKX_SECRET_KEY,
            'password': Config.OKX_PASSPHRASE,
            'sandbox': Config.OKX_SANDBOX,
            'enableRateLimit': True,
            'timeout': 30000,  # 30秒超时
            'options': {
                'defaultType': 'swap',  # 设置默认为永续合约
            }
        }
        
        # 检查是否使用代理
        if Config.USE_PROXY:
            # CCXT支持的代理配置方式
            proxy_url = f"{Config.PROXY_TYPE}://{Config.PROXY_HOST}:{Config.PROXY_PORT}"
            config['proxies'] = {
                'http': proxy_url,
                'https': proxy_url
            }
            logger.info(f"使用代理配置连接OKX: {proxy_url}")
        else:
            logger.info("直接连接OKX（不使用代理）")
            
        try:
            self.exchange = ccxt.okx(config)
            logger.info("OKX客户端初始化成功")
        except Exception as e:
            logger.error(f"OKX客户端初始化失败: {e}")
            # 如果代理连接失败，尝试不使用代理
            if Config.USE_PROXY:
                logger.warning("代理连接失败，尝试直接连接")
                # 移除代理配置
                config.pop('proxies', None)
                try:
                    self.exchange = ccxt.okx(config)
                    logger.info("直接连接OKX成功")
                except Exception as e2:
                    logger.error(f"直接连接也失败: {e2}")
                    raise e2
            else:
                raise e
        
    def get_usdt_swap_symbols(self) -> List[str]:
        """获取所有USDT结算的永续合约交易对"""
        try:
            # 使用OKX的公共API直接获取交易工具信息，避免load_markets的bug
            response = self.exchange.public_get_public_instruments({
                'instType': 'SWAP'
            })
            
            if response.get('code') != '0':
                logger.error(f"获取交易工具失败: {response.get('msg', 'Unknown error')}")
                return []
            
            instruments = response.get('data', [])
            usdt_swaps = []
            
            for instrument in instruments:
                # 检查是否为USDT结算的永续合约
                if (instrument.get('settleCcy') == 'USDT' and 
                    instrument.get('state') == 'live'):
                    # 直接使用BTC-USDT-SWAP格式
                    inst_id = instrument.get('instId', '')
                    if inst_id.endswith('-SWAP'):
                        usdt_swaps.append(inst_id)
            
            logger.info(f"找到 {len(usdt_swaps)} 个USDT永续合约交易对")
            return usdt_swaps
            
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            # 返回一些常用的交易对作为fallback
            fallback_symbols = [
                'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP',
                'ADA-USDT-SWAP', 'DOT-USDT-SWAP', 'LINK-USDT-SWAP'
            ]
            logger.info(f"使用fallback交易对: {len(fallback_symbols)} 个")
            return fallback_symbols
    
    def _convert_timeframe_to_okx_format(self, timeframe: str) -> str:
        """转换时间周期格式为OKX格式"""
        timeframe_map = {
            '1m': '1m',
            '3m': '3m', 
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1H',
            '2h': '2H',
            '4h': '4H',
            '6h': '6H',
            '12h': '12H',
            '1d': '1D',
            '1w': '1W',
            '1M': '1M'
        }
        return timeframe_map.get(timeframe, '1H')
    
    def get_kline_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> Optional[pd.DataFrame]:
        """获取K线数据 - 使用OKX原生API"""
        try:
            # 直接使用BTC-USDT-SWAP格式
            inst_id = symbol
            
            # 转换时间周期格式
            okx_timeframe = self._convert_timeframe_to_okx_format(timeframe)
            
            # 使用OKX原生API获取K线数据
            response = self.exchange.public_get_market_candles({
                'instId': inst_id,
                'bar': okx_timeframe,
                'limit': str(limit)
            })
            
            if response.get('code') != '0':
                logger.error(f"获取K线数据失败: {response.get('msg', 'Unknown error')}")
                return None
            
            candles_data = response.get('data', [])
            if not candles_data:
                logger.warning(f"没有获取到 {symbol} 的K线数据")
                return None
            
            # 转换数据格式
            df_data = []
            for candle in candles_data:
                df_data.append({
                    'timestamp': int(candle[0]),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
            
            df = pd.DataFrame(df_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df.sort_index()  # 确保时间顺序正确
            
            logger.info(f"获取 {symbol} K线数据成功，共 {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取 {symbol} K线数据失败: {e}")
            return None
    
    def _convert_symbol_to_okx_format(self, symbol: str) -> str:
        """统一使用BTC-USDT-SWAP格式，不做转换"""
        return symbol
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """获取实时价格信息 - 使用OKX原生API"""
        try:
            # 直接使用BTC-USDT-SWAP格式
            inst_id = symbol
            
            # 使用OKX原生API获取ticker数据
            response = self.exchange.public_get_market_ticker({
                'instId': inst_id
            })
            
            if response.get('code') != '0':
                logger.error(f"获取价格信息失败: {response.get('msg', 'Unknown error')}")
                return None
            
            ticker_data = response.get('data', [])
            if not ticker_data:
                logger.warning(f"没有获取到 {symbol} 的价格信息")
                return None
            
            ticker = ticker_data[0]
            return {
                'symbol': symbol,
                'last_price': float(ticker.get('last', 0)),
                'bid': float(ticker.get('bidPx', 0)) if ticker.get('bidPx') else None,
                'ask': float(ticker.get('askPx', 0)) if ticker.get('askPx') else None,
                'volume_24h': float(ticker.get('vol24h', 0)),
                'change_24h': float(ticker.get('chg24h', 0)),
                'percentage_24h': float(ticker.get('chgUtc0', 0))
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
        """获取资金费率 - 使用OKX原生API"""
        try:
            # 直接使用BTC-USDT-SWAP格式
            inst_id = symbol
            
            # 使用OKX原生API获取资金费率
            response = self.exchange.public_get_public_funding_rate({
                'instId': inst_id
            })
            
            if response.get('code') != '0':
                logger.error(f"获取资金费率失败: {response.get('msg', 'Unknown error')}")
                return None
            
            funding_data = response.get('data', [])
            if not funding_data:
                logger.warning(f"没有获取到 {symbol} 的资金费率")
                return None
            
            funding = funding_data[0]
            return {
                'symbol': symbol,
                'funding_rate': float(funding.get('fundingRate', 0)),
                'next_funding_time': funding.get('nextFundingTime')
            }
        except Exception as e:
            logger.error(f"获取 {symbol} 资金费率失败: {e}")
            return None
    
    def get_market_data(self, symbols: List[str]) -> Dict:
        """获取多个交易对的市场数据"""
        market_data = {}
        failed_symbols = []
        
        logger.info(f"开始获取 {len(symbols)} 个交易对的市场数据")
        
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
                    logger.info(f"成功获取 {symbol} 的市场数据")
                else:
                    failed_symbols.append(symbol)
                    logger.warning(f"跳过 {symbol}：K线数据获取失败")
                    
            except Exception as e:
                failed_symbols.append(symbol)
                logger.error(f"获取 {symbol} 市场数据失败: {e}")
                continue
        
        logger.info(f"市场数据获取完成：成功 {len(market_data)} 个，失败 {len(failed_symbols)} 个")
        if failed_symbols:
            logger.warning(f"获取失败的交易对: {failed_symbols}")
        
        return market_data
    
    def test_connection(self) -> bool:
        """测试API连接是否正常"""
        try:
            # 测试获取服务器时间 - 使用公共API，不需要认证
            logger.info("正在测试OKX API连接...")
            
            # 使用fetch_time来测试连接，这是最简单的公共API
            server_time = self.exchange.fetch_time()
            if server_time:
                logger.info(f"OKX API连接正常，服务器时间: {server_time}")
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
            # 获取所有可用的交易对
            available_symbols = self.get_usdt_swap_symbols()
            return symbol in available_symbols
        except Exception as e:
            logger.error(f"验证交易对 {symbol} 失败: {e}")
            # 如果验证失败，对常用交易对返回True
            common_symbols = [
                'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT',
                'ADA/USDT:USDT', 'DOT/USDT:USDT', 'LINK/USDT:USDT'
            ]
            return symbol in common_symbols
    
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
            # 返回空列表，避免使用有问题的load_markets
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