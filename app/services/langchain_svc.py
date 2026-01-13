import os
from typing import List, Literal, Dict
from typing_extensions import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage

# --- Redis 聊天紀錄 ---
from langchain_community.chat_message_histories import RedisChatMessageHistory
from app.services.redis_svc import redis_svc  # <--- 引入剛剛寫好的服務

# --- 修正點：直接使用 pydantic ---
from pydantic import BaseModel, Field
# ------------------------------

# --- LangGraph 核心 ---
from langgraph.graph import END, StateGraph, START

import chromadb

# --- 定義 Graph 的狀態 (State) ---
class GraphState(TypedDict):
    question: str
    messages: List[BaseMessage]
    documents: List[Document]
    generation: str
    relevance: str

# --- 定義評分器的資料結構 ---
class GradeDocuments(BaseModel):
    """評分檢索到的文件是否與問題相關"""
    binary_score: str = Field(description="文件是否與問題相關，'yes' 或 'no'")

class GradeAnswer(BaseModel):
    """評分回答是否解決了問題"""
    binary_score: str = Field(description="回答是否解決了問題，'yes' 或 'no'")

class LangChainService:
    def __init__(self):
        # 1. 設定 LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            convert_system_message_to_human=True
        )

        # 2. 設定 Ollama
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=ollama_url
        )

        # 3. 設定 ChromaDB
        chroma_host = os.getenv("CHROMA_DB_HOST", "chromadb")
        chroma_port = int(os.getenv("CHROMA_DB_PORT", 8000))
        
        self.chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name="my_knowledge_base",
            embedding_function=self.embeddings
        )
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})

        # 初始化 Graph
        self.app = self.build_graph()

        self.redis_url = redis_svc.get_url()

    # ==========================
    #      Node Functions
    # ==========================

    def retrieve(self, state: GraphState):
        """節點：檢索文件"""
        question = state.get("question", "")
        if not question:
            # 如果沒有 question，嘗試從 messages 中取得最後一個用戶訊息
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    question = last_msg.content
                elif isinstance(last_msg, dict):
                    question = last_msg.get('content', '')
        
        documents = self.retriever.invoke(question) if question else []
        return {"documents": documents, "question": question}

    def grade_documents(self, state: GraphState):
        """節點：評分並過濾文件"""
        question = state.get("question", "")
        documents = state.get("documents", [])
        
        if not question:
            # 如果沒有 question，嘗試從 messages 中取得
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    question = last_msg.content
                elif isinstance(last_msg, dict):
                    question = last_msg.get('content', '')
        
        structured_llm_grader = self.llm.with_structured_output(GradeDocuments)
        
        system = """你是一個評分員，負責評估檢索到的文件與使用者問題的相關性。
        如果是關鍵字匹配或語意相關，請評為 'yes'。不需要非常嚴格，目標是過濾掉完全錯誤的文件。
        請依照 JSON 格式回傳 binary_score。"""
        
        grade_prompt = ChatPromptTemplate.from_messages([
            ("system", system),
            ("human", "Retrieved document: \n\n {document} \n\n User question: {question}"),
        ])
        
        retrieval_grader = grade_prompt | structured_llm_grader
        
        filtered_docs = []
        for doc in documents:
            # 加入錯誤處理，避免 LLM 輸出格式錯誤導致崩潰
            try:
                score = retrieval_grader.invoke({"question": question, "document": doc.page_content})
                if score and score.binary_score == "yes":
                    filtered_docs.append(doc)
            except Exception as e:
                filtered_docs.append(doc) # 保守策略：如果評分失敗，先保留文件
                
        return {"documents": filtered_docs, "question": question}

    def generate(self, state: GraphState):
        """節點：生成回答"""
        question = state.get("question", "")
        documents = state.get("documents", [])
        messages = state.get("messages", []) # <--- 1. 務必從 state 取得完整的對話歷史
        
        if not question and messages:
            # 如果沒有 question，從 messages 中取得最後一個用戶訊息
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                question = last_msg.content
            elif isinstance(last_msg, dict):
                question = last_msg.get('content', '')
        
        if not documents:
            return {"documents": [], "question": question, "generation": "抱歉，我在知識庫中找不到與您問題相關的有效資訊。"}

        # --- 2. 修改 Prompt 結構 ---
        # 最佳實踐：把 Context 放在 System Message 裡，讓對話歷史保持自然流暢
        prompt = ChatPromptTemplate.from_messages([
            (
                "system", 
                "你是一個專業助教。請根據以下檢索到的 Context 回答問題。若 Context 無法回答，請說不知道。\n\n"
                "【參考資訊 (Context)】:\n{context}"
            ),
            # 這裡會自動填入 [歷史對話 A, 歷史回答 B, ..., 最新問題]
            ("placeholder", "{messages}"), 
        ])
        
        rag_chain = prompt | self.llm
        
        docs_txt = "\n\n".join([d.page_content for d in documents])
        
        # --- 3. 修改 invoke 參數 ---
        # 這裡必須同時傳入 'context' 和 'messages'
        generation = rag_chain.invoke({
            "context": docs_txt, 
            "messages": messages
        })
        
        return {"documents": documents, "question": question, "generation": generation.content}

    def build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("grade_documents", self.grade_documents)
        workflow.add_node("generate", self.generate)

        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "grade_documents")
        workflow.add_edge("grade_documents", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    # ==========================
    #      Public API
    # ==========================
    # (process_file 函式保持不變，不用動)
    def process_file(self, file_path, original_filename):
        from langchain_community.document_loaders import PyPDFLoader, TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        try:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding='utf-8')
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            for split in splits:
                split.metadata['source'] = original_filename
            self.vector_store.add_documents(documents=splits)
            return len(splits)
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def get_answer(self, question, session_id):
        """
        執行 Graph，並掛載 Redis 記憶
        """
        # 1. 連線 Redis 取得歷史紀錄
        #這會自動去 Redis 找 key 為 "chat:session_id" 的資料
        chat_history = RedisChatMessageHistory(
            session_id=session_id,
            url=self.redis_url,
            key_prefix="chat:" 
        )

        # 2. 準備輸入給 Graph 的訊息列表
        # 我們把「歷史紀錄」+「現在使用者的問題」串接起來
        # 注意：為了避免 Token 爆炸，實務上通常會限制只取最後 10 句，這裡先全取
        current_messages = chat_history.messages + [HumanMessage(content=question)]

        # 3. 執行 Graph
        # 注意：GraphState 需要包含所有必要的字段
        inputs = {
            "messages": current_messages, 
            "question": question,
            "documents": [],  # 初始為空，會在 retrieve 節點中填充
            "generation": "",  # 初始為空，會在 generate 節點中填充
            "relevance": ""  # 可選字段
        }
        
        try:
            final_state = self.app.invoke(inputs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

        # 4. 解析結果
        # 從 Graph 的 generation 字段取得 AI 的回答（不是從 messages）
        final_answer = final_state.get("generation", "")
        
        # 如果 generation 為空，嘗試從 messages 中尋找最後一個 AI 訊息
        if not final_answer:
            from langchain_core.messages import AIMessage
            for msg in reversed(final_state.get("messages", [])):
                if isinstance(msg, AIMessage) and hasattr(msg, 'content') and msg.content:
                    final_answer = msg.content
                    break
        
        # 如果還是沒有答案，返回錯誤訊息
        if not final_answer:
            final_answer = "抱歉，無法產生回應。"
        
        # 5. 更新 Redis 記憶
        # 必須手動把這一輪的「問」與「答」存進去
        chat_history.add_user_message(question)
        chat_history.add_ai_message(final_answer)
        
        # 6. 提取來源 (Artifacts)
        sources = []
        for msg in final_state["messages"]:
            if hasattr(msg, "artifact") and msg.artifact:
                for doc in msg.artifact:
                    sources.append(doc.metadata.get('source', 'unknown'))

        return {
            "answer": final_answer,
            "sources": list(set(sources))
        }
    
    # ==========================
    #      Debug API
    # ==========================
    def get_graph_trace(self, question):
        """
        除錯專用：回傳完整的 Graph 執行流程與中間狀態
        """
        inputs = {"question": question}
        
        # 用來儲存每一步的 log
        trace_logs = []
        final_answer = None
        
        print(f"--- [DEBUG] Start Processing: {question} ---")

        try:
            # 使用 stream 監聽每一個節點的輸出
            for output in self.app.stream(inputs):
                for node_name, state_content in output.items():
                    # 1. 紀錄節點名稱
                    print(f"--- [DEBUG] Node Finished: {node_name} ---")
                    
                    # 2. 處理資料 (轉成字串以免 JSON 序列化失敗)
                    # 這裡我們嘗試抓取關鍵資訊
                    log_entry = {
                        "node": node_name,
                        "state_snapshot": {}
                    }
                    
                    # 嘗試解析 state 內容
                    if "documents" in state_content:
                        log_entry["state_snapshot"]["docs_count"] = len(state_content["documents"])
                        log_entry["state_snapshot"]["docs_preview"] = [d.page_content[:50]+"..." for d in state_content["documents"]]
                    
                    if "generation" in state_content:
                        log_entry["state_snapshot"]["generation"] = state_content["generation"]
                        final_answer = state_content["generation"]

                    if "question" in state_content:
                        log_entry["state_snapshot"]["question"] = state_content["question"]

                    trace_logs.append(log_entry)

        except Exception as e:
            trace_logs.append({"error": str(e)})
            print(f"--- [DEBUG] Error: {e} ---")

        return {
            "final_answer": final_answer,
            "trace_logs": trace_logs
        }