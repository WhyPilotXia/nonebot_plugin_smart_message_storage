# python3
# -*- coding: utf-8 -*-

from datetime import datetime

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, PrivateMessageEvent
from nonebot.log import logger

from ..config import config
from ..db import SessionLocal
from ..models import GroupMessage
from ..services.contacts import get_display_name
from ..services.image_tasks import collect_pending_images
from ..services.message_utils import conversation_group_id, raw_message_text

message_logger = on_message(priority=100)


@message_logger.handle()
async def log_message(bot: Bot, event: MessageEvent):
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return

    group_id = conversation_group_id(event)
    session = SessionLocal()
    msg = None
    try:
        reply_id = None
        if event.reply:
            reply_id = event.reply.message_id

        sender_nickname = getattr(event.sender, "nickname", "") or await get_display_name(bot, event.user_id, group_id)
        sender_card = getattr(event.sender, "card", "") or ""
        raw_message = raw_message_text(event)

        msg = GroupMessage(
            time=datetime.now(),
            self_id=event.self_id,
            user_id=event.user_id,
            group_id=group_id,
            raw_message=raw_message,
            sender_nickname=sender_nickname,
            sender_card=sender_card,
            message_id=event.message_id,
            reply_id=reply_id,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        logger.debug(f"[DB] 已记录消息: group_id={group_id}, user_id={event.user_id}, message_id={event.message_id}")
    except Exception as e:
        logger.error(f"[DB] 保存消息失败: {e}")
        session.rollback()
        return
    finally:
        session.close()

    if msg and config.ai_api_key:
        await collect_pending_images(bot, event.message_id, event.message, msg)
