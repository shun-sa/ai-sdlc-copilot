"""DBスキーマ初期化スクリプト (ADR-010 Step13: スキーマ再現)。

ORMメタデータから全テーブルを作成する。接続先はDATABASE_URLで注入される。
本番DBに固定依存せず、Docker等の使い捨てDBにも同一スキーマを再現できる。

使用例:
    python -m scripts.init_db
"""

from __future__ import annotations

from app.database import create_all


def main() -> None:
    create_all()
    print("Database schema created.")


if __name__ == "__main__":
    main()
