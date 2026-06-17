# python3
# -*- coding: utf-8 -*-

import os

from nonebot import get_plugin_config
from pydantic import BaseModel


class MessageStorageConfig(BaseModel):
    ai_base_url: str = "https://api.exesim.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gemini-3.5-flash"
    image_batch_size: int = 5
    image_flush_seconds: int = 30 * 60
    db_url: str = "sqlite:///qq_messages.db"


config = get_plugin_config(MessageStorageConfig)

config.ai_base_url = os.getenv("AI_BASE_URL", config.ai_base_url)
config.ai_api_key = os.getenv("AI_API_KEY", config.ai_api_key)
config.ai_model = os.getenv("AI_MODEL", config.ai_model)
config.db_url = os.getenv("DB_URL", config.db_url)
config.image_batch_size = int(os.getenv("IMAGE_BATCH_SIZE", config.image_batch_size))
config.image_flush_seconds = int(os.getenv("IMAGE_FLUSH_SECONDS", config.image_flush_seconds))
