# python3
# -*- coding: utf-8 -*-

from nonebot import get_driver, require
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_localstore")

from .config import MessageStorageConfig
from .db import init_db
from .services.pending import start_stale_flush_loop

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-message-storage",
    description="OneBot v11 QQ 消息存储插件，支持群聊/私聊消息、notice 事件入库和图片 AI 总结回写。",
    usage=(
        "/查消息 关键词\n"
        "/查消息 群号 关键词\n"
        "/识别\n"
        "/立即识别\n"
        "/立即识别 全部"
    ),
    type="application",
    config=MessageStorageConfig,
    supported_adapters={"~onebot.v11"},
)

init_db()

driver = get_driver()


@driver.on_startup
async def _startup() -> None:
    start_stale_flush_loop()
    logger.debug("Message storage plugin started.")


from . import handlers as handlers
