"""開発用のデモデータ投入スクリプト。

これは開発時の動作確認用データであり、テストデータではない。テストは
後続Test Agentが使い捨てDBに対して独自に用意する（ADR-003）。
"""
from datetime import timedelta

from app.config import load_settings
from app.constants import MovieStatus, PublishStatus, TicketType
from app.database import create_all, create_db_engine, create_session_factory
from app.models.movie import Movie
from app.models.product import Product
from app.models.screening import Screening, ScreeningTicketPrice
from app.time_utils import now_utc


def main() -> None:
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    create_all(engine)
    session_factory = create_session_factory(engine)
    now = now_utc()

    with session_factory() as session:
        movie = Movie(
            title="サンプル映画",
            synopsis="デモ用の作品です。",
            genre="ドラマ",
            status=MovieStatus.PUBLISHED,
        )
        session.add(movie)
        session.flush()

        session.add(
            Product(
                name="サンプルグッズ",
                price_tax_included=1980,
                stock=10,
                publish_status=PublishStatus.PUBLISHED,
                sales_start_at=now - timedelta(days=1),
                sales_end_at=now + timedelta(days=30),
                movie_id=movie.id,
            )
        )

        screening = Screening(
            movie_id=movie.id,
            starts_at=now + timedelta(days=2),
            theater_name="サンプルシアター",
            screen_name="スクリーン1",
            seats_remaining=50,
            sales_start_at=now - timedelta(days=1),
            sales_end_at=now + timedelta(days=2),
        )
        session.add(screening)
        session.flush()

        # ADR-012: 券種ごとの単価は上映回に紐づく価格設定データ（暫定初期価格）。
        session.add_all(
            [
                ScreeningTicketPrice(screening_id=screening.id, ticket_type=TicketType.GENERAL, unit_price=1900),
                ScreeningTicketPrice(screening_id=screening.id, ticket_type=TicketType.STUDENT, unit_price=1500),
                ScreeningTicketPrice(screening_id=screening.id, ticket_type=TicketType.SENIOR, unit_price=1300),
            ]
        )
        session.commit()
    print("seeded demo data")


if __name__ == "__main__":
    main()
