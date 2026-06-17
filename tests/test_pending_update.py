# python3
# -*- coding: utf-8 -*-

from datetime import datetime

from nonebot_plugin_message_storage.db import SessionLocal, init_db
from nonebot_plugin_message_storage.models import GroupMessage
from nonebot_plugin_message_storage.services.pending import _update_messages, build_timeline


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
