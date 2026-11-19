# trace: ADDR-011, ADDR-014
"""自動テスト用の設定（ADDR-011 4.3 の6、ADDR-014 9章）。

単一の設定モジュール（app/config/settings.py）を読み込む前に、試験に必要な環境の指定だけを与える。
- MINICOMMERCE_ENV=development、MINICOMMERCE_DEV_FEATURES=true を明示する（試験支援モジュールを組み込む）。
- DJANGO_SECRET_KEY が未設定なら実行ごとに乱数で生成する（リポジトリに秘密情報を置かない）。
- DB 接続（DB_HOST・DB_PORT・DB_NAME・DB_USER・DB_PASSWORD）は環境変数で与える（既定値を持たない利用者名・
  パスワードは未設定なら設定エラー）。本番・検証の DB を指定しないこと。
"""

import os
import secrets

os.environ["MINICOMMERCE_ENV"] = "development"
os.environ["MINICOMMERCE_DEV_FEATURES"] = "true"
os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(50))
os.environ.pop("DJANGO_DEBUG", None)

from config.settings import *  # noqa: E402,F403
