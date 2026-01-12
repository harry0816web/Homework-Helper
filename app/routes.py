"""
Flask API 路由定義
定義所有的 API 端點 (Endpoints)
只包含 Gmail OAuth2 認證和郵件抓取功能
"""
import json
import secrets
from flask import Blueprint, request, jsonify, session, redirect, url_for
from app import redis_client
from app.services.gmail_svc import GmailService
from google.oauth2.credentials import Credentials
import os
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

bp = Blueprint('api', __name__)

# 獲取基礎 URL（用於構建回調 URI）
def get_base_url():
    """獲取應用程式的基礎 URL"""
    base_url = os.getenv('BASE_URL', 'http://localhost:8080')
    return base_url.rstrip('/')

# 初始化 Gmail 服務（使用 Web OAuth2 流程）
gmail_service = GmailService(
    credentials_path=os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials/google_secret.json'),
    token_path=os.getenv('GMAIL_TOKEN_PATH', 'credentials/token.json'),
    redirect_uri=urljoin(get_base_url(), '/auth/gmail/callback')
)


def get_user_credentials():
    """從 session 獲取用戶憑證"""
    if 'gmail_credentials' not in session:
        return None
    
    try:
        creds_dict = session['gmail_credentials']
        creds = gmail_service.get_credentials_from_dict(creds_dict)
        
        # 如果 token 被刷新了，更新 session 中的憑證
        if creds.valid and creds.token != creds_dict.get('token'):
            print("💾 更新 session 中的憑證（token 已刷新）")
            session['gmail_credentials'] = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
        
        return creds
    except Exception as e:
        print(f"⚠️ 從 session 載入憑證失敗: {e}")
        import traceback
        print(f"   詳細錯誤: {traceback.format_exc()}")
        session.pop('gmail_credentials', None)
        return None


@bp.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "redis_connected": redis_client is not None and redis_client.ping() if redis_client else False
    })


@bp.route('/auth/debug', methods=['GET'])
def auth_debug():
    """
    除錯端點：顯示 OAuth2 設定資訊
    幫助確認 redirect_uri 是否正確
    """
    # 嘗試清理舊的 session（如果存在）
    try:
        session.clear()
    except Exception:
        pass
    
    return jsonify({
        "base_url": get_base_url(),
        "redirect_uri": gmail_service.redirect_uri,
        "credentials_path": gmail_service.credentials_path,
        "note": "請在 Google Cloud Console 的 OAuth 2.0 用戶端設定中，確認「已授權的重新導向 URI」包含以下 URI：",
        "required_redirect_uri": gmail_service.redirect_uri
    })


