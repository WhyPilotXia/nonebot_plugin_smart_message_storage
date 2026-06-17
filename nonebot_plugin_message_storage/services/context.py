# python3
# -*- coding: utf-8 -*-

from sqlalchemy import desc

from ..db import SessionLocal
from ..models import GroupMessage


def message_snapshot(msg: GroupMessage) -> dict:
    name = msg.sender_card or msg.sender_nickname or str(msg.user_id)
    return {
        "id": msg.id,
        "message_id": msg.message_id,
        "user_id": msg.user_id,
        "user": f"{name}({msg.user_id})",
        "text": msg.raw_message or "",
    }


def select_context_messages(group_id: int, user_id: int, before_db_id: int) -> list[dict]:
    session = SessionLocal()
    try:
        query = session.query(GroupMessage).filter(GroupMessage.id < before_db_id)
        if group_id == -1:
            query = query.filter(GroupMessage.group_id == -1, GroupMessage.user_id == user_id)
        else:
            query = query.filter(GroupMessage.group_id == group_id)

        selected: list[dict] = []
        total = 0
        rows = query.order_by(desc(GroupMessage.id)).limit(2000).all()
        for msg in rows:
            name = msg.sender_card or msg.sender_nickname or str(msg.user_id)
            line = f"{name}({msg.user_id}): {msg.raw_message or ''}"
            line_len = len(line)

            if selected and total + line_len > 600:
                break

            selected.append(message_snapshot(msg))
            total += line_len
            if total > 150:
                break

        return list(reversed(selected))
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
