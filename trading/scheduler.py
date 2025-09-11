import schedule
import time
from datetime import datetime
from loguru import logger
from typing import Optional
import threading
import signal
import sys

from trading.trading_analyzer import TradingAnalyzer
from core.config import Config

class TradingScheduler:
    def __init__(self):
        """初始化交易调度器"""
        self.analyzer = TradingAnalyzer()
        self.is_running = False
        self.scheduler_thread = None
        
        # 设置信号处理器用于优雅退出
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，正在停止调度器...")
        self.stop()
        sys.exit(0)
    
    def run_scheduled_analysis(self):
        """执行定时分析任务"""
        try:
            logger.info("开始执行定时分析任务")
            
            # 验证配置
            validation = self.analyzer.validate_configuration()
            if not all(validation.values()):
                logger.error(f"配置验证失败: {validation}")
                return
            
            # 执行分析
            result = self.analyzer.run_analysis()
            
            if result.get('success'):
                logger.info("定时分析任务完成")
                
                # 打印分析结果
                if 'formatted_output' in result:
                    print("\n" + "="*60)
                    print(result['formatted_output'])
                    print("="*60 + "\n")
                
                # 生成汇总报告
                summary = self.analyzer.generate_summary_report()
                print(summary)
                
            else:
                logger.error(f"分析任务失败: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"定时分析任务执行失败: {e}")
    
    def start(self, interval_hours: int = None, interval_minutes: int = None):
        """启动定时调度器"""
        if self.is_running:
            logger.warning("调度器已在运行中")
            return
        
        # 清除之前的任务
        schedule.clear()
        
        # 设置定时任务
        if interval_minutes and interval_minutes < 60:
            logger.info(f"启动交易分析调度器，间隔: {interval_minutes} 分钟")
            schedule.every(interval_minutes).minutes.do(self.run_scheduled_analysis)
        else:
            hours = interval_hours or 1
            logger.info(f"启动交易分析调度器，间隔: {hours} 小时")
            schedule.every(hours).hours.do(self.run_scheduled_analysis)
        
        # 立即执行一次
        logger.info("立即执行首次分析")
        self.run_scheduled_analysis()
        
        # 启动调度器线程
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("调度器已启动")
    
    def _run_scheduler(self):
        """运行调度器主循环"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"调度器运行错误: {e}")
                time.sleep(60)
    
    def stop(self):
        """停止调度器"""
        if not self.is_running:
            logger.warning("调度器未在运行")
            return
        
        logger.info("正在停止调度器...")
        self.is_running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        schedule.clear()
        logger.info("调度器已停止")
    
    def get_next_run_time(self) -> Optional[str]:
        """获取下次运行时间"""
        try:
            jobs = schedule.get_jobs()
            if jobs:
                next_run = min(job.next_run for job in jobs)
                return next_run.strftime('%Y-%m-%d %H:%M:%S')
            return None
        except:
            return None
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            'is_running': self.is_running,
            'next_run_time': self.get_next_run_time(),
            'scheduled_jobs': len(schedule.get_jobs()),
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def run_manual_analysis(self):
        """手动执行分析"""
        logger.info("手动执行分析任务")
        self.run_scheduled_analysis()

def main():
    """主函数"""
    # 配置日志
    logger.add(
        Config.LOG_FILE,
        rotation="1 day",
        retention="30 days",
        level=Config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    
    scheduler = TradingScheduler()
    
    try:
        # 启动调度器
        from core.config import Config
        interval_minutes = Config.ANALYSIS_INTERVAL // 60
        if interval_minutes < 60:
            scheduler.start(interval_minutes=interval_minutes)
        else:
            interval_hours = Config.ANALYSIS_INTERVAL // 3600
            scheduler.start(interval_hours=interval_hours)
        
        # 保持主线程运行
        logger.info("调度器正在运行，按 Ctrl+C 停止")
        
        while scheduler.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("接收到中断信号")
    except Exception as e:
        logger.error(f"程序运行错误: {e}")
    finally:
        scheduler.stop()
        logger.info("程序已退出")

if __name__ == "__main__":
    main()