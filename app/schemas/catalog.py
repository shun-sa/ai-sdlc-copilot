from pydantic import BaseModel, Field


class MovieSearchParams(BaseModel):
    keyword: str | None = Field(default=None, max_length=100)
    genre: str | None = Field(default=None, max_length=100)
    sort: str | None = Field(default=None, max_length=20)
    page: int = Field(default=1, ge=1)


class ProductSearchParams(BaseModel):
    keyword: str | None = Field(default=None, max_length=100)
    movie_id: int | None = Field(default=None, ge=1)
    in_stock_only: bool = False
    page: int = Field(default=1, ge=1)
