# python3
# -*- coding: utf-8 -*-

from datetime import datetime

from nonebot import on_notice
from nonebot.adapters.onebot.v11 import (
    Bot,
    FriendRecallNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupRecallNoticeEvent,
    PokeNotifyEvent,
)
from nonebot.log import logger

from ..db import SessionLocal
from ..models import GroupMessage
from ..services.contacts import get_display_name
from ..services.message_utils import conversation_group_id

notice_logger = on_notice(priority=100)


def build_poke_raw_message(event: PokeNotifyEvent, target_name: str) -> str:
    action = "戳了戳"
    suffix = ""
    raw_info = event.dict().get("raw_info") or []
    texts = [
        item["txt"]
        for item in raw_info
        if isinstance(item, dict) and item.get("type") == "nor" and item.get("txt")
    ]

    if texts:
        action = texts[0]
    if len(texts) >= 2:
        suffix = "".join(texts[1:])
    if not texts:
        action = getattr(event, "action", "戳了戳")
        suffix = getattr(event, "suffix", "")

    return f"[戳一戳]{action}{event.target_id}({target_name}){suffix}"


def build_notice_raw_message(event) -> str:
    if isinstance(event, GroupDecreaseNoticeEvent):
        if event.operator_id == event.user_id:
            return f"[退群]用户{event.user_id}自己退群"
        return f"[被踢]用户{event.user_id}被{event.operator_id}移出本群"

    if isinstance(event, GroupIncreaseNoticeEvent):
        return f"[加群]用户{event.user_id}由{event.operator_id}同意加入本群"

    if isinstance(event, GroupRecallNoticeEvent):
        return f"[撤回]消息{event.message_id}被用户{event.operator_id}撤回"

    if isinstance(event, FriendRecallNoticeEvent):
        return f"[撤回]消息{event.message_id}被用户{event.user_id}撤回"

    return ""


@notice_logger.handle()
async def log_notice_event(bot: Bot, event):
    if not isinstance(
        event,
        (
            PokeNotifyEvent,
            GroupDecreaseNoticeEvent,
            GroupIncreaseNoticeEvent,
            GroupRecallNoticeEvent,
            FriendRecallNoticeEvent,
        ),
    ):
        return

    group_id = conversation_group_id(event)
    session = SessionLocal()
    try:
        if isinstance(event, PokeNotifyEvent):
            target_name = await get_display_name(bot, event.target_id, group_id)
            raw_message = build_poke_raw_message(event, target_name)
        else:
            raw_message = build_notice_raw_message(event)

        if not raw_message:
            return

        sender_nickname = await get_display_name(bot, event.user_id, group_id)
        sender_card = sender_nickname if group_id == -1 else ""
        msg = GroupMessage(
            time=datetime.now(),
            self_id=event.self_id,
            user_id=event.user_id,
            group_id=group_id,
            raw_message=raw_message,
            sender_nickname=sender_nickname,
            sender_card=sender_card,
            message_id=-1,
            reply_id=-1,
        )
        session.add(msg)
        session.commit()
        logger.debug(f"[DB] 已记录 notice 到消息表: group_id={group_id}, raw_message={raw_message}")
    except Exception as e:
        logger.error(f"[DB] 保存 notice 到消息表失败: {e}")
        session.rollback()
    finally:
        session.close()
