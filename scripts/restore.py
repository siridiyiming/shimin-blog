"""Verify and restore a backup. Default target is an isolated *_restore_test database."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import BadZipFile, ZipFile

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_ARCHIVE = 2 * 1024 * 1024 * 1024


def checked_member(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise SystemExit('备份路径中包含非法文件名。')
    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='验证并还原博客数据库与图片备份')
    parser.add_argument('archive', type=Path)
    parser.add_argument('--target', default='test', choices=['test', 'main'], help='test 使用 TEST_RESTORE_DATABASE_URL；main 必须手动输入 BLOG-RESTORE')
    args = parser.parse_args()
    path = args.archive.resolve()
    backup_root = (ROOT / 'backups').resolve()
    if path.parent != backup_root or not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        raise SystemExit('请选择 backups 文件夹中的 ZIP 备份（最大 2 GB）。')
    try:
        archive = ZipFile(path)
        names = archive.namelist()
        if len(names) != len(set(names)) or sum(item.file_size for item in archive.infolist()) > MAX_ARCHIVE:
            raise SystemExit('备份包含重复成员或超过 2 GB；停止还原。')
        if 'manifest.json' not in names or 'database.sql' not in names:
            raise SystemExit('备份中缺少清单或数据库快照。')
        manifest_info = archive.getinfo('manifest.json')
        if manifest_info.file_size > 1024 * 1024:
            raise SystemExit('备份清单异常地大，停止还原。')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or not isinstance(manifest.get('media_files'), list) or len(names) != manifest.get('media_count', 0) + 2:
            raise SystemExit('备份清单不完整，停止还原。')
        expected_media = {checked_member(record['name']).as_posix(): record['sha256'] for record in manifest['media_files']}
        if len(expected_media) != manifest.get('media_count') or set(names) != {'manifest.json', 'database.sql'} | {'uploads/' + name for name in expected_media}:
            raise SystemExit('备份图片清单与文件列表不一致。')
        for name in ['database.sql', *['uploads/' + media for media in expected_media]]:
            if name == 'database.sql' and archive.getinfo(name).file_size != manifest.get('database_bytes'):
                raise SystemExit('数据库快照长度校验失败，停止还原。')
            digest = hashlib.sha256()
            with archive.open(name) as member:
                while block := member.read(1024 * 1024):
                    digest.update(block)
            expected = manifest['database_sha256'] if name == 'database.sql' else expected_media[name.removeprefix('uploads/')]
            if digest.hexdigest() != expected:
                raise SystemExit(('数据库快照' if name == 'database.sql' else '图片 ' + name) + ' 校验失败，停止还原。')

        env = {**dotenv_values(ROOT / '.env'), **os.environ}
        key = 'TEST_RESTORE_DATABASE_URL' if args.target == 'test' else 'DATABASE_URL'
        url = make_url(env.get(key, ''))
        if url.drivername != 'mysql+pymysql' or not url.database:
            raise SystemExit(f'请先配置独立的 {key} MySQL 地址。')
        if args.target == 'test' and not url.database.endswith('_restore_test'):
            raise SystemExit('测试还原数据库名称必须以 _restore_test 结尾。')
        if args.target == 'main':
            if url.database != 'siriblog' or input('还原会覆盖博客内容。确认博客服务已停止，并输入 BLOG-RESTORE：') != 'BLOG-RESTORE':
                raise SystemExit('确认失败，数据库没有修改。')
        destination = (ROOT / env.get('TEST_RESTORE_DATA_DIR', 'data/restore-test') / 'uploads').resolve() if args.target == 'test' else (ROOT / env.get('DATA_DIR', 'data') / 'uploads').resolve()
        if not destination.is_relative_to(ROOT):
            raise SystemExit('图片还原目录必须位于项目目录中。')
        from shutil import which
        client = which('mysql')
        if not client:
            raise SystemExit('未找到 mysql 客户端，无法还原数据库。')
        temporary_dir = ROOT / '.cache'
        temporary_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=temporary_dir, suffix='.sql', delete=False) as snapshot:
            with archive.open('database.sql') as member:
                while block := member.read(1024 * 1024):
                    snapshot.write(block)
            snapshot_path = Path(snapshot.name)
        try:
            from sqlalchemy import create_engine
            from backend.models import Base
            engine = create_engine(url, pool_pre_ping=True)
            # Test restores are disposable and the public application uses another database.
            Base.metadata.drop_all(engine)
            engine.dispose()
            process_env = dict(os.environ, MYSQL_PWD=url.password or '')
            with snapshot_path.open('rb') as source, tempfile.TemporaryFile() as errors:
                process = subprocess.run([client, '--no-defaults', '--protocol=TCP', f'--host={url.host}', f'--port={url.port or 3306}', f'--user={url.username}', f'--database={url.database}', '--default-character-set=utf8mb4'], stdin=source, stdout=subprocess.DEVNULL, stderr=errors, env=process_env)
                if process.returncode:
                    errors.seek(0)
                    raise SystemExit('MySQL 还原失败：' + errors.read().decode('utf-8', 'replace')[-1800:])
            for name in expected_media:
                output = (destination / checked_member(name)).resolve()
                if not output.is_relative_to(destination):
                    raise SystemExit('备份中包含不安全的图片路径。')
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open('uploads/' + name) as member, output.open('wb') as restored:
                    shutil.copyfileobj(member, restored, length=1024 * 1024)
        finally:
            snapshot_path.unlink(missing_ok=True)
        print(f'备份校验和数据库还原已完成：{url.database}（{manifest["media_count"]} 张图片）。')
    except BadZipFile as exc:
        raise SystemExit('备份 ZIP 文件损坏，停止还原。') from exc
    finally:
        if 'archive' in locals():
            archive.close()


if __name__ == '__main__':
    main()
