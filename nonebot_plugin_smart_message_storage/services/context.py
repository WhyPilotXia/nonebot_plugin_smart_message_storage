# python3
# -*- coding: utf-8 -*-

from sqlalchemy import asc, desc

from ..config import config
from ..db import SessionLocal
from ..models import GroupMessage
from .message_utils import IMAGE_CQ_RE

CONTEXT_MAX_CHARS = 600


def message_snapshot(msg: GroupMessage) -> dict:
    name = msg.sender_card or msg.sender_nickname or str(msg.user_id)
    return {
        "id": msg.id,
        "message_id": msg.message_id,
        "user_id": msg.user_id,
        "user": f"{name}({msg.user_id})",
        "text": msg.raw_message or "",
    }


def context_text(raw_message: str) -> str:
    return IMAGE_CQ_RE.sub("", raw_message or "").strip()


def context_line(msg: GroupMessage) -> str:
    name = msg.sender_card or msg.sender_nickname or str(msg.user_id)
    return f"{name}({msg.user_id}): {context_text(msg.raw_message or '')}"


def conversation_query(session, group_id: int, user_id: int):
    query = session.query(GroupMessage)
    if group_id == -1:
        return query.filter(GroupMessage.group_id == -1, GroupMessage.user_id == user_id)
    return query.filter(GroupMessage.group_id == group_id)


def select_context_messages(group_id: int, user_id: int, image_db_id: int) -> list[dict]:
    before = select_context_messages_before(
        group_id,
        user_id,
        image_db_id,
        config.message_image_context_before_chars,
    )
    after = select_context_messages_after(
        group_id,
        user_id,
        image_db_id,
        config.message_image_context_after_chars,
    )
    merged = {int(msg["id"]): msg for msg in before}
    merged.update({int(msg["id"]): msg for msg in after})
    return [merged[key] for key in sorted(merged)]


def select_context_messages_before(group_id: int, user_id: int, before_db_id: int, target_chars: int) -> list[dict]:
    session = SessionLocal()
    try:
        query = conversation_query(session, group_id, user_id).filter(GroupMessage.id < before_db_id)

        selected: list[dict] = []
        total = 0
        rows = query.order_by(desc(GroupMessage.id)).limit(2000).all()
        for msg in rows:
            line = context_line(msg)
            line_len = len(line)
            if not context_text(msg.raw_message or ""):
                continue

            if selected and total + line_len > CONTEXT_MAX_CHARS:
                break

            selected.append(message_snapshot(msg))
            total += line_len
            if total >= target_chars:
                break

        return list(reversed(selected))
    finally:
        session.close()


def select_context_messages_after(group_id: int, user_id: int, after_db_id: int, target_chars: int) -> list[dict]:
    session = SessionLocal()
    try:
        query = conversation_query(session, group_id, user_id).filter(GroupMessage.id > after_db_id)

        selected: list[dict] = []
        total = 0
        rows = query.order_by(asc(GroupMessage.id)).limit(2000).all()
        for msg in rows:
            line = context_line(msg)
            line_len = len(line)
            if not context_text(msg.raw_message or ""):
                continue

            if selected and total + line_len > CONTEXT_MAX_CHARS:
                break

            selected.append(message_snapshot(msg))
            total += line_len
            if total >= target_chars:
                break

        return selected
    finally:
        session.close()


def after_context_chars(group_id: int, user_id: int, after_db_id: int) -> int:
    session = SessionLocal()
    try:
        query = conversation_query(session, group_id, user_id).filter(GroupMessage.id > after_db_id)
        total = 0
        for msg in query.order_by(asc(GroupMessage.id)).limit(2000).all():
            text = context_text(msg.raw_message or "")
            if not text:
                continue
            total += len(context_line(msg))
            if total >= config.message_image_context_after_chars:
                break
        return total
    finally:
        session.close()


def get_messages_by_ids(db_ids: set[int]) -> dict[int, dict]:
    if not db_ids:
        return {}
    session = SessionLocal()
    try:
        rows = session.query(GroupMessage).filter(GroupMessage.id.in_(db_ids)).all()
        return {msg.id: message_snapshot(msg) for msg in rows}
    finally:
        session.close()
