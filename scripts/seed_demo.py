"""ローカル動作確認用のデモデータ投入 (開発専用)。

注意:
- これは手動動作確認用の開発補助であり、本番データではない。
- 自動テストのテストデータ作成は後続Test Agentの責務であり、本スクリプトに依存しない。
- Credential/Secretはハードコードしない (接続先はDATABASE_URL経由)。

使用例:
    python -m scripts.seed_demo
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, create_all
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening


def main() -> None:
    create_all()
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        movie = Movie(
            title="サンプル・ムービー",
            synopsis="デモ用の映画作品です。",
            genre="ドラマ",
            release_date=(now - timedelta(days=10)).date(),
            runtime_minutes=120,
            status="published",
        )
        db.add(movie)
        db.flush()

        db.add(
            Product(
                name="サンプルグッズ",
                price_tax_included=1980,
                stock=10,
                publish_status="published",
                category="goods",
                movie_id=movie.id,
            )
        )
        db.add(
            Screening(
                movie_id=movie.id,
                starts_at=now + timedelta(days=2),
                theater_name="デモシアター",
                screen_name="スクリーン1",
                seats_remaining=50,
                sales_start_at=now - timedelta(days=1),
                sales_end_at=now + timedelta(days=2),
            )
        )
        db.commit()
        print("Demo data seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
