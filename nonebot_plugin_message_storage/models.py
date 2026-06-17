# python3
# -*- coding: utf-8 -*-

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class GroupMessage(Base):
    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime)
    self_id = Column(Integer)
    user_id = Column(Integer)
    group_id = Column(Integer)
    raw_message = Column(Text)
    sender_nickname = Column(String(255))
    sender_card = Column(String(255))
    message_id = Column(Integer)
    reply_id = Column(Integer, nullable=True)
