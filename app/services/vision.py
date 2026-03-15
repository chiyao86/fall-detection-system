"""Groq Vision service — 跌倒偵測結構化分析"""

import base64
import io
import json
import os
import re
import time

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

    image = None
    try:
        image = Image.open(image_path)
        
        # 壓縮圖片以減少傳輸時間和 API 成本
        max_size = (1024, 1024)  # 限制最大尺寸
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            current_app.logger.info(f"圖片已壓縮至 {image.size}")
        
        b64 = encode_image(image)

        prompt = custom_prompt or FALL_DETECTION_PROMPT

        client = Groq(api_key=api_key)
        
        # 重試機制 - 最多重試 4 次（平衡速度和穩定性）
        max_retries = 4
        base_delay = 2  # 基礎延遲 2 秒（折中方案）
        
        for attempt in range(max_retries):
            try:
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
                result = _parse_json_response(raw)
                
                # 免費版延遲：2-3 秒（平衡速度和速率限制）
                time.sleep(base_delay + (attempt * 0.3))
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                
                # 檢查是否為速率限制或配額用盡
                if "rate_limit" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_retries - 1:
                        # 速率限制：較短的指數退避 2s, 4s, 8s, 16s
                        wait_time = base_delay * (2 ** attempt)
                        current_app.logger.warning(
                            f"⚠️ Groq API 速率限制（嘗試 {attempt + 1}/{max_retries}），"
                            f"等待 {wait_time} 秒後重試..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # 所有重試都失敗
                        current_app.logger.error(
                            "❌ Groq API 配額可能已用盡。"
                            "建議：1) 一次只處理 2-3 張圖片 2) 等待 1 分鐘後再試 3) 使用序列模式減少 API 調用"
                        )
                        raise ValueError(
                            "Groq API 請求失敗：免費配額已用盡或速率限制。"
                            "請稍後再試或一次處理較少圖片。"
                        )
                
                # 其他錯誤直接拋出
                raise e
                
    finally:
        # 確保圖片資源被釋放
        if image:
            image.close()


def analyze_image_sequence(image_paths: list[str], custom_prompt: str | None = None) -> dict:
    """分析多張連續圖片序列。最多 5 張。"""
    MAX_IMAGES = 5
    api_key = current_app.config["GROQ_API_KEY"]
    model = current_app.config["GROQ_MODEL"]

    if not api_key:
        raise ValueError("GROQ_API_KEY 未設定")

    paths = image_paths[:MAX_IMAGES]
    opened_images = []

    try:
        image_contents = []
        for p in paths:
            if not os.path.exists(p):
                continue
            image = Image.open(p)
            opened_images.append(image)  # 記錄以便後續關閉
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
        
        # 重試機制
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": message_content}],
                    temperature=0.3,
                    max_completion_tokens=1024,
                    top_p=1,
                    stream=False,
                )

                raw = completion.choices[0].message.content
                result = _parse_json_response(raw)
                
                # 添加延遲
                time.sleep(2)
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                if "rate_limit" in error_msg.lower() or "429" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1) * 2
                        current_app.logger.warning(f"遇到速率限制，等待 {wait_time} 秒後重試...")
                        time.sleep(wait_time)
                        continue
                raise e
                
    finally:
        # 關閉所有開啟的圖片
        for img in opened_images:
            try:
                img.close()
            except:
                pass
