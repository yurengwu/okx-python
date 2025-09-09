#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP检测工具
用于获取当前公网IP地址，帮助配置API白名单
"""

import requests
import json
from typing import Optional, Dict
from loguru import logger
import time

class IPDetector:
    """IP检测器类"""
    
    def __init__(self):
        """初始化IP检测器"""
        # 多个IP检测服务，提高可靠性
        self.ip_services = [
            {
                'name': 'ipify',
                'url': 'https://api.ipify.org?format=json',
                'key': 'ip'
            },
            {
                'name': 'ip-api',
                'url': 'http://ip-api.com/json/',
                'key': 'query'
            },
            {
                'name': 'httpbin',
                'url': 'https://httpbin.org/ip',
                'key': 'origin'
            },
            {
                'name': 'myip',
                'url': 'https://api.myip.com',
                'key': 'ip'
            },
            {
                'name': 'ipinfo',
                'url': 'https://ipinfo.io/json',
                'key': 'ip'
            }
        ]
        
    def get_public_ip(self, timeout: int = 10) -> Optional[str]:
        """获取公网IP地址"""
        for service in self.ip_services:
            try:
                logger.info(f"正在通过 {service['name']} 获取公网IP...")
                response = requests.get(service['url'], timeout=timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    ip = data.get(service['key'])
                    
                    if ip:
                        # 处理可能的多IP情况（如httpbin返回的格式）
                        if ',' in str(ip):
                            ip = str(ip).split(',')[0].strip()
                        
                        logger.info(f"✓ 通过 {service['name']} 获取到公网IP: {ip}")
                        return str(ip)
                    else:
                        logger.warning(f"⚠ {service['name']} 返回数据中未找到IP字段")
                else:
                    logger.warning(f"⚠ {service['name']} 返回状态码: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠ {service['name']} 请求超时")
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠ {service['name']} 连接失败")
            except Exception as e:
                logger.warning(f"⚠ {service['name']} 获取IP失败: {e}")
                
        logger.error("✗ 所有IP检测服务都失败了")
        return None
    
    def get_detailed_ip_info(self, timeout: int = 10) -> Optional[Dict]:
        """获取详细的IP信息（包括地理位置等）"""
        try:
            logger.info("获取详细IP信息...")
            
            # 使用ip-api.com获取详细信息
            response = requests.get('http://ip-api.com/json/', timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    ip_info = {
                        'ip': data.get('query'),
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'isp': data.get('isp'),
                        'org': data.get('org'),
                        'timezone': data.get('timezone'),
                        'lat': data.get('lat'),
                        'lon': data.get('lon')
                    }
                    
                    logger.info(f"✓ 获取到详细IP信息: {ip_info['ip']} ({ip_info['country']}, {ip_info['isp']})")
                    return ip_info
                else:
                    logger.error(f"✗ IP信息查询失败: {data.get('message')}")
            else:
                logger.error(f"✗ 请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            logger.error(f"✗ 获取详细IP信息失败: {e}")
            
        return None
    
    def check_ip_whitelist_status(self, api_key: str, secret_key: str, passphrase: str) -> Dict:
        """检查当前IP是否在OKX API白名单中"""
        try:
            import ccxt
            
            # 创建OKX客户端测试连接
            exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': secret_key,
                'password': passphrase,
                'sandbox': False,
                'enableRateLimit': True,
                'timeout': 10000
            })
            
            logger.info("测试API密钥是否在白名单中...")
            
            # 尝试调用需要认证的API
            try:
                balance = exchange.fetch_balance()
                logger.info("✓ API密钥可正常使用，当前IP在白名单中")
                return {
                    'status': 'success',
                    'in_whitelist': True,
                    'message': 'API密钥可正常使用，当前IP在白名单中'
                }
            except ccxt.AuthenticationError as e:
                if 'IP' in str(e) or 'whitelist' in str(e).lower():
                    logger.error("✗ 当前IP不在API白名单中")
                    return {
                        'status': 'error',
                        'in_whitelist': False,
                        'message': f'当前IP不在API白名单中: {e}'
                    }
                else:
                    logger.error(f"✗ API认证失败: {e}")
                    return {
                        'status': 'error',
                        'in_whitelist': False,
                        'message': f'API认证失败: {e}'
                    }
            except Exception as e:
                logger.error(f"✗ API测试失败: {e}")
                return {
                    'status': 'error',
                    'in_whitelist': False,
                    'message': f'API测试失败: {e}'
                }
                
        except Exception as e:
            logger.error(f"✗ 白名单检查失败: {e}")
            return {
                'status': 'error',
                'in_whitelist': False,
                'message': f'白名单检查失败: {e}'
            }
    
    def generate_whitelist_guide(self, ip: str) -> str:
        """生成白名单配置指南"""
        guide = f"""
