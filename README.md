# Email Summarizer - Flask 應用程式

一個基於 Flask 的 Gmail 郵件摘要和問答系統，使用 LangChain 和 OpenAI 進行智能處理。

## 專案架構

```
email-summarizer/
├── docker-compose.yml       # 管理 Flask 和 Redis 的關聯
├── Dockerfile               # 定義 Flask 映像檔
├── requirements.txt         # 包含 flask, redis, langchain, google-api-python-client 等
├── .env                     # [重要] 放 OpenAI API Key, Gmail 帳密等敏感資訊
├── .env.example             # 環境變數範例檔
├── wsgi.py                  # WSGI 入口點（用於生產環境部署）
├── app/                     # 程式碼主目錄
│   ├── __init__.py          # 初始化 Flask app, Redis 連線
│   ├── routes.py            # 定義 API 路由 (Endpoint)
│   └── services/            # [核心邏輯層]
│       ├── __init__.py
│       ├── langchain_svc.py # 專門處理 LangChain 邏輯
	├── pinecone_svc.py  # 專門處理 Vector DB 邏輯
│       └── gmail_svc.py     # 專門處理 Gmail 抓取邏輯
└── credentials/             # 放 Gmail OAuth 的 json 檔
    └── google_secret.json
```

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env` 並填入你的 API Keys：

```bash
cp .env.example .env
# 編輯 .env 填入你的 OPENAI_API_KEY 等資訊
```

### 3. 設定 Gmail OAuth

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案
2. 啟用 Gmail API
3. 建立 OAuth 2.0 憑證：
   - **應用程式類型**：選擇「網頁應用程式」（Web application）
   - **已授權的重新導向 URI**：**必須精確添加** `http://localhost:8080/auth/gmail/callback`
     - ⚠️ **重要**：URI 必須完全一致，包括：
       - 協議：`http://`（本地開發）或 `https://`（生產環境）
       - 域名：`localhost` 或你的網域
       - 端口：`8080`（或你設定的端口）
       - 路徑：`/auth/gmail/callback`（必須完全一致）
     - 如果部署到生產環境，也要添加生產環境的回調 URI，例如：`https://yourdomain.com/auth/gmail/callback`
   - 💡 **提示**：如果不確定 URI，可以訪問 `/auth/debug` 端點查看
4. 下載憑證 JSON 檔，重新命名為 `google_secret.json` 並放入 `credentials/` 目錄

#### 常見錯誤：`redirect_uri_mismatch`

如果遇到此錯誤，請確認：

- Google Cloud Console 中的「已授權的重新導向 URI」包含：`http://localhost:8080/auth/gmail/callback`
- URI 必須**完全一致**，不能有多餘的斜線或空格
- 訪問 `http://localhost:8080/auth/debug` 可以查看程式碼使用的 redirect_uri

### 4. 啟動服務

#### 使用 Docker Compose（推薦）

```bash
docker-compose up -d
```

#### 本地開發

```bash
# 啟動 Redis（如果還沒啟動）
docker run -d -p 6379:6379 redis:7-alpine

# 啟動 Flask 應用程式
export FLASK_APP=wsgi.py
flask run
```

應用程式會在 `http://localhost:8080` 運行（使用 Docker）或 `http://localhost:5000`（本地開發）。

訪問 `http://localhost:8080/` 可以看到**聊天介面**，與 AI Agent 對話！

## 聊天介面

本專案提供了簡單易用的聊天介面，讓你可以直接與 AI Agent 對話：

### 功能特色

- 💬 **智能對話**：與 Gemini AI 進行自然對話
- 📧 **郵件上下文**：可以選擇使用郵件作為上下文，讓 AI 回答更精準
- 🔍 **智能搜尋**：自動從 Pinecone 搜尋相關郵件
- 🎨 **美觀介面**：現代化的漸層設計，使用體驗流暢

### 使用方式

1. 訪問 `http://localhost:8080/`
2. 首次使用需要登入 Gmail（點擊提示中的登入連結）
3. 在輸入框中輸入問題
4. 可以選擇是否使用郵件上下文

## 系統架構

### 三層架構說明

本系統採用現代化的 RAG（Retrieval-Augmented Generation）架構：

