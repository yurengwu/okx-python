#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKX加密货币交易分析系统
使用DeepSeek AI进行智能分析，每小时提供交易建议

项目结构:
- core: 核心模块（配置、数据库、数据存储）
- trading: 交易模块（OKX客户端、交易分析器、调度器）
- analysis: 分析模块（AI分析、技术指标、预测模型、胜率分析）
- monitoring: 监控通知模块（WebSocket监控、Server酱通知）
- utils: 工具模块（IP检测等）
- scripts: 脚本模块（各种检查和测试脚本）
"""

__version__ = "1.0.0"
__author__ = "Trading Analysis System"

# 导入主要模块
from .core import Config, TradingDatabase, DataStorageManager
from .trading import OKXClient, TradingAnalyzer, TradingScheduler
from .analysis import DeepSeekAnalyzer, EnhancedTechnicalIndicators, TradingPredictionModel, WinRateAnalyzer
from .monitoring import WebSocketMonitor, ServerChanNotifier
from .utils import IPDetector

__all__ = [
    # Core modules
    'Config',
    'TradingDatabase',
    'DataStorageManager',
    
    # Trading modules
    'OKXClient',
    'TradingAnalyzer',
    'TradingScheduler',
    
    # Analysis modules
    'DeepSeekAnalyzer',
    'EnhancedTechnicalIndicators',
    'TradingPredictionModel',
    'WinRateAnalyzer',
    
    # Monitoring modules
    'WebSocketMonitor',
    'ServerChanNotifier',
    
    # Utils
    'IPDetector'
]