"""通知 service — LINE Bot + Twilio SMS"""

from datetime import datetime

import pytz
from flask import current_app

TZ = pytz.timezone("Asia/Taipei")


def send_line_message(description: str, filename: str, timestamp: str) -> bool:
    """發送 LINE 跌倒警報。回傳是否成功。"""
    token = current_app.config.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = current_app.config.get("LINE_USER_ID", "")

    if not token or not user_id:
        return False

    try:
        from linebot import LineBotApi
        from linebot.models import TextSendMessage

        line_bot = LineBotApi(token)
        body = (
            f"🚨【跌倒偵測警報】\n"
            f"📁 檔案: {filename}\n"
            f"🕐 時間: {timestamp}\n\n"
            f"📝 描述:\n{description[:500]}"
        )
        line_bot.push_message(user_id, TextSendMessage(text=body))
        current_app.logger.info(f"LINE 通知已發送: {filename}")
        return True
    except Exception as e:
        current_app.logger.error(f"LINE 發送失敗: {e}")
        return False


def send_sms(description: str, filename: str, timestamp: str) -> bool:
    """發送 Twilio SMS 跌倒警報。回傳是否成功。"""
    sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    token = current_app.config.get("TWILIO_AUTH_TOKEN", "")
    from_num = current_app.config.get("TWILIO_FROM_NUMBER", "")
    to_num = current_app.config.get("TWILIO_TO_NUMBER", "")

    if not all([sid, token, from_num, to_num]):
        return False

    try:
        from twilio.rest import Client

        client = Client(sid, token)
        body = (
            f"【跌倒偵測】{filename}\n"
            f"時間: {timestamp}\n"
            f"結果: {description[:100]}..."
        )
        client.messages.create(from_=from_num, to=to_num, body=body)
        current_app.logger.info(f"SMS 通知已發送: {filename}")
        return True
    except Exception as e:
        current_app.logger.error(f"SMS 發送失敗: {e}")
        return False


def notify_fall_event(fall_result: dict, filename: str, timestamp: str) -> bool:
    """根據跌倒偵測結果決定是否通知。fall_detected=True 且 confidence != low 才通知。"""
    if not fall_result.get("fall_detected"):
        return False
    if fall_result.get("confidence") == "low":
        return False

    description = fall_result.get("description", "偵測到潛在跌倒事件")
    line_ok = send_line_message(description, filename, timestamp)
    sms_ok = send_sms(description, filename, timestamp)
    return line_ok or sms_ok

