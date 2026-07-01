# python3
# -*- coding: utf-8 -*-

import os
import asyncio
from pathlib import Path

import pytest

from nonebot_plugin_smart_message_storage.config import config
from nonebot_plugin_smart_message_storage.services.images import maybe_compress_jpeg
from nonebot_plugin_smart_message_storage.vision import summarize_images

ASSET_DIR = Path(__file__).resolve().parent / "assets"
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime" / "ai_assets"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}


@pytest.mark.integration
def test_ai_summarizes_all_fixture_images():
    api_key = os.getenv("MESSAGE_AI_API_KEY")
    if not api_key:
        pytest.skip("MESSAGE_AI_API_KEY is not configured")
    config.message_ai_api_key = api_key

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    assets = sorted(path for path in ASSET_DIR.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    images = []
    for index, asset in enumerate(assets):
        payload = maybe_compress_jpeg(asset.read_bytes())
        out = RUNTIME_DIR / f"{index:02d}_{asset.stem}.jpg"
        out.write_bytes(payload)
        images.append({
            "path": str(out),
            "name": asset.name,
        })

    timeline = [{"user": "用户A(10001)", "type": "text", "text": "群友正在连续发送截图、表情包、人物和动漫角色图片，希望把它们总结成可搜索文本。"}]
    for index, asset in enumerate(assets):
        if "截图" in asset.name:
            text = "这张图可能是截图，请重点提取界面或文字关键信息。"
        elif "表情包" in asset.name or "猫动图" in asset.name:
            text = "这张图可能是表情包或梗图，请结合常见网络语境说明用途。"
        else:
            text = "这张图可能是人物、cos 或动漫角色，请描述画面主体和可见信息。"
        timeline.append({"user": "用户B(10002)", "type": "text", "text": text})
        timeline.append({"user": "用户A(10001)", "type": "image", "index": index})

    result = asyncio.run(summarize_images(images, timeline))

    records = result.get("images")
    assert isinstance(records, list)
    assert len(records) == len(images)
    for index, record in enumerate(records):
        assert record.get("imageIndex") == index
        assert isinstance(record.get("summary"), str)
        assert record["summary"].strip()
        assert isinstance(record.get("tip"), str)
