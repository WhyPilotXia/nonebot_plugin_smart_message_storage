# python3
# -*- coding: utf-8 -*-

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from .config import config
from .prompt import build_vision_prompt


class VisionError(RuntimeError):
    pass


def image_file_to_payload(path: str) -> str:
    raw = Path(path).read_bytes()
    return f"data:image/jpeg;base64,{base64.b64encode(raw).decode('utf-8')}"


async def summarize_images(images: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> dict[str, Any]:
    if not config.message_ai_api_key:
        raise VisionError("message_ai_api_key is not configured")
    if not images:
        raise VisionError("no images to recognize")

    items = [
        {
            "imageIndex": index,
            "name": image.get("name", f"image_{index + 1}.jpg"),
        }
        for index, image in enumerate(images)
    ]
    content: list[dict[str, Any]] = [{"type": "text", "text": build_vision_prompt(items, timeline)}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": image_file_to_payload(image["path"]), "detail": "high"},
        }
        for image in images
    )

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{config.message_ai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.message_ai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.message_ai_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "你只输出可解析 JSON，不能输出 Markdown 或解释文字。"},
                    {"role": "user", "content": content},
                ],
            },
        )

    try:
        data = response.json()
    except Exception as e:
        raise VisionError(f"AI response is not JSON: {response}（{e}）") from e

    if response.status_code >= 400:
        message = data.get("error", {}).get("message") if isinstance(data, dict) else ""
        raise VisionError(message or f"AI request failed: HTTP {response.status_code}")

    text = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not text:
        raise VisionError("AI returned empty content")
    return parse_ai_json(text)


def parse_ai_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.lower().startswith("![image](") or "/t2i/" in raw.lower():
        raise VisionError("AI model returned an image link; it looks like a generation model, not a vision model")

    candidates = [
        raw,
        raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip(),
        raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw and "}" in raw else "",
        *list(reversed(extract_json_objects(raw))),
    ]
    for candidate in candidates:
        if not candidate or "{" not in candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    raise VisionError("AI returned invalid JSON")


def extract_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    start = -1
    depth = 0
    in_string = False
    escaping = False
    for i, char in enumerate(text):
        if in_string:
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(text[start:i + 1])
                start = -1
            if depth < 0:
                depth = 0
                start = -1
    return objects
