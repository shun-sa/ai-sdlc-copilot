# trace: FR-010, FR-011, FR-012, ADDR-006, ADDR-007
"""商品カタログ参照（FR-010〜FR-012）の結合試験。

期待結果は機能要件定義書 6.5〜6.7（処理内容・検索仕様・例外）と
api-contract 6.1〜6.2、ADDR-006・ADDR-007 から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from tests.integration import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-010, ADDR-006
@pytest.mark.case("IT-AI-012")
def test_collection_list_returns_tree_order_without_auth(api):
    """商品分類一覧は認証不要で、親子の木構造の深さ優先順に全件返す（FR-010 手順2）。"""
    parent_b = _helpers.make_collection(collection_code="b-parent", name="家電", sort_order=5)
    parent_a = _helpers.make_collection(collection_code="a-parent", name="書籍", sort_order=10)
    child_a2 = _helpers.make_collection(collection_code="a-child2", name="技術書", parent=parent_a, sort_order=0)
    child_a1 = _helpers.make_collection(collection_code="a-child1", name="雑誌", parent=parent_a, sort_order=1)

    response = api.get("/api/collections")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert [row["collection_id"] for row in body] == [
        parent_b.collection_id,
        parent_a.collection_id,
        child_a2.collection_id,
        child_a1.collection_id,
    ]
    assert body[0]["parent_collection_id"] is None
    assert body[2]["parent_collection_id"] == parent_a.collection_id
    assert body[2]["depth"] == 2
    assert set(body[0]) == {"collection_id", "collection_code", "name", "parent_collection_id", "depth", "sort_order"}


# trace: FR-011, ADDR-006
@pytest.mark.case("IT-AI-013")
def test_item_search_returns_public_items_with_stock_units_in_new_order(api):
    """商品一覧検索は公開かつ在庫単位を持つ商品のみを新着順・20件/ページで返す（FR-011 手順3・7・8）。"""
    supplier = _helpers.make_supplier()
    collection = _helpers.make_collection()
    base = timeutils.now()
    items = []
    for index in range(21):
        item = _helpers.make_item(
            item_code=f"ITEM-{index:03d}",
            name=f"商品{index:03d}",
            created_at=base - timedelta(minutes=index),
            collections=[collection],
        )
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{index:03d}", price=1000 + index, quantity=index)
        items.append(item)
    hidden = _helpers.make_item(item_code="ITEM-HID", name="非公開商品", is_public=False, created_at=base)
    _helpers.make_stock_unit(hidden, supplier, sku="SKU-HID")
    _helpers.make_item(item_code="ITEM-NOSU", name="在庫単位なし商品", created_at=base)

    first = api.get("/api/items")
    second = api.get("/api/items", {"page": "2"})

    assert first.status_code == 200
    body = first.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_count"] == 21
    assert body["total_pages"] == 2
    returned_ids = [row["item_id"] for row in body["results"]]
    assert returned_ids == [item.item_id for item in items[:20]]
    assert hidden.item_id not in returned_ids

    head = body["results"][0]
    assert head["min_price"] == 1000
    assert head["min_price_incl_tax"] == 1000 * 110 // 100
    assert head["in_stock"] is False
    assert head["collections"] == [{"collection_id": collection.collection_id, "name": collection.name}]
    assert body["results"][1]["in_stock"] is True

    assert [row["item_id"] for row in second.json()["results"]] == [items[20].item_id]


# trace: FR-011, ADDR-006
@pytest.mark.case("IT-AI-014")
def test_item_search_combines_collection_and_keyword(api):
    """分類ID（配下分類を含む）とキーワードはANDで評価される（FR-011 手順4・5）。"""
    supplier = _helpers.make_supplier()
    parent = _helpers.make_collection(collection_code="parent", name="親分類")
    child = _helpers.make_collection(collection_code="child", name="子分類", parent=parent)
    other = _helpers.make_collection(collection_code="other", name="別分類")

    in_child = _helpers.make_item(item_code="ITEM-A", name="Sample ノート", collections=[child])
    in_parent = _helpers.make_item(
        item_code="ITEM-B", name="ペン", description="sample の説明文", collections=[parent]
    )
    in_parent_no_keyword = _helpers.make_item(item_code="ITEM-C", name="消しゴム", collections=[parent])
    outside = _helpers.make_item(item_code="ITEM-D", name="SAMPLE 定規", collections=[other])
    for index, item in enumerate([in_child, in_parent, in_parent_no_keyword, outside]):
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{index:03d}")

    by_collection = api.get("/api/items", {"collection_id": str(parent.collection_id)})
    by_both = api.get("/api/items", {"collection_id": str(parent.collection_id), "keyword": "SaMpLe"})

    assert by_collection.status_code == 200
    assert {row["item_id"] for row in by_collection.json()["results"]} == {
        in_child.item_id,
        in_parent.item_id,
        in_parent_no_keyword.item_id,
    }
    assert {row["item_id"] for row in by_both.json()["results"]} == {in_child.item_id, in_parent.item_id}
    assert outside.item_id not in {row["item_id"] for row in by_both.json()["results"]}


# trace: FR-011, ADDR-006
@pytest.mark.case("IT-AI-015")
def test_item_search_applies_four_sort_orders(api):
    """並び順4種が FR-011 手順7 のとおり適用される。"""
    supplier = _helpers.make_supplier()
    base = timeutils.now()
    cheap_new = _helpers.make_item(item_code="ITEM-A", name="A商品", created_at=base)
    mid_old = _helpers.make_item(item_code="ITEM-B", name="C商品", created_at=base - timedelta(minutes=2))
    high_mid = _helpers.make_item(item_code="ITEM-C", name="B商品", created_at=base - timedelta(minutes=1))
    _helpers.make_stock_unit(cheap_new, supplier, sku="SKU-A", price=500)
    _helpers.make_stock_unit(mid_old, supplier, sku="SKU-B", price=1500)
    _helpers.make_stock_unit(high_mid, supplier, sku="SKU-C", price=3000)

    def ids(sort):
        """指定した並び順の商品IDの並びを返す。"""
        response = api.get("/api/items", {"sort": sort})
        assert response.status_code == 200
        return [row["item_id"] for row in response.json()["results"]]

    assert ids("new") == [cheap_new.item_id, high_mid.item_id, mid_old.item_id]
    assert ids("price_asc") == [cheap_new.item_id, mid_old.item_id, high_mid.item_id]
    assert ids("price_desc") == [high_mid.item_id, mid_old.item_id, cheap_new.item_id]
    assert ids("name") == [cheap_new.item_id, high_mid.item_id, mid_old.item_id]


# trace: FR-011, ADDR-007
@pytest.mark.case("IT-AI-016")
def test_item_search_rejects_invalid_conditions(api):
    """不正な検索条件は条件を満たさない全項目を通知する入力エラーとなる（E-011-01）。"""
    response = api.get(
        "/api/items",
        {"collection_id": "999999", "keyword": "あ" * 51, "sort": "unknown", "page": "0"},
    )

    assert response.status_code == 400
    assert _helpers.error_code(response) == "VALIDATION_ERROR"
    assert _helpers.error_fields(response) == {"collection_id", "keyword", "sort", "page"}


# trace: FR-012, ADDR-006
@pytest.mark.case("IT-AI-017")
def test_item_detail_returns_stock_units_in_sku_order(api):
    """商品詳細は在庫単位をSKU昇順で税込価格つきに返す（FR-012 手順3）。"""
    supplier = _helpers.make_supplier()
    collection = _helpers.make_collection()
    item = _helpers.make_item(collections=[collection])
    second = _helpers.make_stock_unit(item, supplier, sku="SKU-B", variant_name="大", price=1999, quantity=0)
    first = _helpers.make_stock_unit(item, supplier, sku="SKU-A", variant_name="小", price=1000, quantity=3)

    response = api.get(f"/api/items/{item.item_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item.item_id
    assert body["description"] == item.description
    assert body["collections"] == [{"collection_id": collection.collection_id, "name": collection.name}]
    assert [unit["stock_unit_id"] for unit in body["stock_units"]] == [first.stock_unit_id, second.stock_unit_id]
    assert body["stock_units"][0] == {
        "stock_unit_id": first.stock_unit_id,
        "sku": "SKU-A",
        "variant_name": "小",
        "price": 1000,
        "price_incl_tax": 1100,
        "quantity": 3,
        "in_stock": True,
    }
    assert body["stock_units"][1]["price_incl_tax"] == 1999 * 110 // 100
    assert body["stock_units"][1]["in_stock"] is False


# trace: FR-012, ADDR-007
@pytest.mark.case("IT-AI-018")
def test_item_detail_hides_existence_of_private_and_unknown_items(api):
    """非公開商品・存在しない商品ID・解釈できない値はいずれも対象なしエラーとなる（CMN-18、ERR-06）。"""
    supplier = _helpers.make_supplier()
    hidden = _helpers.make_item(item_code="ITEM-HID", name="非公開商品", is_public=False)
    _helpers.make_stock_unit(hidden, supplier, sku="SKU-HID")

    private = api.get(f"/api/items/{hidden.item_id}")
    unknown = api.get("/api/items/999999")
    malformed = api.get("/api/items/not-an-id")

    assert private.status_code == 404
    assert unknown.status_code == 404
    assert malformed.status_code == 404
    assert _helpers.error_code(private) == "NOT_FOUND"
    assert private.json()["error"] == unknown.json()["error"] == malformed.json()["error"]


# trace: FR-011, ADDR-006
@pytest.mark.case("IT-AI-GF-001")
def test_item_search_page_over_total_and_zero_hit_are_not_errors(api):
    """総ページ数超過・該当0件はエラーとせず0件の一覧を返す（FR-011 手順8、CMN-35）。"""
    supplier = _helpers.make_supplier()
    item = _helpers.make_item()
    _helpers.make_stock_unit(item, supplier)

    over_page = api.get("/api/items", {"page": "5"})
    zero_hit = api.get("/api/items", {"keyword": "該当しないキーワード"})

    assert over_page.status_code == 200
    assert over_page.json()["results"] == []
    assert over_page.json()["page"] == 5
    assert over_page.json()["total_count"] == 1
    assert over_page.json()["total_pages"] == 1

    assert zero_hit.status_code == 200
    assert zero_hit.json()["results"] == []
    assert zero_hit.json()["total_count"] == 0
    assert zero_hit.json()["total_pages"] == 0
