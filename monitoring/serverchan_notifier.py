#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server酱微信通知模块
用于发送交易分析结果到微信
"""

import requests
import json
import time
from typing import Dict, Optional, List, Union
from loguru import logger
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

class ServerChanNotifier:
    def __init__(self, sendkey: Union[str, List[str]]):
        """
        初始化Server酱通知器
        
        Args:
            sendkey: Server酱的SendKey，支持单个token字符串或多个token列表
        """
        if isinstance(sendkey, str):
            self.sendkeys = [sendkey]
        else:
            self.sendkeys = sendkey
        self.base_url = "https://sctapi.ftqq.com"
        
    def send_notification(self, title: str, content: str, short: Optional[str] = None) -> Dict:
        """
        发送通知到微信（支持多token群发）
        
        Args:
            title: 通知标题
            content: 通知内容（支持Markdown格式）
            short: 消息卡片内容（可选）
            
        Returns:
            Dict: 发送结果
        """
        if not self.sendkeys:
            logger.error("Server酱SendKey未配置")
            return {"success": False, "error": "SendKey未配置"}
        
        data = {
            "title": title,
            "desp": content
        }
        
        if short:
            data["short"] = short
        
        # 并发群发到所有token
        results = []
        success_count = 0
        
        def send_to_single_token(sendkey_info):
            """发送通知到单个token（带重试机制）"""
            i, sendkey = sendkey_info
            url = f"{self.base_url}/{sendkey}.send"
            max_retries = 3
            retry_delay = 1  # 秒
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(f"Token {i+1} 第{attempt+1}次重试...")
                        time.sleep(retry_delay * attempt)  # 递增延迟
                    else:
                        logger.info(f"发送通知到token {i+1}/{len(self.sendkeys)}: {sendkey[:10]}...")
                    
                    # 使用更短的超时时间，避免长时间卡死
                    response = requests.post(url, data=data, timeout=5)
                    result = response.json()
                    
                    if result.get("code") == 0:
                        logger.info(f"Token {i+1} 发送成功")
                        return {"token_index": i+1, "success": True, "response": result, "attempts": attempt+1}
                    else:
                        error_msg = result.get("message", "未知错误")
                        if attempt == max_retries - 1:  # 最后一次尝试
                            logger.error(f"Token {i+1} 发送失败: {error_msg}")
                            return {"token_index": i+1, "success": False, "error": error_msg, "response": result, "attempts": attempt+1}
                        else:
                            logger.warning(f"Token {i+1} 发送失败，准备重试: {error_msg}")
                            
                except requests.exceptions.Timeout:
                    if attempt == max_retries - 1:
                        logger.error(f"Token {i+1} 请求超时，已重试{max_retries}次")
                        return {"token_index": i+1, "success": False, "error": "请求超时", "attempts": attempt+1}
                    else:
                        logger.warning(f"Token {i+1} 请求超时，准备重试...")
                        
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Token {i+1} 发送异常: {e}")
                        return {"token_index": i+1, "success": False, "error": str(e), "attempts": attempt+1}
                    else:
                        logger.warning(f"Token {i+1} 发送异常，准备重试: {e}")
                        
            # 理论上不会到达这里
            return {"token_index": i+1, "success": False, "error": "未知错误", "attempts": max_retries}
        
        # 使用线程池并发发送（带整体超时控制）
        overall_timeout = 30  # 整体超时30秒，防止无限等待
        start_time = time.time()
        
        try:
            with ThreadPoolExecutor(max_workers=min(len(self.sendkeys), 10)) as executor:
                # 提交所有发送任务
                future_to_token = {executor.submit(send_to_single_token, (i, sendkey)): i 
                                 for i, sendkey in enumerate(self.sendkeys)}
                
                # 收集结果（带超时控制）
                for future in as_completed(future_to_token, timeout=overall_timeout):
                    try:
                        # 为每个future设置超时
                        result = future.result(timeout=5)
                        results.append(result)
                        if result["success"]:
                            success_count += 1
                            
                        # 检查是否超过整体超时
                        if time.time() - start_time > overall_timeout:
                            logger.warning("整体发送超时，停止等待剩余任务")
                            break
                            
                    except TimeoutError:
                        token_index = future_to_token[future] + 1
                        logger.error(f"Token {token_index} 任务执行超时")
                        results.append({"token_index": token_index, "success": False, "error": "任务执行超时"})
                    except Exception as e:
                        token_index = future_to_token[future] + 1
                        logger.error(f"Token {token_index} 发送任务异常: {e}")
                        results.append({"token_index": token_index, "success": False, "error": str(e)})
                        
        except TimeoutError:
            logger.error(f"整体发送操作超时({overall_timeout}秒)，强制结束")
            # 为未完成的任务添加超时结果
            completed_tokens = {r.get("token_index") for r in results}
            for i in range(len(self.sendkeys)):
                if (i + 1) not in completed_tokens:
                    results.append({"token_index": i+1, "success": False, "error": "整体操作超时"})
        except Exception as e:
            logger.error(f"线程池执行异常: {e}")
            # 确保所有token都有结果
            completed_tokens = {r.get("token_index") for r in results}
            for i in range(len(self.sendkeys)):
                if (i + 1) not in completed_tokens:
                    results.append({"token_index": i+1, "success": False, "error": f"线程池异常: {str(e)}"})
        
        # 返回群发结果
        overall_success = success_count > 0
        logger.info(f"群发完成: {success_count}/{len(self.sendkeys)} 个token发送成功")
        
        return {
            "success": overall_success,
            "total_tokens": len(self.sendkeys),
            "success_count": success_count,
            "results": results,
            "message": f"群发完成，{success_count}/{len(self.sendkeys)} 个token发送成功"
        }
            
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