╔══════════════════════════════════════════════════════════════╗
║                    OKX API 白名单配置指南                      ║
╠══════════════════════════════════════════════════════════════╣
║ 当前检测到的公网IP: {ip:<40} ║
╠══════════════════════════════════════════════════════════════╣
║ 配置步骤:                                                    ║
║ 1. 登录 OKX 官网 (https://www.okx.com)                      ║
║ 2. 进入 "API管理" 页面                                       ║
║ 3. 找到您的API密钥                                          ║
║ 4. 点击 "编辑" 或 "IP白名单设置"                            ║
║ 5. 添加以下IP地址到白名单:                                   ║
║    {ip:<54} ║
║ 6. 保存设置并等待生效（通常需要几分钟）                      ║
╠══════════════════════════════════════════════════════════════╣
║ 注意事项:                                                    ║
║ • 如果您使用动态IP，建议定期检查和更新白名单                 ║
║ • 可以添加多个IP地址，用换行分隔                             ║
║ • 白名单设置后需要等待几分钟才能生效                         ║
║ • 建议同时配置备用IP地址以防网络变化                         ║
╚══════════════════════════════════════════════════════════════╝
        """
        return guide
    
    def monitor_ip_changes(self, interval: int = 300, callback=None):
        """监控IP变化"""
        logger.info(f"开始监控IP变化，检查间隔: {interval}秒")
        
        last_ip = self.get_public_ip()
        if not last_ip:
            logger.error("无法获取初始IP地址")
            return
            
        logger.info(f"初始IP地址: {last_ip}")
        
        while True:
            try:
                time.sleep(interval)
                current_ip = self.get_public_ip()
                
                if current_ip and current_ip != last_ip:
                    logger.warning(f"检测到IP变化: {last_ip} -> {current_ip}")
                    
                    if callback:
                        callback(last_ip, current_ip)
                    
                    # 显示新的白名单配置指南
                    print(self.generate_whitelist_guide(current_ip))
                    
                    last_ip = current_ip
                elif current_ip:
                    logger.info(f"IP地址未变化: {current_ip}")
                else:
                    logger.warning("无法获取当前IP地址")
                    
            except KeyboardInterrupt:
                logger.info("IP监控已停止")
                break
            except Exception as e:
                logger.error(f"IP监控出错: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续

def test_ip_detector():
    """测试IP检测器"""
    detector = IPDetector()
    
    print("=" * 60)
    print("IP检测器测试")
    print("=" * 60)
    
    # 获取公网IP
    ip = detector.get_public_ip()
    if ip:
        print(f"当前公网IP: {ip}")
        
        # 获取详细信息
        ip_info = detector.get_detailed_ip_info()
        if ip_info:
            print(f"详细信息: {json.dumps(ip_info, indent=2, ensure_ascii=False)}")
        
        # 显示白名单配置指南
        print(detector.generate_whitelist_guide(ip))
    else:
        print("无法获取公网IP")

if __name__ == "__main__":
    test_ip_detector()