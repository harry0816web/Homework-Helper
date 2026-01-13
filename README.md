# Homework Helper 

一個基於 **LangChain**、**LangGraph** 和 **RAG** 技術的智能問答系統，可以上傳作業相關文件並進行智能問答。

## ✨ 功能特色

- 📄 **文件上傳與索引**：支援 PDF 和文字檔，自動進行分塊和向量化
- 💬 **智能問答**：基於上傳的文件內容回答使用者問題
- 🧠 **對話記憶**：使用 Redis 儲存對話歷史，支援多輪對話
- 🔍 **文件評分機制**：使用 LLM 評估檢索文件的相關性，提升回答品質
- 🎨 **現代化介面**：簡潔美觀的 Web 介面

## 🏗️ 技術架構

本專案採用 **RAG (Retrieval-Augmented Generation)** 架構，結合以下技術：

```
前端 (HTML/JS) 
    ↕ HTTP/JSON
Flask 應用程式 (路由層)
    ↕
LangChain Service (服務層)
    ↕
┌─────────────┬─────────────┬─────────────┐
│  ChromaDB   │    Redis    │   Ollama    │
│  (向量資料庫) │  (對話記憶)  │ (Embedding) │
└─────────────┴─────────────┴─────────────┘
    ↕
Google Gemini (LLM)
```

**核心技術棧：**

- **Flask**: Web 框架
- **LangChain**: AI 應用程式開發框架
- **LangGraph**: 複雜工作流程管理
- **ChromaDB**: 向量資料庫（語意搜尋）
- **Redis**: 對話記憶儲存
- **Ollama**: 本地 Embedding 模型
- **Ollama (gemini-3-flash)**: 本地LLM

## 🚀 快速開始

### 前置需求

- Python 3.11+
- Docker 和 Docker Compose
- Ollama（本地運行 LLM 和 Embedding 模型）

### 1. 安裝 Ollama 和下載模型

```bash
# 安裝 Ollama (如果還沒安裝)
# macOS
brew install ollama

# 或從官網下載: https://ollama.ai

# 啟動 Ollama 服務
ollama serve

# 在另一個終端下載所需的模型
ollama pull gemini-3-flash    # LLM 模型
ollama pull nomic-embed-text  # Embedding 模型
```

### 2. 設定環境變數

建立 `.env` 檔案：

```env
# Redis 連線 (Docker Compose 會自動設定)
REDIS_URL=redis://redis:6379/0

# Ollama 服務位置 (從容器訪問主機)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# ChromaDB 設定 (Docker Compose 會自動設定)
CHROMA_DB_HOST=chromadb
CHROMA_DB_PORT=8000
```

**注意：** 不再需要 Google Gemini API Key，所有模型都在本地運行。

### 3. 啟動服務

使用 Docker Compose（推薦）：

```bash
docker-compose up -d
```

服務啟動後，訪問 `http://localhost:5001` 即可使用。

### 4. 本地開發（可選）

如果需要本地開發：

```bash
# 安裝依賴
pip install -r requirements.txt

# 啟動 Redis 和 ChromaDB (使用 Docker Compose)
docker-compose up -d redis chromadb

# 設定環境變數
export REDIS_URL=redis://localhost:6379/0
export OLLAMA_BASE_URL=http://localhost:11434
export CHROMA_DB_HOST=localhost
export CHROMA_DB_PORT=8000

# 啟動 Flask
export FLASK_APP=app
flask run
```

## 📖 使用方式

### 1. 上傳文件

1. 訪問 `http://localhost:5001`
2. 在左側面板選擇 PDF 或文字檔
3. 點擊「上傳並建立索引」
4. 等待處理完成（文件會被分塊並向量化儲存到 ChromaDB）

### 2. 開始問答

1. 在右側聊天介面輸入問題
2. 系統會自動：
   - 從 ChromaDB 檢索相關文件
   - 使用 LLM 評分文件相關性
   - 基於相關文件生成回答
3. 對話歷史會自動儲存在 Redis 中

## 🔌 API 端點

### 文件上傳

```bash
POST /api/upload
Content-Type: multipart/form-data

file: <檔案>
```

**回應：**

```json
{
  "status": "success",
  "message": "成功處理 filename.pdf，共建立了 15 個知識片段。"
}
```

### 問答對話

