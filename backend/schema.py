"""Small, idempotent MySQL schema upgrades for the local first release."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .models import Base, Setting

NEW_SITE_NAME = '一码当先小柿民博客'


def initialize_schema(engine):
    Base.metadata.create_all(engine)
    if engine.dialect.name != 'mysql':
        return
    columns = inspect(engine).get_columns('contents')
    names = {column['name'] for column in columns}
    with engine.begin() as connection:
        if 'video_url' not in names:
            connection.execute(text("ALTER TABLE contents ADD COLUMN video_url VARCHAR(2048) NOT NULL DEFAULT ''"))
        if 'show_published_at' not in names:
            connection.execute(text('ALTER TABLE contents ADD COLUMN show_published_at BOOLEAN NOT NULL DEFAULT TRUE'))
    body = next((column for column in columns if column['name'] == 'body'), None)
    if body and body['type'].__class__.__name__.lower() != 'mediumtext':
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE contents MODIFY body MEDIUMTEXT NOT NULL'))
    with Session(engine) as db:
        settings = db.get(Setting, 1)
        if settings and settings.value.get('name') == 'Blog':
            settings.value = {**settings.value, 'name': NEW_SITE_NAME}
            db.commit()
