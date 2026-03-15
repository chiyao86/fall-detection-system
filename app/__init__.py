"""App Factory — 低耦合入口"""

import os

from flask import Flask, jsonify

from app.config import Config
from app.extensions import db, migrate


def create_app(config_class=Config) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
    )
    app.config.from_object(config_class)

    # 確保 uploads 資料夾存在
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 初始化 extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # 註冊 Blueprints
    from app.api.upload import upload_bp
    from app.api.analyze import analyze_bp
    from app.api.results import results_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(results_bp)

    # JSON 錯誤處理（避免回傳 HTML 給前端 fetch）
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "找不到該路徑"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "error": "HTTP method 不允許"}), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"success": False, "error": "檔案太大，超出上限"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"success": False, "error": "伺服器內部錯誤"}), 500

    # 首頁路由
    @app.route("/")
    def index():
        from flask import render_template
        return render_template("index.html")

    return app