```bash
POST /api/chat
Content-Type: application/json

{
  "message": "什麼是 Python？",
  "session_id": "user_123"
}
```

**回應：**

```json
{
  "answer": "Python 是一種高階程式語言...",
  "source_documents": ["file1.pdf", "file2.pdf"],
  "session_id": "user_123"
}
```

## 🏛️ 專案結構

```
homework-helper/
├── docker-compose.yml      # Docker 服務編排
├── Dockerfile              # Flask 應用程式映像檔
├── requirements.txt        # Python 依賴
├── .env                    # 環境變數（需自行建立）
├── app/                    # 應用程式主目錄
│   ├── __init__.py        # Flask 應用程式工廠
│   ├── routes.py          # API 路由定義
│   ├── templates/         # HTML 模板
│   │   └── index.html     # 前端介面
│   └── services/          # 服務層
│       ├── langchain_svc.py  # LangChain 核心服務
│       └── redis_svc.py     # Redis 服務
└── ARCHITECTURE.md        # 詳細架構文檔（學習用）
```

## 🔄 工作流程

### LangGraph 執行流程

```
使用者問題
    ↓
[retrieve] 從 ChromaDB 檢索相關文件
    ↓
[grade_documents] 使用 LLM 評分文件相關性
    ↓
[generate] 基於過濾後的文件生成回答
    ↓
更新 Redis 對話歷史
    ↓
返回回答
```

**詳細說明請參考 [ARCHITECTURE.md](./ARCHITECTURE.md)**

## ⚙️ 環境變數

| 變數名稱            | 說明                  | 必填 | 預設值                                |
| ------------------- | --------------------- | ---- | ------------------------------------- |
| `REDIS_URL`       | Redis 連線 URL        | ❌   | `redis://redis:6379/0`              |
| `OLLAMA_BASE_URL` | Ollama 服務地址       | ❌   | `http://host.docker.internal:11434` |
| `CHROMA_DB_HOST`  | ChromaDB 主機         | ❌   | `chromadb`                          |
| `CHROMA_DB_PORT`  | ChromaDB 端口         | ❌   | `8000`                              |

## 🐳 Docker 服務

專案使用 Docker Compose 管理以下服務：

- **web**: Flask 應用程式（端口 5001）
- **redis**: Redis 服務（端口 6379）
- **chromadb**: ChromaDB 向量資料庫（端口 8000）

## 📚 學習資源

- **詳細架構說明**：請參考 [ARCHITECTURE.md](./ARCHITECTURE.md)
  - Flask 應用程式設計模式
  - LangChain 與 RAG 實作
  - LangGraph 工作流程設計
  - 核心元件詳解

## 🛠️ 開發

### 本地開發環境

```bash
# 啟動依賴服務
docker-compose up -d redis chromadb

# 安裝開發依賴
pip install -r requirements.txt

# 設定環境變數
export FLASK_ENV=development
export OLLAMA_BASE_URL=http://localhost:11434

# 啟動應用程式
flask run --debug
```

### 除錯

應用程式提供除錯方法 `get_graph_trace()`，可以查看 LangGraph 執行流程：

```python
from app.services.langchain_svc import LangChainService

svc = LangChainService()
trace = svc.get_graph_trace("你的問題")
print(trace)
```

## 🚢 部署

### 生產環境部署

```bash
# 使用 Docker Compose
docker-compose up -d --build

# 或使用 Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

## 📝 授權

MIT License

## 🙋 常見問題

### Q: Ollama 無法連線？

**A:** 確保 Ollama 服務正在運行：

```bash
ollama serve
```

在 Docker 容器中，使用 `host.docker.internal` 訪問主機服務。

### Q: ChromaDB 連線失敗？

**A:** 確保 ChromaDB 容器正在運行：

```bash
docker-compose ps
docker-compose logs chromadb
```

### Q: 如何清除對話歷史？

**A:** 清除 Redis 中的對話資料：

```bash
docker exec -it redis_service redis-cli
> KEYS chat:*
> DEL chat:session_id
```

### Q: 如何重置知識庫？

**A:** 刪除 ChromaDB 的持久化資料：

```bash
docker-compose down -v
docker-compose up -d
```

---

**需要更多技術細節？** 請參考 [ARCHITECTURE.md](./ARCHITECTURE.md) 了解完整的架構設計和實作細節。
