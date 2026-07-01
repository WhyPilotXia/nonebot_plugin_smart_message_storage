# python3
# -*- coding: utf-8 -*-

from nonebot.log import logger
from nonebot import get_driver, require
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_data_dir

from .config import config

DATA_DIR = get_data_dir("nonebot_plugin_smart_message_storage")
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
PENDING_FILE = DATA_DIR / "pending_images.json"

IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"Smart message storage data dir: {DATA_DIR}")
if not config.message_ai_api_key:
    logger.info(
        "Smart message storage AI image recognition is disabled: "
        "message_ai_api_key is not configured."
    )
