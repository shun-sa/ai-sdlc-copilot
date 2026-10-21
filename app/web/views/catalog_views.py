# trace: ADDR-010
"""商品一覧（SCR-001）・商品詳細（SCR-002）。"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from catalog import serializers, services
from common.exceptions import ValidationFailed
from common.pagination import page_range
from web.support import current_user, query_prefix, screen
from web.views.messages import field_errors


@screen
def item_list(request: HttpRequest) -> HttpResponse:
    """SCR-001 商品一覧。FR-010 と FR-011 を実行する。"""
    collections = [serializers.collection_payload(item) for item in services.list_collections()]
    context = {
        "collections": collections,
        "keyword": request.GET.get("keyword", ""),
        "sort": request.GET.get("sort", services.SORT_NEW),
        "selected_collection_id": request.GET.get("collection_id", ""),
    }
    try:
        items, meta, conditions = services.search_items(request.GET.dict())
    except ValidationFailed as error:
        context["field_errors"] = field_errors(error)
        context["error_message"] = "検索条件に誤りがあります。条件を指定し直してください。"
        return render(request, "buyer/item_list.html", context, status=400)

    context.update(
        {
            "items": [serializers.item_summary_payload(item) for item in items],
            "meta": meta,
            "page_numbers": page_range(meta),
            "conditions": conditions,
            "selected_collection_id": str(conditions["collection_id"] or ""),
            "keyword": conditions["keyword"],
            "sort": conditions["sort"],
            "range_from": (meta["page"] - 1) * meta["page_size"] + 1 if meta["total_count"] else 0,
            "range_to": min(meta["page"] * meta["page_size"], meta["total_count"]),
            "query_prefix": query_prefix(request),
        }
    )
    return render(request, "buyer/item_list.html", context)


def item_detail_context(request: HttpRequest, item_id: str, form: dict[str, Any] | None = None) -> dict[str, Any]:
    """SCR-002 の表示内容を組み立てる。

    入力エラー・業務エラーで本画面へ留まる場合は、利用者が入力した数量と選択した規格を
    そのまま返して再表示に用いる（CMN-17、UI-19、SCR-002-OP01）。
    """
    item = services.get_public_item(item_id)
    payload = serializers.item_detail_payload(item)
    available = [unit for unit in payload["stock_units"] if unit["in_stock"]]
    user = current_user(request)
    entered = form or {}
    selected = str(entered.get("stock_unit_id") or "").strip()
    if not selected:
        selected = str(available[0]["stock_unit_id"]) if available else ""
    quantity = entered.get("quantity")
    return {
        "item": payload,
        "has_stock": bool(available),
        "can_add_to_cart": user is None or user.is_buyer,
        "form": {
            "stock_unit_id": selected,
            "quantity": "1" if quantity is None else str(quantity),
        },
    }


@screen
def item_detail(request: HttpRequest, item_id: str) -> HttpResponse:
    """SCR-002 商品詳細。FR-012 を実行する。"""
    return render(request, "buyer/item_detail.html", item_detail_context(request, item_id))
