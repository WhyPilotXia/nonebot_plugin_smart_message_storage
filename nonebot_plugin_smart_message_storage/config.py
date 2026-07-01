# python3
# -*- coding: utf-8 -*-

from nonebot import get_plugin_config
from pydantic import BaseModel


class MessageStorageConfig(BaseModel):
    message_ai_base_url: str = "https://api.exesim.com/v1"
    message_ai_api_key: str = ""
    message_ai_model: str = "gemini-3.5-flash"
    message_image_batch_size: int = 5
    message_image_flush_seconds: int = 30 * 60
    message_image_context_before_chars: int = 100
    message_image_context_after_chars: int = 100
    message_db_url: str = "sqlite:///qq_messages.db"


config = get_plugin_config(MessageStorageConfig)
