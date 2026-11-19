# trace: ADDR-001, ADDR-012, ENT-002, ENT-003, ENT-004, ENT-005, ENT-006
"""商品カタログの業務処理（FR-010 商品分類一覧、FR-011 商品一覧検索、FR-012 商品詳細、FR-040 在庫単位一覧）。"""

from typing import Any

from django.db.models import Exists, Min, OuterRef, Q
from django.db.models.functions import Collate

from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
from common import codes
from common.codes import Visibility
from common.errors import MSG_SEARCH_CONDITION_ERROR, FieldErrors, not_found
from common.normalize import has_unstorable_chars, is_blank, parse_identifier, strip_text, unstorable_message
from common.paging import build_page, parse_page, slice_queryset
from common.tax import price_including_tax

PRODUCT_PAGE_SIZE = 20
STOCK_UNIT_PAGE_SIZE = 50
LOW_STOCK_THRESHOLD = 5
_CODE_POINT = "C"  # 名称・コードの並べ替えは Unicode のコードポイント順（CMN-36）


# trace: ENT-003, ADDR-001
def list_categories() -> list[dict[str, Any]]:
    """FR-010 全商品分類を親子の木構造の深さ優先順で返す（表示順→分類名→登録順）。"""
    categories = list(Category.objects.all())
    children: dict[int | None, list[Category]] = {}
    for category in categories:
        children.setdefault(category.parent_id, []).append(category)
    for siblings in children.values():
        siblings.sort(key=lambda c: (c.display_order, c.name, c.pk))
    ordered: list[dict[str, Any]] = []

    def visit(parent_id: int | None) -> None:
        for category in children.get(parent_id, []):
            ordered.append(
                {
                    "category_id": category.pk,
                    "category_code": category.category_code,
                    "name": category.name,
                    "parent_category_id": category.parent_id,
                    "depth": category.depth,
                    "display_order": category.display_order,
                }
            )
            visit(category.pk)

    visit(None)
    return ordered


# trace: ENT-003
def _descendant_ids(category_id: int) -> list[int]:
    pairs = list(Category.objects.values_list("pk", "parent_id"))
    result = [category_id]
    frontier = [category_id]
    while frontier:
        current = set(frontier)
        frontier = [pk for pk, parent in pairs if parent in current]
        result.extend(frontier)
    return result


# trace: ENT-004, ENT-005
def _categories_by_product(product_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    rows = ProductCategory.objects.filter(product_id__in=product_ids).select_related("category").order_by("pk")
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row.product_id, []).append({"category_id": row.category_id, "name": row.category.name})
    return result


