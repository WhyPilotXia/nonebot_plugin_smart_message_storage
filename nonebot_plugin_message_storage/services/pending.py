# python3
# -*- coding: utf-8 -*-

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Optional

from nonebot.log import logger

from ..config import config
from ..constants import PENDING_FILE
from ..db import SessionLocal
from ..models import GroupMessage
from ..vision import summarize_images
from .context import get_messages_by_ids, select_context_messages
from .message_utils import IMAGE_CQ_RE, image_summary_segment

_lock = asyncio.Lock()
_flush_task: Optional[asyncio.Task] = None
_in_progress: set[str] = set()


def _load_pending_unlocked() -> list[dict[str, Any]]:
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning(f"[AI识图] 读取 pending_images.json 失败: {e}")
    return []


def _save_pending_unlocked(tasks: list[dict[str, Any]]) -> None:
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


async def add_pending_tasks(tasks: list[dict[str, Any]]) -> None:
    if not tasks:
        return
    should_flush = False
    async with _lock:
        pending = _load_pending_unlocked()
        known = {task.get("task_id") for task in pending}
        for task in tasks:
            if task.get("task_id") not in known:
                pending.append(task)
                continue
            _cleanup_tasks([task])
        _save_pending_unlocked(pending)
        should_flush = len(pending) >= config.image_batch_size

    if should_flush:
        asyncio.create_task(flush_pending(reason="batch"))


async def flush_pending(
    *,
    reason: str,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
    all_conversations: bool = False,
) -> int:
    if not config.ai_api_key:
        logger.info("[AI识图] 未配置 ai_api_key，跳过识图。")
        return 0

    async with _lock:
        pending = _load_pending_unlocked()
        selected = [
            task for task in pending
            if all_conversations or _task_in_scope(task, group_id=group_id, user_id=user_id)
        ]
        selected = [task for task in selected if task.get("task_id") not in _in_progress]
        if not selected:
            return 0
        _in_progress.update(str(task.get("task_id")) for task in selected)

    logger.info(f"[AI识图] 开始提交 {len(selected)} 个待识别图片任务，reason={reason}")
    try:
        await _recognize_and_update(selected)
    except Exception as e:
        logger.opt(exception=e).warning(f"[AI识图] 批量识别失败，任务将删除并保留原始 CQ 码: {e}")
    finally:
        async with _lock:
            pending = _load_pending_unlocked()
            selected_ids = {task.get("task_id") for task in selected}
            pending = [task for task in pending if task.get("task_id") not in selected_ids]
            _save_pending_unlocked(pending)
            for task_id in selected_ids:
                _in_progress.discard(str(task_id))
        _cleanup_tasks(selected)
    return len(selected)


def _task_in_scope(task: dict[str, Any], *, group_id: Optional[int], user_id: Optional[int]) -> bool:
    if group_id is None:
        return False
    if group_id == -1:
        return int(task.get("group_id", 0)) == -1 and int(task.get("user_id", 0)) == int(user_id or 0)
    return int(task.get("group_id", 0)) == int(group_id)


async def flush_stale_pending() -> int:
    async with _lock:
        pending = _load_pending_unlocked()
        if not pending:
            return 0
        oldest = min(float(task.get("created_at", 0)) for task in pending)
    if time.time() - oldest >= config.image_flush_seconds:
        return await flush_pending(reason="stale", all_conversations=True)
    return 0


async def _recognize_and_update(tasks: list[dict[str, Any]]) -> None:
    by_hash, unique_images, hash_to_index = _unique_images_in_chat_order(tasks)
    timeline = build_timeline(tasks, hash_to_index)

    result = await summarize_images(unique_images, timeline)
    raw_records = result.get("images") if isinstance(result.get("images"), list) else []
    records = {}
    for index, image in enumerate(unique_images):
        raw = next((r for r in raw_records if int(r.get("imageIndex", -1)) == index), None)
        if not isinstance(raw, dict):
            logger.warning(f"[AI识图] AI 未返回第 {index} 张图片结果，hash={image['hash']}")
            continue
        summary = str(raw.get("summary") or "").strip()
        tip = str(raw.get("tip") or "").strip()
        if not summary and not tip:
            logger.warning(f"[AI识图] 第 {index} 张图片结果为空，hash={image['hash']}")
            continue
        records[image["hash"]] = {"summary": summary, "tip": tip}

    message_replacements: dict[int, list[dict[str, Any]]] = {}
    for digest, digest_tasks in by_hash.items():
        record = records.get(digest)
        if not record:
            continue
        replacement = image_summary_segment(record["summary"], record["tip"])
        for task in digest_tasks:
            message_replacements.setdefault(int(task["message_id"]), []).append({
                "image_index": int(task["image_index"]),
                "segment_text": task.get("segment_text", ""),
                "replacement": replacement,
            })

    _update_messages(message_replacements)


