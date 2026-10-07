import time
import uuid

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.mysql import MEDIUMTEXT


def now():
    return int(time.time())


class Base(DeclarativeBase):
    pass


class Content(Base):
    __tablename__ = 'contents'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String(12), nullable=False, index=True)
    status = Column(String(12), nullable=False, default='draft', index=True)
    title = Column(String(160), nullable=False)
    summary = Column(Text, nullable=False, default='')
    body = Column(MEDIUMTEXT, nullable=False, default='')
    category = Column(String(60), nullable=False, default='')
    tags = Column(JSON, nullable=False, default=list)
    cover = Column(String(512), nullable=False, default='')
    url = Column(String(2048), nullable=False, default='')
    screenshots = Column(JSON, nullable=False, default=list)
    device = Column(String(120), nullable=False, default='')
    instructions = Column(Text, nullable=False, default='')
    video_url = Column(String(2048), nullable=False, default='')
    show_published_at = Column(Boolean, nullable=False, default=True)
    featured = Column(Boolean, nullable=False, default=False)
    featured_order = Column(Integer, nullable=False, default=0)
    published_at = Column(Integer, nullable=True, index=True)
    created_at = Column(Integer, nullable=False, default=now)
    updated_at = Column(Integer, nullable=False, default=now)


class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(36), ForeignKey('contents.id'), nullable=True, index=True)
    root_id = Column(Integer, ForeignKey('comments.id'), nullable=True, index=True)
    reply_to = Column(Integer, ForeignKey('comments.id'), nullable=True)
    nickname = Column(String(40), nullable=False)
    body = Column(Text, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    deleted = Column(Boolean, nullable=False, default=False)
    visitor = Column(String(64), nullable=False)
    created_at = Column(Integer, nullable=False, default=now, index=True)


class Like(Base):
    __tablename__ = 'likes'
    content_id = Column(String(36), ForeignKey('contents.id'), primary_key=True)
    visitor = Column(String(64), primary_key=True)


class Admin(Base):
    __tablename__ = 'admin'
    id = Column(Integer, primary_key=True, default=1)
    username = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash = Column(String(64), primary_key=True)
    expires_at = Column(Integer, nullable=False)


class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True, default=1)
    value = Column(JSON, nullable=False)


class Taxonomy(Base):
    __tablename__ = 'taxonomies'
    id = Column(Integer, primary_key=True)
    kind = Column(String(12), nullable=False)
    name = Column(String(60), nullable=False)
    __table_args__ = (UniqueConstraint('kind', 'name'),)


class Media(Base):
    __tablename__ = 'media'
    id = Column(String(36), primary_key=True)
    name = Column(String(160), nullable=False)
    url = Column(String(512), nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(Integer, nullable=False, default=now)


class RateEvent(Base):
    __tablename__ = 'rate_events'
    id = Column(Integer, primary_key=True)
    bucket = Column(String(100), nullable=False, index=True)
    created_at = Column(Integer, nullable=False, default=now, index=True)
