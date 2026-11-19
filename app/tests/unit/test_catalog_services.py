# trace: FR-010, FR-011, FR-012, FR-040, NFR-SC-04, NFR-SC-24, ADDR-001
"""商品カタログの業務処理（catalog.services：FR-010・FR-011・FR-012・FR-040）の単体テスト。

期待値は functional_requirements.md 6.5〜6.7・6.20（処理内容・検索仕様・例外）、CMN-32・35・36・39、
ADDR-001 4.3 の8・10〜12 から導出する。DB Test Strategy：CONTAINER（並び順・照合順序・部分一致の SQL を含めて検証）。
"""

import pytest

from catalog import services
from common import errors
from tests.unit.conftest import jst

pytestmark = pytest.mark.django_db


# trace: FR-011
def _fields(exc_info):
    return {(f.field, f.reason) for f in exc_info.value.fields}


# ---------------------------------------------------------------------------
# FR-010 商品分類一覧照会
# ---------------------------------------------------------------------------


# trace: FR-010
def test_list_categories_empty_returns_empty_list():
    assert services.list_categories() == []


# trace: FR-010
def test_list_categories_depth_first_by_display_order_name_then_registration(catalog):
    b = catalog.category("B", display_order=1, code="b")
    a = catalog.category("A", display_order=1, code="a")
    z = catalog.category("Z", display_order=0, code="z")
    a_child2 = catalog.category("子2", parent=a, display_order=0, code="a-2")
    a_child1 = catalog.category("子1", parent=a, display_order=0, code="a-1")
    a_grand = catalog.category("孫", parent=a_child2, code="a-2-1")
    same_name_first = catalog.category("同名", parent=b, code="b-1")
    same_name_second_parent = catalog.category("同名X", parent=b, code="b-2")
    result = services.list_categories()
    assert [c["category_code"] for c in result] == ["z", "a", "a-1", "a-2", "a-2-1", "b", "b-1", "b-2"]
    first = result[0]
    assert first == {
        "category_id": z.pk,
        "category_code": "z",
        "name": "Z",
        "parent_category_id": None,
        "depth": 1,
        "display_order": 0,
    }
    grand = next(c for c in result if c["category_code"] == "a-2-1")
    assert grand["parent_category_id"] == a_child2.pk and grand["depth"] == 3
    assert len(result) == 8  # 6.5.6：返した件数は登録済みの件数と一致
    assert {a_child1.pk, a_grand.pk, same_name_first.pk, same_name_second_parent.pk} <= {
        c["category_id"] for c in result
    }


# trace: FR-010
def test_list_categories_same_display_order_sorted_by_name_code_point(catalog):
    parent = catalog.category("親", code="p")
    first = catalog.category("同じ", parent=parent, display_order=5, code="first")
    # 同じ親の中で分類名は一意（IDF-ENT-003-003）。表示順が同じ場合は分類名の昇順（コードポイント順：CMN-36）
    second = catalog.category("あ", parent=parent, display_order=5, code="second")
    assert [c["category_id"] for c in services.list_categories()][1:] == [second.pk, first.pk]


# ---------------------------------------------------------------------------
# FR-011 商品一覧検索
# ---------------------------------------------------------------------------


# trace: FR-011
def test_search_returns_only_public_products_with_stock_units(catalog):
    visible = catalog.product("見える")
    catalog.stock_unit(visible, price=1000, stock=0)  # 在庫数量0の在庫単位しか持たない商品も対象
    hidden = catalog.product("非公開", is_public=False)
    catalog.stock_unit(hidden)
    catalog.product("在庫単位なし")
    result = services.search_products(None, None, None, None)
    assert [i["product_id"] for i in result["items"]] == [visible.pk]
    item = result["items"][0]
    assert item["is_in_stock"] is False
    assert (result["page"], result["page_size"], result["total_count"], result["total_pages"]) == (1, 20, 1, 1)


# trace: FR-011
def test_search_item_has_min_prices_stock_flag_and_categories(catalog):
    cat = catalog.category("家具")
    product = catalog.product("椅子", categories=(cat,), code="CHAIR")
    catalog.stock_unit(product, price=1999, stock=0)
    catalog.stock_unit(product, price=999, stock=0)
    catalog.stock_unit(product, price=5000, stock=3)
    item = services.search_products(None, None, None, None)["items"][0]
    assert item == {
        "product_id": product.pk,
        "product_code": "CHAIR",
        "name": "椅子",
        "min_price_excluding_tax": 999,
        "min_price_including_tax": 1098,  # 999×110÷100 の切捨て
        "is_in_stock": True,
        "categories": [{"category_id": cat.pk, "name": "家具"}],
    }


