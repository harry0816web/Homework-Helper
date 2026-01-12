import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from langchain_google_community import GMailLoader

# 設定權限範圍：只讀取 Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_credentials():
    """
    負責處理 Google 登入驗證的函數
    """
    creds = None
    # 1. 如果已經有 token.json (之前登入過)，就直接讀取
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # 2. 如果沒有憑證，或是憑證過期，就啟動登入流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 憑證過期，正在重新整理...")
            creds.refresh(Request())
        else:
            print("🔑 找不到有效憑證，正在啟動瀏覽器登入...")
            # 這裡明確指定使用 credentials.json
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("❌ 找不到 'credentials.json'！請確認檔案名稱與路徑正確。")
                
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            # 啟動本地伺服器接收回傳的 token
            creds = flow.run_local_server(port=8080)
            
        # 3. 登入成功後，把憑證存起來，下次就不用再登入
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("✅ 登入成功！憑證已儲存為 token.json")
            
    return creds

def fetch_recent_emails():
    print("🚀 開始連接 Gmail...")

    # 取得憑證
    try:
        creds = get_credentials()
    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return

    # 初始化 Loader，把憑證 (creds) 直接餵給它
    try:
        loader = GMailLoader(creds=creds, n=5)
        print("📥 正在抓取最近的郵件...")
        docs = loader.load()
        
        print(f"✅ 成功抓取到 {len(docs)} 筆資料！\n")
        
        # 顯示信件內容
        for i, doc in enumerate(docs):
            subject = doc.metadata.get('subject', '無主旨')
            sender = doc.metadata.get('from', '未知')
            snippet = doc.page_content[:100].replace('\n', ' ')
            
            print(f"📧 [{i+1}] {subject}")
            print(f"   👤 {sender}")
            print(f"   📝 {snippet}...")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ 抓取錯誤: {e}")

if __name__ == "__main__":
    fetch_recent_emails()