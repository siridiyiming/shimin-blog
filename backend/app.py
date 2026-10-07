import hashlib
import io
import json
import os
import re
import secrets
import uuid
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import bleach
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory, session
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import create_engine, delete, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from .models import Admin, AuthSession, Comment, Content, Like, Media, RateEvent, Setting, Taxonomy, now
from .schema import NEW_SITE_NAME

ROOT = Path(__file__).resolve().parents[1]
TYPES = ('game', 'article', 'note', 'tool')
DEFAULT_SETTINGS = {'name': NEW_SITE_NAME, 'tagline': '把有趣的想法，变成可以分享的作品。',
                    'bio': '这里是个人简介占位内容。记录创作、整理知识，也收藏那些让生活更轻松的工具。',
                    'avatar': '', 'links': [], 'placeholder': True,
                    'hero_title': '记录灵感，分享值得发现的事。',
                    'hero_kicker': 'A LITTLE SPACE FOR BIG IDEAS',
                    'hero_note': '关于热爱、好奇，和每一个新的开始',
                    'home_intro_first': True, 'carousel': []}


class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def text(value, label, maximum, required=False):
    if not isinstance(value, str) or len(value.strip()) > maximum:
        raise ApiError(f'{label}格式不正确或超过 {maximum} 字')
    value = value.strip()
    if required and not value:
        raise ApiError(f'请填写{label}')
    return value


def http_url(value, required=False):
    value = text(value, '链接', 2048, required)
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not parsed.password
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid or re.search(r'[\s\x00-\x1f]', value):
        raise ApiError('链接必须是有效的 HTTP 或 HTTPS 地址')
    return value


def mp4_url(value):
    value = http_url(value)
    if value and (urlsplit(value).scheme != 'https' or not urlsplit(value).path.lower().endswith('.mp4')):
        raise ApiError('宣传视频须填写 HTTPS 的 MP4 文件直链')
    return value


def image_url(value):
    value = text(value, '图片地址', 512)
    if not value or re.fullmatch(r'/(uploads|images)/[a-zA-Z0-9_.-]+', value):
        return value
    raise ApiError('请选择上传的图片或本站示例图片')


def sanitize_body(value):
    def allowed_attribute(tag, name, val):
        if tag == 'a' and name == 'href':
            try:
                return bool(http_url(val, True))
            except ApiError:
                return False
        if tag == 'img' and name == 'src':
            try:
                return bool(image_url(val))
            except ApiError:
                return False
        return (tag == 'img' and name == 'alt') or (tag == 'code' and name == 'class' and re.fullmatch(r'language-[a-z0-9+-]+', val))
    return bleach.clean(text(value, '正文', 200000),
                        tags=['p', 'br', 'h2', 'h3', 'h4', 'strong', 'em', 'u', 's', 'blockquote', 'ul', 'ol', 'li', 'pre', 'code', 'a', 'img', 'hr'],
                        attributes=allowed_attribute, protocols=['http', 'https'], strip=True)


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError('请求内容必须为 JSON 对象')
    return data


def pagination():
    try:
        page = max(1, min(100000, int(request.args.get('page', 1))))
    except (TypeError, ValueError):
        raise ApiError('分页参数不正确')
    return page, 12


