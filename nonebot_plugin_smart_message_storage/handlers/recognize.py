# python3
# -*- coding: utf-8 -*-

from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, PrivateMessageEvent
from nonebot.log import logger
from nonebot.params import CommandArg
from sqlalchemy import desc, select

from ..db import SessionLocal
from ..models import GroupMessage
from ..services.image_tasks import collect_pending_images
from ..services.message_utils import IMAGE_CQ_RE, conversation_group_id
from ..services.pending import flush_pending


def _reply_command_rule(event: MessageEvent) -> bool:
    return isinstance(event, MessageEvent) and _has_reply(event)


recognize_now = on_command("立即识别", priority=5, block=True)
recognize_reply = on_command("识别", priority=5, block=True, rule=_reply_command_rule)


@recognize_now.handle()
async def handle_recognize_now(event: MessageEvent, args: Message = CommandArg()):
    text = str(args).strip()
    group_id = conversation_group_id(event)

    if text == "全部":
        superusers = {str(user) for user in get_driver().config.superusers}
        if str(event.user_id) not in superusers:
            await recognize_now.finish("只有 SUPERUSERS 可以执行全局识别。")
        count = await flush_pending(reason="command_all", all_conversations=True)
        await recognize_now.finish(f"已提交全局待识别图片 {count} 张。")

    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        await recognize_now.finish("当前会话不支持立即识别。")

    count = await flush_pending(reason="command", group_id=group_id, user_id=event.user_id)
    await recognize_now.finish(f"已提交当前会话待识别图片 {count} 张。")


@recognize_reply.handle()
async def handle_recognize_reply(bot: Bot, event: MessageEvent):
    reply_message_id = _get_reply_message_id(event)
    if reply_message_id is None:
        return

    msg = await _get_stored_message(reply_message_id)
    if not msg:
        await recognize_reply.finish("没有在数据库中找到回复的消息。")

    raw_message = msg.raw_message or ""
    if not IMAGE_CQ_RE.search(raw_message):
        if _has_recognized_image(raw_message):
            await _like_command(bot, event, "320")
            await recognize_reply.finish(raw_message)
        await recognize_reply.finish("回复的消息似乎不包含图片哦")

    await _like_command(bot, event, "314")
    reply_message = await _get_reply_message(bot, event, reply_message_id, raw_message)
    if reply_message:
        await collect_pending_images(bot, reply_message_id, reply_message, msg)

    await flush_pending(reason="reply_command", group_id=msg.group_id, user_id=msg.user_id)
    refreshed = await _get_stored_message(reply_message_id)
    await recognize_reply.finish((refreshed.raw_message if refreshed else raw_message) or raw_message)


def _has_reply(event: MessageEvent) -> bool:
    if event.reply:
        return True
    return any(seg.type == "reply" for seg in event.message)


def _get_reply_message_id(event: MessageEvent) -> int | None:
    if event.reply:
        return event.reply.message_id
    for seg in event.message:
        if seg.type != "reply":
            continue
        try:
            return int(seg.data["id"])
        except Exception:
            logger.warning(f"读取回复消息 ID 失败: {seg.data}")
            return None
    return None


async def _get_reply_message(bot: Bot, event: MessageEvent, message_id: int, fallback_raw_message: str) -> Message | None:
    if event.reply and event.reply.message:
        return event.reply.message

    for seg in event.message:
        if seg.type == "reply" and str(seg.data.get("id", "")) == str(message_id):
            try:
                msg = await bot.get_msg(message_id=message_id)
                return Message(msg["message"])
            except Exception as e:
                logger.opt(exception=e).warning(f"通过 get_msg 获取回复消息失败: message_id={message_id}")
                break

    try:
        return Message(fallback_raw_message)
    except Exception as e:
        logger.opt(exception=e).warning(f"从数据库 raw_message 解析回复消息失败: message_id={message_id}")
        return None


async def _get_stored_message(message_id: int) -> GroupMessage | None:
    stmt = (
        select(GroupMessage)
        .where(GroupMessage.message_id == message_id)
        .order_by(desc(GroupMessage.id))
    )
    async with SessionLocal() as session:
        return (await session.scalars(stmt)).first()


def _has_recognized_image(raw_message: str) -> bool:
    return "[image:{" in raw_message


async def _like_command(bot: Bot, event: MessageEvent, emoji_id: str) -> None:
    if not isinstance(event, GroupMessageEvent):
        return
    try:
        await bot.call_api(
            "set_msg_emoji_like",
            group_id=event.group_id,
            message_id=event.message_id,
            emoji_id=emoji_id,
            set=True,
        )
    except Exception as e:
        logger.opt(exception=e).warning("贴表情失败")
