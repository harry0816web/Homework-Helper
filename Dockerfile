# 使用官方 Python 3.11 映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements 檔案
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式程式碼
COPY app/ ./app/
COPY credentials/ ./credentials/

# 暴露 Flask 預設端口
EXPOSE 5000

# 設定環境變數
ENV FLASK_APP=app
ENV FLASK_ENV=production

# 啟動 Flask 應用程式
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
