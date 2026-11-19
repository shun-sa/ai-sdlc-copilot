# trace: ADDR-001
"""一覧の分割表示（CMN-35、NFR-PF-08、ADDR-001 4.3 の8・DD-004）。

ページ番号は1以上の整数（省略時は1）。総ページ数を超えるページは0件の一覧を返す（エラーにしない）。
page_size は各 FR が定める件数で固定し、利用者には指定させない（上限50）。
"""

from dataclasses import dataclass
from typing import Any

from common import codes
from common.errors import FieldErrors
from common.normalize import is_blank, parse_int

MAX_PAGE_SIZE = 50


# trace: ADDR-001
@dataclass(frozen=True)
class PageInfo:
    page: int
    page_size: int
    total_count: int
    total_pages: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def is_beyond(self) -> bool:
        return self.page > self.total_pages

    @property
    def first_index(self) -> int:
        return self.offset + 1

    def last_index(self, item_count: int) -> int:
        return self.offset + item_count

    def as_dict(self) -> dict[str, int]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total_count": self.total_count,
            "total_pages": self.total_pages,
        }


# trace: ADDR-001
def parse_page(raw: Any, errors: FieldErrors, field_name: str = "page") -> int:
    """ページ番号を判定する。誤りは errors に追加し、1 を返す（判定の継続用）。"""
    if is_blank(raw):
        return 1
    value = parse_int(raw)
    if value is None:
        errors.add(field_name, codes.FIELD_INVALID_TYPE, "ページは1以上の整数で指定してください。")
        return 1
    if value < 1:
        errors.add(field_name, codes.FIELD_OUT_OF_RANGE, "ページは1以上の整数で指定してください。")
        return 1
    return value


# trace: ADDR-001
def build_page(page: int, page_size: int, total_count: int) -> PageInfo:
    size = min(page_size, MAX_PAGE_SIZE)
    total_pages = (total_count + size - 1) // size if total_count > 0 else 0
    return PageInfo(page=page, page_size=size, total_count=total_count, total_pages=total_pages)


# trace: ADDR-001
def slice_queryset(queryset: Any, info: PageInfo) -> list[Any]:
    """指定ページの件数を取り出す。総ページ数を超えるページは問い合わせずに0件を返す。"""
    if info.is_beyond:
        return []
    return list(queryset[info.offset : info.offset + info.page_size])
