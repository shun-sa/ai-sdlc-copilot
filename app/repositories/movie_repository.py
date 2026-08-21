"""Movie Repository (FR-003 / FR-004)。"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.movie import Movie


class MovieRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _visible(self) -> Select:
        # C-DATA-001: 非公開作品は顧客画面に表示しない
        return select(Movie).where(Movie.status == "published")

    def search(
        self,
        *,
        keyword: str | None,
        genre: str | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Movie], int]:
        stmt = self._visible()
        count_stmt = select(func.count()).select_from(Movie).where(Movie.status == "published")

        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(Movie.title.ilike(like))
            count_stmt = count_stmt.where(Movie.title.ilike(like))
        if genre:
            stmt = stmt.where(Movie.genre == genre)
            count_stmt = count_stmt.where(Movie.genre == genre)

        if sort == "title_asc":
            stmt = stmt.order_by(Movie.title.asc())
        else:
            stmt = stmt.order_by(Movie.release_date.desc().nullslast(), Movie.id.desc())

        total = self.db.execute(count_stmt).scalar_one()
        rows = list(self.db.execute(stmt.limit(limit).offset(offset)).scalars())
        return rows, total

    def get_visible(self, movie_id: int) -> Movie | None:
        return self.db.execute(
            self._visible().where(Movie.id == movie_id)
        ).scalar_one_or_none()
