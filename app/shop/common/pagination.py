# trace: ADDR-006, ADDR-007
"""ページング（CMN-35）の共通実装。1ページ件数は各機能の固定値とする。"""
from math import ceil
from typing import Any

from django.db.models import QuerySet

from shop.common.errors import ValidationError
from shop.common.validators import parse_int

PAGE_ERROR_REASON = "ページ番号は1以上の整数で指定してください。"


# trace: ADDR-007
def parse_page(raw_page: Any) -> int:
    """ページ番号を検証して返す（省略時は1、整数でない・1未満は入力エラー）。"""
    if raw_page is None or raw_page == "":
        return 1
    page = parse_int(raw_page)
    if page is None or page < 1:
        raise ValidationError(details=[{"field": "page", "reason": PAGE_ERROR_REASON}])
    return page


# trace: ADDR-006, ADDR-007
def paginate(queryset: QuerySet, page: int, page_size: int) -> dict[str, Any]:
    """指定ページの要素と、ページ番号・1ページ件数・総件数・総ページ数を返す。"""
    total_count = queryset.count()
    total_pages = ceil(total_count / page_size) if total_count else 0
    offset = (page - 1) * page_size
    results = list(queryset[offset : offset + page_size]) if page <= total_pages else []
    return {
        "results": results,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
    }
