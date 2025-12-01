FROM python:3.9-slim

# 1. 安装系统依赖 (FFmpeg)
# update: 更新源
# install ffmpeg: 安装视频处理工具
# clean: 清理缓存减小镜像体积
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖文件并安装 Python 库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制所有项目文件
COPY . .

# 5. 启动命令
CMD ["python", "main.py"]
