FROM python:3.9-slim

# 1. 设置环境变量
# PYTHONUNBUFFERED=1: 确保日志实时输出，不缓存
# PORT=8000: 默认端口
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# 2. 安装系统依赖 (FFmpeg)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. 设置工作目录
WORKDIR /app

# 4. 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制项目文件
COPY . .

# 6. 暴露端口 (明确告诉 Koyeb 我们监听 8000)
EXPOSE 8000

# 7. 启动命令
CMD ["python", "main.py"]
