import chromadb
import os

def check_chroma():
    print("正在連線到 ChromaDB...")
    # 連線到 Docker 內的 Chroma 服務
    client = chromadb.HttpClient(host='chromadb', port=8000)
    
    # 列出所有集合
    collections = client.list_collections()
    print(f"目前的 Collections: {collections}")
    
    try:
        # 取得集合
        collection = client.get_collection("my_knowledge_base")
        count = collection.count()
        print(f"\n✅ 資料庫連線成功！")
        print(f"📊 目前共有 {count} 個知識片段 (Chunks)")
        
        if count > 0:
            print("\n👀 偷看前 1 筆資料：")
            data = collection.peek(limit=1)
            print(f"ID: {data['ids']}")
            print(f"Metadata: {data['metadatas']}")
            print(f"Content (前100字): {data['documents'][0][:100]}...")
        else:
            print("\n⚠️ 資料庫是空的！請先上傳檔案。")
            
    except Exception as e:
        print(f"\n❌ 讀取失敗: {e}")

if __name__ == "__main__":
    check_chroma()