# python3
# -*- coding: utf-8 -*-

from nonebot.adapters.onebot.v11 import Message, MessageSegment

from nonebot_plugin_message_storage.services.message_utils import image_segments, image_summary_segment
from nonebot_plugin_message_storage.services.pending import _replace_one_image


def test_image_segments_are_numbered_by_image_order():
    message = Message("前文") + MessageSegment.image("a.jpg") + Message("中间") + MessageSegment.image("b.jpg")

    images = image_segments(message)

    assert len(images) == 2
    assert images[0][0] == 0
    assert images[1][0] == 1


def test_image_summary_segment_escapes_json_strings():
    segment = image_summary_segment('写着 "hello"', "看不清右下角")

    assert segment == '[image:{summary:"写着 \\"hello\\"",tip:"看不清右下角"}]'


def test_replace_one_image_by_image_index():
    raw = "a[CQ:image,file=1,url=x]b[CQ:image,file=2,url=y]c"

    replaced = _replace_one_image(raw, "", 1, '[image:{summary:"第二张",tip:""}]')

    assert replaced == 'a[CQ:image,file=1,url=x]b[image:{summary:"第二张",tip:""}]c'


def test_replace_one_image_falls_back_to_segment_text():
    raw = "before <image-token> after"

    replaced = _replace_one_image(raw, "<image-token>", 9, '[image:{summary:"fallback",tip:""}]')

    assert replaced == 'before [image:{summary:"fallback",tip:""}] after'
