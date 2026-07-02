# python3
# -*- coding: utf-8 -*-

from datetime import datetime

import asyncio
import json

from sqlalchemy import delete, select

from nonebot_plugin_smart_message_storage.config import config
from nonebot_plugin_smart_message_storage.constants import PENDING_FILE
from nonebot_plugin_smart_message_storage.db import SessionLocal, init_db
from nonebot_plugin_smart_message_storage.models import GroupMessage
from nonebot_plugin_smart_message_storage.services.context import after_context_chars
from nonebot_plugin_smart_message_storage.services.pending import (
    _has_enough_after_context,
    _update_messages,
    build_timeline,
    maybe_flush_batch_pending,
)


async def clear_messages() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(GroupMessage))
        await session.commit()


def make_message(
    *,
    message_id: int,
    raw_message: str,
    user_id: int = 10001,
    group_id: int = 20002,
    sender_nickname: str = "user",
) -> GroupMessage:
    return GroupMessage(
        time=datetime.now(),
        self_id=1,
        user_id=user_id,
        group_id=group_id,
        raw_message=raw_message,
        sender_nickname=sender_nickname,
        sender_card="",
        message_id=message_id,
        reply_id=None,
    )


def test_update_messages_replaces_multiple_images_by_position():
    async def run() -> None:
        await init_db()
        await clear_messages()
        async with SessionLocal() as session:
            session.add(
                make_message(
                    message_id=30003,
                    raw_message="look [CQ:image,file=1,url=x] and [CQ:image,file=2,url=y]",
                )
            )
            await session.commit()

        await _update_messages({
            30003: [
                {"image_index": 0, "segment_text": "", "replacement": '[image:{summary:"first",tip:""}]'},
                {"image_index": 1, "segment_text": "", "replacement": '[image:{summary:"second",tip:""}]'},
            ]
        })

        async with SessionLocal() as session:
            saved = (await session.scalars(select(GroupMessage).where(GroupMessage.message_id == 30003))).one()
        assert saved.raw_message == 'look [image:{summary:"first",tip:""}] and [image:{summary:"second",tip:""}]'

    asyncio.run(run())


def test_build_timeline_deduplicates_overlapping_context_windows():
    async def run() -> None:
        await init_db()
        await clear_messages()
        rows = [
            make_message(message_id=40001, raw_message="before one", sender_nickname="A"),
            make_message(message_id=40002, raw_message="before two", user_id=10002, sender_nickname="B"),
            make_message(message_id=40003, raw_message="[CQ:image,file=1,url=x]", sender_nickname="A"),
            make_message(message_id=40004, raw_message="between images", user_id=10002, sender_nickname="B"),
            make_message(message_id=40005, raw_message="[CQ:image,file=2,url=y]", sender_nickname="A"),
        ]
        async with SessionLocal() as session:
            session.add_all(rows)
            await session.commit()
            for row in rows:
                await session.refresh(row)

        tasks = [
            {
                "db_id": rows[2].id,
                "group_id": 20002,
                "user_id": 10001,
                "message_id": 40003,
                "image_index": 0,
                "hash": "hash-a",
                "task_id": "task-a",
            },
            {
                "db_id": rows[4].id,
                "group_id": 20002,
                "user_id": 10001,
                "message_id": 40005,
                "image_index": 0,
                "hash": "hash-b",
                "task_id": "task-b",
            },
        ]

        timeline = await build_timeline(tasks, {"hash-a": 0, "hash-b": 1})

        assert timeline == [
            {"user": "A(10001)", "type": "text", "text": "before one"},
            {"user": "B(10002)", "type": "text", "text": "before two"},
            {"user": "A(10001)", "type": "image", "index": 0},
            {"user": "B(10002)", "type": "text", "text": "between images"},
            {"user": "A(10001)", "type": "image", "index": 1},
        ]

    asyncio.run(run())


def test_after_context_chars_control_batch_readiness():
    async def run() -> None:
        old_after = config.message_image_context_after_chars
        config.message_image_context_after_chars = 30
        await init_db()
        await clear_messages()
        try:
            image = make_message(message_id=50001, raw_message="[CQ:image,file=1,url=x]")
            short_after = make_message(message_id=50002, raw_message="short", user_id=10002, sender_nickname="B")
            async with SessionLocal() as session:
                session.add_all([image, short_after])
                await session.commit()
                await session.refresh(image)

            task = {"db_id": image.id, "group_id": 20002, "user_id": 10001}
            assert await after_context_chars(20002, 10001, image.id) < 30
            assert not await _has_enough_after_context(task)

            async with SessionLocal() as session:
                session.add(
                    make_message(
                        message_id=50003,
                        raw_message="this after-context message is long enough to trigger recognition",
                        user_id=10003,
                        sender_nickname="C",
                    )
                )
                await session.commit()

            assert await after_context_chars(20002, 10001, image.id) >= 30
            assert await _has_enough_after_context(task)
        finally:
            config.message_image_context_after_chars = old_after

    asyncio.run(run())


def test_batch_flush_only_selects_tasks_with_enough_after_context(monkeypatch):
    async def run() -> None:
        old_key = config.message_ai_api_key
        old_batch = config.message_image_batch_size
        old_after = config.message_image_context_after_chars
        config.message_ai_api_key = "test-key"
        config.message_image_batch_size = 2
        config.message_image_context_after_chars = 20
        await init_db()
        await clear_messages()
        try:
            rows = [
                make_message(message_id=60001, raw_message="[CQ:image,file=1,url=x]"),
                make_message(message_id=60002, raw_message="after first image has enough text", user_id=10002),
                make_message(message_id=60003, raw_message="[CQ:image,file=2,url=y]"),
                make_message(message_id=60004, raw_message="after second image also has enough text", user_id=10002),
                make_message(message_id=60005, raw_message="[CQ:image,file=3,url=z]"),
            ]
            async with SessionLocal() as session:
                session.add_all(rows)
                await session.commit()
                for row in rows:
                    await session.refresh(row)

            tasks = [
                {"task_id": "ready-a", "db_id": rows[0].id, "message_id": 60001, "group_id": 20002, "user_id": 10001},
                {"task_id": "ready-b", "db_id": rows[2].id, "message_id": 60003, "group_id": 20002, "user_id": 10001},
                {"task_id": "not-ready", "db_id": rows[4].id, "message_id": 60005, "group_id": 20002, "user_id": 10001},
            ]
            PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            PENDING_FILE.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")

            captured = {}

            async def fake_flush_pending(**kwargs):
                captured.update(kwargs)
                return len(kwargs["task_ids"])

            monkeypatch.setattr("nonebot_plugin_smart_message_storage.services.pending.flush_pending", fake_flush_pending)

            count = await maybe_flush_batch_pending()

            assert count == 2
            assert captured["reason"] == "batch"
            assert captured["all_conversations"] is True
            assert captured["task_ids"] == {"ready-a", "ready-b"}
        finally:
            config.message_ai_api_key = old_key
            config.message_image_batch_size = old_batch
            config.message_image_context_after_chars = old_after
            PENDING_FILE.unlink(missing_ok=True)

    asyncio.run(run())
