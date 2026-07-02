# python3
# -*- coding: utf-8 -*-

from sqlalchemy import asc, desc, select

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


def conversation_stmt(group_id: int, user_id: int):
    stmt = select(GroupMessage)
    if group_id == -1:
        return stmt.where(GroupMessage.group_id == -1, GroupMessage.user_id == user_id)
    return stmt.where(GroupMessage.group_id == group_id)


async def select_context_messages(group_id: int, user_id: int, image_db_id: int) -> list[dict]:
    before = await select_context_messages_before(
        group_id,
        user_id,
        image_db_id,
        config.message_image_context_before_chars,
    )
    after = await select_context_messages_after(
        group_id,
        user_id,
        image_db_id,
        config.message_image_context_after_chars,
    )
    merged = {int(msg["id"]): msg for msg in before}
    merged.update({int(msg["id"]): msg for msg in after})
    return [merged[key] for key in sorted(merged)]


async def select_context_messages_before(group_id: int, user_id: int, before_db_id: int, target_chars: int) -> list[dict]:
    stmt = (
        conversation_stmt(group_id, user_id)
        .where(GroupMessage.id < before_db_id)
        .order_by(desc(GroupMessage.id))
        .limit(2000)
    )
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()

    selected: list[dict] = []
    total = 0
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


async def select_context_messages_after(group_id: int, user_id: int, after_db_id: int, target_chars: int) -> list[dict]:
    stmt = (
        conversation_stmt(group_id, user_id)
        .where(GroupMessage.id > after_db_id)
        .order_by(asc(GroupMessage.id))
        .limit(2000)
    )
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()

    selected: list[dict] = []
    total = 0
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


async def after_context_chars(group_id: int, user_id: int, after_db_id: int) -> int:
    stmt = (
        conversation_stmt(group_id, user_id)
        .where(GroupMessage.id > after_db_id)
        .order_by(asc(GroupMessage.id))
        .limit(2000)
    )
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()

    total = 0
    for msg in rows:
        text = context_text(msg.raw_message or "")
        if not text:
            continue
        total += len(context_line(msg))
        if total >= config.message_image_context_after_chars:
            break
    return total


async def get_messages_by_ids(db_ids: set[int]) -> dict[int, dict]:
    if not db_ids:
        return {}
    stmt = select(GroupMessage).where(GroupMessage.id.in_(db_ids))
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {msg.id: message_snapshot(msg) for msg in rows}
