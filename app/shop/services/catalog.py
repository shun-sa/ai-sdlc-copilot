# trace: ADDR-006, ADDR-007
"""商品カタログ参照（FR-010、FR-011、FR-012）の業務ロジック。

一覧検索は Django ORM の QuerySet だけで組み立てる（生SQL・文字列連結を使わない）。
"""
from typing import Any

from django.db.models import Exists, Min, OuterRef, Q, QuerySet

from shop.common.errors import NotFoundError
from shop.common.pagination import paginate
from shop.common.validators import ErrorCollector, parse_int, strip_value
from shop.models import Collection, Item, StockUnit
from shop.services.amounts import tax_included_price

ITEM_PAGE_SIZE = 20
KEYWORD_MAX_LENGTH = 50
SORT_NEW = "new"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_NAME = "name"
SORT_OPTIONS = (SORT_NEW, SORT_PRICE_ASC, SORT_PRICE_DESC, SORT_NAME)


# trace: ADDR-006
def list_collections() -> list[dict[str, Any]]:
    """商品分類一覧（FR-010）。親子の木構造の深さ優先順で全件返す。"""
    collections = list(Collection.objects.all())
    children: dict[int | None, list[Collection]] = {}
    for collection in collections:
        children.setdefault(collection.parent_collection_id, []).append(collection)
    for group in children.values():
        group.sort(key=lambda item: (item.sort_order, item.name, item.collection_id))

    ordered: list[dict[str, Any]] = []

    def walk(parent_id: int | None) -> None:
        """指定した親の配下を深さ優先で並べる。"""
        for collection in children.get(parent_id, []):
            ordered.append(
                {
                    "collection_id": collection.collection_id,
                    "collection_code": collection.collection_code,
                    "name": collection.name,
                    "parent_collection_id": collection.parent_collection_id,
                    "depth": collection.depth,
                    "sort_order": collection.sort_order,
                }
            )
            walk(collection.collection_id)

    walk(None)
    return ordered


# trace: ADDR-006
def _descendant_collection_ids(collection_id: int) -> list[int]:
    """指定した分類とその配下すべての分類IDを返す（最大3階層のため再帰クエリを使わない）。"""
    ids = [collection_id]
    frontier = [collection_id]
    for _ in range(2):
        if not frontier:
            break
        frontier = list(
            Collection.objects.filter(parent_collection_id__in=frontier).values_list("collection_id", flat=True)
        )
        ids.extend(frontier)
    return ids


# trace: ADDR-006, ADDR-007
def search_items(
    raw_collection_id: Any = None,
    raw_keyword: Any = None,
    raw_sort: Any = None,
    raw_page: Any = None,
) -> dict[str, Any]:
    """商品一覧検索（FR-011）。公開中かつ在庫単位を1件以上持つ商品を返す。"""
    keyword = strip_value(raw_keyword)
    sort = strip_value(raw_sort) or SORT_NEW
    errors = ErrorCollector()

    collection_id: int | None = None
    if strip_value(raw_collection_id) != "":
        collection_id = parse_int(raw_collection_id)
        if collection_id is None or not Collection.objects.filter(collection_id=collection_id).exists():
            errors.add("collection_id", "指定した商品分類が見つかりません。")

    if len(keyword) > KEYWORD_MAX_LENGTH:
        errors.add("keyword", "キーワードは50文字以下で入力してください。")

    if sort not in SORT_OPTIONS:
        errors.add("sort", "並び順の指定が正しくありません。")

    page = 1
    raw_page_text = strip_value(raw_page)
    if raw_page_text != "":
        parsed_page = parse_int(raw_page)
        if parsed_page is None or parsed_page < 1:
            errors.add("page", "ページ番号は1以上の整数で指定してください。")
        else:
            page = parsed_page

    errors.raise_if_error()

    queryset = _public_items_with_stock_units().annotate(min_price=Min("stock_units__price"))

    if collection_id is not None:
        queryset = queryset.filter(item_collections__collection_id__in=_descendant_collection_ids(collection_id))

    if keyword:
        queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))

    queryset = queryset.distinct()
    queryset = _apply_item_sort(queryset, sort)

    page_data = paginate(queryset, page, ITEM_PAGE_SIZE)
    items = page_data["results"]
    in_stock_ids = set(
        StockUnit.objects.filter(item__in=items, quantity__gte=1).values_list("item_id", flat=True).distinct()
    )
    collections_by_item = _collections_by_item([item.item_id for item in items])

    page_data["results"] = [
        {
            "item_id": item.item_id,
            "item_code": item.item_code,
            "name": item.name,
            "min_price": item.min_price,
            "min_price_incl_tax": tax_included_price(item.min_price),
            "in_stock": item.item_id in in_stock_ids,
            "collections": collections_by_item.get(item.item_id, []),
        }
        for item in items
    ]
    return page_data


# trace: ADDR-006
def _public_items_with_stock_units() -> QuerySet:
    """公開中かつ在庫単位を1件以上持つ商品の QuerySet を返す。"""
    has_stock_unit = Exists(StockUnit.objects.filter(item_id=OuterRef("pk")))
    return Item.objects.filter(is_public=True).filter(has_stock_unit)


# trace: ADDR-006
def _apply_item_sort(queryset: QuerySet, sort: str) -> QuerySet:
    """並び順（FR-011 手順7）を QuerySet へ適用する。"""
    if sort == SORT_PRICE_ASC:
        return queryset.order_by("min_price", "item_id")
    if sort == SORT_PRICE_DESC:
        return queryset.order_by("-min_price", "item_id")
    if sort == SORT_NAME:
        return queryset.order_by("name", "item_id")
    return queryset.order_by("-created_at", "-item_id")


# trace: ADDR-006
def _collections_by_item(item_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """商品ごとの所属分類（分類ID・分類名）を取得する（N+1 を避ける）。"""
    result: dict[int, list[dict[str, Any]]] = {}
    rows = (
        Item.objects.filter(item_id__in=item_ids)
        .values_list("item_id", "item_collections__collection__collection_id", "item_collections__collection__name")
        .order_by("item_id", "item_collections__collection__collection_id")
    )
    for item_id, collection_id, name in rows:
        if collection_id is None:
            result.setdefault(item_id, [])
            continue
        result.setdefault(item_id, []).append({"collection_id": collection_id, "name": name})
    return result


# trace: ADDR-006, ADDR-007
def get_item_detail(raw_item_id: Any) -> dict[str, Any]:
    """商品詳細照会（FR-012）。非公開・在庫単位0件・存在しない商品は対象なしとする。"""
    item_id = parse_int(raw_item_id)
    if item_id is None:
        raise NotFoundError(message="指定した商品が見つかりません。")
    item = Item.objects.filter(item_id=item_id, is_public=True).first()
    if item is None:
        raise NotFoundError(message="指定した商品が見つかりません。")

    stock_units = list(item.stock_units.order_by("sku"))
    if not stock_units:
        raise NotFoundError(message="指定した商品が見つかりません。")

    return {
        "item_id": item.item_id,
        "item_code": item.item_code,
        "name": item.name,
        "description": item.description,
        "collections": _collections_by_item([item.item_id]).get(item.item_id, []),
        "stock_units": [
            {
                "stock_unit_id": unit.stock_unit_id,
                "sku": unit.sku,
                "variant_name": unit.variant_name,
                "price": unit.price,
                "price_incl_tax": tax_included_price(unit.price),
                "quantity": unit.quantity,
                "in_stock": unit.quantity >= 1,
            }
            for unit in stock_units
        ],
    }
