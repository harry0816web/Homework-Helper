import os
import redis

class RedisService:
    _instance = None
    
    def __new__(cls):
        """實作 Singleton 模式，確保整個 App 只會有一個 Redis 連線池"""
        if cls._instance is None:
            cls._instance = super(RedisService, cls).__new__(cls)
            cls._instance.init_connection()
        return cls._instance

    def init_connection(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        # 建立連線池 (Connection Pool)
        # decode_responses=True 讓回傳結果自動轉成字串，不用手動 .decode('utf-8')
        self.pool = redis.ConnectionPool.from_url(self.redis_url, decode_responses=True)
        self.client = redis.Redis(connection_pool=self.pool)
        print(f"--- [Redis] Connection Pool Initialized: {self.redis_url} ---")

    def get_client(self):
        """回傳原始 Redis Client (給一般用途用，如存取簡單 Key-Value)"""
        return self.client

    def get_url(self):
        """LangChain 的某些元件需要直接吃 URL"""
        return self.redis_url

# 全域單例
redis_svc = RedisService()