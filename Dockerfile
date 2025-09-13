# 使用Python 3.8官方镜像作为基础镜像
FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 安装TA-Lib（如果项目需要）
# 注意：TA-Lib需要编译，可能需要额外配置
# RUN pip install TA-Lib

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p /app/analysis_results && \
    mkdir -p /app/logs && \
    mkdir -p /app/data

# 设置权限
RUN chmod +x main.py

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# 确保数据库文件有写权限
RUN touch /app/trading_data.db && \
    chown app:app /app/trading_data.db && \
    chmod 664 /app/trading_data.db

USER app

# 暴露端口（如果需要Web服务）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# 默认命令
CMD ["python", "main.py", "--schedule"]
