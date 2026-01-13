from flask import Blueprint, render_template, request, jsonify
import os
import sys
import traceback
from app.services.langchain_svc import LangChainService

main_bp = Blueprint('main', __name__)
lc_service = None

def get_service():
    global lc_service
    if lc_service is None:
        lc_service = LangChainService()
    return lc_service

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 1. 暫存檔案到磁碟 (LangChain Loader 需要實體路徑)
    save_path = os.path.join("/tmp", file.filename)
    file.save(save_path)

    try:
        # 2. 呼叫服務處理
        svc = get_service()
        chunks_count = svc.process_file(save_path, file.filename)
        
        # 3. 清理暫存檔
        os.remove(save_path)

        return jsonify({
            "status": "success", 
            "message": f"成功處理 {file.filename}，共建立了 {chunks_count} 個知識片段。"
        })
    except Exception as e:
        # 清理暫存檔（如果存在）
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except:
                pass
        
        return jsonify({"error": str(e)}), 500

@main_bp.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    # 嘗試從前端取得 session_id，如果沒有就幫他產生一個 (或是報錯)
    # 這裡我們假設前端 localStorage 會存一個 ID
    session_id = data.get('session_id') 
    
    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    if not session_id:
        # 如果是第一次來，後端可以產生一個回傳給他，或者暫時用預設值測試
        session_id = "default_user" 

    # langchain log
    print("=" * 80)
    print(f"[API] POST /api/chat - Question: {user_message}")
    print(f"[API] Session ID: {session_id}")
    print("=" * 80)
    sys.stdout.flush()  # flush the log

    try:
        svc = get_service()
        # 傳入 session_id
        result = svc.get_answer(user_message, session_id)
        
        # 確保 answer 存在且不為空
        answer = result.get('answer', '')
        if not answer or answer == 'None' or answer == 'undefined':
            answer = "抱歉，無法產生回應。請確認知識庫中是否有相關資料。"
        
        # langchain log completed
        print("=" * 80)
        print(f"[API] POST /api/chat - Completed successfully")
        print(f"[API] Answer length: {len(answer)} characters")
        print(f"[API] Source documents: {len(result.get('sources', []))} files")
        print("=" * 80)
        sys.stdout.flush()  
        return jsonify({
            "answer": answer,
            "source_documents": result.get('sources', []),
            "session_id": session_id
        })
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Chat error: {e}")
        print(error_traceback)
        sys.stdout.flush()
        return jsonify({
            "error": str(e),
            "traceback": error_traceback if os.getenv('FLASK_ENV') == 'development' else None
        }), 500
