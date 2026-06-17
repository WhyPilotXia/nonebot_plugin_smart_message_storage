# python3
# -*- coding: utf-8 -*-

import base64
import io
import re
import textwrap

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.exception import FinishedException
from nonebot.log import logger
from nonebot.params import CommandArg
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import Integer, cast, desc

from ..db import SessionLocal
from ..models import GroupMessage
from ..services.message_utils import conversation_group_id

search_message = on_command("查消息", priority=5)


def text_to_base64_image(lines: list[str]) -> str:
    font = ImageFont.truetype("simkai.ttf", size=20)
    wrapped_lines = []
    for line in lines:
        wrapped = textwrap.wrap(line, width=80)
        if not wrapped:
            wrapped = [""]
        wrapped_lines.extend(wrapped)

    line_height = 30
    img_width = 1200
    img_height = max(100, len(wrapped_lines) * line_height + 40)
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)
    y = 20
    for line in wrapped_lines:
        draw.text((20, y), line, fill="black", font=font)
        y += line_height

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return "base64://" + base64.b64encode(buffer.getvalue()).decode()


@search_message.handle()
async def handle_search(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return

    args_text = str(args).strip()
    if not args_text:
        await search_message.finish("用法：/查消息 关键词\n或\n/查消息 群号 关键词")

    if isinstance(event, GroupMessageEvent):
        try:
            await bot.call_api(
                "set_msg_emoji_like",
                group_id=event.group_id,
                message_id=event.message_id,
                emoji_id="269",
                set=True,
            )
        except Exception as e:
            logger.warning(f"贴表情失败: {e}")

    target_group_id = conversation_group_id(event)
    target_user_id = event.user_id
    keyword = args_text

    m = re.match(r"^(\d{8,11})\s+(.+)$", args_text)
    if m:
        target_group_id = int(m.group(1))
        target_user_id = None
        keyword = m.group(2).strip()

    if not keyword:
        await search_message.finish("请输入关键词")

    session = SessionLocal()
    try:
        query = session.query(GroupMessage).filter(
            GroupMessage.group_id == cast(target_group_id, Integer),
            GroupMessage.raw_message.like(f"%{keyword}%"),
        )
        if target_group_id == -1 and target_user_id is not None:
            query = query.filter(GroupMessage.user_id == target_user_id)

        results = query.order_by(desc(GroupMessage.time)).limit(100).all()
        if not results:
            await search_message.finish("七七翻遍了消息也没找到这个关键词哇/(ㄒoㄒ)/~~")

        lines = []
        for msg in reversed(results):
            name = msg.sender_card or msg.sender_nickname
            lines.append(
                f"[{msg.time.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{name}({msg.user_id}): "
                f"{msg.raw_message}"
            )

        await search_message.finish(MessageSegment.image(text_to_base64_image(lines)))
    except FinishedException:
        pass
    except Exception as e:
        logger.error(f"查消息失败: {e}")
        await search_message.finish("查询失败")
    finally:
        session.close()
