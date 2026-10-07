from io import BytesIO

from PIL import Image
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.models import Content, Setting
from backend.schema import NEW_SITE_NAME, initialize_schema
from conftest import headers


def article_payload(**overrides):
    data = {'type': 'article', 'status': 'published', 'title': '初夏的笔记', 'summary': '一段精心整理的文字。',
            'category': '示例分类', 'tags': ['示例标签'], 'body': '<h2>从小事开始</h2><p>一点一点，慢慢写下去。</p>',
            'featured': True, 'featured_order': 1}
    data.update(overrides)
    return data


def test_existing_default_site_name_migrates_without_losing_settings(app):
    engine = app.extensions['db_engine']
    with Session(engine) as db:
        db.add(Setting(id=1, value={'name': 'Blog', 'bio': '原有个人简介', 'links': [{'label': '主页', 'url': 'https://example.org'}]}))
        db.commit()
    initialize_schema(engine)
    with Session(engine) as db:
        value = db.get(Setting, 1).value
        assert value == {'name': NEW_SITE_NAME, 'bio': '原有个人简介', 'links': [{'label': '主页', 'url': 'https://example.org'}]}
        db.get(Setting, 1).value = {**value, 'name': '站长自定义名称'}
        db.commit()
    initialize_schema(engine)
    with Session(engine) as db:
        assert db.get(Setting, 1).value['name'] == '站长自定义名称'


def test_existing_mysql_content_table_gains_new_fields_without_losing_rows(app):
    engine = app.extensions['db_engine']
    with Session(engine) as db:
        db.add(Content(type='article', status='published', title='旧内容', published_at=100))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE contents DROP COLUMN video_url'))
        connection.execute(text('ALTER TABLE contents DROP COLUMN show_published_at'))
    initialize_schema(engine)
    initialize_schema(engine)
    assert {'video_url', 'show_published_at'}.issubset({column['name'] for column in inspect(engine).get_columns('contents')})
    with Session(engine) as db:
        old = db.scalar(select(Content).where(Content.title == '旧内容'))
        assert old and old.video_url == '' and old.show_published_at is True


def test_admin_auth_and_same_origin_guarded_writes(client):
    assert client.get('/api/admin/contents').status_code == 401
    blocked = client.post('/api/auth/login', json={'username': 'admin', 'password': 'guess'}, headers=headers('https://evil.invalid'))
    assert blocked.status_code == 403
    good = client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-only-password-2026'}, headers=headers())
    assert good.status_code == 200
    assert client.get('/api/admin/contents').status_code == 200
    assert client.post('/api/admin/contents', json=article_payload(), headers=headers()).status_code == 201


def test_publication_search_isolation_and_mysql_persistence(client, authed, app):
    result = client.post('/api/admin/contents', json=article_payload(), headers=headers())
    assert result.status_code == 201, result.json
    item_id = result.json['id']
    assert client.get('/api/contents/' + item_id).status_code == 200
    assert client.get('/api/contents?type=article&q=初夏的笔记').json['items'][0]['id'] == item_id
    draft = article_payload(status='draft', title='草稿不对外公开', featured=False)
    unpublished = client.post('/api/admin/contents', json=draft, headers=headers())
    assert unpublished.status_code == 201
    draft_id = unpublished.json['id']
    assert client.get('/api/contents/' + draft_id).status_code == 404
    assert client.get('/api/contents?q=草稿不对外公开').json['items'] == []
    archived = client.put('/api/admin/contents/' + item_id, json=article_payload(status='archived'), headers=headers())
    assert archived.status_code == 200
    assert client.get('/api/contents/' + item_id).status_code == 404
    database_url = app.config['DATABASE_URL']
    secret_key, directory = app.config['SECRET_KEY'], app.config['DATA_DIR']
    app.extensions['db_engine'].dispose()
    restarted = create_app({'DATABASE_URL': database_url, 'SECRET_KEY': secret_key, 'DATA_DIR': directory, 'TESTING': True})
    try:
        with Session(restarted.extensions['db_engine']) as db:
            records = db.scalars(select(Content).where(Content.id.in_([item_id, draft_id]))).all()
            assert len(records) == 2
            assert {record.status for record in records} == {'draft', 'archived'}
    finally:
        restarted.extensions['db_engine'].dispose()


