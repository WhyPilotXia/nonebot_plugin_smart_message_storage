# python3
# -*- coding: utf-8 -*-

from datetime import datetime

import asyncio
import json

from nonebot_plugin_smart_message_storage.config import config
from nonebot_plugin_smart_message_storage.constants import PENDING_FILE
from nonebot_plugin_smart_message_storage.db import SessionLocal, init_db
from nonebot_plugin_smart_message_storage.models import GroupMessage
from nonebot_plugin_smart_message_storage.services.context import after_context_chars
from nonebot_plugin_smart_message_storage.services.pending import _has_enough_after_context, _update_messages, build_timeline, maybe_flush_batch_pending


def test_update_messages_replaces_multiple_images_by_position():
    init_db()
    session = SessionLocal()
    try:
        session.query(GroupMessage).delete()
        msg = GroupMessage(
            time=datetime.now(),
            self_id=1,
            user_id=10001,
            group_id=20002,
            raw_message="看这个[CQ:image,file=1,url=x]还有这个[CQ:image,file=2,url=y]",
            sender_nickname="tester",
            sender_card="",
            message_id=30003,
            reply_id=None,
        )
        session.add(msg)
        session.commit()
    finally:
        session.close()

    _update_messages({
        30003: [
            {"image_index": 0, "segment_text": "", "replacement": '[image:{summary:"第一张",tip:""}]'},
            {"image_index": 1, "segment_text": "", "replacement": '[image:{summary:"第二张",tip:""}]'},
        ]
    })

    session = SessionLocal()
    try:
        saved = session.query(GroupMessage).filter(GroupMessage.message_id == 30003).one()
        assert saved.raw_message == '看这个[image:{summary:"第一张",tip:""}]还有这个[image:{summary:"第二张",tip:""}]'
    finally:
        session.close()


def test_build_timeline_deduplicates_overlapping_context_windows():
    init_db()
    session = SessionLocal()
    try:
        session.query(GroupMessage).delete()
        rows = [
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="前文一",
                sender_nickname="用户A",
                sender_card="",
                message_id=40001,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10002,
                group_id=20002,
                raw_message="前文二",
                sender_nickname="用户B",
                sender_card="",
                message_id=40002,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="[CQ:image,file=1,url=x]",
                sender_nickname="用户A",
                sender_card="",
                message_id=40003,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10002,
                group_id=20002,
                raw_message="夹在两图之间的回复",
                sender_nickname="用户B",
                sender_card="",
                message_id=40004,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="[CQ:image,file=2,url=y]",
                sender_nickname="用户A",
                sender_card="",
                message_id=40005,
                reply_id=None,
            ),
        ]
        session.add_all(rows)
        session.commit()
        for row in rows:
            session.refresh(row)
        first_image_id = rows[2].id
        second_image_id = rows[4].id
    finally:
        session.close()

    tasks = [
        {
            "db_id": first_image_id,
            "group_id": 20002,
            "user_id": 10001,
            "message_id": 40003,
            "image_index": 0,
            "hash": "hash-a",
            "task_id": "task-a",
        },
        {
            "db_id": second_image_id,
            "group_id": 20002,
            "user_id": 10001,
            "message_id": 40005,
            "image_index": 0,
            "hash": "hash-b",
            "task_id": "task-b",
        },
    ]

    timeline = build_timeline(tasks, {"hash-a": 0, "hash-b": 1})

    assert timeline == [
        {"user": "用户A(10001)", "type": "text", "text": "前文一"},
        {"user": "用户B(10002)", "type": "text", "text": "前文二"},
        {"user": "用户A(10001)", "type": "image", "index": 0},
        {"user": "用户B(10002)", "type": "text", "text": "夹在两图之间的回复"},
        {"user": "用户A(10001)", "type": "image", "index": 1},
    ]


def test_after_context_chars_control_batch_readiness():
    old_after = config.message_image_context_after_chars
    config.message_image_context_after_chars = 30
    init_db()
    session = SessionLocal()
    try:
        session.query(GroupMessage).delete()
        image = GroupMessage(
            time=datetime.now(),
            self_id=1,
            user_id=10001,
            group_id=20002,
            raw_message="[CQ:image,file=1,url=x]",
            sender_nickname="用户A",
            sender_card="",
            message_id=50001,
            reply_id=None,
        )
        short_after = GroupMessage(
            time=datetime.now(),
            self_id=1,
            user_id=10002,
            group_id=20002,
            raw_message="短",
            sender_nickname="用户B",
            sender_card="",
            message_id=50002,
            reply_id=None,
        )
        session.add_all([image, short_after])
        session.commit()
        session.refresh(image)
        task = {"db_id": image.id, "group_id": 20002, "user_id": 10001}

        assert after_context_chars(20002, 10001, image.id) < 30
        assert not _has_enough_after_context(task)

        enough_after = GroupMessage(
            time=datetime.now(),
            self_id=1,
            user_id=10003,
            group_id=20002,
            raw_message="这一段后文已经足够说明图片发送后的聊天语境",
            sender_nickname="用户C",
            sender_card="",
            message_id=50003,
            reply_id=None,
        )
        session.add(enough_after)
        session.commit()

        assert after_context_chars(20002, 10001, image.id) >= 30
        assert _has_enough_after_context(task)
    finally:
        config.message_image_context_after_chars = old_after
        session.close()


def test_batch_flush_only_selects_tasks_with_enough_after_context(monkeypatch):
    old_key = config.message_ai_api_key
    old_batch = config.message_image_batch_size
    old_after = config.message_image_context_after_chars
    config.message_ai_api_key = "test-key"
    config.message_image_batch_size = 2
    config.message_image_context_after_chars = 20
    init_db()
    session = SessionLocal()
    try:
        session.query(GroupMessage).delete()
        rows = [
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="[CQ:image,file=1,url=x]",
                sender_nickname="用户A",
                sender_card="",
                message_id=60001,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10002,
                group_id=20002,
                raw_message="第一张图后面的文字足够触发",
                sender_nickname="用户B",
                sender_card="",
                message_id=60002,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="[CQ:image,file=2,url=y]",
                sender_nickname="用户A",
                sender_card="",
                message_id=60003,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10002,
                group_id=20002,
                raw_message="第二张图后面的文字也足够触发",
                sender_nickname="用户B",
                sender_card="",
                message_id=60004,
                reply_id=None,
            ),
            GroupMessage(
                time=datetime.now(),
                self_id=1,
                user_id=10001,
                group_id=20002,
                raw_message="[CQ:image,file=3,url=z]",
                sender_nickname="用户A",
                sender_card="",
                message_id=60005,
                reply_id=None,
            ),
        ]
        session.add_all(rows)
        session.commit()
        for row in rows:
            session.refresh(row)

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

        count = asyncio.run(maybe_flush_batch_pending())

        assert count == 2
        assert captured["reason"] == "batch"
        assert captured["all_conversations"] is True
        assert captured["task_ids"] == {"ready-a", "ready-b"}
    finally:
        config.message_ai_api_key = old_key
        config.message_image_batch_size = old_batch
        config.message_image_context_after_chars = old_after
        session.close()
        PENDING_FILE.unlink(missing_ok=True)
