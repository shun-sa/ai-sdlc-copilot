# trace: ADDR-008
"""ページング（件数取得クエリと範囲取得で行う。全件取得して数えない）。"""

from __future__ import annotations

import math
from typing import Any

from django.db.models import QuerySet


def paginate(queryset: QuerySet, page: int, page_size: int) -> tuple[list[Any], dict[str, int]]:
    """指定ページの要素と、ページ情報（page/page_size/total_count/total_pages）を返す。"""
    total_count = queryset.count()
    total_pages = math.ceil(total_count / page_size) if total_count else 0
    offset = (page - 1) * page_size
    items = list(queryset[offset : offset + page_size])
    meta = {
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
    }
    return items, meta


def page_payload(results: list[Any], meta: dict[str, int]) -> dict[str, Any]:
    """ページング形式の応答本文を組み立てる。"""
    return {
        "results": results,
        "page": meta["page"],
        "page_size": meta["page_size"],
        "total_count": meta["total_count"],
        "total_pages": meta["total_pages"],
    }


def page_range(meta: dict[str, int]) -> list[int]:
    """画面のページ移動に表示するページ番号（前後2ページ・先頭・最終）を返す。"""
    total_pages = meta["total_pages"]
    if total_pages <= 1:
        return []
    current = meta["page"]
    numbers = {1, total_pages}
    for candidate in range(current - 2, current + 3):
        if 1 <= candidate <= total_pages:
            numbers.add(candidate)
    return sorted(numbers)