```
[Gmail API]  <-- (1. 抓取郵件) --> [Flask Server]
                                          |
                                          |-- (2. 原始郵件緩存) --> [Redis]
                                          |       (用途：Cache, 避免重複抓取)
                                          |
                                          |-- (3. 向量化儲存) --> [Pinecone]
                                                  (用途：語意搜尋, 相似度比對)
```

**各層職責：**

1. **Gmail API**：資料來源，提供原始郵件內容
2. **Redis**：短期緩存，儲存原始郵件 JSON，避免頻繁調用 Gmail API
3. **Pinecone**：長期記憶，儲存郵件的向量嵌入，用於語意搜尋

### 工作流程

#### 資料同步流程（`POST /emails/sync`）

1. Flask 從 Gmail API 抓取郵件
2. 郵件存入 Redis（作為緩存）
3. 郵件向量化並存入 Pinecone（用於搜尋）

#### 搜尋流程（`POST /emails/search-with-answer`）

1. 使用者問題轉換為向量
2. 在 Pinecone 中搜尋最相似的郵件
3. 將相關郵件作為上下文提供給 LLM
4. LLM 生成回答

## API 端點

### OAuth2 認證流程

#### 1. 登入（重定向到 Google 授權頁面）

```bash
GET /auth/gmail/login
```

**說明：** 訪問此端點會自動重定向到 Google 登入頁面，使用者授權後會回調到 `/auth/gmail/callback`

**使用範例：**

```javascript
// 在前端，直接重定向或打開新視窗
window.location.href = 'http://localhost:8080/auth/gmail/login';
```

#### 2. OAuth2 回調（自動處理）

```bash
GET /auth/gmail/callback?code=...&state=...
```

**說明：** 這是 Google 授權後自動回調的端點，會自動處理並儲存憑證到 session

#### 3. 檢查登入狀態

```bash
GET /auth/status
```

**回應範例：**

```json
{
  "authenticated": true,
  "email": "user@gmail.com",
  "has_valid_token": true
}
```

#### 4. 登出

```bash
POST /auth/logout
```

**回應範例：**

```json
{
  "success": true,
  "message": "已登出"
}
```

### 健康檢查

```bash
GET /health
```

### 取得郵件列表

```bash
GET /emails?n=5&use_cache=true&cache_ttl=3600
```

**說明：** 需要先進行 OAuth2 登入，否則會返回 401 錯誤

**參數：**

- `n`: 要抓取的郵件數量（預設: 5）
- `use_cache`: 是否使用快取（預設: true）
- `cache_ttl`: 快取存活時間，秒（預設: 3600）

**未登入時的回應（401）：**

```json
{
  "success": false,
  "error": "未登入，請先進行 OAuth2 認證",
  "auth_url": "/auth/gmail/login"
}
```

### 同步郵件到 Pinecone

```bash
POST /emails/sync
Content-Type: application/json

{
  "mode": "weekly",
  "n": 10,
  "namespace": "user_123"  // 可選
}
```

**說明：** 將郵件從 Gmail 抓取並向量化存入 Pinecone

**參數：**

- `mode`: "recent" (最新幾封) 或 "weekly" (上週) (預設: weekly)
- `n`: 要同步的郵件數量 (預設: 10)
- `namespace`: 可選的命名空間（用於區分不同用戶或時間段）

### 語意搜尋郵件

```bash
POST /emails/search
Content-Type: application/json

{
  "query": "上週有什麼重要的面試？",
  "k": 5,
  "namespace": "user_123"  // 可選
}
```

**說明：** 使用 Pinecone 進行語意搜尋，找出最相關的郵件

**參數：**

- `query`: 搜尋查詢（必填）
- `k`: 返回最相似的 k 個結果 (預設: 5)
- `namespace`: 可選的命名空間

### 搜尋並回答（RAG 流程）

```bash
POST /emails/search-with-answer
Content-Type: application/json

{
  "question": "上週我有什麼重要的面試？",
  "k": 5,
  "namespace": "user_123"  // 可選
}
```

**說明：** 完整的 RAG 流程：

1. 從 Pinecone 搜尋相關郵件
2. 使用 LLM 基於搜尋結果回答問題

**參數：**

- `question`: 使用者問題 (必填)
- `k`: 從 Pinecone 返回最相似的 k 個結果 (預設: 5)
- `namespace`: 可選的命名空間

### 郵件摘要

```bash
POST /emails/summarize
Content-Type: application/json

{
  "n": 5
}
```

