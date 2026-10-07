"""Create a checksummed database-and-media archive."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = {**dotenv_values(ROOT / '.env'), **os.environ}
    url = make_url(env.get('DATABASE_URL', ''))
    if url.drivername != 'mysql+pymysql' or not url.host or not url.database:
        raise SystemExit('DATABASE_URL 必须指向 MySQL 中的博客专用数据库。')
    dump = shutil.which('mysqldump')
    if not dump:
        raise SystemExit('未找到 mysqldump。请安装 MySQL Client tools。')
    password = url.password or ''
    media_dir = (ROOT / env.get('DATA_DIR', 'data') / 'uploads').resolve()
    destination = ROOT / 'backups'
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = destination / f'siriblog-backup-{stamp}.zip'
    temporary = archive.with_suffix('.zip.partial')
    process_env = dict(os.environ, MYSQL_PWD=password)
    args = [dump, '--no-defaults', '--protocol=TCP', f'--host={url.host}', f'--port={url.port or 3306}', f'--user={url.username}', '--single-transaction', '--quick', '--hex-blob', '--no-tablespaces', '--column-statistics=0', '--set-gtid-purged=OFF', url.database]
    try:
        with tempfile.TemporaryFile() as errors, ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
            proc = subprocess.Popen(args, cwd=ROOT, env=process_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors)
            database_hash = hashlib.sha256()
            total = 0
            with output.open('database.sql', 'w', force_zip64=True) as sql:
                while block := proc.stdout.read(1024 * 1024):
                    sql.write(block)
                    database_hash.update(block)
                    total += len(block)
            code = proc.wait()
            if code:
                errors.seek(0)
                detail = errors.read().decode('utf-8', 'replace')[-1800:]
                raise SystemExit('MySQL 备份失败：' + detail)
            if not total:
                raise SystemExit('MySQL 备份内容为空。')
            media_records = []
            if media_dir.exists():
                for path in sorted(media_dir.rglob('*')):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(media_dir).as_posix()
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    output.write(path, 'uploads/' + relative)
                    media_records.append({'name': relative, 'sha256': digest})
            manifest = {'format': 1, 'created_utc': stamp, 'database': url.database,
                        'database_sha256': database_hash.hexdigest(), 'database_bytes': total,
                        'media_files': media_records, 'media_count': len(media_records)}
            output.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
        temporary.replace(archive)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f'备份已创建：{archive.relative_to(ROOT)}（数据库 {total:,} bytes，图片 {len(media_records)} 张）。')


if __name__ == '__main__':
    main()
