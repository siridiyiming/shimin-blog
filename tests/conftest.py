import os

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.models import Admin, Base, Taxonomy


@pytest.fixture(scope='session')
def test_config(tmp_path_factory):
    env = dotenv_values('.env')
    url = os.getenv('TEST_DATABASE_URL') or env.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('设置独立的 TEST_DATABASE_URL 后运行 MySQL API 测试。')
    database_name = url.split('/')[-1].split('?')[0]
    if not database_name.endswith('_test'):
        pytest.fail('TEST_DATABASE_URL 数据库名称必须以 _test 结尾，以保护正常数据。')
    return {'TESTING': True, 'DATABASE_URL': url,
            'SECRET_KEY': 'test-only-session-secret-long-enough-12345678',
            'DATA_DIR': str(tmp_path_factory.mktemp('siriblog-uploads'))}


@pytest.fixture(autouse=True)
def reset_test_database(test_config):
    engine = create_engine(test_config['DATABASE_URL'], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Admin(id=1, username='admin', password_hash=generate_password_hash('test-only-password-2026', method='scrypt')))
        for kind, name in [('category', '示例分类'), ('category', '游戏分类'), ('tag', '示例标签')]:
            session.add(Taxonomy(kind=kind, name=name))
        session.commit()
    yield
    engine.dispose()


@pytest.fixture()
def app(test_config):
    instance = create_app(test_config)
    yield instance
    instance.extensions['db_engine'].dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def headers(origin='http://127.0.0.1:5173'):
    return {'X-Blog-Request': '1', 'Origin': origin}


@pytest.fixture()
def authed(client):
    result = client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-only-password-2026'}, headers=headers())
    assert result.status_code == 200
    return client
