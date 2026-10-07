import argparse
import getpass
import secrets
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash
from .app import create_app, DEFAULT_SETTINGS
from .models import Admin, AuthSession, Base, Content, Setting, Taxonomy, now
from .schema import initialize_schema


def seed(db):
    if db.scalar(select(Content.id).limit(1)):
        raise SystemExit('已有内容，不重复添加占位示例。')
    for kind, names in [('category', ['独立游戏', '开发笔记', '灵感碎片', '效率工具']), ('tag', ['占位示例', '网页游戏', '前端', '学习', '效率'])]:
        for name in names:
            if not db.scalar(select(Taxonomy).where(Taxonomy.kind == kind, Taxonomy.name == name)):
                db.add(Taxonomy(kind=kind, name=name))
    records = [
        dict(type='game', title='星际漫游', summary='在星球之间寻找下一段旅程。轻量、即开即玩的游戏展示占位示例。', category='独立游戏', tags=['占位示例', '网页游戏'], cover='/images/orbit.svg', screenshots=['/images/orbit.svg'], device='手机触控 / 电脑键鼠', instructions='占位示例：点击或轻触屏幕进行探索，实际操作说明待站长替换。', url='https://example.com/game', body='<h2>关于这个游戏</h2><p>这是游戏介绍的占位示例，不代表已经发布的实际作品。站长可在后台替换封面、截图、介绍和链接。</p>'),
        dict(type='game', title='方块之间', summary='留一点时间给简单的快乐。一个益智游戏介绍的占位示例。', category='独立游戏', tags=['占位示例'], cover='/images/blocks.svg', screenshots=['/images/blocks.svg'], device='手机触控 / 电脑键鼠', instructions='占位操作说明：选择方块完成排列。', url='https://example.com/game', body='<p>此处展示游戏介绍的排版样式，请通过后台替换为真实作品。</p>'),
        dict(type='article', title='从一个想法，到一个可用的小作品', summary='把想法拆成可以完成的小步骤，让每一次动手都有一点收获。', category='开发笔记', tags=['占位示例', '学习'], cover='/images/notebook.svg', body='<h2>从一个小问题开始</h2><p>本文是长文章的占位示例，用来展示阅读排版、目录与代码块。请在后台替换为真实文章。</p><h2>先完成一条完整路径</h2><p>把最重要的使用过程写下来，再逐步完善细节。一个清楚的目标，会让每次修改更有方向。</p><pre><code class="language-python">def create_something():\n    return "从今天的一小步开始"</code></pre><h2>记录与分享</h2><p>留下过程、问题和解法，让未来的自己也能从中受益。</p>'),
        dict(type='note', title='让灵感有一个落脚的地方', summary='不必等到想法完整，先把它记下来。', category='灵感碎片', tags=['占位示例'], body='<p>短知识卡片占位示例：记录一个技巧、一点发现，或者一个还没有完成的想法。点击展开即可阅读与交流。</p>'),
        dict(type='tool', title='Vue.js', summary='构建交互界面的渐进式框架。这里是工具推荐卡片的占位示例，可在后台修改。', category='效率工具', tags=['占位示例', '前端'], url='https://cn.vuejs.org/', body='', cover=''),
        dict(type='tool', title='Python 文档', summary='把官方文档放在手边，遇到问题时多一个可靠的查阅入口。占位推荐示例。', category='效率工具', tags=['占位示例', '学习'], url='https://docs.python.org/zh-cn/3/', body='', cover='')
    ]
    for index, item in enumerate(records):
        db.add(Content(**item, status='published', featured=True, featured_order=index, published_at=now() - index * 3600))
    if not db.get(Setting, 1):
        db.add(Setting(id=1, value=DEFAULT_SETTINGS))
    db.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-db', 'admin', 'seed'])
    parser.add_argument('--username', default='admin')
    args = parser.parse_args()
    app = create_app()
    engine = app.extensions['db_engine']
    if args.command == 'init-db':
        initialize_schema(engine)
        print('MySQL schema initialized.')
        return
    with Session(engine) as db:
        if args.command == 'admin':
            password = getpass.getpass('设置站长密码（至少 12 位，不回显）: ')
            if len(password) < 12 or len(password) > 256 or not args.username.strip() or len(args.username) > 80:
                raise SystemExit('用户名或密码长度不符合要求。')
            if password != getpass.getpass('再次输入密码: '):
                raise SystemExit('两次密码不一致。')
            admin = db.get(Admin, 1)
            if admin:
                admin.username, admin.password_hash = args.username, generate_password_hash(password, method='scrypt')
            else:
                db.add(Admin(id=1, username=args.username, password_hash=generate_password_hash(password, method='scrypt')))
            db.execute(delete(AuthSession))
            db.commit()
            print('站长账号已保存，旧会话已失效。')
        else:
            seed(db)
            print('已保存带有占位标记的示例内容；未生成评论或点赞。')


if __name__ == '__main__':
    main()