def test_like_is_idempotent_per_browser(client, authed):
    item = client.post('/api/admin/contents', json=article_payload(), headers=headers()).json
    endpoint = '/api/contents/' + item['id'] + '/like'
    first = client.put(endpoint, json={'liked': True}, headers=headers())
    again = client.put(endpoint, json={'liked': True}, headers=headers())
    assert first.json['like_count'] == again.json['like_count'] == 1
    assert client.get('/api/contents/' + item['id']).json['liked'] is True
    assert client.put(endpoint, json={'liked': False}, headers=headers()).json['like_count'] == 0
    assert client.put(endpoint, json={'liked': False}, headers=headers()).json['like_count'] == 0


def test_replies_remain_flat_and_deleted_quotes_hide_old_text(client, authed):
    item = client.post('/api/admin/contents', json=article_payload(), headers=headers()).json
    base = {'contentId': item['id'], 'nickname': '访客甲', 'body': '原评论正文'}
    root = client.post('/api/comments', json=base, headers=headers())
    assert root.status_code == 201
    reply = client.post('/api/comments', json={**base, 'nickname': '访客乙', 'body': '收到，谢谢你。', 'replyTo': root.json['id']}, headers=headers())
    assert reply.status_code == 201 and reply.json['root_id'] == root.json['id']
    followup = client.post('/api/comments', json={**base, 'nickname': '访客丙', 'body': '我也有相同的想法。', 'replyTo': reply.json['id']}, headers=headers())
    assert followup.status_code == 201 and followup.json['root_id'] == root.json['id']
    before = client.get('/api/comments?contentId=' + item['id']).json['items'][0]
    assert [reply['id'] for reply in before['replies']] == [reply.json['id'], followup.json['id']]
    assert client.post('/api/admin/comments/delete', json={'ids': [root.json['id']]}, headers=headers()).status_code == 200
    after = client.get('/api/comments?contentId=' + item['id']).json['items'][0]
    assert after['body'] == '该评论已删除'
    assert after['replies'][0]['quote'] == {'nickname': '已删除', 'body': '该评论已删除'}
    assert after['replies'][1]['quote']['body'] == '收到，谢谢你。'
    assert '原评论正文' not in str(after) and len(after['replies']) == 2
    assert client.post('/api/admin/comments/delete', json={'ids': [reply.json['id']]}, headers=headers()).status_code == 200
    remaining = client.get('/api/comments?contentId=' + item['id']).json['items'][0]
    assert len(remaining['replies']) == 1
    assert remaining['replies'][0]['quote'] == {'nickname': '已删除', 'body': '该评论已删除'}


def test_taxonomies_cannot_delete_categories_still_in_use(client, authed):
    item = client.post('/api/admin/contents', json=article_payload(), headers=headers())
    assert item.status_code == 201
    category = next(t for t in client.get('/api/admin/taxonomies').json['items'] if t['name'] == '示例分类')
    assert client.delete('/api/admin/taxonomies/' + str(category['id']), headers=headers()).status_code == 400
    assert client.put('/api/admin/taxonomies/' + str(category['id']), json={'name': '我的文章'}, headers=headers()).status_code == 200
    assert client.get('/api/admin/contents/' + item.json['id']).json['category'] == '我的文章'


def test_external_links_only_accept_http_and_https(client, authed):
    game = article_payload(type='game', cover='/images/orbit.svg', screenshots=['/images/orbit.svg'], device='手机触控', instructions='点击操作', url='javascript:alert(1)')
    assert client.post('/api/admin/contents', json=game, headers=headers()).status_code == 400
    tool = article_payload(type='tool', body='', summary='一个不错的工具', url='https://example.org', cover='')
    assert client.post('/api/admin/contents', json=tool, headers=headers()).status_code == 201


