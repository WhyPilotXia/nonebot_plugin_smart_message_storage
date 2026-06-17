# python3
# -*- coding: utf-8 -*-

import pytest

from nonebot_plugin_message_storage.vision import VisionError, parse_ai_json


def test_parse_ai_json_plain_object():
    parsed = parse_ai_json('{"images":[{"imageIndex":0,"summary":"表情包","tip":""}]}')

    assert parsed["images"][0]["summary"] == "表情包"


def test_parse_ai_json_markdown_fence():
    parsed = parse_ai_json('```json\n{"images":[{"imageIndex":0,"summary":"截图","tip":"字小"}]}\n```')

    assert parsed["images"][0]["tip"] == "字小"


def test_parse_ai_json_extracts_last_json_object():
    parsed = parse_ai_json('前缀 {"bad": true} 后缀 {"images":[{"imageIndex":0,"summary":"人物照片","tip":""}]}')

    assert parsed["images"][0]["summary"] == "人物照片"


def test_parse_ai_json_rejects_image_generation_response():
    with pytest.raises(VisionError):
        parse_ai_json("![image](https://example.com/t2i/output.png)")
