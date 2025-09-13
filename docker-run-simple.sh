#!/bin/bash

# OKX交易分析系统 纯Docker运行脚本

set -e

echo "🚀 启动OKX交易分析系统..."

# 检查Docker是否运行
if ! docker info &> /dev/null; then
    echo "❌ Docker未运行，请先启动Docker"
    exit 1
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "❌ .env文件不存在，请先创建并配置API密钥"
    echo "   可以复制env.example为.env并编辑"
    exit 1
fi

# 检查必要的API密钥
source .env
if [ -z "$OKX_API_KEY" ] || [ -z "$OKX_SECRET_KEY" ] || [ -z "$OKX_PASSPHRASE" ]; then
    echo "❌ OKX API密钥未配置，请在.env文件中设置："
    echo "   OKX_API_KEY=your_api_key"
    echo "   OKX_SECRET_KEY=your_secret_key"
    echo "   OKX_PASSPHRASE=your_passphrase"
    exit 1
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "❌ DeepSeek API密钥未配置，请在.env文件中设置："
    echo "   DEEPSEEK_API_KEY=your_deepseek_api_key"
    exit 1
fi

# 停止现有容器
echo "🛑 停止现有容器..."
docker stop okx-trading-analyzer 2>/dev/null || true
docker rm okx-trading-analyzer 2>/dev/null || true

# 创建必要的目录
mkdir -p data
mkdir -p analysis_results
mkdir -p logs

# 启动容器
echo "🚀 启动容器..."
docker run -d \
    --name okx-trading-analyzer \
    --restart unless-stopped \
    --env-file .env \
    -v "$(pwd)/data:/app/data" \
    -v "$(pwd)/analysis_results:/app/analysis_results" \
    -v "$(pwd)/logs:/app/logs" \
    -v "$(pwd)/trading_data.db:/app/trading_data.db" \
    -p 8000:8000 \
    okx-trading-analyzer

# 等待容器启动
echo "⏳ 等待容器启动..."
sleep 5

# 检查容器状态
echo "📊 检查容器状态..."
docker ps | grep okx-trading-analyzer

# 显示日志
echo "📋 显示最新日志..."
docker logs --tail=20 okx-trading-analyzer

echo ""
echo "✅ 容器启动完成！"
echo ""
echo "📋 常用命令："
echo "  查看日志: docker logs -f okx-trading-analyzer"
echo "  停止容器: docker stop okx-trading-analyzer"
echo "  重启容器: docker restart okx-trading-analyzer"
echo "  进入容器: docker exec -it okx-trading-analyzer bash"
echo "  查看状态: docker ps"
echo "  删除容器: docker rm okx-trading-analyzer"
echo ""
echo "📁 数据目录："
echo "  分析结果: ./analysis_results/"
echo "  日志文件: ./logs/"
echo "  数据库: ./trading_data.db"
