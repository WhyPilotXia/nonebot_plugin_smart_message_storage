# python3
# -*- coding: utf-8 -*-

import html
import json
import re
from typing import Any

from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment


IMAGE_CQ_RE = re.compile(r"\[CQ:image,[^\]]+\]")


def conversation_group_id(event: Any) -> int:
    group_id = getattr(event, "group_id", None)
    return int(group_id) if group_id is not None else -1


def is_private_conversation(event: Any) -> bool:
    return conversation_group_id(event) == -1


def raw_message_text(event: MessageEvent) -> str:
    return html.unescape(event.raw_message)


def image_segments(message: Message) -> list[tuple[int, MessageSegment]]:
    images = []
    for segment in message:
        if segment.type == "image":
            images.append((len(images), segment))
    return images


def segment_to_text(segment: MessageSegment) -> str:
    return html.unescape(str(segment))


def compact_json_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False, separators=(",", ":"))


def image_summary_segment(summary: str, tip: str) -> str:
    return f"[image:{{summary:{compact_json_string(summary)},tip:{compact_json_string(tip)}}}]"
