#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKX加密货币交易分析系统
使用DeepSeek AI进行智能分析，每小时提供交易建议
"""

import argparse
import sys
import time
from datetime import datetime
from loguru import logger

from core.config import Config
from trading.trading_analyzer import TradingAnalyzer
from trading.scheduler import TradingScheduler
from utils.ip_detector import IPDetector
from monitoring.websocket_monitor import WebSocketMonitor

def setup_logging():
    """设置日志配置"""
    logger.remove()  # 移除默认处理器
    
    # 控制台输出
    logger.add(
        sys.stdout,
        level=Config.LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    
    # 文件输出
    logger.add(
        Config.LOG_FILE,
        rotation="1 day",
        retention="30 days",
        level=Config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

def check_configuration():
    """检查配置"""
    print("\n=== 配置检查 ===")
    
    analyzer = TradingAnalyzer()
    validation = analyzer.validate_configuration()
    
    for key, status in validation.items():
        status_text = "✓" if status else "✗"
        print(f"{status_text} {key}: {status}")
    
    if not all(validation.values()):
        print("\n⚠️  配置不完整，请检查以下项目:")
        if not validation['okx_api_configured']:
            print("   - OKX API密钥未配置")
        if not validation['deepseek_api_configured']:
            print("   - DeepSeek API密钥未配置")
        if not validation['okx_connection']:
            print("   - OKX API连接失败")
        if not validation.get('serverchan_configured', True):
            print("   - Server酱SendKey未配置（通知功能已启用但缺少配置）")
        
        print("\n请复制 .env.example 为 .env 并填入正确的API密钥")
        return False
    
    print("\n✅ 配置检查通过")
    return True

def check_ip_whitelist():
    """检查IP白名单状态"""
    print("\n=== IP白名单检查 ===")
    
    detector = IPDetector()
    
    # 获取当前公网IP
    current_ip = detector.get_public_ip()
    if not current_ip:
        print("❌ 无法获取当前公网IP地址")
        return False
    
    print(f"当前公网IP: {current_ip}")
    
    # 获取详细IP信息
    ip_info = detector.get_detailed_ip_info()
    if ip_info:
        print(f"地理位置: {ip_info.get('country', 'Unknown')}, {ip_info.get('city', 'Unknown')}")
        print(f"ISP: {ip_info.get('isp', 'Unknown')}")
    
    # 检查API密钥配置
    if not (Config.OKX_API_KEY and Config.OKX_SECRET_KEY and Config.OKX_PASSPHRASE):
        print("\n⚠️  OKX API密钥未配置，无法检查白名单状态")
        print("   请先配置API密钥后再检查白名单")
        print("\n📋 白名单配置指南:")
        print(detector.generate_whitelist_guide(current_ip))
        return False
    
    # 检查白名单状态
    print("\n正在检查API白名单状态...")
    whitelist_status = detector.check_ip_whitelist_status(
        Config.OKX_API_KEY,
        Config.OKX_SECRET_KEY, 
        Config.OKX_PASSPHRASE
    )
    
    if whitelist_status['status'] == 'success' and whitelist_status['in_whitelist']:
        print("✅ 当前IP已在API白名单中，可以正常使用")
        return True
    else:
        print(f"❌ {whitelist_status['message']}")
        print("\n📋 白名单配置指南:")
        print(detector.generate_whitelist_guide(current_ip))
        return False

def show_ip_info():
    """显示IP信息"""
    print("\n=== 当前IP信息 ===")
    
    detector = IPDetector()
    
    # 获取公网IP
    current_ip = detector.get_public_ip()
    if not current_ip:
        print("❌ 无法获取当前公网IP地址")
        return
    
    print(f"\n🌐 公网IP地址: {current_ip}")
    
    # 获取详细信息
    ip_info = detector.get_detailed_ip_info()
    if ip_info:
        print(f"🌍 国家/地区: {ip_info.get('country', 'Unknown')} ({ip_info.get('country_code', 'Unknown')})")
        print(f"🏙️  城市: {ip_info.get('city', 'Unknown')}")
        print(f"📡 ISP: {ip_info.get('isp', 'Unknown')}")
        print(f"🏢 组织: {ip_info.get('org', 'Unknown')}")
        print(f"🕐 时区: {ip_info.get('timezone', 'Unknown')}")
        if ip_info.get('lat') and ip_info.get('lon'):
            print(f"📍 坐标: {ip_info['lat']}, {ip_info['lon']}")
    
    # 显示白名单配置指南
    print("\n📋 OKX API白名单配置指南:")
    print(detector.generate_whitelist_guide(current_ip))

def monitor_ip_changes():
    """监控IP变化"""
    print("\n=== IP变化监控 ===")
    
    detector = IPDetector()
    
    def on_ip_change(old_ip, new_ip):
        """IP变化回调函数"""
        print(f"\n🚨 检测到IP地址变化!")
        print(f"   旧IP: {old_ip}")
        print(f"   新IP: {new_ip}")
        print("\n⚠️  请及时更新OKX API白名单配置!")
    
    try:
        print("\n🔍 开始监控IP地址变化...")
        print("   检查间隔: 5分钟")
        print("   按 Ctrl+C 停止监控")
        
        detector.monitor_ip_changes(interval=300, callback=on_ip_change)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  IP监控已停止")
    except Exception as e:
        print(f"\n❌ 监控出错: {e}")

def run_single_analysis():
    """运行单次分析"""
    print("\n=== 执行单次分析 ===")
    
    analyzer = TradingAnalyzer()
    
    # 检查配置
    if not check_configuration():
        return
    
    print("\n正在分析市场数据...")
    result = analyzer.run_analysis()
    
    if result.get('success'):
        print("\n" + "="*60)
        print(result['formatted_output'])
        print("="*60)
        
        # 生成汇总报告
        summary = analyzer.generate_summary_report()
        print("\n" + summary)
        
    else:
        print(f"\n❌ 分析失败: {result.get('error', 'Unknown error')}")

def run_scheduler():
    """运行定时调度器"""
    print("\n=== 启动定时调度器 ===")
    
    # 检查配置
    if not check_configuration():
        return
    
    scheduler = TradingScheduler()
    
    try:
        interval_minutes = Config.ANALYSIS_INTERVAL // 60
        if interval_minutes < 60:
            print(f"\n🚀 启动每{interval_minutes}分钟自动分析...")
            scheduler.start(interval_minutes=interval_minutes)
        else:
            interval_hours = Config.ANALYSIS_INTERVAL // 3600
            print(f"\n🚀 启动每{interval_hours}小时自动分析...")
            scheduler.start(interval_hours=interval_hours)
        
        print("\n📊 调度器状态:")
        status = scheduler.get_status()
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        print("\n⏰ 系统将每小时自动执行分析")
        print("   按 Ctrl+C 停止程序")
        
        # 保持程序运行
        while scheduler.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  接收到停止信号")
    except Exception as e:
        print(f"\n❌ 程序运行错误: {e}")
    finally:
        scheduler.stop()
        print("\n✅ 程序已安全退出")

def show_latest_analysis():
    """显示最新分析结果"""
    print("\n=== 最新分析结果 ===")
    
    analyzer = TradingAnalyzer()
    latest = analyzer.get_latest_analysis()
    
    if latest:
        formatted_output = analyzer.deepseek_analyzer.format_analysis_output(latest)
        print(formatted_output)
        
        # 显示汇总
        summary = analyzer.generate_summary_report()
        print("\n" + summary)
    else:
        print("\n📭 暂无分析结果")
        print("   请先运行分析: python main.py --analyze")

def show_analysis_history():
    """显示分析历史"""
    print("\n=== 分析历史 (最近7天) ===")
    
    analyzer = TradingAnalyzer()
    history = analyzer.get_analysis_history(days=7)
    
    if history:
        print(f"\n找到 {len(history)} 条历史记录:\n")
        
        for i, analysis in enumerate(history[:10], 1):  # 只显示最近10条
            analysis_time = analysis.get('analysis_time', 'Unknown')
            recommendations = analysis.get('recommendations', {})
            
            print(f"{i}. {analysis_time}")
            print(f"   分析交易对: {len(recommendations)} 个")
            
            # 统计操作建议
            actions = {}
            for rec in recommendations.values():
                action = rec.get('action', '观望')
                actions[action] = actions.get(action, 0) + 1
            
            action_summary = ", ".join([f"{action}:{count}" for action, count in actions.items()])
            print(f"   操作分布: {action_summary}")
            print()
    else:
        print("\n📭 暂无历史记录")

def test_serverchan_notification():
    """测试Server酱通知功能"""
    print("\n=== 测试Server酱通知 ===")
    
    analyzer = TradingAnalyzer()
    
    # 检查配置
    if not Config.ENABLE_SERVERCHAN_NOTIFICATION:
        print("❌ Server酱通知功能未启用")
        print("   请在.env文件中设置 ENABLE_SERVERCHAN_NOTIFICATION=true")
        return
    
    tokens = Config.get_serverchan_tokens()
    if not tokens:
        print("❌ Server酱SendKey未配置")
        print("   请在.env文件中设置 SERVERCHAN_SENDKEY=你的SendKey")
        print("   或设置 SERVERCHAN_SENDKEYS=token1,token2,token3 进行群发")
        return
    
    print(f"📱 配置了 {len(tokens)} 个SendKey")
    for i, token in enumerate(tokens):
        print(f"   Token {i+1}: {token[:8]}...")
    print("\n正在发送测试通知...")
    
    result = analyzer.test_serverchan_notification()
    
    if result.get('success'):
        print("✅ 测试通知发送成功！")
        print("   请检查您的微信是否收到测试消息")
    else:
        print(f"❌ 测试通知发送失败: {result.get('error')}")
        print("\n💡 解决建议:")
        print("   1. 检查SendKey是否正确")
        print("   2. 确认Server酱服务是否正常")
        print("   3. 检查网络连接")

def interactive_mode():
    """交互模式"""
    print("\n=== 交互模式 ===")
    print("\n可用命令:")
    print("  1 - 执行单次分析")
    print("  2 - 启动定时调度器")
    print("  3 - 查看最新分析")
    print("  4 - 查看分析历史")
    print("  5 - 检查配置")
    print("  6 - 查看当前IP信息")
    print("  7 - 检查IP白名单状态")
    print("  8 - 监控IP变化")
    print("  9 - 测试Server酱通知")
    print("  10 - 启动WebSocket实时监控")
    print("  11 - 测试WebSocket连接")
    print("  q - 退出")
    
    while True:
        try:
            choice = input("\n请选择操作 (1-11, q): ").strip().lower()
            
            if choice == '1':
                run_single_analysis()
            elif choice == '2':
                run_scheduler()
            elif choice == '3':
                show_latest_analysis()
            elif choice == '4':
                show_analysis_history()
            elif choice == '5':
                check_configuration()
            elif choice == '6':
                show_ip_info()
            elif choice == '7':
                check_ip_whitelist()
            elif choice == '8':
                monitor_ip_changes()
            elif choice == '9':
                test_serverchan_notification()
            elif choice == '10':
                run_websocket_monitor()
            elif choice == '11':
                test_websocket_connection()
            elif choice == 'q':
                print("\n👋 再见!")
                break
            else:
                print("\n❌ 无效选择，请重试")
                
        except KeyboardInterrupt:
            print("\n\n👋 再见!")
            break
        except Exception as e:
            print(f"\n❌ 操作失败: {e}")

def run_websocket_monitor():
    """启动WebSocket实时监控"""
    try:
        if not Config.ENABLE_WEBSOCKET_MONITOR:
            print("\n⚠️  WebSocket监控未启用")
            print("请在.env文件中设置 ENABLE_WEBSOCKET_MONITOR=true")
            return
            
        if not Config.SERVERCHAN_SENDKEY:
            print("\n⚠️  未配置Server酱通知")
            print("WebSocket监控需要Server酱来发送实时警报")
            return
            
        print("\n🔄 启动WebSocket实时监控系统...")
        
        # 动态获取交易对
        from trading.okx_client import OKXClient
        okx_client = OKXClient()
        trading_pairs = Config.get_trading_pairs(okx_client)
        
        print(f"监控交易对: {', '.join(trading_pairs[:5])}{'...' if len(trading_pairs) > 5 else ''}")
        print(f"总计: {len(trading_pairs)} 个交易对")
        print(f"波动率阈值: {Config.VOLATILITY_THRESHOLD}")
        print(f"成交量异常倍数: {Config.VOLUME_SPIKE_MULTIPLIER}")
        print("\n按 Ctrl+C 停止监控\n")
        
        monitor = WebSocketMonitor()
        
        # 定义异步主函数
        async def websocket_main():
            try:
                await monitor.start_monitoring()
            except KeyboardInterrupt:
                print("\n\n🛑 收到停止信号，正在关闭监控系统...")
                monitor.stop_monitoring()
                await monitor.close_websocket()
        
        # 运行监控
        import asyncio
        asyncio.run(websocket_main())
        
    except KeyboardInterrupt:
        print("\n\n🛑 程序已安全退出")
    except Exception as e:
        logger.error(f"WebSocket监控启动失败: {e}")
        print(f"\n❌ WebSocket监控启动失败: {e}")

def test_websocket_connection():
    """测试WebSocket连接"""
    try:
        print("\n🔄 测试WebSocket连接...")
        
        monitor = WebSocketMonitor()
        
        import asyncio
        import signal
        
        async def test_connection():
            success = await monitor.connect_websocket()
            if success:
                print("✅ WebSocket连接测试成功")
                print(f"连接地址: {monitor.ws_url}")
                print(f"订阅交易对: {len(monitor.symbols)} 个")
                
                # 接收几条消息测试
                print("\n📡 接收测试数据...")
                count = 0
                try:
                    async for message in monitor.websocket:
                        count += 1
                        print(f"收到消息 {count}: {message[:100]}...")
                        if count >= 3:
                            break
                except asyncio.CancelledError:
                    pass
                        
                await monitor.close_websocket()
                print("\n✅ WebSocket功能测试完成")
            else:
                print("❌ WebSocket连接测试失败")
        
        # 创建事件循环并设置信号处理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def signal_handler():
            print("\n\n🛑 测试被用户中断")
            for task in asyncio.all_tasks(loop):
                task.cancel()
        
        # 在Windows上使用不同的信号处理方式
        try:
            if hasattr(signal, 'SIGINT'):
                loop.add_signal_handler(signal.SIGINT, signal_handler)
        except NotImplementedError:
            # Windows不支持add_signal_handler
            pass
        
        try:
            loop.run_until_complete(test_connection())
        except KeyboardInterrupt:
            print("\n\n🛑 测试被用户中断")
            # 确保WebSocket连接被关闭
            try:
                loop.run_until_complete(monitor.close_websocket())
            except:
                pass
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"WebSocket连接测试失败: {e}")
        print(f"\n❌ WebSocket连接测试失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OKX加密货币交易分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py --analyze          # 执行单次分析
  python main.py --schedule         # 启动定时调度器
  python main.py --latest           # 查看最新分析结果
  python main.py --history          # 查看分析历史
  python main.py --check            # 检查配置
  python main.py --ip-info          # 查看当前IP信息
  python main.py --ip-whitelist     # 检查IP白名单状态
  python main.py --ip-monitor       # 监控IP变化
  python main.py --test-serverchan  # 测试Server酱通知
  python main.py --websocket        # 启动WebSocket实时监控
  python main.py --test-websocket   # 测试WebSocket连接
  python main.py                    # 交互模式
        """
    )
    
    parser.add_argument('--analyze', action='store_true', help='执行单次分析')
    parser.add_argument('--schedule', action='store_true', help='启动定时调度器')
    parser.add_argument('--latest', action='store_true', help='查看最新分析结果')
    parser.add_argument('--history', action='store_true', help='查看分析历史')
    parser.add_argument('--check', action='store_true', help='检查配置')
    parser.add_argument('--ip-info', action='store_true', help='查看当前IP信息')
    parser.add_argument('--ip-whitelist', action='store_true', help='检查IP白名单状态')
    parser.add_argument('--ip-monitor', action='store_true', help='监控IP变化')
    parser.add_argument('--test-serverchan', action='store_true', help='测试Server酱通知')
    parser.add_argument('--websocket', action='store_true', help='启动WebSocket实时监控')
    parser.add_argument('--test-websocket', action='store_true', help='测试WebSocket连接')
    parser.add_argument('--version', action='version', version='OKX Trading Analyzer v1.0.0')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 显示欢迎信息
    print("\n" + "="*60)
    print("🚀 OKX加密货币交易分析系统")
    print("   基于DeepSeek AI的智能交易建议")
    print("="*60)
    
    # 根据参数执行相应功能
    if args.analyze:
        run_single_analysis()
    elif args.schedule:
        run_scheduler()
    elif args.latest:
        show_latest_analysis()
    elif args.history:
        show_analysis_history()
    elif args.check:
        check_configuration()
    elif getattr(args, 'ip_info', False):
        show_ip_info()
    elif getattr(args, 'ip_whitelist', False):
        check_ip_whitelist()
    elif getattr(args, 'ip_monitor', False):
        monitor_ip_changes()
    elif getattr(args, 'test_serverchan', False):
        test_serverchan_notification()
    elif args.websocket:
        run_websocket_monitor()
    elif getattr(args, 'test_websocket', False):
        test_websocket_connection()
    else:
        # 默认进入交互模式
        interactive_mode()

if __name__ == "__main__":
    main()