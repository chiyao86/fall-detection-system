"""共用工具函數和常數"""

from datetime import datetime
import pytz

# 台灣時區（統一管理，避免重複定義）
TZ = pytz.timezone("Asia/Taipei")


def get_taiwan_time() -> datetime:
    """取得台灣時間（datetime 物件）"""
    return datetime.now(TZ)


def get_taiwan_time_str() -> str:
    """取得台灣時間（字串格式）"""
    return get_taiwan_time().strftime("%Y-%m-%d %H:%M:%S")