def _unique_images_in_chat_order(tasks: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_hash: dict[str, list[dict[str, Any]]] = {}
    unique_images: list[dict[str, Any]] = []
    hash_to_index: dict[str, int] = {}

    for task in sorted(tasks, key=lambda item: (int(item["db_id"]), int(item["image_index"]))):
        digest = task.get("hash") or task.get("task_id")
        by_hash.setdefault(digest, []).append(task)
        if digest in hash_to_index:
            continue
        hash_to_index[digest] = len(unique_images)
        unique_images.append({
            "hash": digest,
            "path": task["path"],
            "name": task.get("name") or Path(task["path"]).name,
        })

    return by_hash, unique_images, hash_to_index


def build_timeline(tasks: list[dict[str, Any]], hash_to_index: dict[str, int]) -> list[dict[str, Any]]:
    context_messages: dict[int, dict] = {}
    image_db_ids = {int(task["db_id"]) for task in tasks}

    for task in tasks:
        for msg in select_context_messages(int(task["group_id"]), int(task["user_id"]), int(task["db_id"])):
            context_messages[int(msg["id"])] = msg

    image_messages = get_messages_by_ids(image_db_ids)
    all_messages = {**context_messages, **image_messages}
    tasks_by_db_id: dict[int, list[dict[str, Any]]] = {}
    for task in tasks:
        tasks_by_db_id.setdefault(int(task["db_id"]), []).append(task)

    timeline: list[dict[str, Any]] = []
    for db_id in sorted(all_messages):
        msg = all_messages[db_id]
        image_tasks = sorted(tasks_by_db_id.get(db_id, []), key=lambda item: int(item["image_index"]))
        if image_tasks:
            timeline.extend(_image_message_timeline_items(msg, image_tasks, hash_to_index))
        elif msg.get("text"):
            timeline.append({"user": msg["user"], "type": "text", "text": msg["text"]})

    return timeline


def _image_message_timeline_items(msg: dict[str, Any], image_tasks: list[dict[str, Any]], hash_to_index: dict[str, int]) -> list[dict[str, Any]]:
    raw = msg.get("text") or ""
    user = msg["user"]
    by_image_index = {int(task["image_index"]): task for task in image_tasks}
    items: list[dict[str, Any]] = []
    cursor = 0
    matches = list(IMAGE_CQ_RE.finditer(raw))

    for image_index, match in enumerate(matches):
        _append_text_item(items, user, raw[cursor:match.start()])
        task = by_image_index.get(image_index)
        if task:
            digest = task.get("hash") or task.get("task_id")
            items.append({"user": user, "type": "image", "index": hash_to_index[digest]})
        else:
            _append_text_item(items, user, match.group(0))
        cursor = match.end()

    _append_text_item(items, user, raw[cursor:])

    if not matches:
        for task in image_tasks:
            digest = task.get("hash") or task.get("task_id")
            items.append({"user": user, "type": "image", "index": hash_to_index[digest]})

    return items


def _append_text_item(items: list[dict[str, Any]], user: str, text: str) -> None:
    cleaned = (text or "").strip()
    if cleaned:
        items.append({"user": user, "type": "text", "text": cleaned})


def _update_messages(message_replacements: dict[int, list[dict[str, Any]]]) -> None:
    if not message_replacements:
        return
    session = SessionLocal()
    try:
        for message_id, replacements in message_replacements.items():
            msg = session.query(GroupMessage).filter(GroupMessage.message_id == message_id).order_by(GroupMessage.id.desc()).first()
            if not msg:
                logger.warning(f"[AI识图] 找不到待回写消息: message_id={message_id}")
                continue
            raw = msg.raw_message or ""
            original = raw
            for item in sorted(replacements, key=lambda x: x["image_index"], reverse=True):
                raw = _replace_one_image(raw, item["segment_text"], item["image_index"], item["replacement"])
            if raw != original:
                msg.raw_message = raw
                logger.debug(f"[AI识图] 已回写消息: message_id={message_id}")
            else:
                logger.warning(f"[AI识图] 未能替换图片段: message_id={message_id}")
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def _replace_one_image(raw: str, segment_text: str, image_index: int, replacement: str) -> str:
    matches = list(IMAGE_CQ_RE.finditer(raw))
    if image_index < len(matches):
        match = matches[image_index]
        return raw[:match.start()] + replacement + raw[match.end():]
    if segment_text and segment_text in raw:
        return raw.replace(segment_text, replacement, 1)
    return raw


def _cleanup_tasks(tasks: list[dict[str, Any]]) -> None:
    for task in tasks:
        path = task.get("path")
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"[AI识图] 删除缓存图片失败: path={path}, error={e}")


async def stale_flush_loop() -> None:
    while True:
        try:
            await asyncio.sleep(60)
            await flush_stale_pending()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.opt(exception=e).warning(f"[AI识图] 定时检查待识别图片失败: {e}")


def start_stale_flush_loop() -> None:
    global _flush_task
    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.create_task(stale_flush_loop())
