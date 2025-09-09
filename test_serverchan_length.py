#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Server酱消息长度和内容
"""

import json
from serverchan_notifier import ServerChanNotifier
from config import Config

def test_message_length():
    """测试Server酱消息长度"""
    print("=== Server酱消息长度测试 ===")
    
    # 加载最新的分析结果
    try:
        with open('analysis_results/analysis_20250909_155030.json', 'r', encoding='utf-8') as f:
            analysis_result = json.load(f)
    except Exception as e:
        print(f"加载分析结果失败: {e}")
        return
    
    # 创建Server酱通知器
    if not Config.SERVERCHAN_SENDKEY:
        print("❌ Server酱SendKey未配置")
        return
        
    notifier = ServerChanNotifier(Config.SERVERCHAN_SENDKEY)
    
    # 格式化消息
    try:
        title, content = notifier.format_trading_analysis(analysis_result)
        
        print(f"标题长度: {len(title)} 字符")
        print(f"内容长度: {len(content)} 字符")
        print(f"总长度: {len(title) + len(content)} 字符")
        
        print("\n=== 标题 ===")
        print(title)
        
        print("\n=== 内容前500字符 ===")
        print(content[:500])
        
        print("\n=== 内容后500字符 ===")
        print(content[-500:])
        
        # 统计交易对数量
        recommendations = analysis_result.get('recommendations', {})
        print(f"\n分析结果中的交易对数量: {len(recommendations)}")
        
        # 检查内容中包含的交易对
        content_pairs = []
        for symbol in recommendations.keys():
            symbol_name = symbol.replace('-USDT-SWAP', '')
            if f"【{symbol_name}】" in content:
                content_pairs.append(symbol_name)
        
        print(f"通知内容中包含的交易对数量: {len(content_pairs)}")
        print(f"通知内容中的交易对: {content_pairs}")
        
        # 检查是否有遗漏的交易对
        missing_pairs = []
        for symbol in recommendations.keys():
            symbol_name = symbol.replace('-USDT-SWAP', '')
            if symbol_name not in content_pairs:
                missing_pairs.append(symbol_name)
        
        if missing_pairs:
            print(f"\n❌ 遗漏的交易对: {missing_pairs}")
        else:
            print(f"\n✅ 所有交易对都包含在通知中")
            
        # 检查Server酱消息长度限制
        print("\n=== Server酱限制检查 ===")
        if len(content) > 20000:  # Server酱单条消息限制约20KB
            print(f"⚠️ 消息可能超过Server酱长度限制 ({len(content)} > 20000)")
            print("建议优化消息格式或分批发送")
        else:
            print(f"✅ 消息长度在合理范围内 ({len(content)} <= 20000)")
            
    except Exception as e:
        print(f"格式化消息失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_message_length()