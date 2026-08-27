"""開発用: DATABASE_URL（未指定時は開発デフォルト）へスキーマを作成する。

テストは使い捨てDBを使用するため本スクリプトに依存しない（ADR-003）。
"""
from app.config import load_settings
from app.database import create_all, create_db_engine


def main() -> None:
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    create_all(engine)
    print(f"initialized schema at {settings.database_url}")


if __name__ == "__main__":
    main()
