# trace: FR-010, FR-011, FR-012, FR-021, FR-040, NFR-LG-02, NFR-SC-04, ADDR-008
"""商品カタログ（FR-010〜FR-012、FR-040）の単体テスト。

期待結果は機能要件 6.5（商品分類一覧）・6.6（商品一覧検索）・6.7（商品詳細）・
6.20（在庫単位一覧）の処理内容・検索仕様・例外、および NFR-LG-02（税込価格の算出）から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from _helpers import make_collection, make_item, make_stock_unit, make_supplier
from catalog import services
from catalog.models import LOW_STOCK_THRESHOLD, Item
from common import timeutils
from common.exceptions import NotFoundError, ValidationFailed

pytestmark = pytest.mark.django_db


# trace: NFR-LG-02
@pytest.mark.parametrize(
    ("price", "expected"),
    [(0, 0), (1, 1), (10, 11), (999, 1098), (1000, 1100), (1999, 2198)],
)
def test_price_incl_tax_truncates_fraction(price, expected):
    """NFR-LG-02：税込価格＝税抜価格×110÷100 の1円未満切り捨て。"""
    assert services.price_incl_tax(price) == expected


# trace: FR-010
def test_list_collections_returns_depth_first_order():
    """FR-010 手順2：表示順→分類名→分類IDの順で深さ優先に並べる。"""
    root_b = make_collection(collection_code="root-b", name="B", sort_order=2)
    root_a = make_collection(collection_code="root-a", name="A", sort_order=1)
    child_a2 = make_collection(collection_code="a-2", name="A2", parent=root_a, sort_order=2)
    child_a1 = make_collection(collection_code="a-1", name="A1", parent=root_a, sort_order=1)
    grandchild = make_collection(collection_code="a-1-1", name="A11", parent=child_a1)

    ordered = services.list_collections()

    assert [collection.collection_code for collection in ordered] == [
        root_a.collection_code,
        child_a1.collection_code,
        grandchild.collection_code,
        child_a2.collection_code,
        root_b.collection_code,
    ]


# trace: FR-010
def test_list_collections_returns_empty_list_without_collections():
    """FR-010 手順3：0件の場合は空の一覧を返す（エラーにしない）。"""
    assert services.list_collections() == []


# trace: FR-011
def test_collection_subtree_ids_includes_all_descendants():
    """FR-011 手順4：指定した分類とその配下すべての分類を対象とする。"""
    root = make_collection(collection_code="c-root", name="root")
    child = make_collection(collection_code="c-child", name="child", parent=root)
    grandchild = make_collection(collection_code="c-grand", name="grand", parent=child)
    other = make_collection(collection_code="c-other", name="other")

    ids = services.collection_subtree_ids(root.pk)

    assert set(ids) == {root.pk, child.pk, grandchild.pk}
    assert other.pk not in ids


# trace: FR-011
def test_search_items_returns_only_public_items_with_stock_units():
    """FR-011 手順3：公開かつ在庫単位を1件以上持つ商品だけを対象とする。"""
    sellable = make_item(name="公開商品")
    make_stock_unit(sellable, quantity=0)
    hidden = make_item(name="非公開商品", is_public=False)
    make_stock_unit(hidden)
    make_item(name="在庫単位なし")

    items, meta, _conditions = services.search_items({})

    assert [item.pk for item in items] == [sellable.pk]
    assert meta["total_count"] == 1


# trace: FR-011
def test_search_items_marks_in_stock_only_when_quantity_is_positive():
    """FR-011 手順9：在庫数量1以上の在庫単位を1件以上持つ場合に「在庫あり」とする。"""
    item = make_item()
    make_stock_unit(item, quantity=0, price=500)
    make_stock_unit(item, quantity=1, price=800)

    items, _meta, _conditions = services.search_items({})

    assert items[0].has_stock is True
    assert items[0].min_price == 500


# trace: FR-011
def test_search_items_filters_by_keyword_in_name_or_description():
    """FR-011 手順5：商品名または商品説明に部分一致（大文字小文字を区別しない）。"""
    by_name = make_item(name="Blue Mug")
    by_description = make_item(name="無地カップ", description="This is a BLUE item")
    unrelated = make_item(name="赤い皿", description="red")
    for item in (by_name, by_description, unrelated):
        make_stock_unit(item)

    items, meta, conditions = services.search_items({"keyword": "  blue "})

    assert {item.pk for item in items} == {by_name.pk, by_description.pk}
    assert meta["total_count"] == 2
    assert conditions["keyword"] == "blue"


# trace: NFR-SC-04
@pytest.mark.parametrize(
    "keyword",
    ["' OR '1'='1", "'; DROP TABLE items; --", "%", "_", "Blue' --"],
)
def test_search_items_treats_attack_strings_as_plain_keyword(keyword):
    """NFR-SC-04／VUL-04：入力値をそのままSQLへ連結せず、検索キーワードの文字列として扱う。"""
    item = make_item(name="Blue Mug", description="plain description")
    make_stock_unit(item)

    items, meta, conditions = services.search_items({"keyword": keyword})

    assert items == []
    assert meta["total_count"] == 0
    assert conditions["keyword"] == keyword.strip()
    assert Item.objects.filter(pk=item.pk).exists()


# trace: FR-011
def test_search_items_filters_by_collection_subtree():
    """FR-011 手順4：指定した分類とその配下の分類に所属する商品へ絞り込む。"""
    root = make_collection(collection_code="s-root", name="root")
    child = make_collection(collection_code="s-child", name="child", parent=root)
    in_child = make_item(collections=[child])
    in_root = make_item(collections=[root])
    outside = make_item(collections=[make_collection(collection_code="s-other", name="other")])
    for item in (in_child, in_root, outside):
        make_stock_unit(item)

    items, _meta, conditions = services.search_items({"collection_id": str(root.pk)})

    assert {item.pk for item in items} == {in_child.pk, in_root.pk}
    assert conditions["collection_id"] == root.pk


# trace: FR-011
def test_search_items_sorts_by_requested_order():
    """FR-011 手順7：新着順／価格の安い順／価格の高い順／商品名順に並べる。"""
    base = timeutils.now()
    old_cheap = make_item(name="AAA", created_at=base - dt.timedelta(days=2))
    make_stock_unit(old_cheap, price=100)
    new_expensive = make_item(name="ZZZ", created_at=base)
    make_stock_unit(new_expensive, price=900)

    newest = [item.pk for item in services.search_items({"sort": "new"})[0]]
    cheapest = [item.pk for item in services.search_items({"sort": "price_asc"})[0]]
    expensive = [item.pk for item in services.search_items({"sort": "price_desc"})[0]]
    by_name = [item.pk for item in services.search_items({"sort": "name"})[0]]

    assert newest == [new_expensive.pk, old_cheap.pk]
    assert cheapest == [old_cheap.pk, new_expensive.pk]
    assert expensive == [new_expensive.pk, old_cheap.pk]
    assert by_name == [old_cheap.pk, new_expensive.pk]


# trace: FR-011
def test_search_items_defaults_to_newest_order():
    """FR-011 手順1：並び順の省略時は新着順とする。"""
    _items, _meta, conditions = services.search_items({})

    assert conditions["sort"] == services.SORT_NEW


# trace: FR-011
def test_search_items_paginates_by_20_items():
    """FR-011 手順8：1ページ20件とし、総ページ数は切り上げる。"""
    for index in range(21):
        item = make_item(name=f"商品{index:02d}")
        make_stock_unit(item)

    first_page, meta, _conditions = services.search_items({"page": "1"})
    second_page, second_meta, _ = services.search_items({"page": "2"})

    assert len(first_page) == services.ITEM_PAGE_SIZE == 20
    assert len(second_page) == 1
    assert meta == {"page": 1, "page_size": 20, "total_count": 21, "total_pages": 2}
    assert second_meta["page"] == 2


# trace: FR-011
def test_search_items_returns_empty_page_beyond_total_pages():
    """FR-011 手順8：総ページ数を超えるページ番号には0件の一覧を返す（エラーにしない）。"""
    item = make_item()
    make_stock_unit(item)

    items, meta, _conditions = services.search_items({"page": "5"})

    assert items == []
    assert meta["total_count"] == 1


# trace: FR-011
def test_search_items_returns_empty_result_without_matches():
    """該当0件は空の一覧（総件数0・総ページ数0）を返す。"""
    items, meta, _conditions = services.search_items({"keyword": "該当しない語"})

    assert items == []
    assert meta["total_count"] == 0
    assert meta["total_pages"] == 0


# trace: FR-011
def test_search_items_reports_every_invalid_condition():
    """E-011-01：条件を満たさない全項目を1回で通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.search_items({"collection_id": "999999", "keyword": "あ" * 51, "sort": "unknown", "page": "0"})

    assert {detail["field"] for detail in error.value.details} == {
        "collection_id",
        "keyword",
        "sort",
        "page",
    }


