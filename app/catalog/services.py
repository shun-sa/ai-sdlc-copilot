# trace: ADDR-008
"""商品カタログの業務ロジック（FR-010〜FR-012、FR-040）。

一覧・詳細では関連データを結合取得・一括取得し、ループ内で追加の問い合わせを行わない
（ADDR-008 INV-002）。分類名・商品名・SKU の並べ替えは、対象列の照合順序を "C" に固定
することで Unicode のコードポイント順とする（CMN-36。catalog/models.py の db_collation）。
"""

from __future__ import annotations

from typing import Any

from django.db.models import Exists, Min, OuterRef, Q, QuerySet

from catalog.models import LOW_STOCK_THRESHOLD, Collection, Item, StockUnit, Supplier
from catalog.models import price_incl_tax as calculate_price_incl_tax
from common.exceptions import NotFoundError
from common.pagination import paginate
from common.validators import ValidationCollector, normalize_text, parse_bool, parse_int, validate_page

SORT_NEW = "new"
SORT_PRICE_ASC = "price_asc"
SORT_PRICE_DESC = "price_desc"
SORT_NAME = "name"
SORT_CHOICES = (SORT_NEW, SORT_PRICE_ASC, SORT_PRICE_DESC, SORT_NAME)

ITEM_PAGE_SIZE = 20
STOCK_UNIT_PAGE_SIZE = 50


# trace: ADDR-008
def price_incl_tax(price: int) -> int:
    """税込価格（税抜価格×110÷100 の1円未満切り捨て）を返す（表示用の公開関数）。"""
    return calculate_price_incl_tax(price)


# trace: ADDR-008
def list_collections() -> list[Collection]:
    """全商品分類を木構造の深さ優先順に並べて返す（FR-010）。"""
    collections = list(Collection.objects.all().order_by("sort_order", "name", "id"))
    children: dict[int | None, list[Collection]] = {}
    for collection in collections:
        children.setdefault(collection.parent_id, []).append(collection)

    ordered: list[Collection] = []

    def walk(parent_id: int | None) -> None:
        for child in children.get(parent_id, []):
            ordered.append(child)
            walk(child.pk)

    walk(None)
    return ordered


# trace: ADDR-008
def collection_subtree_ids(collection_id: int) -> list[int]:
    """指定した分類とその配下すべての分類の識別子を返す。"""
    collections = list(Collection.objects.all().only("id", "parent_id"))
    children: dict[int | None, list[int]] = {}
    for collection in collections:
        children.setdefault(collection.parent_id, []).append(collection.pk)
    result: list[int] = []
    stack = [collection_id]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(children.get(current, []))
    return result


# trace: ADDR-008
def public_item_queryset() -> QuerySet[Item]:
    """公開中で在庫単位を1件以上持つ商品の問い合わせを組み立てる。"""
    in_stock = StockUnit.objects.filter(item=OuterRef("pk"), quantity__gte=1)
    return (
        Item.objects.filter(is_public=True)
        .annotate(min_price=Min("stock_units__price"), has_stock=Exists(in_stock))
        .filter(min_price__isnull=False)
    )


# trace: ADDR-008
def search_items(params: dict[str, Any]) -> tuple[list[Item], dict[str, int], dict[str, Any]]:
    """商品一覧検索（FR-011）。検索結果・ページ情報・正規化した検索条件を返す。"""
    collector = ValidationCollector()
    keyword = normalize_text(params.get("keyword"))
    sort = normalize_text(params.get("sort")) or SORT_NEW
    page = validate_page(params.get("page"), collector)

    collection_id: int | None = None
    raw_collection = params.get("collection_id")
    if raw_collection is not None and normalize_text(raw_collection) != "":
        collection_id = parse_int(raw_collection)
        if collection_id is None or not Collection.objects.filter(pk=collection_id).exists():
            collector.add("collection_id", "指定された商品分類は存在しません。")
            collection_id = None
    if len(keyword) > 50:
        collector.add("keyword", "キーワードは50文字以内で入力してください。")
    if sort not in SORT_CHOICES:
        collector.add("sort", "並び順の指定が正しくありません。")
    collector.raise_if_any()

    queryset = public_item_queryset()
    if collection_id is not None:
        queryset = queryset.filter(item_collections__collection_id__in=collection_subtree_ids(collection_id)).distinct()
    if keyword:
        queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))

    order_by = {
        SORT_NEW: ("-created_at", "-id"),
        SORT_PRICE_ASC: ("min_price", "id"),
        SORT_PRICE_DESC: ("-min_price", "id"),
        SORT_NAME: ("name", "id"),
    }[sort]
    queryset = queryset.order_by(*order_by).prefetch_related("item_collections__collection")

    items, meta = paginate(queryset, page, ITEM_PAGE_SIZE)
    conditions = {"collection_id": collection_id, "keyword": keyword, "sort": sort}
    return items, meta, conditions


