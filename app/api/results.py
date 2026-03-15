"""Blueprint: 結果查詢、匯出、清除、健康檢查"""

import csv
import io
import os
from datetime import datetime

import pytz
from flask import Blueprint, current_app, jsonify, request, send_file

from app.extensions import db
from app.models import FallEvent

results_bp = Blueprint("results", __name__)
TZ = pytz.timezone("Asia/Taipei")


@results_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(TZ).isoformat()})


@results_bp.route("/api/results", methods=["GET"])
def get_results():
    """取得所有辨識結果（最新在前）"""
    events = FallEvent.query.order_by(FallEvent.created_at.desc()).all()
    return jsonify({
        "success": True,
        "results": [e.to_dict() for e in events],
        "count": len(events),
    })


@results_bp.route("/api/events", methods=["GET"])
def get_events():
    """分頁查詢事件（給前端事件歷史用）"""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    fall_only = request.args.get("fall_only", "false").lower() == "true"

    query = FallEvent.query.order_by(FallEvent.created_at.desc())
    if fall_only:
        query = query.filter(FallEvent.fall_detected.is_(True))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "events": [e.to_dict() for e in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    })


@results_bp.route("/api/export-csv", methods=["GET"])
def export_csv():
    events = FallEvent.query.order_by(FallEvent.created_at.desc()).all()
    if not events:
        return jsonify({"success": False, "error": "沒有資料可匯出"}), 400

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["時間", "檔名", "跌倒偵測", "信心程度", "描述", "已通知"])

    for e in events:
        writer.writerow([
            e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "",
            e.filename,
            "是" if e.fall_detected else "否",
            e.confidence,
            e.description,
            "是" if e.notified else "否",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    fname = f"fall_events_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.csv"

    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name=fname,
    )


@results_bp.route("/api/clear", methods=["POST"])
def clear_all():
    """清除所有資料（DB + uploads）"""
    FallEvent.query.delete()
    db.session.commit()

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    for fname in os.listdir(upload_dir):
        fpath = os.path.join(upload_dir, fname)
        try:
            if os.path.isfile(fpath) and fname != ".gitkeep":
                os.unlink(fpath)
        except OSError:
            pass

    return jsonify({"success": True, "message": "已清除所有資料"})