# trace: FR-011
def test_search_items_rejects_non_integer_collection_id():
    """E-011-01：分類IDが登録済みの分類IDでない場合は入力エラーとする。"""
    with pytest.raises(ValidationFailed) as error:
        services.search_items({"collection_id": "abc"})

    assert error.value.details[0]["field"] == "collection_id"


# trace: FR-011
def test_search_items_accepts_keyword_of_50_characters():
    """FR-011 6.6.3：キーワードは50文字以下（境界値）。"""
    _items, _meta, conditions = services.search_items({"keyword": "あ" * 50})

    assert len(conditions["keyword"]) == 50


# trace: FR-012
def test_get_public_item_returns_stock_units_in_sku_order():
    """FR-012 手順5：在庫単位を SKU 昇順で返す。"""
    item = make_item()
    make_stock_unit(item, sku="SKU-B")
    make_stock_unit(item, sku="SKU-A")

    loaded = services.get_public_item(str(item.pk))

    assert [unit.sku for unit in loaded.ordered_stock_units] == ["SKU-A", "SKU-B"]


# trace: FR-012
def test_get_public_item_rejects_non_public_item():
    """E-012-01：非公開の商品は対象なしとする（存在有無を区別しない）。"""
    item = make_item(is_public=False)
    make_stock_unit(item)

    with pytest.raises(NotFoundError):
        services.get_public_item(item.pk)