# trace: ADDR-008
def get_public_item(item_id: Any) -> Item:
    """商品詳細の対象商品を取得する（FR-012）。公開・在庫単位1件以上に限る。"""
    identifier = parse_int(item_id)
    if identifier is None:
        raise NotFoundError()
    item = (
        Item.objects.filter(pk=identifier, is_public=True)
        .prefetch_related("item_collections__collection")
        .first()
    )
    if item is None:
        raise NotFoundError()
    stock_units = list(item.stock_units.all().order_by("sku"))
    if not stock_units:
        raise NotFoundError()
    item.ordered_stock_units = stock_units
    return item


# trace: ADDR-008
def get_public_stock_unit(stock_unit_id: Any) -> StockUnit:
    """公開中の商品に属する在庫単位を取得する（カート操作の対象判定）。"""
    identifier = parse_int(stock_unit_id)
    if identifier is None:
        raise NotFoundError()
    stock_unit = StockUnit.objects.select_related("item").filter(pk=identifier, item__is_public=True).first()
    if stock_unit is None:
        raise NotFoundError()
    return stock_unit


# trace: ADDR-008
def list_suppliers() -> list[Supplier]:
    """登録済みの全仕入先を仕入先コード昇順で返す（管理者向け画面の選択肢）。"""
    return list(Supplier.objects.all().order_by("supplier_code"))


# trace: ADDR-008
def search_stock_units(params: dict[str, Any]) -> tuple[list[StockUnit], dict[str, int], dict[str, Any]]:
    """在庫単位一覧照会（FR-040）。非公開商品・在庫数量0の在庫単位も対象とする。"""
    collector = ValidationCollector()
    sku = normalize_text(params.get("sku"))
    item_name = normalize_text(params.get("item_name"))
    page = validate_page(params.get("page"), collector)

    supplier_id: int | None = None
    raw_supplier = params.get("supplier_id")
    if raw_supplier is not None and normalize_text(raw_supplier) != "":
        supplier_id = parse_int(raw_supplier)
        if supplier_id is None or not Supplier.objects.filter(pk=supplier_id).exists():
            collector.add("supplier_id", "指定された仕入先は存在しません。")
            supplier_id = None

    low_stock_only = False
    raw_low_stock = params.get("low_stock_only")
    if raw_low_stock is not None and normalize_text(raw_low_stock) != "":
        parsed = parse_bool(raw_low_stock)
        if parsed is None:
            collector.add("low_stock_only", "低在庫のみは true または false で指定してください。")
        else:
            low_stock_only = parsed

    if len(sku) > 32:
        collector.add("sku", "SKU は32文字以内で入力してください。")
    if len(item_name) > 100:
        collector.add("item_name", "商品名は100文字以内で入力してください。")
    collector.raise_if_any()

    queryset = StockUnit.objects.select_related("item", "supplier").all()
    if sku:
        queryset = queryset.filter(sku__istartswith=sku)
    if item_name:
        queryset = queryset.filter(item__name__icontains=item_name)
    if supplier_id is not None:
        queryset = queryset.filter(supplier_id=supplier_id)
    if low_stock_only:
        queryset = queryset.filter(quantity__lte=LOW_STOCK_THRESHOLD)
    queryset = queryset.order_by("sku")

    stock_units, meta = paginate(queryset, page, STOCK_UNIT_PAGE_SIZE)
    conditions = {
        "sku": sku,
        "item_name": item_name,
        "supplier_id": supplier_id,
        "low_stock_only": low_stock_only,
    }
    return stock_units, meta, conditions
