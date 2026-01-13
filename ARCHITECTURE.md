# Homework Helper 專案架構學習指南

> 本文件詳細說明如何使用 LangChain、LangGraph、RAG 技術以及 Flask 應用程式架構來建構一個智能問答系統。

## 📋 目錄

1. [專案概述](#專案概述)
2. [整體架構](#整體架構)
3. [技術棧](#技術棧)
4. [Flask 應用程式架構](#flask-應用程式架構)
5. [LangChain 與 RAG 實作](#langchain-與-rag-實作)
6. [LangGraph 工作流程](#langgraph-工作流程)
7. [資料流程](#資料流程)
8. [核心元件詳解](#核心元件詳解)
9. [部署架構](#部署架構)
10. [學習重點](#學習重點)

---

## 專案概述

這是一個基於 **RAG (Retrieval-Augmented Generation)** 技術的 AI 助教系統，主要功能包括：

- 📄 **文件上傳與索引**：支援 PDF 和文字檔，自動進行分塊和向量化
- 💬 **智能問答**：基於上傳的文件內容回答使用者問題
- 🧠 **對話記憶**：使用 Redis 儲存對話歷史，支援多輪對話
- 🔍 **文件評分機制**：使用 LLM 評估檢索文件的相關性，提升回答品質

---

## 整體架構

```
┌─────────────────────────────────────────────────────────────┐
│                        前端層 (Frontend)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  index.html (Bootstrap UI)                           │   │
│  │  - 文件上傳介面                                       │   │
│  │  - 聊天對話介面                                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/JSON
┌─────────────────────────────────────────────────────────────┐
│                    Flask 應用程式層 (Backend)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  routes.py (API Endpoints)                          │   │
│  │  - POST /api/upload  (文件上傳)                      │   │
│  │  - POST /api/chat    (問答對話)                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ↕                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  services/langchain_svc.py (核心服務層)              │   │
│  │  - LangChainService                                  │   │
│  │  - LangGraph Workflow                                │   │
│  │  - RAG Pipeline                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                      資料儲存層 (Storage)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   ChromaDB   │  │    Redis     │  │   Ollama     │    │
│  │  (向量資料庫) │  │  (對話記憶)  │  │  (Embedding) │    │
│  │              │  │              │  │              │    │
│  │  - 文件向量   │  │  - 對話歷史   │  │  - 文字向量化 │    │
│  │  - 語意搜尋   │  │  - Session   │  │  - 本地模型   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                      LLM 服務層 (AI Models)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Google Gemini (gemini-2.5-flash)                    │   │
│  │  - 文字生成                                            │   │
│  │  - 文件評分                                            │   │
│  │  - 結構化輸出                                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 技術棧

### 後端框架

- **Flask**: 輕量級 Python Web 框架
- **Blueprint**: Flask 模組化路由管理

### LangChain 生態系

- **langchain**: 核心框架
- **langchain-google-genai**: Google Gemini 整合
- **langchain-ollama**: 本地 Embedding 模型
- **langchain-chroma**: ChromaDB 向量資料庫整合
- **langchain-community**: 社群擴充套件
- **langchain-text-splitters**: 文件分塊工具

### LangGraph

- **langgraph**: 狀態圖工作流程管理
- 用於建構複雜的 RAG 工作流程

### 資料儲存

- **ChromaDB**: 開源向量資料庫，用於儲存文件嵌入向量
- **Redis**: 記憶體資料庫，用於儲存對話歷史

### 部署

- **Docker**: 容器化應用程式
- **Docker Compose**: 多容器編排

---

## Flask 應用程式架構

### 1. 應用程式初始化 (`app/__init__.py`)

```python
from flask import Flask

def create_app():
    app = Flask(__name__)
  
    # 註冊 Blueprint
    from app.routes import main_bp
    app.register_blueprint(main_bp)
  
    return app
```

**設計模式：應用程式工廠 (Application Factory)**

- 優點：支援多實例、測試友好、延遲初始化
- 使用 `create_app()` 函數創建應用程式實例

### 2. 路由層 (`app/routes.py`)

```python
from flask import Blueprint, render_template, request, jsonify
from app.services.langchain_svc import LangChainService

main_bp = Blueprint('main', __name__)
lc_service = None

def get_service():
    global lc_service
    if lc_service is None:
        lc_service = LangChainService()
    return lc_service
```

**設計模式：單例模式 (Singleton)**

- `get_service()` 確保整個應用程式只有一個 `LangChainService` 實例
- 避免重複初始化昂貴的資源（LLM、向量資料庫連線等）

**API 端點：**

#### `/api/upload` - 文件上傳

```python
@main_bp.route('/api/upload', methods=['POST'])
def upload_file():
    # 1. 接收檔案
    file = request.files['file']
  
    # 2. 暫存到磁碟
    save_path = os.path.join("/tmp", file.filename)
    file.save(save_path)
  
    # 3. 處理檔案（分塊、向量化、儲存）
    svc = get_service()
    chunks_count = svc.process_file(save_path, file.filename)
  
    # 4. 清理暫存檔
    os.remove(save_path)
  
    return jsonify({"status": "success", "chunks": chunks_count})
```

**流程說明：**

1. 接收前端上傳的檔案
2. 暫存到 `/tmp` 目錄（LangChain Loader 需要實體檔案路徑）
3. 呼叫服務層處理檔案
4. 清理暫存檔

#### `/api/chat` - 問答對話

```python
@main_bp.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id', 'default_user')
  
    svc = get_service()
    result = svc.get_answer(user_message, session_id)
  
    return jsonify({
        "answer": result.get('answer'),
        "source_documents": result.get('sources', [])
    })
```

**流程說明：**

1. 接收使用者訊息和 session_id
2. 呼叫服務層的 `get_answer()` 方法
3. 返回 AI 回答和來源文件

---

## LangChain 與 RAG 實作

### RAG (Retrieval-Augmented Generation) 概念

RAG 是一種結合**檢索 (Retrieval)** 和**生成 (Generation)** 的技術：

1. **檢索階段**：從知識庫中找出與問題相關的文件
2. **增強階段**：將檢索到的文件作為上下文
3. **生成階段**：LLM 基於上下文生成回答

**優點：**

- 減少 LLM 的幻覺 (Hallucination)
- 可以引用具體來源
- 知識庫可以持續更新

### 核心服務 (`app/services/langchain_svc.py`)

#### 1. 初始化元件

```python
class LangChainService:
    def __init__(self):
        # 1. LLM (大語言模型)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            convert_system_message_to_human=True
        )
      
        # 2. Embedding 模型 (文字向量化)
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url="http://host.docker.internal:11434"
        )
      
        # 3. 向量資料庫
        self.chroma_client = chromadb.HttpClient(
            host="chromadb", 
            port=8000
        )
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name="my_knowledge_base",
            embedding_function=self.embeddings
        )
      
        # 4. 檢索器 (Retriever)
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": 3}  # 返回最相似的 3 個文件
        )
      
        # 5. 建構 LangGraph 工作流程
        self.app = self.build_graph()
```

**元件說明：**

- **LLM**: 負責文字生成和文件評分
- **Embeddings**: 將文字轉換為向量，用於語意搜尋
- **Vector Store**: 儲存文件向量，支援相似度搜尋
- **Retriever**: 封裝檢索邏輯，從向量資料庫中找出相關文件

#### 2. 文件處理 (`process_file`)

```python
def process_file(self, file_path, original_filename):
    # 1. 載入文件
    if file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
  
    # 2. 文件分塊 (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,      # 每個塊 1000 字元
        chunk_overlap=200      # 塊之間重疊 200 字元
    )
    splits = text_splitter.split_documents(docs)
  
    # 3. 添加元資料
    for split in splits:
        split.metadata['source'] = original_filename
  
    # 4. 向量化並儲存到 ChromaDB
    self.vector_store.add_documents(documents=splits)
  
    return len(splits)
```

**文件分塊的重要性：**

- LLM 有 Token 限制，不能一次處理整個文件
- 分塊可以讓檢索更精準（只檢索相關段落）
- 重疊 (overlap) 確保上下文不丟失

---

## LangGraph 工作流程

### 什麼是 LangGraph？

LangGraph 是 LangChain 的擴展，用於建構**狀態圖 (State Graph)** 工作流程。它允許你定義複雜的多步驟 AI 應用程式。

### 狀態定義

```python
class GraphState(TypedDict):
    question: str              # 使用者問題
    messages: List[BaseMessage] # 對話歷史
    documents: List[Document]  # 檢索到的文件
    generation: str            # 生成的回答
    relevance: str             # 相關性評分（可選）
```

**TypedDict 說明：**

- 定義了 Graph 中流動的資料結構
- 每個節點可以讀取和更新這些狀態

### 工作流程節點

#### 1. Retrieve 節點 - 檢索文件

```python
def retrieve(self, state: GraphState):
    """從向量資料庫中檢索相關文件"""
    question = state.get("question", "")
  
    # 使用 Retriever 搜尋相關文件
    documents = self.retriever.invoke(question)
  
    return {"documents": documents, "question": question}
```

**功能：**

- 將使用者問題轉換為向量
- 在 ChromaDB 中搜尋最相似的 k 個文件塊
- 返回候選文件列表

#### 2. Grade Documents 節點 - 評分文件

```python
def grade_documents(self, state: GraphState):
    """使用 LLM 評估文件與問題的相關性"""
    question = state.get("question", "")
    documents = state.get("documents", [])
  
    # 定義評分器的輸出結構
    class GradeDocuments(BaseModel):
        binary_score: str = Field(description="'yes' 或 'no'")
  
    # 使用結構化輸出
    structured_llm_grader = self.llm.with_structured_output(GradeDocuments)
  
    # 評分提示詞
    grade_prompt = ChatPromptTemplate.from_messages([
        ("system", "評估文件與問題的相關性"),
        ("human", "文件: {document}\n問題: {question}"),
    ])
  
    retrieval_grader = grade_prompt | structured_llm_grader
  
    # 過濾不相關的文件
    filtered_docs = []
    for doc in documents:
        score = retrieval_grader.invoke({
            "question": question, 
            "document": doc.page_content
        })
        if score.binary_score == "yes":
            filtered_docs.append(doc)
  
    return {"documents": filtered_docs}
```

**為什麼需要評分？**

- 向量搜尋可能返回不相關的文件（關鍵字匹配但語意無關）
- LLM 可以更準確地判斷語意相關性
- 過濾掉不相關文件，提升最終回答品質

**結構化輸出 (Structured Output)：**

- 使用 Pydantic 定義輸出格式
- LLM 會按照定義的格式返回結果
- 確保程式碼可以可靠地解析 LLM 輸出

#### 3. Generate 節點 - 生成回答

```python
def generate(self, state: GraphState):
    """基於檢索到的文件生成回答"""
    question = state.get("question", "")
    documents = state.get("documents", [])
    messages = state.get("messages", [])  # 對話歷史
  
    if not documents:
        return {"generation": "抱歉，找不到相關資訊。"}
  
    # 建構 RAG Prompt
    prompt = ChatPromptTemplate.from_messages([
        (
            "system", 
            "你是專業助教。根據以下 Context 回答問題。\n\n"
            "【參考資訊】:\n{context}"
        ),
        ("placeholder", "{messages}"),  # 對話歷史
    ])
  
    rag_chain = prompt | self.llm
  
    # 將文件合併為上下文
    docs_txt = "\n\n".join([d.page_content for d in documents])
  
    # 生成回答
    generation = rag_chain.invoke({
        "context": docs_txt,
        "messages": messages
    })
  
    return {"generation": generation.content}
```

**RAG Prompt 設計：**

- **System Message**: 定義 AI 角色和 Context
- **Messages Placeholder**: 自動填入對話歷史
- **Context**: 檢索到的文件內容

### 建構工作流程圖

```python
def build_graph(self):
    workflow = StateGraph(GraphState)
  
    # 添加節點
    workflow.add_node("retrieve", self.retrieve)
    workflow.add_node("grade_documents", self.grade_documents)
    workflow.add_node("generate", self.generate)
  
    # 定義邊 (Edge) - 執行順序
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_edge("grade_documents", "generate")
    workflow.add_edge("generate", END)
  
    return workflow.compile()
```

**工作流程圖：**

```
START → retrieve → grade_documents → generate → END
         (檢索)      (評分過濾)        (生成)
```

**執行流程：**

1. **START** → 接收使用者問題
2. **retrieve** → 從向量資料庫檢索候選文件
3. **grade_documents** → 使用 LLM 評分並過濾文件
4. **generate** → 基於過濾後的文件生成回答
5. **END** → 返回最終結果

### 執行工作流程

```python
def get_answer(self, question, session_id):
    # 1. 從 Redis 載入對話歷史
    chat_history = RedisChatMessageHistory(
        session_id=session_id,
        url=self.redis_url,
        key_prefix="chat:"
    )
  
    # 2. 準備輸入
    current_messages = chat_history.messages + [
        HumanMessage(content=question)
    ]
  
    inputs = {
        "messages": current_messages,
        "question": question,
        "documents": [],
        "generation": "",
        "relevance": ""
    }
  
    # 3. 執行 Graph
    final_state = self.app.invoke(inputs)
  
    # 4. 取得結果
    final_answer = final_state.get("generation", "")
  
    # 5. 更新 Redis 記憶
    chat_history.add_user_message(question)
    chat_history.add_ai_message(final_answer)
  
    return {"answer": final_answer, "sources": [...]}
```

---

## 資料流程

### 文件上傳流程

```
使用者上傳 PDF/Text
    ↓
Flask 接收檔案 (routes.py)
    ↓
暫存到 /tmp
    ↓
LangChainService.process_file()
    ↓
┌─────────────────────────┐
│ 1. PyPDFLoader/TextLoader│ → 載入原始文件
│ 2. RecursiveTextSplitter │ → 分塊 (1000字元, 200重疊)
│ 3. 添加 metadata         │ → 標記來源檔案
│ 4. vector_store.add_     │ → 向量化並儲存到 ChromaDB
└─────────────────────────┘
    ↓
返回 chunks_count
```

### 問答流程

```
使用者輸入問題
    ↓
Flask /api/chat (routes.py)
    ↓
LangChainService.get_answer()
    ↓
從 Redis 載入對話歷史
    ↓
LangGraph 執行
    ↓
┌─────────────────────────────────────┐
│ 1. retrieve 節點                    │
│    - question → embedding           │
│    - ChromaDB 向量搜尋 (k=3)        │
│    → 返回候選文件                    │
│                                     │
│ 2. grade_documents 節點             │
│    - LLM 評分每個文件                │
│    - 過濾 binary_score='no' 的文件  │
│    → 返回相關文件                    │
│                                     │
│ 3. generate 節點                    │
│    - 合併文件為 Context             │
│    - 加入對話歷史                    │
│    - LLM 生成回答                    │
│    → 返回最終回答                    │
└─────────────────────────────────────┘
    ↓
更新 Redis 對話歷史
    ↓
返回回答和來源文件
```

---

## 核心元件詳解

### 1. Redis 服務 (`app/services/redis_svc.py`)

```python
class RedisService:
    _instance = None
  
    def __new__(cls):
        """單例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_connection()
        return cls._instance
  
    def init_connection(self):
        self.redis_url = "redis://redis:6379/0"
        self.pool = redis.ConnectionPool.from_url(
            self.redis_url, 
            decode_responses=True
        )
        self.client = redis.Redis(connection_pool=self.pool)
```

**用途：**

- 儲存對話歷史（每個 session_id 獨立）
- 使用連線池提升效能
- 單例模式確保只有一個連線池

**對話歷史結構：**

```
Redis Key: "chat:{session_id}"
Value: List of messages
  - HumanMessage("問題1")
  - AIMessage("回答1")
  - HumanMessage("問題2")
  - AIMessage("回答2")
```

### 2. 向量資料庫 (ChromaDB)

**為什麼需要向量資料庫？**

- 傳統資料庫無法進行語意搜尋
- 向量資料庫支援相似度搜尋（Cosine Similarity）
- 可以快速找出語意相關的文件

**ChromaDB 特點：**

- 開源、輕量級
- 支援持久化儲存
- 提供 HTTP API
- 整合 LangChain 生態系

**資料結構：**

```
Collection: "my_knowledge_base"
  Document 1:
    - id: "doc_1_chunk_0"
    - embedding: [0.1, 0.2, ..., 0.9]  (768維向量)
    - metadata: {"source": "file1.pdf", "chunk_index": 0}
    - content: "文件內容..."
```

### 3. Embedding 模型 (Ollama)

**什麼是 Embedding？**

- 將文字轉換為數值向量
- 語意相似的文字會有相似的向量
- 用於計算文字之間的相似度

**Ollama 本地模型：**

- `nomic-embed-text`: 開源 Embedding 模型
- 可以在本地運行，不需要 API Key
- 適合開發和測試環境

**Embedding 流程：**

```
文字 → Embedding 模型 → 向量
"什麼是 Python？" → [0.1, 0.2, ..., 0.9]
"Python 是什麼？" → [0.11, 0.21, ..., 0.91]  (相似向量)
```

### 4. LLM (Google Gemini)

**為什麼選擇 Gemini？**

- 免費額度較高
- 支援結構化輸出
- 回應速度快

**使用場景：**

1. **文件評分**：判斷文件與問題的相關性
2. **文字生成**：基於 Context 生成回答
3. **結構化輸出**：確保輸出格式一致

---

## 部署架構

### Docker Compose 配置

```yaml
services:
  web:
    build: .
    ports:
      - "5001:5000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - CHROMA_DB_HOST=chromadb
      - CHROMA_DB_PORT=8000
    depends_on:
      - redis
      - chromadb

  redis:
    image: redis/redis-stack:latest
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
```

**服務說明：**

- **web**: Flask 應用程式容器
- **redis**: 對話記憶儲存
- **chromadb**: 向量資料庫

**網路架構：**

- 所有服務在同一個 Docker 網路中
- 使用服務名稱進行內部通訊（`redis`, `chromadb`）
- Ollama 在主機上運行，使用 `host.docker.internal` 訪問

---

## 學習重點

### 1. Flask 應用程式設計模式

✅ **應用程式工廠模式**

- 使用 `create_app()` 函數創建應用程式
- 支援多實例和測試

✅ **Blueprint 模組化**

- 將路由組織成模組
- 提升程式碼可維護性

✅ **單例模式**

- 確保服務只初始化一次
- 節省資源和提升效能

### 2. LangChain 核心概念

✅ **Document Loaders**

- 支援多種檔案格式（PDF、Text、CSV 等）
- 自動處理編碼和格式轉換

✅ **Text Splitters**

- 智能分塊策略
- 保留上下文（overlap）

✅ **Vector Stores**

- 統一的向量資料庫介面
- 支援多種後端（ChromaDB、Pinecone、Weaviate 等）

✅ **Retrievers**

- 封裝檢索邏輯
- 支援多種搜尋策略（相似度、MMR、自定義等）

### 3. LangGraph 工作流程設計

✅ **狀態管理**

- 使用 TypedDict 定義狀態結構
- 節點之間通過狀態傳遞資料

✅ **節點設計**

- 每個節點職責單一
- 節點可以讀取和更新狀態

✅ **邊 (Edge) 設計**

- 定義執行順序
- 可以根據條件動態路由（本專案未使用，但 LangGraph 支援）

### 4. RAG 最佳實踐

✅ **文件分塊**

- 適當的 chunk_size（1000-2000 字元）
- 使用 overlap 保留上下文

✅ **文件評分**

- 使用 LLM 過濾不相關文件
- 提升最終回答品質

✅ **Prompt 設計**

- 明確的 System Message
- 清晰的 Context 格式
- 保留對話歷史

✅ **對話記憶**

- 使用 Redis 儲存歷史
- 支援多輪對話
- 每個 session 獨立

### 5. 錯誤處理與除錯

✅ **異常處理**

- 在關鍵節點加入 try-except
- 提供友好的錯誤訊息

✅ **日誌記錄**

- 記錄關鍵步驟
- 方便追蹤問題

✅ **除錯工具**

- `get_graph_trace()` 方法
- 可以查看每個節點的執行狀態

---

## 進階擴展建議

### 1. 條件路由 (Conditional Edges)

可以根據文件評分結果決定是否重新檢索：

```python
def should_retry(self, state: GraphState):
    documents = state.get("documents", [])
    if len(documents) == 0:
        return "retry_retrieve"  # 沒有相關文件，重新檢索
    return "generate"  # 有文件，直接生成

workflow.add_conditional_edges(
    "grade_documents",
    should_retry,
    {
        "retry_retrieve": "retrieve",
        "generate": "generate"
    }
)
```

### 2. 回答品質評分

在生成回答後，可以再次使用 LLM 評分回答品質：

```python
def grade_answer(self, state: GraphState):
    question = state.get("question", "")
    generation = state.get("generation", "")
  
    # 評分回答是否解決了問題
    # 如果評分低，可以重新生成或要求使用者澄清
    ...
```

### 3. 多輪檢索 (Multi-Retrieval)

如果第一次檢索結果不理想，可以：

- 重新表述問題
- 擴大搜尋範圍
- 使用不同的檢索策略

### 4. 來源引用

改進 `get_answer()` 方法，返回更詳細的來源資訊：

```python
sources = []
for doc in final_state.get("documents", []):
    sources.append({
        "content": doc.page_content[:200] + "...",
        "source": doc.metadata.get("source", "unknown"),
        "page": doc.metadata.get("page", None)
    })
```

### 5. 流式輸出 (Streaming)

使用 LangGraph 的 `stream()` 方法實現流式回應：

```python
for output in self.app.stream(inputs):
    # 逐步返回結果，提升使用者體驗
    yield output
```

---

## 總結

這個專案展示了如何結合以下技術建構一個完整的 RAG 系統：

1. **Flask**: Web 應用程式框架
2. **LangChain**: AI 應用程式開發框架
3. **LangGraph**: 複雜工作流程管理
4. **RAG**: 檢索增強生成技術
5. **向量資料庫**: 語意搜尋
6. **Redis**: 對話記憶管理

**關鍵學習點：**

- 如何設計分層架構（路由層、服務層、資料層）
- 如何使用 LangGraph 建構複雜工作流程
- 如何實作 RAG 系統的核心功能
- 如何整合多種技術棧（Flask、Redis、ChromaDB、LLM）

**下一步學習方向：**

- 探索更複雜的 LangGraph 模式（Agent、Tool Calling）
- 優化 RAG 流程（重新排序、混合檢索）
- 實作更進階的功能（多模態、知識圖譜）
- 部署到生產環境（Gunicorn、Nginx、監控）

---

**祝學習愉快！** 🚀
