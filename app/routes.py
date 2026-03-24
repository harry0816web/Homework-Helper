from flask import Blueprint, render_template, request, jsonify
import os
import sys
import traceback
import uuid
from werkzeug.utils import secure_filename
from app.services.langchain_svc import LangChainService
from app.services.notion_svc import NotionService

main_bp = Blueprint('main', __name__)
lc_service = None
notion_service = None

def get_service():
    global lc_service
    if lc_service is None:
        lc_service = LangChainService()
    return lc_service


def get_notion_service():
    global notion_service
    if notion_service is None:
        notion_service = NotionService()
    return notion_service

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

    session_id = request.form.get('session_id') or "default_user"
    file_id = "file_" + uuid.uuid4().hex[:8]

    # 1. 暫存檔案到磁碟 (LangChain Loader 需要實體路徑)
    save_path = os.path.join("/tmp", file.filename)
    file.save(save_path)

    try:
        # 2. 呼叫服務處理
        svc = get_service()
        chunks_count = svc.process_file(save_path, file.filename)

        # 3. 上傳成功後加入 System Message 到聊天記錄
        svc.add_upload_system_message(session_id, file_id, file.filename)

        # 4. 清理暫存檔
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


@main_bp.route('/api/notion/courses', methods=['GET'])
def notion_courses():
    try:
        svc = get_notion_service()
        courses = svc.list_courses()
        return jsonify({"courses": courses})
    except Exception as e:
        return jsonify({"error": f"Failed to load courses: {NotionService.format_api_error(e)}"}), 500


@main_bp.route('/api/notion/homeworks', methods=['GET'])
def notion_homeworks():
    course_id = request.args.get('course_id', '').strip()
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400

    try:
        svc = get_notion_service()
        homeworks = svc.list_homeworks_by_course(course_id)
        return jsonify({"homeworks": homeworks})
    except Exception as e:
        return jsonify({"error": f"Failed to load homeworks: {NotionService.format_api_error(e)}"}), 500


@main_bp.route('/api/notion/homeworks', methods=['POST'])
def notion_create_homework():
    data = request.form.to_dict() if request.form else (request.json or {})
    try:
        uploaded = request.files.get('file')
        file_url = None
        file_name = None
        temp_path = None

        if uploaded and uploaded.filename:
            if not uploaded.filename.lower().endswith('.pdf'):
                return jsonify({"error": "Only PDF files are supported."}), 400

            file_name = secure_filename(uploaded.filename)
            unique_name = f"{uuid.uuid4().hex[:10]}_{file_name}"
            static_dir = os.path.join(os.getcwd(), "app", "static", "homeworks")
            os.makedirs(static_dir, exist_ok=True)
            temp_path = os.path.join(static_dir, unique_name)
            uploaded.save(temp_path)
            file_url = f"{request.host_url.rstrip('/')}/static/homeworks/{unique_name}"

            data["file_url"] = file_url
            data["file_name"] = file_name

        svc = get_notion_service()
        created = svc.create_homework(data)

        # Keep using existing vectorization flow: PDF -> chunks -> Chroma.
        if temp_path:
            lc_svc = get_service()
            chunks_count = lc_svc.process_file(temp_path, file_name or os.path.basename(temp_path))
            created["chroma_chunks"] = chunks_count

        return jsonify({"status": "success", "data": created})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to create homework: {NotionService.format_api_error(e)}"}), 500


@main_bp.route('/api/notion/homeworks/<homework_id>/file', methods=['POST'])
def notion_attach_homework_file(homework_id):
    uploaded = request.files.get('file')
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "PDF file is required."}), 400
    if not uploaded.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are supported."}), 400

    temp_path = None
    try:
        file_name = secure_filename(uploaded.filename)
        unique_name = f"{uuid.uuid4().hex[:10]}_{file_name}"
        static_dir = os.path.join(os.getcwd(), "app", "static", "homeworks")
        os.makedirs(static_dir, exist_ok=True)
        temp_path = os.path.join(static_dir, unique_name)
        uploaded.save(temp_path)
        file_url = f"{request.host_url.rstrip('/')}/static/homeworks/{unique_name}"

        notion_svc = get_notion_service()
        updated = notion_svc.attach_homework_file(
            homework_page_id=homework_id,
            file_url=file_url,
            file_name=file_name,
        )

        lc_svc = get_service()
        chunks_count = lc_svc.process_file(temp_path, file_name)

        return jsonify(
            {
                "status": "success",
                "data": {
                    **updated,
                    "file_url": file_url,
                    "chroma_chunks": chunks_count,
                },
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to attach file: {NotionService.format_api_error(e)}"}), 500
