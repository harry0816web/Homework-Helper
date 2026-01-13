from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # 載入設定 (如果有 config.py)
    # app.config.from_object('config.Config')

    # 註冊 Blueprint
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app