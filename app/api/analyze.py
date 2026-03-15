"""Blueprint: 辨識分析（跌倒偵測）"""

import os
import threading

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import FallEvent
from app.utils import get_taiwan_time_str
from app.services.vision import analyze_single_image, analyze_image_sequence
from app.services.notification import notify_fall_event
from app.services.sheets import write_to_google_sheet

analyze_bp = Blueprint("analyze", __name__)

# 處理進度（in-memory，單 process 足矣）
processing_status = {
    "is_processing": False,
    "current": 0,
    "total": 0,
    "current_file": "",
}


def _save_event(filename: str, image_path: str, result: dict, timestamp_str: str, google_sheets: bool):
    """將分析結果寫入 DB、通知、Google Sheets（需在 app_context 內呼叫）"""
    event = FallEvent(
        filename=filename,
        image_path=image_path,
        fall_detected=result.get("fall_detected", False),
        confidence=result.get("confidence", "low"),
        description=result.get("description", ""),
        needs_immediate_attention=result.get("needs_immediate_attention", False),
    )
    db.session.add(event)
    db.session.commit()

    # 通知判斷
    notified = notify_fall_event(result, filename, timestamp_str)
    if notified:
        event.notified = True
        db.session.commit()

    # Google Sheets
    if google_sheets:
        write_to_google_sheet(timestamp_str, filename, result.get("description", ""))


def _batch_individual(app, files: list, custom_prompt: str | None, google_sheets: bool):
    """逐張分析（個別模式）"""
    global processing_status
    try:
        with app.app_context():
            for idx, f_info in enumerate(files):
                try:
                    processing_status["current"] = idx + 1
                    processing_status["current_file"] = f_info["original_name"]

                    image_path = f_info["path"]
                    if not os.path.exists(image_path):
                        continue

                    result = analyze_single_image(image_path, custom_prompt)
                    _save_event(f_info["original_name"], image_path, result, get_taiwan_time_str(), google_sheets)
                except Exception as e:
                    current_app.logger.error(f"分析失敗 {f_info.get('original_name')}: {e}")
    finally:
        processing_status["is_processing"] = False


def _batch_sequence(app, files: list, custom_prompt: str | None, google_sheets: bool):
    """序列分析模式"""
    global processing_status
    try:
        with app.app_context():
            try:
                processing_status["current"] = 1
                processing_status["current_file"] = f"分析 {len(files)} 張序列"

                paths = [f["path"] for f in files if os.path.exists(f["path"])]
                result = analyze_image_sequence(paths, custom_prompt)

                seq_name = f"序列分析 ({len(paths)} 張)"
                _save_event(seq_name, paths[0] if paths else "", result, get_taiwan_time_str(), google_sheets)
            except Exception as e:
                current_app.logger.error(f"序列分析失敗: {e}")
    finally:
        processing_status["is_processing"] = False


def _batch_grouped(app, groups: list, custom_prompt: str | None, google_sheets: bool):
    """分組序列分析模式"""
    global processing_status
    try:
        with app.app_context():
            for g_idx, group in enumerate(groups):
                try:
                    processing_status["current"] = g_idx + 1
                    processing_status["current_file"] = f"分析第 {g_idx + 1} 組"

                    group_files = group.get("files", [])
                    paths = [f["path"] for f in group_files if os.path.exists(f.get("path", ""))]
                    if not paths:
                        continue

                    result = analyze_image_sequence(paths, custom_prompt)
                    group_name = f"錄影片段 {g_idx + 1} ({len(paths)} 張)"
                    _save_event(group_name, paths[0], result, get_taiwan_time_str(), google_sheets)
                except Exception as e:
                    current_app.logger.error(f"第 {g_idx + 1} 組分析失敗: {e}")
    finally:
        processing_status["is_processing"] = False


@analyze_bp.route("/api/analyze", methods=["POST"])
def analyze():
    global processing_status

    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "請求格式錯誤，需要 JSON body"}), 400

    files = data.get("files", [])
    mode = data.get("analyze_mode", "individual")
    groups = data.get("recording_groups")
    custom_prompt = (data.get("prompt") or "").strip() or None
    google_sheets = data.get("google_sheets_enabled", False)

    if not files and not groups:
        return jsonify({"success": False, "error": "沒有圖片可辨識"}), 400

    if not current_app.config.get("GROQ_API_KEY"):
        return jsonify({"success": False, "error": "GROQ_API_KEY 未設定，請在 .env 填入 API Key"}), 400

    app = current_app._get_current_object()

    if mode == "grouped_sequence" and groups:
        processing_status = {"is_processing": True, "current": 0, "total": len(groups), "current_file": ""}
        thread = threading.Thread(target=_batch_grouped, args=(app, groups, custom_prompt, google_sheets))
    elif mode == "sequence":
        processing_status = {"is_processing": True, "current": 0, "total": 1, "current_file": ""}
        thread = threading.Thread(target=_batch_sequence, args=(app, files, custom_prompt, google_sheets))
    else:
        processing_status = {"is_processing": True, "current": 0, "total": len(files), "current_file": ""}
        thread = threading.Thread(target=_batch_individual, args=(app, files, custom_prompt, google_sheets))

    thread.start()
    return jsonify({"success": True, "message": "開始分析"})


@analyze_bp.route("/api/status", methods=["GET"])
def status():
    return jsonify({"success": True, "status": processing_status})