def create_app(config=None):
    load_dotenv(ROOT / '.env')
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), DATABASE_URL=os.getenv('DATABASE_URL'),
                      DATA_DIR=os.getenv('DATA_DIR', str(ROOT / 'data')), PUBLIC_ORIGIN=os.getenv('PUBLIC_ORIGIN', ''),
                      SESSION_COOKIE_NAME='siriblog_session', SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(days=365),
                      MAX_CONTENT_LENGTH=6 * 1024 * 1024)
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('请先配置至少 32 位 SECRET_KEY，参考 .env.example')
    if not (app.config['DATABASE_URL'] or '').startswith('mysql+pymysql://'):
        raise RuntimeError('必须配置独立的 MySQL DATABASE_URL')
    app.config['SESSION_COOKIE_SECURE'] = app.config['PUBLIC_ORIGIN'].startswith('https://')
    if os.getenv('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    engine = create_engine(app.config['DATABASE_URL'], pool_pre_ping=True, pool_recycle=1800)
    app.extensions['db_engine'] = engine
    upload_dir = Path(app.config['DATA_DIR']).resolve() / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config['UPLOAD_DIR'] = upload_dir

    @app.before_request
    def setup():
        g.db = Session(engine, expire_on_commit=False)
        g.admin = False
        if request.path.startswith('/api/'):
            if 'visitor' not in session:
                session['visitor'] = secrets.token_hex(24)
                session.permanent = True
            g.visitor = digest(session['visitor'])
            token = session.get('auth')
            if token:
                row = g.db.get(AuthSession, digest(token))
                g.admin = bool(row and row.expires_at > now())
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                origins = {app.config['PUBLIC_ORIGIN']} if app.config['PUBLIC_ORIGIN'] else {'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000'}
                if request.headers.get('X-Blog-Request') != '1' or request.headers.get('Sec-Fetch-Site') == 'cross-site' or (request.headers.get('Origin') and request.headers['Origin'] not in origins):
                    raise ApiError('请求来源验证失败，请从本站页面重新操作', 403)

    @app.teardown_request
    def cleanup(_):
        if hasattr(g, 'db'):
            g.db.close()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        else:
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' https:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error='文件过大，请上传不超过 5 MB 的图片' if error.code == 413 else '请求无效或地址不存在'), error.code

    @app.errorhandler(IntegrityError)
    def conflict(_):
        g.db.rollback()
        return jsonify(error='记录已存在或关联数据发生变化，请刷新后重试'), 409

    @app.errorhandler(OperationalError)
    def unavailable(error):
        app.logger.error('Database unavailable: %s', type(error).__name__)
        return jsonify(error='数据库暂时不可用，请稍后重试'), 503

    def admin_only(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            if not g.admin:
                raise ApiError('请先登录站长后台', 401)
            return handler(*args, **kwargs)
        return wrapped

    def published(content_id, lock=False):
        query = select(Content).where(Content.id == content_id, Content.status == 'published')
        if lock:
            query = query.with_for_update()
        item = g.db.scalar(query)
        if not item:
            raise ApiError('内容不存在或已下架', 404)
        return item

    def rate_limit(action, maximum, window=60):
        buckets = [f'{action}:ip:{digest(request.remote_addr or "unknown")}', f'{action}:visitor:{g.visitor}']
        g.db.execute(delete(RateEvent).where(RateEvent.created_at < now() - 3600))
        for bucket in buckets:
            count = g.db.scalar(select(func.count()).select_from(RateEvent).where(RateEvent.bucket == bucket, RateEvent.created_at > now() - window))
            if count >= maximum:
                raise ApiError('操作太频繁，请稍后再试；输入内容已保留', 429)
        for bucket in buckets:
            g.db.add(RateEvent(bucket=bucket))
        g.db.commit()

    def serialize(item):
        result = {column.name: getattr(item, column.name) for column in Content.__table__.columns}
        result['like_count'] = g.db.scalar(select(func.count()).select_from(Like).where(Like.content_id == item.id))
        result['liked'] = g.db.get(Like, (item.id, g.visitor)) is not None
        result['comment_count'] = g.db.scalar(select(func.count()).select_from(Comment).where(Comment.content_id == item.id, Comment.deleted.is_(False)))
        return result

    def content_list(admin=False):
        query = select(Content)
        if not admin:
            query = query.where(Content.status == 'published')
        elif request.args.get('status'):
            query = query.where(Content.status == request.args['status'])
        kind = request.args.get('type')
        if kind:
            query = query.where(Content.type.in_(['article', 'note']) if kind == 'knowledge' else Content.type == kind)
        for field in ('category',):
            if request.args.get(field):
                query = query.where(getattr(Content, field) == request.args[field])
        if request.args.get('tag'):
            query = query.where(func.JSON_CONTAINS(Content.tags, json.dumps(request.args['tag'], ensure_ascii=False)))
        q = request.args.get('q', '').strip()[:100]
        if q:
            query = query.where(or_(*[column.contains(q, autoescape=True) for column in [Content.title, Content.summary, Content.body]], func.JSON_SEARCH(Content.tags, 'one', q) != None))
        if request.args.get('featured') == '1':
            query = query.where(Content.featured.is_(True)).order_by(Content.featured_order.asc())
        query = query.order_by(Content.published_at.desc(), Content.created_at.desc(), Content.id.desc())
        page, limit = pagination()
        items = g.db.scalars(query.offset((page - 1) * limit).limit(limit + 1)).all()
        return jsonify(items=[serialize(item) for item in items[:limit]], hasMore=len(items) > limit)

    @app.get('/api/bootstrap')
    def bootstrap():
        settings = g.db.get(Setting, 1)
        taxonomies = g.db.scalars(select(Taxonomy).order_by(Taxonomy.name)).all()
        return jsonify(settings={**DEFAULT_SETTINGS, **(settings.value if settings else {})},
                       taxonomies=[{'id': t.id, 'kind': t.kind, 'name': t.name} for t in taxonomies], isAdmin=g.admin)

    @app.get('/api/contents')
    def contents():
        return content_list()

    @app.get('/api/contents/<content_id>')
    def content_detail(content_id):
        return jsonify(serialize(published(content_id)))

    @app.put('/api/contents/<content_id>/like')
    def like(content_id):
        data = payload()
        if not isinstance(data.get('liked'), bool):
            raise ApiError('点赞状态必须为布尔值')
        rate_limit('like', 80)
        item = published(content_id, lock=True)
        existing = g.db.get(Like, (content_id, g.visitor))
        if data['liked'] and not existing:
            g.db.add(Like(content_id=content_id, visitor=g.visitor))
        elif not data['liked'] and existing:
            g.db.delete(existing)
        g.db.commit()
        return jsonify(serialize(item))

    def comment_json(item):
        quoted = g.db.get(Comment, item.reply_to) if item.reply_to else None
        return {'id': item.id, 'content_id': item.content_id, 'root_id': item.root_id, 'reply_to': item.reply_to,
                'nickname': '已删除' if item.deleted else item.nickname,
                'body': '该评论已删除' if item.deleted else item.body,
                'is_admin': item.is_admin and not item.deleted, 'deleted': item.deleted, 'created_at': item.created_at,
                'quote': {'nickname': '已删除' if quoted.deleted else quoted.nickname, 'body': '该评论已删除' if quoted.deleted else quoted.body[:200]} if quoted else None}

    @app.get('/api/comments')
    def comments():
        content_id = request.args.get('contentId') or None
        if content_id:
            published(content_id)
        page, limit = pagination()
        # A deleted root remains visible only while a non-deleted reply exists.
        roots_with_replies = select(Comment.root_id).where(Comment.deleted.is_(False), Comment.root_id.is_not(None))
        query = select(Comment).where(Comment.content_id == content_id, Comment.root_id.is_(None), or_(Comment.deleted.is_(False), Comment.id.in_(roots_with_replies))).order_by(Comment.created_at.desc(), Comment.id.desc())
        roots = g.db.scalars(query.offset((page - 1) * limit).limit(limit + 1)).all()
        result = []
        for item in roots[:limit]:
            data = comment_json(item)
            data['replies'] = [comment_json(reply) for reply in g.db.scalars(select(Comment).where(Comment.root_id == item.id, Comment.deleted.is_(False)).order_by(Comment.created_at, Comment.id))]
            result.append(data)
        return jsonify(items=result, hasMore=len(roots) > limit)

    @app.post('/api/comments')
    def add_comment():
        data = payload()
        nickname = text(data.get('nickname', ''), '昵称', 40, True)
        body = text(data.get('body', ''), '评论', 2000, True)
        content_id = data.get('contentId') or None
        rate_limit('comment', 8 if not g.admin else 30)
        if content_id:
            published(content_id, lock=True)
        reply_to, root_id = data.get('replyTo'), None
        if reply_to is not None:
            if type(reply_to) is not int:
                raise ApiError('回复对象无效')
            target = g.db.scalar(select(Comment).where(Comment.id == reply_to).with_for_update())
            if not target or target.content_id != content_id:
                raise ApiError('回复对象不存在或不属于当前内容')
            root_id = target.root_id or target.id
        duplicate = g.db.scalar(select(Comment.id).where(Comment.visitor == g.visitor, Comment.content_id == content_id, Comment.body == body, Comment.created_at > now() - 120, Comment.deleted.is_(False)))
        if duplicate:
            raise ApiError('这条内容刚刚已提交，请勿重复发送', 409)
        item = Comment(content_id=content_id, nickname=nickname, body=body, visitor=g.visitor, is_admin=g.admin, reply_to=reply_to, root_id=root_id)
        g.db.add(item)
        g.db.commit()
        return jsonify(comment_json(item)), 201

    @app.post('/api/auth/login')
    def login():
        rate_limit('login', 10, 900)
        data = payload()
        username = text(data.get('username', ''), '用户名', 80, True)
        password = text(data.get('password', ''), '密码', 256, True)
        admin = g.db.get(Admin, 1)
        if not admin or not check_password_hash(admin.password_hash, password) or admin.username != username:
            raise ApiError('用户名或密码不正确', 401)
        if session.get('auth'):
            g.db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(session['auth'])))
        token = secrets.token_urlsafe(32)
        g.db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
        g.db.add(AuthSession(token_hash=digest(token), expires_at=now() + 8 * 3600))
        g.db.commit()
        session['auth'] = token
        return jsonify(ok=True)

    @app.post('/api/auth/logout')
    def logout():
        token = session.pop('auth', None)
        if token:
            g.db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(token)))
            g.db.commit()
        return jsonify(ok=True)

    @app.get('/api/admin/contents')
    @admin_only
    def admin_contents():
        return content_list(admin=True)

    @app.get('/api/admin/contents/<content_id>')
    @admin_only
    def admin_content(content_id):
        item = g.db.get(Content, content_id)
        if not item:
            raise ApiError('内容不存在', 404)
        return jsonify(serialize(item))

    def save_content(item, data):
        kind, status = data.get('type'), data.get('status', 'draft')
        if kind not in TYPES or status not in ('draft', 'published', 'archived'):
            raise ApiError('内容类型或状态无效')
        item.type, item.status = kind, status
        for field, label, maximum in [('title', '标题', 160), ('summary', '摘要或推荐理由', 1000), ('category', '分类', 60), ('device', '设备支持', 120), ('instructions', '操作说明', 5000)]:
            setattr(item, field, text(data.get(field, ''), label, maximum, field == 'title'))
        item.body = sanitize_body(data.get('body', ''))
        item.cover = image_url(data.get('cover', ''))
        item.url = http_url(data.get('url', ''), status == 'published' and kind in ('game', 'tool'))
        item.video_url = mp4_url(data.get('video_url', '')) if kind == 'game' else ''
        show_published_at = data.get('show_published_at', True)
        if type(show_published_at) is not bool:
            raise ApiError('发布时间展示设置无效')
        item.show_published_at = show_published_at
        tags, screenshots = data.get('tags', []), data.get('screenshots', [])
        if not isinstance(tags, list) or len(tags) > 12 or not isinstance(screenshots, list) or len(screenshots) > 10:
            raise ApiError('标签最多 12 个，截图最多 10 张')
        item.tags = list(dict.fromkeys(text(tag, '标签', 60, True) for tag in tags))
        item.screenshots = [image_url(url) for url in screenshots if url]
        available = {(t.kind, t.name) for t in g.db.scalars(select(Taxonomy))}
        if item.category and ('category', item.category) not in available:
            raise ApiError('请先在分类标签中建立该分类')
        if any(('tag', tag) not in available for tag in item.tags):
            raise ApiError('请先在分类标签中建立所选标签')
        if type(data.get('featured', False)) is not bool or type(data.get('featured_order', 0)) is not int:
            raise ApiError('精选设置格式无效')
        item.featured = data.get('featured', False)
        item.featured_order = max(-10000, min(10000, data.get('featured_order', 0)))
        if status == 'published':
            if not item.published_at:
                item.published_at = now()
        item.updated_at = now()

    @app.post('/api/admin/contents')
    @admin_only
    def create_content():
        item = Content()
        save_content(item, payload())
        g.db.add(item)
        g.db.commit()
        return jsonify(serialize(item)), 201

    @app.put('/api/admin/contents/<content_id>')
    @admin_only
    def update_content(content_id):
        item = g.db.scalar(select(Content).where(Content.id == content_id).with_for_update())
        if not item:
            raise ApiError('内容不存在', 404)
        save_content(item, payload())
        g.db.commit()
        return jsonify(serialize(item))

    @app.get('/api/admin/comments')
    @admin_only
    def admin_comments():
        page, limit = pagination()
        items = g.db.scalars(select(Comment).where(Comment.deleted.is_(False)).order_by(Comment.id.desc()).offset((page - 1) * limit).limit(limit + 1)).all()
        return jsonify(items=[comment_json(item) for item in items[:limit]], hasMore=len(items) > limit)

    @app.post('/api/admin/comments/delete')
    @admin_only
    def delete_comments():
        ids = payload().get('ids')
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(type(i) is not int for i in ids):
            raise ApiError('请选择 1 至 100 条评论')
        for item in g.db.scalars(select(Comment).where(Comment.id.in_(ids)).with_for_update()):
            item.deleted, item.nickname, item.body, item.is_admin = True, '', '', False
        g.db.commit()
        return jsonify(ok=True)

    @app.get('/api/admin/taxonomies')
    @admin_only
    def taxonomies():
        return jsonify(items=[{'id': t.id, 'kind': t.kind, 'name': t.name} for t in g.db.scalars(select(Taxonomy).order_by(Taxonomy.kind, Taxonomy.name))])

    @app.post('/api/admin/taxonomies')
    @admin_only
    def create_taxonomy():
        data = payload()
        if data.get('kind') not in ('category', 'tag'):
            raise ApiError('分类类型无效')
        item = Taxonomy(kind=data['kind'], name=text(data.get('name', ''), '名称', 60, True))
        g.db.add(item)
        g.db.commit()
        return jsonify(id=item.id), 201

    @app.route('/api/admin/taxonomies/<int:item_id>', methods=['PUT', 'DELETE'])
    @admin_only
    def edit_taxonomy(item_id):
        item = g.db.get(Taxonomy, item_id)
        if not item:
            raise ApiError('分类或标签不存在', 404)
        new_name = text(payload().get('name', ''), '名称', 60, True) if request.method == 'PUT' else None
        related = list(g.db.scalars(select(Content).where(Content.category == item.name if item.kind == 'category' else func.JSON_CONTAINS(Content.tags, json.dumps(item.name, ensure_ascii=False))).with_for_update()))
        if request.method == 'DELETE' and related:
            raise ApiError('该分类或标签仍被内容使用，请先调整相关内容')
        for content in related:
            if item.kind == 'category':
                content.category = new_name
            else:
                content.tags = [new_name if tag == item.name else tag for tag in content.tags]
        if new_name:
            item.name = new_name
        else:
            g.db.delete(item)
        g.db.commit()
        return jsonify(ok=True)

    @app.put('/api/admin/settings')
    @admin_only
    def settings():
        data = payload()
        current = g.db.get(Setting, 1)
        previous = {**DEFAULT_SETTINGS, **(current.value if current else {})}
        links = data.get('links', previous['links'])
        if not isinstance(links, list) or len(links) > 6 or any(not isinstance(link, dict) for link in links):
            raise ApiError('最多填写 6 个联系外链')
        carousel = data.get('carousel', previous['carousel'])
        if not isinstance(carousel, list) or len(carousel) > 6 or any(not isinstance(slide, dict) for slide in carousel):
            raise ApiError('轮播图最多 6 张')
        slides = []
        for slide in carousel:
            action = slide.get('action', 'preview')
            if action not in ('link', 'preview_link', 'preview'):
                raise ApiError('轮播图点击方式无效')
            slides.append({'image': image_url(slide.get('image', '')),
                           'title': text(slide.get('title', ''), '轮播图标题', 80),
                           'action': action,
                           'url': http_url(slide.get('url', ''), action != 'preview') if action != 'preview' else ''})
            if not slides[-1]['image']:
                raise ApiError('请为轮播图选择图片')
        intro_first = data.get('home_intro_first', previous['home_intro_first'])
        if type(intro_first) is not bool:
            raise ApiError('手机首页顺序设置无效')
        value = {'name': text(data.get('name', previous['name']), '网站名称', 60, True), 'tagline': text(data.get('tagline', previous['tagline']), '短介绍', 120), 'bio': text(data.get('bio', previous['bio']), '个人简介', 1000), 'avatar': image_url(data.get('avatar', previous['avatar'])), 'placeholder': bool(data.get('placeholder', previous['placeholder'])),
                 'hero_title': text(data.get('hero_title', previous['hero_title']), '首页主标题', 120),
                 'hero_kicker': text(data.get('hero_kicker', previous['hero_kicker']), '首页眉题', 80),
                 'hero_note': text(data.get('hero_note', previous['hero_note']), '首页小字', 120),
                 'home_intro_first': intro_first, 'carousel': slides,
                 'links': [{'label': text(link.get('label', ''), '链接名称', 40, True), 'url': http_url(link.get('url', ''), True)} for link in links]}
        item = current
        if item:
            item.value = value
        else:
            g.db.add(Setting(id=1, value=value))
        g.db.commit()
        return jsonify(value)

    @app.get('/api/admin/media')
    @admin_only
    def media():
        return jsonify(items=[{'id': m.id, 'name': m.name, 'url': m.url, 'size': m.size} for m in g.db.scalars(select(Media).order_by(Media.created_at.desc()))])

    @app.post('/api/admin/media')
    @admin_only
    def upload():
        file = request.files.get('file')
        if not file:
            raise ApiError('请选择图片')
        raw = file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise ApiError('图片不能超过 5 MB')
        try:
            with Image.open(io.BytesIO(raw)) as original:
                if original.format not in ('JPEG', 'PNG', 'WEBP') or original.width * original.height > 25000000:
                    raise ApiError('仅支持 2500 万像素以内的 JPEG、PNG、WebP 图片')
                original.load()
                image = ImageOps.exif_transpose(original).convert('RGBA' if 'A' in original.getbands() else 'RGB')
                image.thumbnail((1920, 1920))
                output = io.BytesIO()
                image.save(output, format='WEBP', quality=85)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ApiError('文件不是有效图片')
        media_id = str(uuid.uuid4())
        filename = media_id + '.webp'
        (upload_dir / filename).write_bytes(output.getvalue())
        item = Media(id=media_id, name=(file.filename or '图片')[:160], url='/uploads/' + filename, size=output.tell())
        g.db.add(item)
        try:
            g.db.commit()
        except Exception:
            (upload_dir / filename).unlink(missing_ok=True)
            raise
        return jsonify(id=item.id, url=item.url, name=item.name), 201

    @app.delete('/api/admin/media/<media_id>')
    @admin_only
    def delete_media(media_id):
        item = g.db.get(Media, media_id)
        if not item:
            raise ApiError('图片不存在', 404)
        referenced = any(item.url in json.dumps(serialize(content), ensure_ascii=False) for content in g.db.scalars(select(Content)))
        setting = g.db.get(Setting, 1)
        if referenced or (setting and item.url in json.dumps(setting.value)):
            raise ApiError('图片仍被内容或站点设置引用，不能删除')
        (upload_dir / Path(item.url).name).unlink(missing_ok=True)
        g.db.delete(item)
        g.db.commit()
        return jsonify(ok=True)

    @app.get('/uploads/<filename>')
    def uploaded(filename):
        return send_from_directory(upload_dir, filename, max_age=31536000, mimetype='image/webp')

    @app.get('/', defaults={'path': ''})
    @app.get('/<path:path>')
    def frontend(path):
        dist = ROOT / 'dist'
        if path.startswith('api/'):
            raise ApiError('接口不存在', 404)
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        if not (dist / 'index.html').exists():
            return jsonify(error='请先运行 npm run build，或使用开发前端 http://127.0.0.1:5173'), 503
        return send_from_directory(dist, 'index.html')

    return app
