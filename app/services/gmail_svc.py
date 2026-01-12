"""
Gmail 服務模組
負責處理 Gmail API 的連線、認證和郵件抓取邏輯
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from langchain_google_community import GMailLoader
from langchain_core.documents import Document

# 設定權限範圍：只讀取 Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

class GmailService:
    """Gmail 服務類別，封裝所有 Gmail 相關操作"""
    
    def __init__(self, credentials_path: str = "credentials/google_secret.json", 
                 token_path: str = "credentials/token.json",
                 redirect_uri: Optional[str] = None):
        """
        初始化 Gmail 服務
        Args:
            credentials_path: 下載的 OAuth credentials 檔案路徑
            token_path: 儲存/讀取 token 的檔案路徑
            redirect_uri: OAuth2 回調 URI（用於 Web 應用程式流程）
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.redirect_uri = redirect_uri
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        處理 Google 登入驗證 (自動處理 Token 刷新)
        """
        creds = None
        
        # 1. 嘗試讀取現有的 token
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"⚠️ 讀取 token 失敗: {e}")
        
        # 2. 如果沒有憑證或過期
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 憑證過期，正在重新整理...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"❌ 憑證刷新失敗: {e}")
                    creds = None
            
            # 如果真的沒有可用憑證 (這段在 Docker 內部如果沒有 GUI 會卡住，需注意)
            if not creds:
                print("🔑 找不到有效憑證，正在啟動瀏覽器登入 (僅限本地執行)...")
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"❌ 找不到 '{self.credentials_path}'！ 請確認檔案位置。"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=8080)
            
            # 3. 儲存新的 Token
            # 確保目錄存在（如果路徑包含目錄）
            try:
                token_dir = os.path.dirname(self.token_path)
                if token_dir:
                    os.makedirs(token_dir, exist_ok=True)
                
                if self.token_path:
                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())
                        print(f"✅ 登入成功！憑證已儲存至 {self.token_path}")
            except Exception as e:
                print(f"⚠️ 檔案儲存失敗: {e}")
        
        return creds
    
    def create_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        創建 OAuth2 授權 URL（用於 Web 應用程式流程）
        
        Args:
            state: 可選的狀態參數，用於防止 CSRF 攻擊
            
        Returns:
            (authorization_url, state) 元組
        """
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"❌ 找不到 '{self.credentials_path}'！請確認檔案位置。"
            )
        
        if not self.redirect_uri:
            raise ValueError("❌ redirect_uri 未設定！請設定 OAuth2 回調 URI。")
        
        # 創建 Flow 實例（Web 應用程式流程）
        flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        # 如果沒有提供 state，生成一個隨機的
        import secrets
        if not state:
            state = secrets.token_urlsafe(32)
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # 強制顯示同意畫面，確保能獲取 refresh_token
        )
        
        return authorization_url, state
    
    def get_credentials_from_code(self, code: str, state: Optional[str] = None) -> Credentials:
        """
        使用授權碼換取憑證（用於 OAuth2 回調處理）
        
        Args:
            code: OAuth2 授權碼
            state: 狀態參數（應該與授權時的一致）
            
        Returns:
            Credentials 物件
        """
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"❌ 找不到 '{self.credentials_path}'！請確認檔案位置。"
            )
        
        if not self.redirect_uri:
            raise ValueError("❌ redirect_uri 未設定！請設定 OAuth2 回調 URI。")
        
        # 創建 Flow 實例
        flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        # 使用授權碼換取 token
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # 儲存 token（可選，因為我們已經儲存到 session 了）
        # 但如果 token_path 設定為相對路徑，可能需要建立目錄
        try:
            token_dir = os.path.dirname(self.token_path)
            # 只有在路徑包含目錄時才建立目錄
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)
            
            # 只有當 token_path 有設定時才寫入檔案
            if self.token_path:
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
                    print(f"✅ 登入成功！憑證已儲存至 {self.token_path}")
        except Exception as e:
            # 如果檔案儲存失敗，仍然繼續（因為我們會儲存到 session）
            print(f"⚠️ 檔案儲存失敗（將使用 session）: {e}")
        
        return creds
    
    def get_credentials_from_dict(self, token_dict: dict) -> Credentials:
        """
        從字典載入憑證（用於 session 儲存）
        
        Args:
            token_dict: 包含 token 資訊的字典
            
        Returns:
            Credentials 物件
        """
        creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
        
        # 如果 token 過期且有 refresh_token，嘗試刷新
        if creds.expired and creds.refresh_token:
            try:
                print("🔄 從 session 載入的憑證已過期，正在刷新...")
                creds.refresh(Request())
                print("✅ Token 刷新成功")
            except Exception as e:
                print(f"⚠️ Token 刷新失敗: {e}")
                # 即使刷新失敗，也返回 creds，讓上層處理
        
        return creds

    def _get_last_week_query(self) -> str:
        """
        生成 Gmail 搜尋語法：抓取過去 7 天的郵件
        格式範例: 'after:2023/01/01 before:2023/01/08'
        """
        today = datetime.now()
        seven_days_ago = today - timedelta(days=7)
        
        # Gmail API 日期格式為 YYYY/MM/DD
        query = f"in:inbox after:{seven_days_ago.strftime('%Y/%m/%d')}"
        return query
    
    def _extract_message_body(self, payload: dict) -> str:
        """
        從 Gmail API 的 payload 中提取郵件正文
        
        Args:
            payload: Gmail API 返回的 payload 字典
            
        Returns:
            郵件正文文字
        """
        body = ""
        
        # 檢查是否有 parts（多部分郵件）
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                # 優先提取 text/plain
                if mime_type == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        import base64
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        break
                # 如果沒有 plain text，使用 html
                elif mime_type == 'text/html' and not body:
                    data = part.get('body', {}).get('data', '')
                    if data:
                        import base64
                        from bs4 import BeautifulSoup
                        html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(html, 'html.parser')
                        body = soup.get_text()
        else:
            # 單部分郵件
            mime_type = payload.get('mimeType', '')
            if mime_type in ['text/plain', 'text/html']:
                data = payload.get('body', {}).get('data', '')
                if data:
                    import base64
                    text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime_type == 'text/html':
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, 'html.parser')
                        body = soup.get_text()
                    else:
                        body = text
        
        return body.strip()

    def fetch_emails(self, mode: str = "recent", n: int = 5, credentials: Optional[Credentials] = None) -> List[Document]:
        """
        從 Gmail 抓取郵件
        
        Args:
            mode: "recent" (抓最新幾封) 或 "weekly" (抓上週)
            n: 若為 recent 模式，限制抓取數量；weekly 模式下為最大抓取上限
            credentials: 可選的 Credentials 物件，如果不提供則使用 get_credentials()
            
        Returns:
            Document 列表
        """
        if credentials is None:
            creds = self.get_credentials()
        else:
            creds = credentials
            
        if not creds:
            raise ValueError("無法取得有效的憑證")
        
        # 檢查並刷新過期的 token
        if creds.expired and creds.refresh_token:
            try:
                print("🔄 憑證已過期，正在刷新...")
                creds.refresh(Request())
                print("✅ Token 刷新成功")
            except Exception as e:
                print(f"⚠️ Token 刷新失敗: {e}")
                raise ValueError("憑證已過期且無法刷新，請重新登入")
        
        # 驗證憑證是否真的可用（即使 valid 為 false，也可能可以正常使用）
        # 我們直接嘗試使用，如果失敗會在 loader.load() 時拋出錯誤

        # 使用 Gmail API 直接抓取郵件（因為 GMailLoader 不支援查詢參數）
        try:
            from googleapiclient.discovery import build
            service = build('gmail', 'v1', credentials=creds)
            
            print(f"🔍 憑證狀態: valid={creds.valid}, expired={creds.expired}")
            
            # 設定查詢條件
            query = None
            if mode == "weekly":
                query = self._get_last_week_query()
                print(f"📅 正在抓取上週郵件，搜尋條件: {query}")
            else:
                # recent 模式：抓取 INBOX 中的最新郵件
                query = "in:inbox"
                print(f"📥 正在抓取 INBOX 中最新的 {n} 封郵件...")
            
            # 使用 Gmail API 搜尋郵件
            result = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=n
            ).execute()
            
            messages = result.get('messages', [])
            print(f"✅ Gmail API 找到 {len(messages)} 個訊息 ID")
            
            if not messages:
                print(f"⚠️ 沒有找到符合條件的郵件")
                # 嘗試不指定查詢條件
                print(f"   嘗試抓取所有最新郵件（不指定查詢條件）...")
                result = service.users().messages().list(
                    userId='me',
                    maxResults=n
                ).execute()
                messages = result.get('messages', [])
                print(f"   找到 {len(messages)} 個訊息 ID")
            
            if not messages:
                print(f"⚠️ Gmail 中沒有找到任何郵件")
                return []
            
            # 將 Gmail 訊息轉換為 Document
            docs = []
            for msg in messages[:n]:  # 限制數量
                try:
                    # 取得完整郵件內容
                    message = service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    # 解析郵件標頭
                    headers = message['payload'].get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '無主旨')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '未知')
                    date = next((h['value'] for h in headers if h['name'] == 'Date'), '未知')
                    
                    # 解析郵件內容
                    body = self._extract_message_body(message['payload'])
                    
                    # 創建 Document
                    doc = Document(
                        page_content=body,
                        metadata={
                            'id': msg['id'],
                            'subject': subject,
                            'from': sender,
                            'date': date,
                            'snippet': message.get('snippet', '')
                        }
                    )
                    docs.append(doc)
                except Exception as e:
                    print(f"⚠️ 處理郵件 {msg.get('id', 'unknown')} 失敗: {e}")
                    continue
            
            print(f"✅ 成功轉換 {len(docs)} 封郵件為 Document")
            return docs
            
            print(f"✅ 成功抓取到 {len(docs)} 筆資料！")
            
            # 除錯：顯示第一封郵件的基本資訊
            if docs and len(docs) > 0:
                first_doc = docs[0]
                print(f"📧 第一封郵件預覽：")
                print(f"   主旨: {first_doc.metadata.get('subject', '無主旨')}")
                print(f"   寄件者: {first_doc.metadata.get('from', '未知')}")
                print(f"   內容長度: {len(first_doc.page_content)} 字元")
            
            return docs
            
        except Exception as e:
            print(f"❌ 抓取錯誤: {e}")
            print(f"   錯誤類型: {type(e).__name__}")
            import traceback
            print(f"   詳細錯誤: {traceback.format_exc()}")
            raise
    
    def serialize_emails(self, docs: List[Document]) -> List[Dict]:
        """將 Document 轉換為 API 回傳用的 Dict"""
        serialized_emails = []
        for doc in docs:
            # 簡化內容，避免過長，也可以在這裡做些清理
            content_preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            
            email_dict = {
                "subject": doc.metadata.get("subject", "無主旨"),
                "sender": doc.metadata.get("from", "未知"),
                "date": doc.metadata.get("date", "未知"),
                "snippet": doc.metadata.get("snippet", ""),
                "content": content_preview, 
                "full_content": doc.page_content 
            }
            serialized_emails.append(email_dict)
        
        return serialized_emails

# --- 本地測試用 ---
if __name__ == "__main__":
    # 確保你有 credentials 資料夾
    service = GmailService(
        credentials_path="credentials/google_secret.json",
        token_path="credentials/token.json"
    )
    
    print("--- 測試 1: 抓取最新 3 封 ---")
    docs = service.fetch_emails(mode="recent", n=3)
    print(json.dumps(service.serialize_emails(docs), indent=2, ensure_ascii=False))
    
    print("\n--- 測試 2: 抓取上週郵件 (限制最多 10 封) ---")
    docs_weekly = service.fetch_emails(mode="weekly", n=10)
    # print(len(docs_weekly))