# trace: FR-011
def test_search_by_category_includes_all_descendants(catalog):
    root = catalog.category("根")
    child = catalog.category("子", parent=root)
    grand = catalog.category("孫", parent=child)
    other = catalog.category("他")
    in_grand = catalog.product("孫の商品", categories=(grand,))
    in_root = catalog.product("根の商品", categories=(root,))
    in_other = catalog.product("他の商品", categories=(other,))
    for product in (in_grand, in_root, in_other):
        catalog.stock_unit(product)
    found = {i["product_id"] for i in services.search_products(str(root.pk), None, None, None)["items"]}
    assert found == {in_grand.pk, in_root.pk}
    found = {i["product_id"] for i in services.search_products(str(child.pk), None, None, None)["items"]}
    assert found == {in_grand.pk}


# trace: FR-011
def test_search_keyword_matches_name_or_description_case_insensitively(catalog):
    by_name = catalog.product("Blue MUG")
    by_desc = catalog.product("湯呑", description="とても blue な色")
    miss = catalog.product("皿", description="red")
    for product in (by_name, by_desc, miss):
        catalog.stock_unit(product)
    found = {i["product_id"] for i in services.search_products(None, "  BLUE \u3000", None, None)["items"]}
    assert found == {by_name.pk, by_desc.pk}
    # 0文字（空白のみ）は条件なし
    assert services.search_products(None, "   ", None, None)["total_count"] == 3


# trace: FR-011, NFR-SC-04
def test_search_keyword_is_not_interpreted_as_sql_or_wildcard(catalog):
    product = catalog.product("100%_OFF")
    catalog.stock_unit(product)
    catalog.stock_unit(catalog.product("100 OFF"))
    assert [i["name"] for i in services.search_products(None, "%_", None, None)["items"]] == ["100%_OFF"]
    assert services.search_products(None, "' OR 1=1 --", None, None)["total_count"] == 0


# trace: FR-011
@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        (None, ["C", "B", "A"]),
        ("newest", ["C", "B", "A"]),
        ("price_asc", ["B", "A", "C"]),
        ("price_desc", ["C", "A", "B"]),
        ("name", ["A", "B", "C"]),
    ],
)
def test_search_sort_orders(catalog, sort, expected):
    a = catalog.product("A", registered_at=jst(2027, 1, 1), code="A")
    b = catalog.product("B", registered_at=jst(2027, 1, 2), code="B")
    c = catalog.product("C", registered_at=jst(2027, 1, 3), code="C")
    catalog.stock_unit(a, price=500)
    catalog.stock_unit(b, price=100)
    catalog.stock_unit(c, price=900)
    assert [i["name"] for i in services.search_products(None, None, sort, None)["items"]] == expected


# trace: FR-011
def test_search_sort_ties_follow_registration_order(catalog):
    same = jst(2027, 2, 1)
    first = catalog.product("同", registered_at=same)
    second = catalog.product("同", registered_at=same)
    catalog.stock_unit(first, price=100)
    catalog.stock_unit(second, price=100)
    ids = lambda sort: [i["product_id"] for i in services.search_products(None, None, sort, None)["items"]]  # noqa: E731
    assert ids("newest") == [second.pk, first.pk]  # 同値は後に登録された商品から
    assert ids("price_asc") == [first.pk, second.pk]  # 同値は先に登録された商品から
    assert ids("price_desc") == [first.pk, second.pk]
    assert ids("name") == [first.pk, second.pk]


# trace: FR-011
def test_search_name_sort_uses_code_point_order(catalog):
    """CMN-36：名称の並べ替えは Unicode のコードポイント順。"""
    for name in ("b", "B", "あ", "a", "A"):
        catalog.stock_unit(catalog.product(name))
    names = [i["name"] for i in services.search_products(None, None, "name", None)["items"]]
    assert names == ["A", "B", "a", "b", "あ"]


# trace: FR-011
def test_search_pagination_20_per_page_and_beyond_last_page(catalog):
    for _ in range(21):
        catalog.stock_unit(catalog.product())
    page1 = services.search_products(None, None, None, "1")
    page2 = services.search_products(None, None, None, "2")
    page3 = services.search_products(None, None, None, "3")
    assert (len(page1["items"]), len(page2["items"]), len(page3["items"])) == (20, 1, 0)
    assert page1["total_count"] == 21 and page1["total_pages"] == 2
    assert page3["page"] == 3 and page3["total_pages"] == 2


# trace: FR-011
def test_search_zero_hits_returns_empty_list_not_error(catalog):
    result = services.search_products(None, "存在しない", None, None)
    assert result["items"] == [] and result["total_count"] == 0 and result["total_pages"] == 0


