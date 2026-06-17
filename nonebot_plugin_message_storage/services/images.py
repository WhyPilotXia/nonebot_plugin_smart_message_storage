# python3
# -*- coding: utf-8 -*-

import hashlib
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from nonebot.adapters.onebot.v11 import Bot

from ..constants import IMAGE_CACHE_DIR


async def download_image(bot: Bot, image_data: dict[str, Any]) -> bytes:
    url = image_data.get("url")
    if not url and image_data.get("file"):
        info = await bot.get_image(file=image_data["file"])
        url = info.get("url") or info.get("file")
    if not url:
        raise RuntimeError("未能获取图片地址")

    if str(url).startswith("file://"):
        path = Path(str(url)[7:])
        if path.exists():
            return path.read_bytes()
    if not str(url).startswith(("http://", "https://")):
        path = Path(str(url))
        if path.exists():
            return path.read_bytes()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def maybe_compress_jpeg(raw: bytes) -> bytes:
    try:
        from PIL import Image

        image = Image.open(BytesIO(raw))
        image.thumbnail((2200, 2200))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        out = BytesIO()
        image.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()
    except Exception:
        return raw


def image_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


async def save_image_cache(bot: Bot, message_id: int, image_index: int, image_data: dict[str, Any]) -> dict[str, str]:
    raw = await download_image(bot, image_data)
    payload = maybe_compress_jpeg(raw)
    digest = image_hash(payload)
    filename = f"message_{message_id}_{image_index}_{int(time.time())}_{digest[:12]}.jpg"
    path = Path(IMAGE_CACHE_DIR) / filename
    path.write_bytes(payload)
    return {
        "name": filename,
        "path": str(path),
        "hash": digest,
    }
