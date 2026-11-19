# trace: ADDR-014, ADDR-013, ADDR-008
"""Gunicorn の設定（ADDR-014 4.3 の3）。

- 全環境のコンテナ起動は Gunicorn（sync ワーカー）とする。
- アクセスログは出力しない（LOG-03 はアプリケーションのミドルウェアだけが出力する：ADDR-013 4.3 の5）。
- 要求処理の上限時間は支払の10秒の待機より十分長くする（30秒以上：ADDR-008）。
- プロセス数は GUNICORN_WORKERS で変更する（ADDR-014 4.3 の4）。
"""

import os

bind = "0.0.0.0:8000"
worker_class = "sync"
workers = int(os.environ.get("GUNICORN_WORKERS") or "2")
timeout = 60
graceful_timeout = 30
accesslog = None
errorlog = "-"
loglevel = "warning"
wsgi_app = "config.wsgi:application"
