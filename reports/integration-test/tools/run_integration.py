"""結合試験の実行環境（使い捨て PostgreSQL 16）を準備して pytest を1回実行し、終了時にコンテナを停止・削除する。

python reports/integration-test/tools/run_integration.py [--junit PATH] [pytest の追加引数 ...]

- DB：postgres:16（compose.yaml と同じイメージ）を 127.0.0.1 のランダムポートだけに公開、データ領域は tmpfs。
  statement_timeout・lock_timeout・idle_in_transaction_session_timeout をサーバー設定で与える。
  接続タイムアウトは PGCONNECT_TIMEOUT（libpq）で与える。
- 認証情報は実行ごとに乱数で生成し、ファイル・リポジトリに保存しない（Steering 6.2）。
- pytest は .venv の固定版依存で `-c app/pytest.ini --rootdir=.` として実行する（JUnit classname=app.tests.integration.*）。
- プロセス全体のタイムアウト（既定 1800 秒）を超えたら pytest を停止する。終了時に必ずコンテナを停止する（--rm）。
"""

import argparse
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMAGE = "postgres:16"
CONTAINER = "mc-it-run-aoba-ec-1118"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def docker(*args: str, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=check)


def wait_ready(user: str, db: str, deadline: float) -> None:
    while time.monotonic() < deadline:
        result = docker("exec", CONTAINER, "pg_isready", "-h", "127.0.0.1", "-U", user, "-d", db, check=False, timeout=30)
        if result.returncode == 0:
            # 初期化スクリプト後の再起動を跨ぐため、2回連続の成功を待つ
            time.sleep(1.0)
            again = docker("exec", CONTAINER, "pg_isready", "-h", "127.0.0.1", "-U", user, "-d", db, check=False, timeout=30)
            if again.returncode == 0:
                return
        time.sleep(1.0)
    raise SystemExit("PostgreSQL 16 の起動待ちがタイムアウトしました。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", default="reports/integration-test/junit.xml")
    parser.add_argument("--timeout", type=int, default=1800)
    args, extra = parser.parse_known_args()

    user = "it_runner"
    db = "minicommerce_it"
    password = secrets.token_urlsafe(24)
    port = free_port()
    docker("rm", "-f", CONTAINER, check=False)
    image_id = docker("image", "inspect", "--format", "{{.Id}}", IMAGE).stdout.strip()
    docker(
        "run", "-d", "--rm", "--name", CONTAINER,
        "-e", f"POSTGRES_USER={user}", "-e", f"POSTGRES_PASSWORD={password}", "-e", f"POSTGRES_DB={db}",
        "-e", "TZ=Asia/Tokyo", "-e", "PGTZ=Asia/Tokyo", "-e", "POSTGRES_INITDB_ARGS=--encoding=UTF8",
        "--tmpfs", "/var/lib/postgresql/data",
        "-p", f"127.0.0.1:{port}:5432",
        IMAGE,
        "-c", "statement_timeout=60000",
        "-c", "lock_timeout=30000",
        "-c", "idle_in_transaction_session_timeout=120000",
        "-c", "max_connections=100",
        # 注文番号の確定順（コミットの順）を pg_xact_commit_timestamp で判定するため（GF-016、ADDR-005 検証方法）
        "-c", "track_commit_timestamp=on",
    )
    try:
        wait_ready(user, db, time.monotonic() + 90)
        version = docker("exec", CONTAINER, "postgres", "--version").stdout.strip()
        print(f"[env] image={IMAGE} id={image_id} {version} port=127.0.0.1:{port} container={CONTAINER}", flush=True)
        env = dict(os.environ)
        env.update(
            {
                "DB_HOST": "127.0.0.1",
                "DB_PORT": str(port),
                "DB_NAME": db,
                "DB_USER": user,
                "DB_PASSWORD": password,
                "PGCONNECT_TIMEOUT": "10",
                # 使い捨て DB のコンテナ名（資源使用量の記録・バックアップ/リストアの参考確認で docker exec/stats に使う）
                "IT_DB_CONTAINER": CONTAINER,
                "PYTHONIOENCODING": "utf-8",
                "TZ": "Asia/Tokyo",
            }
        )
        env.pop("DJANGO_SETTINGS_MODULE", None)
        command = [
            str(PYTHON), "-m", "pytest", "-c", "app/pytest.ini", "--rootdir=.", "app/tests/integration",
            "-p", "no:cacheprovider", "-o", "junit_family=xunit2", f"--junitxml={args.junit}",
            *extra,
        ]
        print("[cmd] " + " ".join(command[1:]), flush=True)
        try:
            completed = subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout)
            return completed.returncode
        except subprocess.TimeoutExpired:
            print("[env] pytest がプロセスのタイムアウトを超えたため停止しました。", flush=True)
            return 124
    finally:
        docker("stop", "-t", "5", CONTAINER, check=False, timeout=60)
        print(f"[env] container {CONTAINER} stopped (removed by --rm)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
