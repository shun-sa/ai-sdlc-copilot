"""検索条件スキーマ (FR-003 / FR-005)。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MovieSearchQuery(BaseModel):
    """映画検索条件 (FR-003)。すべて任意入力。"""

    keyword: str | None = Field(default=None, max_length=200)
    genre: str | None = Field(default=None, max_length=50)
    # published / all（顧客画面では非公開は常に除外される）
    release_status: str | None = Field(default=None, max_length=20)
    sort: str = Field(default="release_date_desc", max_length=30)
    page: int = Field(default=1, ge=1)


class ProductSearchQuery(BaseModel):
    """商品検索条件 (FR-005)。すべて任意入力。"""

    keyword: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    movie_id: int | None = Field(default=None, ge=1)
    in_stock_only: bool = Field(default=False)
    page: int = Field(default=1, ge=1)
