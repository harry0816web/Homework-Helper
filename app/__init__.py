"""
Flask 應用程式初始化模組
負責初始化 Flask app 和 Redis 連線
"""
import os
import redis
from flask import Flask, session
from flask_session import Session
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 初始化 Redis 連線
redis_client = None  # 用於應用程式緩存（decode_responses=True）
redis_session_client = None  # 用於 Flask Session（decode_responses=False）

def init_redis():
    """初始化 Redis 連線（用於應用程式緩存）"""
    global redis_client
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_db = int(os.getenv('REDIS_DB', 0))
    
    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True  # 用於緩存數據，需要字符串格式
        )
        # 測試連線
        redis_client.ping()
        print(f"✅ Redis 連線成功: {redis_host}:{redis_port}")
    except Exception as e:
        print(f"⚠️ Redis 連線失敗: {e}")
        redis_client = None
    
    return redis_client

def init_redis_session():
    """初始化 Redis Session 連線（用於 Flask Session）"""
    global redis_session_client
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_db = int(os.getenv('REDIS_DB', 0))
    
    try:
        redis_session_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False  # Session 需要二進制格式
        )
        # 測試連線
        redis_session_client.ping()
        print(f"✅ Redis Session 連線成功: {redis_host}:{redis_port}")
    except Exception as e:
        print(f"⚠️ Redis Session 連線失敗: {e}")
        redis_session_client = None
    
    return redis_session_client


def create_app():
    """創建 Flask 應用程式"""
    import os
    static_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
    app = Flask(__name__, static_folder=static_folder)
    
    # 載入設定
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 初始化 Redis（用於應用程式緩存）
    init_redis()
    
    # 初始化 Redis Session（用於 Flask Session）
    redis_session_conn = init_redis_session()
    
    # 配置 Session（使用 Redis 儲存）
    if redis_session_conn:
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis_session_conn  # 使用專門的 Session 客戶端
        app.config['SESSION_PERMANENT'] = False
        app.config['SESSION_USE_SIGNER'] = True
        app.config['SESSION_KEY_PREFIX'] = 'email_summarizer:session:'
    else:
        # 如果 Redis 不可用，使用檔案系統 session
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'flask_session')
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    
    Session(app)
    
    # 註冊路由
    from app.routes import bp
    app.register_blueprint(bp)
    
    return app
