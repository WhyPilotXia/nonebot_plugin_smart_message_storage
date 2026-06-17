# python3
# -*- coding: utf-8 -*-

from typing import Optional

from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger


async def get_display_name(bot: Bot, user_id: int, group_id: Optional[int] = None) -> str:
    if group_id is not None and group_id != -1:
        try:
            member = await bot.get_group_member_info(group_id=group_id, user_id=user_id, no_cache=False)
            return member.get("card") or member.get("nickname") or str(user_id)
        except Exception as e:
            logger.warning(f"[DB] 获取群成员信息失败: group={group_id}, user={user_id}, error={e}")

    try:
        friends = await bot.get_friend_list()
        for friend in friends:
            if int(friend.get("user_id", 0)) == int(user_id):
                return friend.get("remark") or friend.get("nickname") or str(user_id)
    except Exception as e:
        logger.warning(f"[DB] 获取好友列表失败: user={user_id}, error={e}")

    try:
        stranger = await bot.get_stranger_info(user_id=user_id, no_cache=False)
        return stranger.get("nickname") or str(user_id)
    except Exception as e:
        logger.warning(f"[DB] 获取陌生人信息失败: user={user_id}, error={e}")
        return str(user_id)
