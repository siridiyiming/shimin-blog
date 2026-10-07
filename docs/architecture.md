# 首版技术与接口约定

开源版使用 Vue 3、Python 和 MySQL；代码、配置示例与运行数据分离。

## 技术与目录

- Vue 3 + Vite：手机优先的读者界面与后台；Vue Router 保留筛选状态和浏览器历史。
- Python 3.12 + Flask + SQLAlchemy + MySQL 8.0 + PyMySQL：后端接口与关系型数据持久化。
- Tiptap for Vue：可视化正文编辑；后端用 Bleach 白名单过滤 HTML。
- Pillow：验证上传图片格式、大小和像素，并生成 WebP。
- `backend/`：Flask 接口与数据模型；`src/`：Vue 页面和样式；`scripts/`：本机数据库、管理员、占位内容。
- `data/`、`.env` 和 `backups/`（忽略提交）：本地 MySQL、上传图片、密钥和备份。
- `python scripts/backup.py` 生成带 SHA-256 清单的 MySQL 与上传图片 ZIP；`python scripts/restore.py backups/<备份名>.zip` 默认还原到独立 `_restore_test` 数据库。正式库还原须停服务并手动输入确认口令。

## 数据契约

内容类型 game/article/note/tool；状态 draft/published/archived。正文保存经过 Bleach 清理的 HTML；游戏另存截图、设备支持、操作说明及外链。

内容与首页配置：内容新增 `video_url`（可空，仅游戏接受 HTTPS MP4 直链）与 `show_published_at`（布尔，默认 true）；发布时间本身继续保存并用于排序，前端按开关决定是否显示。发布最低要求为标题，游戏和工具另需有效 HTTP/HTTPS 外链；分类、正文、简介及图片可空。`/api/bootstrap` 的 settings 增加 `hero_title`、`hero_kicker`、`hero_note`、`home_intro_first` 和 `carousel`。轮播项为 `{image,title,action,url}`，`action` 取 `link`、`preview_link` 或 `preview`；前两者需要有效跳转地址，图片必须是本站上传或示例图片。旧设置读取时合并默认值，后台保存保留未提交的新字段。已有 MySQL `contents` 表通过 `python -m backend.manage init-db` 幂等补列，执行前须备份。

分类和标签由站长维护。评论以 content_id 为空表示留言板，root_id 表示主评论，reply_to 表示回复对象；回复在主评论下平铺。删除保留墓碑并清除正文、昵称和站长标记。点赞以内容和匿名浏览器标识联合主键去重。

站长密码由 Werkzeug Scrypt 哈希；登录令牌只存 SHA-256 摘要；Cookie 使用 HttpOnly、SameSite=Lax，HTTPS 启用 Secure。写请求检查自定义同源请求头、Origin 和 Fetch Metadata；后台与上传须登录。留言按浏览器和 IP 限频，并拦截短时间重复提交。

## HTTP 契约

- GET /api/bootstrap：站点设置、公开内容使用的分类标签、当前登录身份。
- GET /api/contents：type、q、category、tag、featured、page；仅返回已发布内容，分页返回 items/hasMore。
- GET /api/contents/:id：公开详情；草稿和下架均 404。
- PUT /api/contents/:id/like：{ liked: boolean }，幂等设置并返回计数及当前状态。
- GET/POST /api/comments：contentId 为空为留言板；POST 带 nickname/body/replyTo。
- POST /api/auth/login、POST /api/auth/logout：单站长会话。
- /api/admin/contents：列表、创建、更新及私有预览；状态变更同更新接口。
- /api/admin/comments：列表和批量删除；回复走登录状态下的评论接口。
- /api/admin/taxonomies：分类标签管理；/api/admin/settings：站点设置。
- /api/admin/media：上传、列表与删除（仍被内容或站点引用时阻止删除）。
- 公开页面不展示后台入口；站长直接访问 `/admin` 登录，管理权限依靠服务器端身份验证，与入口地址是否被猜到无关。
- 失败统一 { error: 中文原因 }；未登录 401，无权限/跨站 403，未公开内容 404，验证 400，频率限制 429。

## 本地验证及上线边界

验证四类内容生命周期、搜索隔离、登录权限、评论删除/引用、点赞去重、重启持久化、图片校验、备份恢复，以及 360/390/430 和桌面布局。所有占位样例明确标识，不添加虚假评论或互动。部署到公网前，使用者需要自行核实域名、HTTPS、运行资源和备份恢复。

实现参考：[Vue 快速开始](https://vuejs.org/guide/quick-start.html)、[Flask SQLAlchemy](https://flask.palletsprojects.com/en/stable/patterns/sqlalchemy/)、[MySQL 8 初始化](https://dev.mysql.com/doc/refman/8.0/en/data-directory-initialization.html)。