def test_optional_content_fields_and_date_visibility_survive_publication(client, authed):
    for kind in ('article', 'note', 'game', 'tool'):
        data = {'type': kind, 'status': 'published', 'title': f'只填必要项的{kind}',
                'show_published_at': False}
        if kind in ('game', 'tool'):
            data['url'] = 'https://example.org/play'
        result = client.post('/api/admin/contents', json=data, headers=headers())
        assert result.status_code == 201, result.json
        public = client.get('/api/contents/' + result.json['id']).json
        assert public['published_at'] and public['show_published_at'] is False
        assert public['summary'] == '' and public['category'] == ''
    missing_link = client.post('/api/admin/contents', json={'type': 'game', 'status': 'published', 'title': '无地址游戏'}, headers=headers())
    assert missing_link.status_code == 400


def test_game_video_requires_https_mp4_and_persists(client, authed):
    payload = {'type': 'game', 'status': 'published', 'title': '视频游戏', 'url': 'https://example.org/play',
               'video_url': 'https://cdn.example.org/trailer.mp4?version=2'}
    created = client.post('/api/admin/contents', json=payload, headers=headers())
    assert created.status_code == 201, created.json
    assert client.get('/api/contents/' + created.json['id']).json['video_url'] == payload['video_url']
    for bad in ('http://cdn.example.org/trailer.mp4', 'https://example.org/watch', 'javascript:alert(1)'):
        result = client.post('/api/admin/contents', json={**payload, 'video_url': bad}, headers=headers())
        assert result.status_code == 400


def test_carousel_settings_validate_links_and_preserve_old_client_values(client, authed):
    settings = {'name': '一码当先小柿民博客', 'carousel': [
        {'image': '/images/orbit.svg', 'title': '本周创作', 'action': 'preview_link', 'url': 'https://example.org/play'},
        {'image': '/images/orbit.svg', 'title': '', 'action': 'preview', 'url': ''}],
        'home_intro_first': False, 'hero_title': '新的首页标题'}
    saved = client.put('/api/admin/settings', json=settings, headers=headers())
    assert saved.status_code == 200, saved.json
    assert client.get('/api/bootstrap').json['settings']['carousel'] == settings['carousel']
    older_client = client.put('/api/admin/settings', json={'name': '更新后的名称'}, headers=headers())
    assert older_client.status_code == 200
    assert older_client.json['carousel'] == settings['carousel']
    assert older_client.json['home_intro_first'] is False
    assert older_client.json['hero_title'] == '新的首页标题'
    unsafe = client.put('/api/admin/settings', json={**settings, 'carousel': [
        {'image': '/images/orbit.svg', 'action': 'link', 'url': 'javascript:alert(1)'}]}, headers=headers())
    assert unsafe.status_code == 400


def test_media_upload_checks_real_format_and_optimizes_webp(client, authed):
    bad = client.post('/api/admin/media', data={'file': (BytesIO(b'<html>not an image</html>'), 'image.png')}, content_type='multipart/form-data', headers=headers())
    assert bad.status_code == 400
    image = Image.new('RGB', (60, 30), '#89a18c')
    source = BytesIO()
    image.save(source, 'PNG')
    result = client.post('/api/admin/media', data={'file': (BytesIO(source.getvalue()), 'sample.png')}, content_type='multipart/form-data', headers=headers())
    assert result.status_code == 201, result.json
    media = client.get('/api/admin/media').json['items'][0]
    assert media['url'].endswith('.webp')
    image_result = client.get(media['url'])
    assert image_result.status_code == 200 and image_result.mimetype == 'image/webp'
    image_result.close()
    assert client.delete('/api/admin/media/' + result.json['id'], headers=headers()).status_code == 200
