"""Start a repository-local MySQL instance without touching installed services."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    binary = shutil.which('mysqld')
    if not binary:
        raise SystemExit('未找到 mysqld。请安装 MySQL 8，或配置 .env 连接独立的博客数据库。')
    directory = ROOT / 'data' / 'local-mysql'
    directory.mkdir(parents=True, exist_ok=True)
    state_file = directory / 'local-credentials.json'
    if not state_file.exists() and (ROOT / '.env').exists():
        raise SystemExit('已有 .env，请保留并检查配置；本脚本不覆盖现有连接。')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    if not state_file.exists():
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', 3307)) == 0:
                raise SystemExit('3307 端口已占用，不修改现有实例。')
        values = {'root': secrets.token_hex(24), 'password': secrets.token_hex(24)}
        state_file.write_text(json.dumps(values), encoding='utf-8')
    values = json.loads(state_file.read_text(encoding='utf-8'))
    datadir = directory / 'db'
    if not (datadir / 'mysql').exists():
        datadir.mkdir(exist_ok=True)
        with (directory / 'initialize.log').open('wb') as log:
            subprocess.run([binary, '--no-defaults', '--initialize-insecure', f'--basedir={Path(binary).parent.parent}', f'--datadir={datadir}'], check=True, stdout=log, stderr=log, creationflags=flags)
    with socket.socket() as sock:
        running = sock.connect_ex(('127.0.0.1', 3307)) == 0
    if not running:
        init_file = datadir / 'bootstrap.sql'
        init_file.write_text(f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{values['root']}';\nCREATE DATABASE IF NOT EXISTS siriblog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nCREATE DATABASE IF NOT EXISTS siriblog_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nCREATE DATABASE IF NOT EXISTS siriblog_restore_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\nCREATE USER IF NOT EXISTS 'blog_user'@'127.0.0.1' IDENTIFIED BY '{values['password']}';\nGRANT ALL ON siriblog.* TO 'blog_user'@'127.0.0.1';\nGRANT ALL ON siriblog_test.* TO 'blog_user'@'127.0.0.1';\nGRANT ALL ON siriblog_restore_test.* TO 'blog_user'@'127.0.0.1';\n", encoding='utf-8')
        config = directory / 'my.ini'
        config.write_text('[mysqld]\ndatadir=./db\nport=3307\nbind-address=127.0.0.1\nmysqlx=0\nlog-error=./server.log\npid-file=./server.pid\ninit-file=./bootstrap.sql\ncharacter-set-server=utf8mb4\n', encoding='utf-8')
        subprocess.Popen([binary, '--defaults-file=./my.ini'], cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    import pymysql
    for _ in range(40):
        try:
            connection = pymysql.connect(host='127.0.0.1', port=3307, user='blog_user', password=values['password'], database='siriblog')
            connection.close()
            break
        except pymysql.Error:
            time.sleep(.5)
    else:
        raise SystemExit('本地 MySQL 未就绪，请检查 data/local-mysql/server.log。')
    init_file = datadir / 'bootstrap.sql'
    init_file.unlink(missing_ok=True)
    if not (ROOT / '.env').exists():
        (ROOT / '.env').write_text(f"HOST=127.0.0.1\nPORT=8000\nDATA_DIR=./data\nDATABASE_URL=mysql+pymysql://blog_user:{values['password']}@127.0.0.1:3307/siriblog?charset=utf8mb4\nTEST_DATABASE_URL=mysql+pymysql://blog_user:{values['password']}@127.0.0.1:3307/siriblog_test?charset=utf8mb4\nTEST_RESTORE_DATABASE_URL=mysql+pymysql://blog_user:{values['password']}@127.0.0.1:3307/siriblog_restore_test?charset=utf8mb4\nTEST_RESTORE_DATA_DIR=./data/restore-test\nSECRET_KEY={secrets.token_hex(32)}\n", encoding='utf-8')
    # The isolated restore-check database is never used by the public app or ordinary tests.
    root_connection = pymysql.connect(host='127.0.0.1', port=3307, user='root', password=values['root'], autocommit=True)
    try:
        with root_connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS siriblog_restore_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("GRANT ALL ON siriblog_restore_test.* TO 'blog_user'@'127.0.0.1'")
    finally:
        root_connection.close()
    env_path = ROOT / '.env'
    current_env = env_path.read_text(encoding='utf-8')
    if 'TEST_RESTORE_DATABASE_URL=' not in current_env:
        with env_path.open('a', encoding='utf-8') as stream:
            stream.write('TEST_RESTORE_DATABASE_URL=mysql+pymysql://blog_user:' + values['password'] + '@127.0.0.1:3307/siriblog_restore_test?charset=utf8mb4\nTEST_RESTORE_DATA_DIR=./data/restore-test\n')
    print('MySQL ready: 127.0.0.1:3307; dedicated blog, test and restore-check databases. Credentials saved locally, not printed.')


if __name__ == '__main__':
    main()