# trace: FR-011, NFR-SC-04
@pytest.mark.parametrize(("length", "ok"), [(50, True), (51, False)])
def test_search_keyword_length_boundary(catalog, length, ok):
    if ok:
        assert services.search_products(None, "あ" * length, None, None)["total_count"] == 0
    else:
        with pytest.raises(errors.InputError) as info:
            services.search_products(None, "あ" * length, None, None)
        assert _fields(info) == {("keyword", "invalid_length")}


# trace: FR-011, NFR-SC-04
def test_search_reports_all_invalid_conditions_together(catalog):
    with pytest.raises(errors.InputError) as info:
        services.search_products("999999", "x" * 51, "cheap", "0")
    assert info.value.code == "E-011-01"
    assert info.value.message == errors.MSG_SEARCH_CONDITION_ERROR
    assert _fields(info) == {
        ("category_id", "unknown_reference"),
        ("keyword", "invalid_length"),
        ("sort", "invalid_choice"),
        ("page", "out_of_range"),
    }


# trace: FR-011, NFR-SC-04
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"category_id": "abc"}, ("category_id", "invalid_type")),
        ({"keyword": 123}, ("keyword", "invalid_type")),
        ({"keyword": "a\x00b"}, ("keyword", "invalid_format")),
        ({"page": "x"}, ("page", "invalid_type")),
        ({"sort": "NEWEST"}, ("sort", "invalid_choice")),
    ],
)
def test_search_rejects_invalid_types_and_formats(catalog, kwargs, expected):
    params = {"category_id": None, "keyword": None, "sort": None, "page": None, **kwargs}
    with pytest.raises(errors.InputError) as info:
        services.search_products(params["category_id"], params["keyword"], params["sort"], params["page"])
    assert expected in _fields(info)


# ---------------------------------------------------------------------------
# FR-012 商品詳細照会
# ---------------------------------------------------------------------------


# trace: FR-012, NFR-SC-24
def test_product_detail_returns_stock_units_by_sku_without_supplier(catalog):
    cat = catalog.category("分類")
    product = catalog.product("マグ", description="説明", categories=(cat,), code="MUG")
    supplier = catalog.supplier("SECRET-SUP", "秘密の仕入先")
    later = catalog.stock_unit(product, sku="MUG-B", price=1000, stock=0, variant_name="青", supplier=supplier)
    earlier = catalog.stock_unit(product, sku="MUG-A", price=999, stock=1, variant_name="赤", supplier=supplier)
    detail = services.get_product_detail(str(product.pk))
    assert detail["product_code"] == "MUG" and detail["description"] == "説明"
    assert detail["categories"] == [{"category_id": cat.pk, "name": "分類"}]
    assert [s["stock_unit_id"] for s in detail["stock_units"]] == [earlier.pk, later.pk]
    assert detail["stock_units"][0] == {
        "stock_unit_id": earlier.pk,
        "sku": "MUG-A",
        "variant_name": "赤",
        "price_excluding_tax": 999,
        "price_including_tax": 1098,
        "stock_quantity": 1,
        "is_in_stock": True,
    }
    assert detail["stock_units"][1]["is_in_stock"] is False
    assert "SECRET-SUP" not in str(detail) and "秘密の仕入先" not in str(detail)  # 仕入先の情報は返さない


# trace: FR-012
def test_product_detail_not_found_cases_are_indistinguishable(catalog):
    private = catalog.product(is_public=False)
    catalog.stock_unit(private)
    no_units = catalog.product()
    messages = set()
    for product_id in ("abc", "0", "-1", "999999999", str(private.pk), str(no_units.pk), None, "1.0"):
        with pytest.raises(errors.NotFoundError) as info:
            services.get_product_detail(product_id)
        assert info.value.code == "E-012-01"
        messages.add(info.value.message)
    assert len(messages) == 1


# ---------------------------------------------------------------------------
# FR-040 在庫単位一覧照会（管理者）
# ---------------------------------------------------------------------------


# trace: FR-040
def test_stock_units_include_private_and_zero_stock_sorted_by_sku(catalog):
    public = catalog.product("公開品", code="PUB")
    private = catalog.product("非公開品", is_public=False, code="PRV")
    supplier = catalog.supplier("SUP-A", "A商事")
    catalog.stock_unit(public, sku="KC-0102", stock=6, supplier=supplier, price=300)
    catalog.stock_unit(private, sku="KC-0101-BL", stock=0, supplier=supplier)
    catalog.stock_unit(public, sku="AB-1", stock=5, supplier=supplier)
    result = services.list_stock_units(None, None, None, None, None)
    assert [i["sku"] for i in result["items"]] == ["AB-1", "KC-0101-BL", "KC-0102"]
    assert result["page_size"] == 50 and result["total_count"] == 3
    private_row = result["items"][1]
    assert private_row["visibility"] == "private" and private_row["visibility_label"] == "非公開"
    assert private_row["product_code"] == "PRV" and private_row["supplier_name"] == "A商事"
    assert [i["is_low_stock"] for i in result["items"]] == [True, True, False]  # 5以下が低在庫