# trace: FR-012
def test_get_public_item_rejects_item_without_stock_units():
    """E-012-01：在庫単位を持たない商品は対象なしとする。"""
    item = make_item()

    with pytest.raises(NotFoundError):
        services.get_public_item(item.pk)


# trace: FR-012
@pytest.mark.parametrize("item_id", ["abc", "", None, 999999])
def test_get_public_item_rejects_unresolvable_identifier(item_id):
    """CMN-04：識別子として解釈できない値・該当なしは対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.get_public_item(item_id)


# trace: FR-021
def test_get_public_stock_unit_returns_unit_of_public_item():
    """カート操作の対象は公開商品に属する在庫単位に限る。"""
    item = make_item()
    unit = make_stock_unit(item)

    assert services.get_public_stock_unit(str(unit.pk)).pk == unit.pk


# trace: FR-021
def test_get_public_stock_unit_rejects_unit_of_non_public_item():
    """E-021-04：非公開商品の在庫単位は対象なしとする。"""
    unit = make_stock_unit(make_item(is_public=False))

    with pytest.raises(NotFoundError):
        services.get_public_stock_unit(unit.pk)


# trace: FR-021
@pytest.mark.parametrize("stock_unit_id", ["abc", 999999])
def test_get_public_stock_unit_rejects_unknown_identifier(stock_unit_id):
    """存在しない在庫単位・解釈できない識別子は対象なしとする。"""
    with pytest.raises(NotFoundError):
        services.get_public_stock_unit(stock_unit_id)


# trace: FR-040
def test_list_suppliers_is_sorted_by_supplier_code():
    """FR-040 6.20.3：仕入先の選択肢は仕入先コード昇順とする。"""
    second = make_supplier(supplier_code="SUP-B")
    first = make_supplier(supplier_code="SUP-A")

    assert [supplier.pk for supplier in services.list_suppliers()] == [first.pk, second.pk]


# trace: FR-040
def test_search_stock_units_includes_non_public_and_zero_quantity():
    """FR-040 手順5：非公開商品・在庫数量0の在庫単位も対象とする。"""
    public_unit = make_stock_unit(make_item(), sku="SKU-PUB", quantity=3)
    hidden_unit = make_stock_unit(make_item(is_public=False), sku="SKU-HID", quantity=0)

    units, meta, _conditions = services.search_stock_units({})

    assert {unit.pk for unit in units} == {public_unit.pk, hidden_unit.pk}
    assert meta["total_count"] == 2


# trace: FR-040
def test_search_stock_units_filters_by_sku_prefix_ignoring_case():
    """FR-040 手順6：SKU の前方一致（大文字小文字を区別しない）。"""
    target = make_stock_unit(make_item(), sku="KC-0101-BL")
    make_stock_unit(make_item(), sku="ZZ-0101-BL")

    units, _meta, conditions = services.search_stock_units({"sku": " kc-01 "})

    assert [unit.pk for unit in units] == [target.pk]
    assert conditions["sku"] == "kc-01"


# trace: FR-040
def test_search_stock_units_filters_by_item_name_partial_match():
    """FR-040 手順7：商品名の部分一致（大文字小文字を区別しない）。"""
    target = make_stock_unit(make_item(name="Blue Mug"), sku="SKU-TARGET")
    make_stock_unit(make_item(name="赤い皿"), sku="SKU-OTHER")

    units, _meta, _conditions = services.search_stock_units({"item_name": "blue"})

    assert [unit.pk for unit in units] == [target.pk]


# trace: FR-040
def test_search_stock_units_filters_by_supplier():
    """FR-040 手順8：指定した仕入先の在庫単位へ絞り込む。"""
    supplier = make_supplier(supplier_code="SUP-TARGET")
    target = make_stock_unit(make_item(), supplier=supplier, sku="SKU-S1")
    make_stock_unit(make_item(), sku="SKU-S2")

    units, _meta, conditions = services.search_stock_units({"supplier_id": str(supplier.pk)})

    assert [unit.pk for unit in units] == [target.pk]
    assert conditions["supplier_id"] == supplier.pk


# trace: FR-040
@pytest.mark.parametrize(("quantity", "expected_count"), [(5, 1), (6, 0), (0, 1)])
def test_search_stock_units_low_stock_only_uses_threshold_of_five(quantity, expected_count):
    """FR-040 手順9：低在庫のみ＝在庫数量5以下（境界値：5／6／0）。"""
    make_stock_unit(make_item(), sku="SKU-LOW", quantity=quantity)

    units, _meta, conditions = services.search_stock_units({"low_stock_only": "true"})

    assert len(units) == expected_count
    assert conditions["low_stock_only"] is True
    assert LOW_STOCK_THRESHOLD == 5


# trace: FR-040
def test_search_stock_units_ignores_low_stock_filter_when_false():
    """FR-040 手順9：false・0文字の場合は在庫数量で絞り込まない。"""
    make_stock_unit(make_item(), sku="SKU-HIGH", quantity=50)

    units, _meta, conditions = services.search_stock_units({"low_stock_only": "false"})

    assert len(units) == 1
    assert conditions["low_stock_only"] is False


# trace: FR-040
def test_search_stock_units_is_sorted_by_sku_and_paginated_by_50():
    """FR-040 手順10〜11：SKU 昇順・1ページ50件とする。"""
    for index in range(51):
        make_stock_unit(make_item(), sku=f"SKU-{index:03d}")

    units, meta, _conditions = services.search_stock_units({})

    assert [unit.sku for unit in units] == sorted(unit.sku for unit in units)
    assert len(units) == services.STOCK_UNIT_PAGE_SIZE == 50
    assert meta == {"page": 1, "page_size": 50, "total_count": 51, "total_pages": 2}


# trace: FR-040
def test_search_stock_units_reports_every_invalid_condition():
    """E-040-03：条件を満たさない全項目を1回で通知する。"""
    with pytest.raises(ValidationFailed) as error:
        services.search_stock_units(
            {
                "sku": "A" * 33,
                "item_name": "あ" * 101,
                "supplier_id": "999999",
                "low_stock_only": "yes",
                "page": "0",
            }
        )

    assert {detail["field"] for detail in error.value.details} == {
        "sku",
        "item_name",
        "supplier_id",
        "low_stock_only",
        "page",
    }


# trace: FR-040
def test_stock_unit_derived_values_follow_data_requirements():
    """D-06：税込価格・在庫有無・低在庫は保持せず算出する。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=5)

    assert unit.price_incl_tax == 1100
    assert unit.in_stock is True
    assert unit.is_low_stock is True
    assert str(unit) == unit.sku


# trace: FR-011
def test_item_string_representation_uses_item_code():
    """商品・分類・仕入先は業務キーで識別できる。"""
    item = make_item(item_code="ITEM-STR")

    assert str(Item.objects.get(pk=item.pk)) == "ITEM-STR"