# trace: ADDR-001, ENT-004, ENT-005, ENT-006
def search_products(category_id: Any, keyword: Any, sort: Any, page: Any) -> dict[str, Any]:
    """FR-011 公開中で在庫単位を1件以上持つ商品を分類・キーワードで検索し20件ずつ返す。"""
    keyword_value = strip_text(keyword) if keyword is not None else ""
    sort_value = codes.SORT_NEWEST if sort is None else sort
    errors = FieldErrors()
    category_pk: int | None = None
    if category_id is not None:
        category_pk = parse_identifier(strip_text(category_id))
        if category_pk is None:
            errors.add("category_id", codes.FIELD_INVALID_TYPE, "商品分類の指定に誤りがあります。")
        elif not Category.objects.filter(pk=category_pk).exists():
            errors.add("category_id", codes.FIELD_UNKNOWN_REFERENCE, "指定した商品分類は存在しません。")
    if not isinstance(keyword_value, str):
        errors.add("keyword", codes.FIELD_INVALID_TYPE, "キーワードは文字列で入力してください。")
        keyword_value = ""
    elif has_unstorable_chars(keyword_value):
        errors.add("keyword", codes.FIELD_INVALID_FORMAT, unstorable_message("キーワード"))
        keyword_value = ""
    elif len(keyword_value) > 50:
        errors.add("keyword", codes.FIELD_INVALID_LENGTH, "キーワードは50文字以内で入力してください。")
    valid_sorts = {value for value, _label in codes.SORT_CHOICES}
    if sort_value not in valid_sorts:
        errors.add("sort", codes.FIELD_INVALID_CHOICE, "並び順の指定に誤りがあります。")
    page_number = parse_page(page, errors)
    errors.raise_if_any("E-011-01", MSG_SEARCH_CONDITION_ERROR)

    queryset = (
        Product.objects.filter(is_public=True)
        .annotate(min_price=Min("stock_units__price_excluding_tax"))
        .filter(min_price__isnull=False)
    )
    if category_pk is not None:
        ids = _descendant_ids(category_pk)
        queryset = queryset.filter(Exists(ProductCategory.objects.filter(product=OuterRef("pk"), category_id__in=ids)))
    if keyword_value:
        queryset = queryset.filter(Q(name__icontains=keyword_value) | Q(description__icontains=keyword_value))
    queryset = queryset.annotate(
        in_stock=Exists(StockUnit.objects.filter(product=OuterRef("pk"), stock_quantity__gte=1))
    )
    if sort_value == codes.SORT_PRICE_ASC:
        queryset = queryset.order_by("min_price", "pk")
    elif sort_value == codes.SORT_PRICE_DESC:
        queryset = queryset.order_by("-min_price", "pk")
    elif sort_value == codes.SORT_NAME:
        queryset = queryset.order_by(Collate("name", _CODE_POINT), "pk")
    else:
        queryset = queryset.order_by("-registered_at", "-pk")

    info = build_page(page_number, PRODUCT_PAGE_SIZE, queryset.count())
    products = slice_queryset(queryset, info)
    categories = _categories_by_product([p.pk for p in products])
    items = [
        {
            "product_id": p.pk,
            "product_code": p.product_code,
            "name": p.name,
            "min_price_excluding_tax": p.min_price,
            "min_price_including_tax": price_including_tax(p.min_price),
            "is_in_stock": bool(p.in_stock),
            "categories": categories.get(p.pk, []),
        }
        for p in products
    ]
    return {"items": items, **info.as_dict()}


# trace: ADDR-001, ENT-004, ENT-005, ENT-006
def get_product_detail(product_id: Any) -> dict[str, Any]:
    """FR-012 公開中で在庫単位を1件以上持つ商品の詳細。仕入先の情報は返さない（MSG-04）。"""
    pk = parse_identifier(product_id)
    if pk is None:
        raise not_found("E-012-01")
    product = Product.objects.filter(pk=pk).first()
    if product is None or not product.is_public:
        raise not_found("E-012-01")
    stock_units = sorted(StockUnit.objects.filter(product=product), key=lambda s: s.sku)
    if not stock_units:
        raise not_found("E-012-01")
    return {
        "product_id": product.pk,
        "product_code": product.product_code,
        "name": product.name,
        "description": product.description,
        "categories": _categories_by_product([product.pk]).get(product.pk, []),
        "stock_units": [
            {
                "stock_unit_id": s.pk,
                "sku": s.sku,
                "variant_name": s.variant_name,
                "price_excluding_tax": s.price_excluding_tax,
                "price_including_tax": price_including_tax(s.price_excluding_tax),
                "stock_quantity": s.stock_quantity,
                "is_in_stock": s.stock_quantity >= 1,
            }
            for s in stock_units
        ],
    }


# trace: ENT-002
def list_suppliers() -> list[dict[str, Any]]:
    """SCR-101 の仕入先の選択肢（仕入先コード昇順）。"""
    return [
        {"supplier_code": s.supplier_code, "name": s.name}
        for s in Supplier.objects.order_by(Collate("supplier_code", _CODE_POINT))
    ]


