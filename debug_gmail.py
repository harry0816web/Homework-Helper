from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def debug_gmail_raw():
    print("🕵️‍♂️ 開始 Gmail API 深度診斷...")

    # 1. 讀取 token
    try:
        creds = Credentials.from_authorized_user_file("token.json")
    except Exception as e:
        print(f"❌ 讀取憑證失敗: {e}")
        return

    # 2. 建立 API 服務
    service = build("gmail", "v1", credentials=creds)

    # 3. 檢查「我是誰？」(確認登入的帳號對不對)
    try:
        profile = service.users().getProfile(userId="me").execute()
        print(f"👤 當前授權的帳號: {profile.get('emailAddress')}")
        print(f"📊 帳號總信件數: {profile.get('messagesTotal')}")
    except Exception as e:
        print(f"❌ 無法取得個人檔案 (權限不足?): {e}")

    print("-" * 30)

    # 4. 直接查詢 INBOX 的信件 ID (不抓內容，只看有沒有 ID)
    print("🔍 嘗試直接搜尋 'label:INBOX'...")
    try:
        # maxResults=10: 先抓 10 筆看看
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
        messages = results.get("messages", [])

        if not messages:
            print("😱 API 回傳：INBOX 是空的 (messages list is empty)！")
            print("👉 可能原因：信件被歸檔(Archived)了，或者都在 'Promotions/Social' 分類標籤下？")
        else:
            print(f"✅ API 成功看到了 {len(messages)} 封信的 ID！")
            print("由此證明：API 連線沒問題，是 LangChain Loader 的設定問題。")
            
            # 5. 抓第一封信的主旨來驗證
            print("\n📝 驗證第一封信內容：")
            msg = service.users().messages().get(userId="me", id=messages[0]["id"]).execute()
            headers = msg["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "無主旨")
            print(f"   主旨: {subject}")

    except Exception as e:
        print(f"❌ API 搜尋失敗: {e}")

if __name__ == "__main__":
    debug_gmail_raw()