# trace: FR-040
def test_stock_units_filters_combine_with_and(catalog):
    sup_a, sup_b = catalog.supplier("SUP-A"), catalog.supplier("SUP-B")
    blue = catalog.product("Blue Mug")
    red = catalog.product("Red Mug")
    target = catalog.stock_unit(blue, sku="KC-0101-BL", stock=5, supplier=sup_a)
    catalog.stock_unit(blue, sku="KC-0101-WH", stock=6, supplier=sup_a)
    catalog.stock_unit(red, sku="KC-0102", stock=0, supplier=sup_b)
    catalog.stock_unit(blue, sku="ZZ-KC-01", stock=1, supplier=sup_a)
    # SKU 前方一致（大文字小文字を区別しない）
    assert {i["sku"] for i in services.list_stock_units(" kc-01 ", None, None, None, None)["items"]} == {
        "KC-0101-BL",
        "KC-0101-WH",
        "KC-0102",
    }
    result = services.list_stock_units("kc-01", "blue", "SUP-A", "true", None)
    assert [i["stock_unit_id"] for i in result["items"]] == [target.pk]
    assert services.list_stock_units(None, "MUG", None, "false", None)["total_count"] == 4
    assert services.list_stock_units("", "", "", "", None)["total_count"] == 4


# trace: FR-040
@pytest.mark.parametrize(("stock", "low"), [(4, True), (5, True), (6, False), (0, True)])
def test_low_stock_threshold_is_5_inclusive(catalog, stock, low):
    catalog.stock_unit(sku="ONE", stock=stock)
    assert services.list_stock_units(None, None, None, "true", None)["total_count"] == (1 if low else 0)
    assert services.list_stock_units(None, None, None, None, None)["items"][0]["is_low_stock"] is low


# trace: FR-040
def test_stock_units_pagination_50_per_page(catalog):
    supplier = catalog.supplier()
    product = catalog.product()
    for n in range(51):
        catalog.stock_unit(product, sku=f"S-{n:03d}", supplier=supplier)
    page1 = services.list_stock_units(None, None, None, None, None)
    page2 = services.list_stock_units(None, None, None, None, "2")
    assert len(page1["items"]) == 50 and [i["sku"] for i in page2["items"]] == ["S-050"]
    assert page1["total_pages"] == 2
    assert services.list_stock_units(None, None, None, None, "3")["items"] == []


# trace: FR-040, NFR-SC-04
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("S" * 32, None, None, None, None), None),
        (("S" * 33, None, None, None, None), ("sku", "invalid_length")),
        ((None, "名" * 100, None, None, None), None),
        ((None, "名" * 101, None, None, None), ("product_name", "invalid_length")),
        ((None, None, "NO-SUCH", None, None), ("supplier_code", "unknown_reference")),
        ((None, None, "SUP\x00", None, None), ("supplier_code", "unknown_reference")),
        ((None, None, None, "TRUE", None), ("low_stock_only", "invalid_choice")),
        ((None, None, None, "yes", None), ("low_stock_only", "invalid_choice")),
        ((None, None, None, None, "0"), ("page", "out_of_range")),
        ((5, None, None, None, None), ("sku", "invalid_type")),
        ((None, 5, None, None, None), ("product_name", "invalid_type")),
        (("a\x00", None, None, None, None), ("sku", "invalid_format")),
        ((None, "a\x00", None, None, None), ("product_name", "invalid_format")),
    ],
)
def test_stock_units_input_validation(catalog, args, expected):
    if expected is None:
        assert services.list_stock_units(*args)["total_count"] == 0
    else:
        with pytest.raises(errors.InputError) as info:
            services.list_stock_units(*args)
        assert info.value.code == "E-040-03"
        assert expected in _fields(info)


# trace: FR-040
def test_list_suppliers_sorted_by_code(catalog):
    catalog.supplier("SUP-B", "B")
    catalog.supplier("SUP-A", "A")
    assert services.list_suppliers() == [
        {"supplier_code": "SUP-A", "name": "A"},
        {"supplier_code": "SUP-B", "name": "B"},
    ]