# trace: ADDR-001, ENT-002, ENT-004, ENT-006
def list_stock_units(sku: Any, product_name: Any, supplier_code: Any, low_stock_only: Any, page: Any) -> dict[str, Any]:
    """FR-040 非公開商品を含む全在庫単位を条件で絞り込み SKU 昇順で50件ずつ返す（管理者）。"""
    sku_value = strip_text(sku) if sku is not None else ""
    name_value = strip_text(product_name) if product_name is not None else ""
    supplier_value = strip_text(supplier_code) if supplier_code is not None else ""
    low_value = strip_text(low_stock_only) if low_stock_only is not None else ""
    errors = FieldErrors()
    if not isinstance(sku_value, str):
        errors.add("sku", codes.FIELD_INVALID_TYPE, "SKU は文字列で入力してください。")
        sku_value = ""
    elif has_unstorable_chars(sku_value):
        errors.add("sku", codes.FIELD_INVALID_FORMAT, unstorable_message("SKU"))
        sku_value = ""
    elif len(sku_value) > 32:
        errors.add("sku", codes.FIELD_INVALID_LENGTH, "SKU は32文字以内で入力してください。")
    if not isinstance(name_value, str):
        errors.add("product_name", codes.FIELD_INVALID_TYPE, "商品名は文字列で入力してください。")
        name_value = ""
    elif has_unstorable_chars(name_value):
        errors.add("product_name", codes.FIELD_INVALID_FORMAT, unstorable_message("商品名"))
        name_value = ""
    elif len(name_value) > 100:
        errors.add("product_name", codes.FIELD_INVALID_LENGTH, "商品名は100文字以内で入力してください。")
    supplier = None
    if has_unstorable_chars(supplier_value):
        # 使用できない文字を含む値は登録済みのどの仕入先コードとも一致しない（照会せずに判定する）
        errors.add("supplier_code", codes.FIELD_UNKNOWN_REFERENCE, "指定した仕入先は登録されていません。")
    elif not is_blank(supplier_value):
        supplier = (
            Supplier.objects.filter(supplier_code=supplier_value).first() if isinstance(supplier_value, str) else None
        )
        if supplier is None:
            errors.add("supplier_code", codes.FIELD_UNKNOWN_REFERENCE, "指定した仕入先は登録されていません。")
    low_only = False
    if not is_blank(low_value):
        if low_value == "true":
            low_only = True
        elif low_value != "false":
            errors.add("low_stock_only", codes.FIELD_INVALID_CHOICE, "低在庫のみの指定に誤りがあります。")
    page_number = parse_page(page, errors)
    errors.raise_if_any("E-040-03", MSG_SEARCH_CONDITION_ERROR)

    queryset = StockUnit.objects.select_related("product", "supplier")
    if sku_value:
        queryset = queryset.filter(sku__istartswith=sku_value)
    if name_value:
        queryset = queryset.filter(product__name__icontains=name_value)
    if supplier is not None:
        queryset = queryset.filter(supplier=supplier)
    if low_only:
        queryset = queryset.filter(stock_quantity__lte=LOW_STOCK_THRESHOLD)
    queryset = queryset.order_by(Collate("sku", _CODE_POINT))
    info = build_page(page_number, STOCK_UNIT_PAGE_SIZE, queryset.count())
    items = [
        {
            "stock_unit_id": s.pk,
            "sku": s.sku,
            "product_id": s.product_id,
            "product_code": s.product.product_code,
            "product_name": s.product.name,
            "variant_name": s.variant_name,
            "visibility": Visibility.PUBLIC if s.product.is_public else Visibility.PRIVATE,
            "visibility_label": (Visibility.PUBLIC if s.product.is_public else Visibility.PRIVATE).label,
            "supplier_name": s.supplier.name,
            "price_excluding_tax": s.price_excluding_tax,
            "stock_quantity": s.stock_quantity,
            "is_low_stock": s.stock_quantity <= LOW_STOCK_THRESHOLD,
        }
        for s in slice_queryset(queryset, info)
    ]
    return {"items": items, **info.as_dict()}
