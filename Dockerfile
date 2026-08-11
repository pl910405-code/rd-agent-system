FROM python:3.11-slim

WORKDIR /app

# Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 数据目录（上传文件 + RAG索引）
RUN mkdir -p /app/data/uploads /app/data/kb

# Render 会自动设置 PORT 环境变量
EXPOSE 10000

CMD ["python", "backend/server.py"]