或者提供郵件列表：

```json
{
  "emails": [
    {
      "subject": "主旨",
      "sender": "寄件者",
      "content": "內容..."
    }
  ]
}
```

### 聊天（與 AI Agent 對話）

```bash
POST /chat
Content-Type: application/json

{
  "message": "上週我有什麼重要的面試？",
  "use_emails": true,
  "search_emails": true,
  "k": 3
}
```

**說明：** 與 AI Agent 對話，可以選擇使用郵件上下文

**參數：**
- `message`: 使用者訊息 (必填)
- `use_emails`: 是否使用郵件上下文 (預設: false)
- `search_emails`: 如果 use_emails 為 true，是否先搜尋相關郵件 (預設: true)
- `k`: 如果 search_emails 為 true，搜尋最相似的 k 個郵件 (預設: 3)
- `namespace`: 可選的命名空間（用於 Pinecone 搜尋）

**前端聊天介面：** 訪問 `http://localhost:8080/` 使用網頁聊天介面

### 問答

```bash
POST /emails/ask
Content-Type: application/json

{
  "question": "這些郵件中有提到什麼重要事項嗎？",
  "n": 5
}
```

## 環境變數說明

在你的 `.env` 檔案中需要設定以下變數：

| 變數名稱                   | 說明                              | 必填                                       | 範例                                            |
| -------------------------- | --------------------------------- | ------------------------------------------ | ----------------------------------------------- |
| `GOOGLE_API_KEY`         | Google API Key (Gemini)           | 是                                         | 從 [Google AI Studio](https://makersuite.google.com/app/apikey) 取得 |
| `REDIS_HOST`             | Redis 主機地址                    | 否（預設: localhost）                      | `localhost`                                   |
| `REDIS_PORT`             | Redis 端口                        | 否（預設: 6379）                           | `6379`                                        |
| `SECRET_KEY`             | Flask 加密金鑰（用於 session）    | 是（生產環境）                             | 隨機字串                                        |
| `GMAIL_CREDENTIALS_PATH` | Gmail OAuth 憑證路徑              | 否（預設: credentials/google_secret.json） | `credentials/google_secret.json`              |
| `GMAIL_TOKEN_PATH`       | Gmail Token 儲存路徑              | 否（預設: credentials/token.json）         | `credentials/token.json`                      |
| `BASE_URL`               | 應用程式基礎 URL（OAuth2 回調用） | 否（預設: http://localhost:8080）          | `http://localhost:8080`                       |
| `FRONTEND_URL`           | 前端 URL（OAuth2 成功後重定向）   | 否（預設: http://localhost:8080）          | `http://localhost:8080`                       |
| `PINECONE_API_KEY`       | Pinecone API Key                  | 是（如果使用 Pinecone）                    | 從[Pinecone Console](https://app.pinecone.io) 取得 |
| `GEMINI_MODEL_NAME`      | Gemini 模型名稱                   | 否（預設: gemini-pro）                     | `gemini-pro` 或 `gemini-1.5-pro`              |
| `PINECONE_INDEX_NAME`    | Pinecone Index 名稱               | 否（預設: gmail-index）                    | `gmail-index`                                 |
| `PINECONE_REGION`        | Pinecone 區域                     | 否（預設: us-east-1）                      | `us-east-1`                                   |

### .env 範例

```env
GOOGLE_API_KEY=your-google-gemini-api-key
PINECONE_API_KEY=your-pinecone-api-key
SECRET_KEY=your-secret-key-here
BASE_URL=http://localhost:8080
FRONTEND_URL=http://localhost:8080
REDIS_HOST=localhost
REDIS_PORT=6379
PINECONE_INDEX_NAME=gmail-index
PINECONE_REGION=us-east-1
GEMINI_MODEL_NAME=gemini-pro
```

## 開發注意事項

1. **首次使用 Gmail API**：第一次運行時會開啟瀏覽器進行 OAuth 授權，授權後會自動儲存 token.json
2. **Redis 快取**：郵件資料會快取在 Redis 中，預設 1 小時過期
3. **環境變數**：敏感資訊請放在 `.env` 檔案中，不要提交到版本控制系統

## 部署

### 使用 Docker Compose（生產環境）

```bash
docker-compose up -d --build
```

### 使用 Gunicorn（生產環境）

```bash
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

## 授權

MIT License
