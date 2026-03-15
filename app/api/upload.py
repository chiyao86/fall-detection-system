"""Blueprint: 檔案上傳 + 影片拆幀"""

import os
import uuid

import cv2
from PIL import Image
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

upload_bp = Blueprint("upload", __name__)


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _is_video(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"mp4", "avi", "mov", "mkv", "webm"}


def _extract_frames(video_path: str, interval_seconds: int = 3) -> list[Image.Image]:
    """從影片中每隔 N 秒提取一幀"""
    frames: list[Image.Image] = []
    cap = cv2.VideoCapture(video_path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            return frames
        frame_interval = int(fps * interval_seconds)
        count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if count % frame_interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(rgb))
            count += 1
    finally:
        cap.release()
    return frames


@upload_bp.route("/api/upload", methods=["POST"])
def upload_files():
    if "files[]" not in request.files:
        return jsonify({"success": False, "error": "沒有選擇檔案"}), 400

    files = request.files.getlist("files[]")
    interval = int(request.form.get("interval", 3))
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    uploaded = []

    for f in files:
        if not f or not f.filename:
            continue

        original_name = f.filename          # 保留原始檔名用於顯示
        safe_name = secure_filename(f.filename) or f"{uuid.uuid4().hex}.jpg"  # 安全化後用於磁碟
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        filepath = os.path.join(upload_dir, unique_name)
        f.save(filepath)

        if _is_video(safe_name):
            frames = _extract_frames(filepath, interval)
            for idx, frame in enumerate(frames):
                frame_name = f"{uuid.uuid4().hex}_frame_{idx:04d}.jpg"
                frame_path = os.path.join(upload_dir, frame_name)
                frame.save(frame_path, "JPEG", quality=85)
                uploaded.append({
                    "original_name": f"{original_name}_frame_{idx:04d}",
                    "stored_name": frame_name,
                    "path": frame_path,
                    "type": "video_frame",
                })
            try:
                os.remove(filepath)
            except OSError:
                pass
        else:
            uploaded.append({
                "original_name": original_name,
                "stored_name": unique_name,
                "path": filepath,
                "type": "image",
            })

    return jsonify({"success": True, "files": uploaded, "count": len(uploaded)})
