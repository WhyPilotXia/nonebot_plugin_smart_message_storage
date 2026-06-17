# python3
# -*- coding: utf-8 -*-

import hashlib
from datetime import datetime

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.log import logger

from ..models import GroupMessage
from .images import save_image_cache
from .message_utils import image_segments, segment_to_text
from .pending import add_pending_tasks


async def collect_pending_images(bot: Bot, message_id: int, message: Message, msg: GroupMessage) -> int:
    tasks = []
    for image_index, segment in image_segments(message):
        try:
            cached = await save_image_cache(bot, message_id, image_index, segment.data)
        except Exception as e:
            logger.warning(
                f"[AI识图] 下载或缓存图片失败，保留原始 CQ 码: "
                f"message_id={message_id}, image_index={image_index}, error={e}"
            )
            continue

        task_id_source = f"{message_id}:{image_index}:{cached['hash']}"
        task_id = hashlib.sha256(task_id_source.encode("utf-8")).hexdigest()
        tasks.append({
            "task_id": task_id,
            "created_at": datetime.now().timestamp(),
            "db_id": msg.id,
            "message_id": message_id,
            "group_id": msg.group_id,
            "user_id": msg.user_id,
            "image_index": image_index,
            "segment_text": segment_to_text(segment),
            "path": cached["path"],
            "name": cached["name"],
            "hash": cached["hash"],
        })

    if tasks:
        await add_pending_tasks(tasks)
    return len(tasks)
