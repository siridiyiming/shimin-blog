# 一码当先小柿民博客

作者：**一码当先小柿民**。一个手机优先的个人博客，分享游戏、知识笔记和实用工具，支持读者留言、评论回复与点赞。

技术栈：Vue 3 + Vite + Python / Flask + SQLAlchemy + MySQL 8。

本仓库提供可自行部署的源码和占位示例，不包含作者的账号密码、文章数据库、访客记录、上传图片、服务器配置或备份。示例游戏地址使用 `example.com`，需要替换成自己的链接。

## 获取源码

```bash
git clone https://github.com/siridiyiming/shimin-blog.git
cd shimin-blog
```

## 本地启动（Windows / PowerShell）

准备 Python 3.12、Node.js 22+ 和 MySQL 8，并让 `mysqld`、`mysql`、`mysqldump` 可在终端调用。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci
.\.venv\Scripts\python scripts/local_mysql.py
.\.venv\Scripts\python -m backend.manage init-db
.\.venv\Scripts\python -m backend.manage admin --username admin
# 可选：添加明确标注的占位内容；不生成评论或点赞
.\.venv\Scripts\python -m backend.manage seed
```

本地 MySQL 脚本使用独立数据目录，监听 `127.0.0.1:3307`，创建 `siriblog`、`siriblog_test` 和 `siriblog_restore_test`。端口占用或已有 `.env` 时会停止，请勿覆盖其他项目的配置。密钥随机生成并保存在本地，不提供通用管理员密码。

打开两个终端，分别启动后端和前端：

```powershell
.\.venv\Scripts\python -m backend.run
```

```powershell
npm run dev
```

访问 `http://127.0.0.1:5173`。站长后台为 `/admin`，使用初始化时设置的账号密码。公开页面没有后台链接，后台操作由服务端身份验证保护。

## 使用已有 MySQL / Linux / macOS

创建博客专用数据库和用户，将 `.env.example` 复制为 `.env`，填写自己的数据库地址、密码和随机密钥；`SECRET_KEY` 至少 32 位。不要把示例占位值用于正式环境。可用 `python -c "import secrets; print(secrets.token_hex(32))"` 在自己的终端生成密钥。

在 Linux / macOS 中通过 `python3 -m venv .venv` 创建环境，使用 `.venv/bin/python` 代替上述 Windows Python 路径。手动配置 MySQL 时跳过 `scripts/local_mysql.py`，依次执行 `init-db`、`admin` 以及可选的 `seed`。

## 功能与配置

- 游戏、长文章、短知识卡片与工具推荐，支持草稿、发布、下架和首页精选。
- 富文本编辑、分类标签、内容搜索与图片管理。
- 可配置首页开场、轮播、作者介绍顺序和单条内容日期展示。
- 游戏支持 HTTPS MP4 视频直链。
- 匿名留言、平铺回复、站长删除、点赞去重与基础限频。
- 内容、设置和互动记录通过 MySQL 持久化。

详见 [站点配置指南](docs/configuration.md) 和 [架构与接口](docs/architecture.md)。

## 检查和构建

```powershell
npm run build
.\.venv\Scripts\python -m pytest -q
```

API 测试需要专用 `TEST_DATABASE_URL`，数据库名称必须以 `_test` 结尾。测试会重建该测试库中的表，不能配置成正式数据库。未提供测试库时测试会跳过，跳过不代表验证通过。

运行 `npm run build` 后，后端可以提供 `dist` 中的前端文件。公网部署需要另行配置 HTTPS、`PUBLIC_ORIGIN`、独立数据库及反向代理；本仓库没有附带任何现有服务器的配置，也不宣称已完成公网部署验收。GitHub Pages 无法直接运行此 Python + MySQL 后端。

## 备份与恢复

```powershell
.\.venv\Scripts\python scripts/backup.py
.\.venv\Scripts\python scripts/restore.py backups/<备份文件名>.zip
```

默认恢复到独立 `_restore_test` 数据库。正式库恢复须停止服务、确认备份，并使用 `--target main` 按提示手动确认；当前脚本要求正式库名为 `siriblog`。备份可能包含文章、访客信息和上传图片，不要公开。

## 后续改名

- 网站显示名称：登录 `/admin`，在“站点设置 → 网站名称”修改并保存。
- 新安装的默认名称：修改 `backend/schema.py` 的 `NEW_SITE_NAME`，同时更新 `src/App.vue` 的回退名称和 `index.html` 的初始标题；已有站点仍通过后台改名。
- GitHub 仓库名：仓库 `Settings → General → Repository name → Rename`。本地随后执行 `git remote set-url origin https://github.com/你的用户名/新仓库名.git`。

## 隐私与贡献

`.env`、`data/`、`uploads/`、`backups/`、依赖与构建产物不应提交。提交前使用 `git diff --cached` 检查内容；`.gitignore` 不能移除已经跟踪的敏感文件。测试中的固定密码与密钥只供隔离测试使用。

欢迎通过 Issue 反馈问题，通过 Fork 和 Pull Request 贡献修改。不要在 Issue 或提交中附上真实密钥、数据库备份或访客数据。

## 许可证

项目源码采用 [MIT License](LICENSE)。第三方依赖遵循各自许可证；本站名称和作者署名为“一码当先小柿民”。
