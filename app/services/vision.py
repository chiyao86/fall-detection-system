"""Groq Vision service — 跌倒偵測結構化分析"""

import base64
import io
import json
import os
import re

from PIL import Image
from groq import Groq
from flask import current_app

# 跌倒偵測專用 prompt，要求回傳 JSON
FALL_DETECTION_PROMPT = """你是一個專業的「老人跌倒偵測 AI」。請仔細觀察圖片，判斷畫面中是否有人跌倒。

請嚴格按照以下 JSON 格式回傳（不要包含任何其他文字）：
{
  "fall_detected": true/false,
  "confidence": "low" | "medium" | "high",
  "description": "詳細的圖片描述",
  "needs_immediate_attention": true/false
}

對於 description 字段，請用繁體中文撰寫，內容必須包含以下所有項目：
1. 場景描述：地點類型（室內/室外/走廊/路面等）、光線狀況、背景環境
2. 人物資訊：畫面中所有人物的數量、大致年齡特徵、衣著顏色、位置
3. 身體姿勢：詳細描述主要人物的身體姿勢（站立/坐下/跦倒/浮台面上等）、頭部方向、四肢位置
4. 跬倒判斷：明確說明為什麼判斷為跬倒或非跬倒，列舉具體的視覺證據（例如：身體與地面平行、無法自行站起、周圍人對其進行救助等）
5. 風險評估：若為跬倒，判斷傷勢嚴重性及是否需要紪急救助

description 長度至少 150 字，內容詳細具體。

判斷標準：
- fall_detected: 畫面中是否有人摘倒或身體與地面接觸且無法自行站起
- confidence: 你對判斷結果的信心程度
- needs_immediate_attention: 跬倒且信心高 → true"""


def encode_image(image: Image.Image) -> str:
    """將 PIL Image 編碼為 base64 字串"""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _parse_json_response(text: str) -> dict:
    """從 LLM 回應中解析 JSON，容忍 markdown code block"""
    # 嘗試直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 嘗試從 ```json ... ``` 中提取
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 嘗試找 { ... } 區塊
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 解析失敗，回傳預設結構
    return {
        "fall_detected": False,
        "confidence": "low",
        "description": text,
        "needs_immediate_attention": False,
    }


def analyze_single_image(image_path: str, custom_prompt: str | None = None) -> dict:
    """分析單張圖片是否有跌倒。回傳結構化 dict。"""
    api_key = current_app.config["GROQ_API_KEY"]
    model = current_app.config["GROQ_MODEL"]

    if not api_key:
        raise ValueError("GROQ_API_KEY 未設定")

    image = Image.open(image_path)
    b64 = encode_image(image)

    prompt = custom_prompt or FALL_DETECTION_PROMPT

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.3,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
    )

    raw = completion.choices[0].message.content
    return _parse_json_response(raw)


def analyze_image_sequence(image_paths: list[str], custom_prompt: str | None = None) -> dict:
    """分析多張連續圖片序列。最多 5 張。"""
    MAX_IMAGES = 5
    api_key = current_app.config["GROQ_API_KEY"]
    model = current_app.config["GROQ_MODEL"]

    if not api_key:
        raise ValueError("GROQ_API_KEY 未設定")

    paths = image_paths[:MAX_IMAGES]

    image_contents = []
    for p in paths:
        if not os.path.exists(p):
            continue
        image = Image.open(p)
        b64 = encode_image(image)
        image_contents.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )

    if not image_contents:
        return {
            "fall_detected": False,
            "confidence": "low",
            "description": "沒有有效的圖片可供分析",
            "needs_immediate_attention": False,
        }

    prompt = custom_prompt or (
        FALL_DETECTION_PROMPT
        + f"\n\n這是 {len(image_contents)} 張連續圖片，請綜合判斷這段時間內是否有人跌倒。"
    )

    message_content = [{"type": "text", "text": prompt}]
    message_content.extend(image_contents)

    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message_content}],
        temperature=0.3,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
    )

    raw = completion.choices[0].message.content
    return _parse_json_response(raw)