@bp.route('/emails/test', methods=['GET'])
def test_email_fetch():
    """
    測試端點：診斷 Gmail 抓取問題
    用於檢查為什麼沒有抓到郵件
    """
    try:
        # 檢查登入狀態
        creds = get_user_credentials()
        if not creds:
            return jsonify({
                "success": False,
                "error": "未登入，請先進行 OAuth2 認證",
                "auth_url": url_for('api.gmail_login')
            }), 401
        
        # 檢查憑證狀態
        creds_info = {
            "valid": creds.valid,
            "expired": creds.expired,
            "has_refresh_token": creds.refresh_token is not None,
            "scopes": creds.scopes
        }
        
        # 嘗試刷新 token（如果需要）
        if creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                creds_info["refreshed"] = True
            except Exception as e:
                creds_info["refresh_error"] = str(e)
        
        # 嘗試直接使用 Gmail API 檢查
        try:
            from googleapiclient.discovery import build
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()
            profile_info = {
                "email": profile.get('emailAddress'),
                "messages_total": profile.get('messagesTotal'),
                "threads_total": profile.get('threadsTotal')
            }
        except Exception as e:
            profile_info = {"error": str(e)}
        
        # 嘗試抓取郵件
        fetch_result = {
            "attempted": True,
            "success": False,
            "email_count": 0,
            "error": None
        }
        
        try:
            docs = gmail_service.fetch_emails(n=3, credentials=creds)
            if docs:
                fetch_result["success"] = True
                fetch_result["email_count"] = len(docs)
                fetch_result["first_email"] = {
                    "subject": docs[0].metadata.get('subject', '無主旨'),
                    "sender": docs[0].metadata.get('from', '未知'),
                    "content_length": len(docs[0].page_content)
                }
            else:
                fetch_result["error"] = "Gmail API 返回空列表"
        except Exception as e:
            fetch_result["error"] = str(e)
            import traceback
            fetch_result["traceback"] = traceback.format_exc()
        
        return jsonify({
            "success": True,
            "credentials": creds_info,
            "profile": profile_info,
            "fetch_result": fetch_result,
            "recommendations": [
                "如果 credentials.valid 為 false，請重新登入",
                "如果 profile.error 存在，檢查 Gmail API 權限",
                "如果 fetch_result.error 存在，查看詳細錯誤訊息"
            ]
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@bp.route('/auth/clear-sessions', methods=['POST'])
def clear_sessions():
    """
    清除所有 Redis Session（用於除錯）
    """
    try:
        if redis_client:
            # 清除所有 session keys
            keys = redis_client.keys('email_summarizer:session:*')
            if keys:
                redis_client.delete(*keys)
                return jsonify({
                    "success": True,
                    "message": f"已清除 {len(keys)} 個 session"
                })
            else:
                return jsonify({
                    "success": True,
                    "message": "沒有找到任何 session"
                })
        else:
            return jsonify({
                "success": False,
                "error": "Redis 未連線"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/auth/gmail/login', methods=['GET'])
def gmail_login():
    """
    Gmail OAuth2 登入端點
    重定向到 Google 授權頁面
    """
    try:
        # 生成 state 參數（用於防止 CSRF 攻擊）
        state = secrets.token_urlsafe(32)
        session['oauth_state'] = state
        
        # 獲取授權 URL
        auth_url, _ = gmail_service.get_authorization_url(state=state)
        
        # 重定向到 Google 授權頁面
        return redirect(auth_url)
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/auth/gmail/callback', methods=['GET'])
def gmail_callback():
    """
    Gmail OAuth2 回調端點
    處理 Google 授權後的回調
    """
    try:
        # 獲取授權碼和 state
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        # 檢查是否有錯誤
        if error:
            return jsonify({
                "success": False,
                "error": f"授權失敗: {error}",
                "error_description": request.args.get('error_description', '')
            }), 400
        
        # 驗證 state 參數
        if 'oauth_state' not in session or session['oauth_state'] != state:
            return jsonify({
                "success": False,
                "error": "無效的 state 參數，可能是 CSRF 攻擊"
            }), 400
        
        # 清除 state（一次性使用）
        session.pop('oauth_state', None)
        
        if not code:
            return jsonify({
                "success": False,
                "error": "未收到授權碼"
            }), 400
        
        # 使用授權碼換取憑證
        creds = gmail_service.get_credentials_from_code(code, state=state)
        
        # 將憑證儲存到 session
        session['gmail_credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        # 重定向到前端（或顯示成功訊息）
        frontend_url = os.getenv('FRONTEND_URL', get_base_url())
        return redirect(f"{frontend_url}/?auth=success")
    
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@bp.route('/auth/status', methods=['GET'])
def auth_status():
    """
    檢查認證狀態
    """
    creds = get_user_credentials()
    return jsonify({
        "authenticated": creds is not None,
        "valid": creds.valid if creds else False,
        "expired": creds.expired if creds else None,
        "has_refresh_token": creds.refresh_token is not None if creds else False
    })


@bp.route('/auth/logout', methods=['POST'])
def logout():
    """
    登出端點
    清除 session 中的憑證
    """
    session.pop('gmail_credentials', None)
    session.pop('oauth_state', None)
    
    return jsonify({
        "success": True,
        "message": "已登出"
    })


@bp.route('/emails', methods=['GET'])
def get_emails():
    """
    取得郵件列表
    
    Query Parameters:
        n: 要抓取的郵件數量 (預設: 5)
        mode: "recent" (抓最新幾封) 或 "weekly" (抓上週) (預設: recent)
        use_cache: 是否使用快取 (預設: true)
        cache_ttl: 快取存活時間 (秒) (預設: 3600)
    """
    try:
        n = int(request.args.get('n', 5))
        mode = request.args.get('mode', 'recent')
        use_cache = request.args.get('use_cache', 'true').lower() == 'true'
        cache_ttl = int(request.args.get('cache_ttl', 3600))
        
        cache_key = f"gmail_emails_{mode}_{n}"
        
        # 檢查快取
        if use_cache and redis_client:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return jsonify({
                    "success": True,
                    "from_cache": True,
                    "data": json.loads(cached_data),
                    "count": len(json.loads(cached_data))
                })
        
        # 從 session 獲取憑證
        creds = get_user_credentials()
        if not creds:
            return jsonify({
                "success": False,
                "error": "未登入，請先進行 OAuth2 認證",
                "auth_url": url_for('api.gmail_login')
            }), 401
        
        # 從 Gmail 抓取
        docs = gmail_service.fetch_emails(mode=mode, n=n, credentials=creds)
        serialized_emails = gmail_service.serialize_emails(docs)
        
        # 存入快取
        if use_cache and redis_client:
            redis_client.setex(
                cache_key,
                cache_ttl,
                json.dumps(serialized_emails, ensure_ascii=False)
            )
        
        return jsonify({
            "success": True,
            "from_cache": False,
            "data": serialized_emails,
            "count": len(serialized_emails)
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
