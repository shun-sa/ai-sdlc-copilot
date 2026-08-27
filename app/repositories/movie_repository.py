from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import MovieStatus
from app.models.movie import Movie


class MovieRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_published(self, movie_id: int) -> Movie | None:
        stmt = select(Movie).where(Movie.id == movie_id, Movie.status == MovieStatus.PUBLISHED)
        return self._session.scalars(stmt).first()

    def search(
        self,
        *,
        keyword: str | None = None,
        genre: str | None = None,
        sort: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Movie], int]:
        # C-DATA-001: 公開作品のみ。パラメータ化クエリを使用（ADR-009）。
        conditions = [Movie.status == MovieStatus.PUBLISHED]
        if keyword:
            conditions.append(Movie.title.contains(keyword))
        if genre:
            conditions.append(Movie.genre == genre)

        base = select(Movie).where(*conditions)
        total = len(self._session.scalars(base).all())

        if sort == "release_desc":
            base = base.order_by(Movie.release_date.desc())
        elif sort == "release_asc":
            base = base.order_by(Movie.release_date.asc())
        else:
            base = base.order_by(Movie.title.asc())

        rows = self._session.scalars(base.offset(offset).limit(limit)).all()
        return list(rows), total
