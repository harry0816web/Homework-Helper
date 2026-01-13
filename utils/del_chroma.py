#!/usr/bin/env python3
"""清除 ChromaDB 中的資料"""
import chromadb
import os
import sys

def clear_chromadb():
    """清除 ChromaDB 中的 collection 資料"""
    print("=" * 60)
    print("清除 ChromaDB 資料")
    print("=" * 60)
    
    # 連線到 Docker 內的 Chroma 服務
    host = os.getenv("CHROMA_DB_HOST", "localhost")
    port = int(os.getenv("CHROMA_DB_PORT", 8000))
    
    print(f"\n正在連線到 ChromaDB ({host}:{port})...")
    
    try:
        client = chromadb.HttpClient(host=host, port=port)
        
        # 列出所有 collections
        collections = client.list_collections()
        print(f"\n目前的 Collections: {[col.name for col in collections]}")
        
        # 檢查目標 collection 是否存在
        collection_name = "my_knowledge_base"
        try:
            collection = client.get_collection(collection_name)
            count = collection.count()
            print(f"\nCollection '{collection_name}' 目前有 {count} 個知識片段 (Chunks)")
            
            if count == 0:
                print("\nCollection 已經是空的，無需清除。")
                return
            
            # 確認清除
            print(f"\n警告：即將清除 Collection '{collection_name}' 中的所有資料！")
            confirm = input("請輸入 'yes' 確認清除，或按 Enter 取消: ").strip().lower()
            
            if confirm != 'yes':
                print("\n操作已取消。")
                return
            
            # 刪除整個 collection 並重新創建
            print(f"\n正在刪除 Collection '{collection_name}'...")
            client.delete_collection(collection_name)
            print(f"Collection '{collection_name}' 已刪除")
            
            # 重新創建空的 collection
            print(f"\n重新創建空的 Collection '{collection_name}'...")
            client.create_collection(collection_name)
            print(f"Collection '{collection_name}' 已重新創建（空的）")
            
            # 驗證清除結果
            new_collection = client.get_collection(collection_name)
            new_count = new_collection.count()
            print(f"\n清除完成！目前有 {new_count} 個知識片段")
            
        except Exception as e:
            if "does not exist" in str(e) or "not found" in str(e).lower():
                print(f"\nCollection '{collection_name}' 不存在，無需清除。")
            else:
                raise e
                
    except Exception as e:
        print(f"\n錯誤: {e}")
        print("\n提示：")
        print("   - 確保 ChromaDB 容器正在運行: docker-compose ps")
        print("   - 如果從主機執行，使用 localhost")
        sys.exit(1)

if __name__ == "__main__":
    clear_chromadb()