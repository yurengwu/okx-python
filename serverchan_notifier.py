#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server酱微信通知模块
用于发送交易分析结果到微信
"""

import requests
import json
from typing import Dict, Optional
from loguru import logger
from datetime import datetime

class ServerChanNotifier:
    def __init__(self, sendkey: str):
        """
        初始化Server酱通知器
        
        Args:
            sendkey: Server酱的SendKey
        """
        self.sendkey = sendkey
        self.base_url = "https://sctapi.ftqq.com"
        
    def send_notification(self, title: str, content: str, short: Optional[str] = None) -> Dict:
        """
        发送通知到微信
        
        Args:
            title: 通知标题
            content: 通知内容（支持Markdown格式）
            short: 消息卡片内容（可选）
            
        Returns:
            Dict: 发送结果
        """
        if not self.sendkey:
            logger.error("Server酱SendKey未配置")
            return {"success": False, "error": "SendKey未配置"}
            
        url = f"{self.base_url}/{self.sendkey}.send"
        
        data = {
            "title": title,
            "desp": content
        }
        
        if short:
            data["short"] = short
            
        # 添加调试信息
        logger.info(f"准备发送Server酱通知: 标题长度={len(title)}, 内容长度={len(content)}")
        
        # 检查内容中的交易对数量
        pair_count = content.count('## 📊 【')
        logger.info(f"通知内容包含 {pair_count} 个交易对")
            
        try:
            response = requests.post(url, data=data, timeout=10)
            result = response.json()
            
            # 记录完整的响应信息
            logger.info(f"Server酱响应: {result}")
            
            if result.get("code") == 0:
                logger.info(f"Server酱通知发送成功: {title}")
                return {"success": True, "message": "通知发送成功", "response": result}
            else:
                error_msg = result.get("message", "未知错误")
                logger.error(f"Server酱通知发送失败: {error_msg}")
                return {"success": False, "error": error_msg, "response": result}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Server酱通知发送异常: {e}")
            return {"success": False, "error": str(e)}
            
    def format_trading_analysis(self, analysis_result: Dict) -> tuple:
        """
        格式化交易分析结果为通知内容
        
        Args:
            analysis_result: 分析结果字典
            
        Returns:
            tuple: (标题, 内容)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"🚀 交易分析报告 - {timestamp}"
        
        # 构建完整格式的内容
        content_lines = [
            "# 🚀 增强加密货币交易分析报告",
            f"**分析时间:** {timestamp}",
            ""
        ]
        
        # 添加市场概述
        market_overview = analysis_result.get('market_overview', '')
        if market_overview:
            content_lines.extend([
                "## 🌍 市场概述",
                f"{market_overview}",
                ""
            ])
        else:
            # 生成默认市场概述
            recommendations = analysis_result.get('recommendations', {})
            if recommendations:
                action_stats = {}
                for rec in recommendations.values():
                    action = rec.get('action', 'HOLD')
                    action_stats[action] = action_stats.get(action, 0) + 1
                
                overview_parts = []
                if action_stats.get('BUY', 0) > 0:
                    overview_parts.append("部分标的显示买入机会")
                if action_stats.get('SELL', 0) > 0:
                    overview_parts.append("部分标的存在卖出信号")
                if action_stats.get('HOLD', 0) > 0:
                    overview_parts.append("多数标的建议观望")
                
                market_desc = "，".join(overview_parts) if overview_parts else "市场整体呈现震荡格局"
                content_lines.extend([
                    "## 🌍 市场概述",
                    f"当前加密货币市场{market_desc}。技术指标显示分化明显，建议根据具体标的情况制定操作策略。",
                    ""
                ])
        
        # 添加具体交易对分析
        recommendations = analysis_result.get('recommendations', {})
        if recommendations:
            for symbol, rec in recommendations.items():
                symbol_name = symbol.replace('-USDT-SWAP', '')
                action = rec.get('action', 'HOLD')
                entry_price = rec.get('entry_price', 'N/A')
                stop_loss = rec.get('stop_loss', 'N/A')
                take_profit = rec.get('take_profit', 'N/A')
                risk_level = rec.get('risk_level', 'N/A')
                confidence = rec.get('confidence', 0)
                win_rate = rec.get('predicted_win_rate', 'N/A')
                technical_score = rec.get('technical_score', 'N/A')
                
                # 技术指标摘要
                technical_summary = rec.get('technical_summary', {})
                trend = technical_summary.get('trend', '震荡')
                momentum = technical_summary.get('momentum', '中性')
                volatility = technical_summary.get('volatility', '中等')
                volume = technical_summary.get('volume', '一般')
                
                # 支撑阻力位 - 修复字段名匹配问题
                key_levels = rec.get('key_levels', {})
                support_levels = key_levels.get('support', [])
                resistance_levels = key_levels.get('resistance', [])
                
                # 分析说明
                analysis_desc = rec.get('analysis', '技术指标显示中性信号，建议观望。')
                
                # 格式化支撑位和阻力位为更美观的显示
                support_str = ", ".join([f"{level:.2f}" if isinstance(level, (int, float)) else str(level) for level in support_levels]) if support_levels else "暂无明确支撑"
                resistance_str = ", ".join([f"{level:.2f}" if isinstance(level, (int, float)) else str(level) for level in resistance_levels]) if resistance_levels else "暂无明确阻力"
                
                # 格式化胜率显示
                if isinstance(win_rate, (int, float)):
                    win_rate_str = f"{win_rate*100:.1f}%" if win_rate <= 1 else f"{win_rate:.1f}%"
                else:
                    win_rate_str = str(win_rate)
                
                content_lines.extend([
                    f"## 📊 【{symbol_name}】",
                    f"**操作建议:** {self._get_action_emoji(action)} {action}",
                    "",
                    f"**入场点位:** {entry_price}",
                    "",
                    f"**止损点位:** {stop_loss}",
                    "",
                    f"**止盈点位:** {take_profit}",
                    "",
                    f"**风险等级:** {risk_level}/5 ⭐",
                    "",
                    f"**信心度:** {confidence}",
                    "",
                    f"**AI预测胜率:** {win_rate_str}",
                    "",
                    f"**技术指标评分:** {technical_score}",
                    "",
                    "### 📈 技术指标摘要",
                    f"- **趋势:** {trend}",
                    f"- **动量:** {momentum}",
                    f"- **波动率:** {volatility}",
                    f"- **成交量:** {volume}",
                    "",
                    "### 🎯 关键点位",
                    f"- **支撑位:** {support_str}",
                    f"- **阻力位:** {resistance_str}",
                    "",
                    "### 💡 分析说明",
                    f"{analysis_desc}",
                    "",
                    "---",
                     ""
                 ])
        
        # 添加汇总报告
        content_lines.extend([
            "# 📋 交易分析汇总报告",
            f"**生成时间:** {timestamp}",
            ""
        ])
        
        # 操作建议分布统计
        if recommendations:
            action_stats = {}
            total_risk = 0
            total_confidence = 0
            count = 0
            
            for rec in recommendations.values():
                action = rec.get('action', 'HOLD')
                action_stats[action] = action_stats.get(action, 0) + 1
                
                # 计算平均值
                risk = rec.get('risk_level')
                confidence = rec.get('confidence')
                if isinstance(risk, (int, float)):
                    total_risk += risk
                    count += 1
                if isinstance(confidence, (int, float)):
                    total_confidence += confidence
            
            content_lines.append("## 📊 操作建议分布")
            for action, count_val in action_stats.items():
                emoji = self._get_action_emoji(action)
                content_lines.append(f"- **{action}:** {emoji} {count_val} 个交易对")
            
            content_lines.append("")
            
            # 平均指标
            if count > 0:
                avg_risk = total_risk / count
                avg_confidence = total_confidence / len(recommendations) if recommendations else 0
                content_lines.extend([
                    "## 📈 平均指标",
                    f"- **平均风险等级:** {avg_risk:.1f}/5 ⭐",
                    f"- **平均信心度:** {avg_confidence:.1f}/10 💪"
                ])
        
        # 添加风险提示
        content_lines.extend([
            "",
            "### ⚠️ 风险提示",
            "- 本分析仅供参考，不构成投资建议",
            "- 加密货币投资存在高风险，请谨慎操作",
            "- 建议设置止损止盈，控制仓位风险"
        ])
        
        content = "\n".join(content_lines)
        return title, content
        
    def _get_action_emoji(self, action: str) -> str:
        """
        根据操作类型返回对应的emoji
        """
        emoji_map = {
            '买入': '🟢',
            '卖出': '🔴', 
            '观望': '🟡',
            '持有': '🔵'
        }
        return emoji_map.get(action, '⚪')
        
    def send_analysis_notification(self, analysis_result: Dict) -> Dict:
        """
        发送交易分析通知
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            Dict: 发送结果
        """
        try:
            title, content = self.format_trading_analysis(analysis_result)
            
            # 生成简短摘要
            recommendations = analysis_result.get('recommendations', {})
            action_stats = {}
            for rec in recommendations.values():
                action = rec.get('action', '观望')
                action_stats[action] = action_stats.get(action, 0) + 1
                
            short_summary = ", ".join([f"{action}:{count}" for action, count in action_stats.items()])
            
            return self.send_notification(title, content, short_summary)
            
        except Exception as e:
            logger.error(f"发送分析通知失败: {e}")
            return {"success": False, "error": str(e)}
            
    def test_connection(self) -> Dict:
        """
        测试Server酱连接
        
        Returns:
            Dict: 测试结果
        """
        test_title = "🧪 Server酱连接测试"
        test_content = f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n如果您收到此消息，说明Server酱配置正确！"
        
        return self.send_notification(test_title, test_content)