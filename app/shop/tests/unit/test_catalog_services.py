# trace: FR-010, FR-011, FR-012, ADDR-006
"""商品分類一覧・商品一覧検索・商品詳細照会（FR-010〜FR-012）の単体テスト。

期待値は FR-010 6.5.4、FR-011 6.6.4、FR-012 6.7.4 の処理内容から導出する。
"""
from datetime import timedelta

import pytest

from shop.common import timeutils
from shop.common.errors import NotFoundError, ValidationError
from shop.services import catalog
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db


# trace: FR-010
def test_list_collections_returns_depth_first_order(db):
    """商品分類は親子の木構造を深さ優先順（同階層は表示順→分類名）で返す。"""
    books = _helpers.make_collection("books", "書籍", sort_order=1)
    foods = _helpers.make_collection("foods", "食品", sort_order=0)
    novel = _helpers.make_collection("novel", "小説", parent=books, sort_order=0)
    _helpers.make_collection("mystery", "推理", parent=novel, sort_order=0)
    _helpers.make_collection("sweets", "菓子", parent=foods, sort_order=0)

    result = catalog.list_collections()

    assert [row["collection_code"] for row in result] == ["foods", "sweets", "books", "novel", "mystery"]
    assert [row["depth"] for row in result] == [1, 2, 1, 2, 3]
    assert result[0]["parent_collection_id"] is None
    assert result[1]["parent_collection_id"] == foods.collection_id


# trace: FR-010
def test_list_collections_returns_empty_list_when_no_collection(db):
    """商品分類が1件もない場合は空の一覧を返す。"""
    assert catalog.list_collections() == []


# trace: FR-011
def test_search_items_returns_only_public_items_with_stock_units(db, supplier):
    """公開中かつ在庫単位を1件以上持つ商品だけを返す。"""
    public_item = _helpers.make_item("ITEM-001", "公開商品")
    _helpers.make_stock_unit(public_item, supplier, sku="SKU-001", quantity=0)
    private_item = _helpers.make_item("ITEM-002", "非公開商品", is_public=False)
    _helpers.make_stock_unit(private_item, supplier, sku="SKU-002")
    _helpers.make_item("ITEM-003", "在庫単位なし商品")

    result = catalog.search_items()

    assert [row["item_code"] for row in result["results"]] == ["ITEM-001"]
    assert result["total_count"] == 1
    assert result["page_size"] == 20


# trace: FR-011
def test_search_items_reports_in_stock_flag(db, supplier):
    """在庫数量1以上の在庫単位を1件以上持つ場合のみ在庫ありとする。"""
    in_stock = _helpers.make_item("ITEM-001", "在庫あり商品")
    _helpers.make_stock_unit(in_stock, supplier, sku="SKU-001", quantity=1)
    out_of_stock = _helpers.make_item("ITEM-002", "在庫なし商品")
    _helpers.make_stock_unit(out_of_stock, supplier, sku="SKU-002", quantity=0)

    rows = {row["item_code"]: row for row in catalog.search_items()["results"]}

    assert rows["ITEM-001"]["in_stock"] is True
    assert rows["ITEM-002"]["in_stock"] is False


# trace: FR-011
def test_search_items_returns_min_price_and_tax_included_price(db, supplier):
    """最低税抜価格とその税込価格（1円未満切り捨て）を返す。"""
    item = _helpers.make_item("ITEM-001", "商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001", price=1500)
    _helpers.make_stock_unit(item, supplier, sku="SKU-002", price=999)

    row = catalog.search_items()["results"][0]

    assert row["min_price"] == 999
    assert row["min_price_incl_tax"] == 1098


# trace: FR-011
def test_search_items_filters_by_collection_including_descendants(db, supplier):
    """分類IDを指定した場合は配下のすべての分類に所属する商品も含める。"""
    books = _helpers.make_collection("books", "書籍")
    novel = _helpers.make_collection("novel", "小説", parent=books)
    mystery = _helpers.make_collection("mystery", "推理", parent=novel)
    foods = _helpers.make_collection("foods", "食品")

    for code, collection in (("ITEM-001", books), ("ITEM-002", novel), ("ITEM-003", mystery), ("ITEM-004", foods)):
        item = _helpers.make_item(code, f"商品{code}", collections=[collection])
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{code}")

    result = catalog.search_items(raw_collection_id=books.collection_id)

    assert sorted(row["item_code"] for row in result["results"]) == ["ITEM-001", "ITEM-002", "ITEM-003"]


# trace: FR-011
def test_search_items_returns_collections_of_each_item(db, supplier):
    """各商品の所属分類（分類ID・分類名）を返す。"""
    books = _helpers.make_collection("books", "書籍")
    item = _helpers.make_item("ITEM-001", "商品", collections=[books])
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    row = catalog.search_items()["results"][0]

    assert row["collections"] == [{"collection_id": books.collection_id, "name": "書籍"}]


# trace: FR-011
@pytest.mark.parametrize("keyword", ["カメラ", "かめら用", "ＫＥＹ"])
def test_search_items_filters_by_keyword_partial_match(db, supplier, keyword):
    """キーワードは商品名または商品説明の部分一致で絞り込む。"""
    target = _helpers.make_item("ITEM-001", "デジタルカメラ", description="かめら用の説明ＫＥＹ")
    _helpers.make_stock_unit(target, supplier, sku="SKU-001")
    other = _helpers.make_item("ITEM-002", "書籍", description="説明")
    _helpers.make_stock_unit(other, supplier, sku="SKU-002")

    result = catalog.search_items(raw_keyword=keyword)

    assert [row["item_code"] for row in result["results"]] == ["ITEM-001"]


# trace: FR-011
def test_search_items_keyword_is_case_insensitive(db, supplier):
    """キーワードの英字は大文字・小文字を区別しない。"""
    item = _helpers.make_item("ITEM-001", "Camera Bag")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    assert catalog.search_items(raw_keyword="camera")["total_count"] == 1
    assert catalog.search_items(raw_keyword="CAMERA")["total_count"] == 1


# trace: FR-011
def test_search_items_ignores_blank_keyword(db, supplier):
    """前後空白だけのキーワードは絞り込みに用いない（CMN-15）。"""
    item = _helpers.make_item("ITEM-001", "商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    assert catalog.search_items(raw_keyword="   ")["total_count"] == 1


# trace: FR-011
def test_search_items_sorts_by_requested_order(db, supplier):
    """並び順（新着順・価格の安い順・価格の高い順・商品名順）に従って並べる。"""
    now = timeutils.now()
    first = _helpers.make_item("ITEM-001", "B商品", created_at=now - timedelta(days=2))
    _helpers.make_stock_unit(first, supplier, sku="SKU-001", price=300)
    second = _helpers.make_item("ITEM-002", "A商品", created_at=now - timedelta(days=1))
    _helpers.make_stock_unit(second, supplier, sku="SKU-002", price=200)
    third = _helpers.make_item("ITEM-003", "C商品", created_at=now)
    _helpers.make_stock_unit(third, supplier, sku="SKU-003", price=100)

    def codes(sort):
        return [row["item_code"] for row in catalog.search_items(raw_sort=sort)["results"]]

    assert codes(catalog.SORT_NEW) == ["ITEM-003", "ITEM-002", "ITEM-001"]
    assert codes(catalog.SORT_PRICE_ASC) == ["ITEM-003", "ITEM-002", "ITEM-001"]
    assert codes(catalog.SORT_PRICE_DESC) == ["ITEM-001", "ITEM-002", "ITEM-003"]
    assert codes(catalog.SORT_NAME) == ["ITEM-002", "ITEM-001", "ITEM-003"]


# trace: FR-011
def test_search_items_defaults_to_newest_order(db, supplier):
    """並び順を省略した場合は新着順とする。"""
    now = timeutils.now()
    old = _helpers.make_item("ITEM-001", "旧商品", created_at=now - timedelta(days=1))
    _helpers.make_stock_unit(old, supplier, sku="SKU-001")
    new = _helpers.make_item("ITEM-002", "新商品", created_at=now)
    _helpers.make_stock_unit(new, supplier, sku="SKU-002")

    assert [row["item_code"] for row in catalog.search_items()["results"]] == ["ITEM-002", "ITEM-001"]


# trace: FR-011
def test_search_items_paginates_20_per_page(db, supplier):
    """1ページ20件で総件数・総ページ数を返す。"""
    for index in range(21):
        item = _helpers.make_item(f"ITEM-{index:03d}", f"商品{index:03d}")
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{index:03d}")

    first_page = catalog.search_items(raw_sort=catalog.SORT_NAME)
    second_page = catalog.search_items(raw_sort=catalog.SORT_NAME, raw_page=2)

    assert len(first_page["results"]) == 20
    assert first_page["total_count"] == 21
    assert first_page["total_pages"] == 2
    assert len(second_page["results"]) == 1
    assert second_page["page"] == 2


# trace: FR-011
def test_search_items_returns_empty_page_beyond_total_pages(db, supplier):
    """総ページ数を超えるページ番号はエラーにせず0件を返す。"""
    item = _helpers.make_item("ITEM-001", "商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    result = catalog.search_items(raw_page=3)

    assert result["results"] == []
    assert result["total_count"] == 1
    assert result["total_pages"] == 1


# trace: FR-011
def test_search_items_returns_zero_total_pages_when_no_match(db):
    """該当0件の場合は総件数0・総ページ数0を返す。"""
    result = catalog.search_items()

    assert (result["total_count"], result["total_pages"], result["results"]) == (0, 0, [])


# trace: FR-011
@pytest.mark.parametrize(
    ("kwargs", "expected_field"),
    [
        ({"raw_collection_id": "999999"}, "collection_id"),
        ({"raw_collection_id": "abc"}, "collection_id"),
        ({"raw_keyword": "あ" * 51}, "keyword"),
        ({"raw_sort": "unknown"}, "sort"),
        ({"raw_page": "0"}, "page"),
        ({"raw_page": "-1"}, "page"),
        ({"raw_page": "abc"}, "page"),
    ],
)
def test_search_items_rejects_invalid_conditions(db, kwargs, expected_field):
    """検索条件が条件を満たさない場合は入力エラーとする（E-011-01）。"""
    with pytest.raises(ValidationError) as exc:
        catalog.search_items(**kwargs)

    assert any(detail["field"] == expected_field for detail in exc.value.details)
    assert exc.value.http_status == 400


# trace: FR-011
def test_search_items_keyword_length_boundary(db, supplier):
    """キーワードは50文字まで受け付ける（境界値）。"""
    keyword = "あ" * 50
    item = _helpers.make_item("ITEM-001", keyword)
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    assert catalog.search_items(raw_keyword=keyword)["total_count"] == 1


# trace: FR-011
def test_search_items_reports_all_invalid_conditions_at_once(db):
    """複数の検索条件の不備を1回でまとめて通知する。"""
    with pytest.raises(ValidationError) as exc:
        catalog.search_items(raw_collection_id="abc", raw_keyword="あ" * 51, raw_sort="x", raw_page="0")

    assert {detail["field"] for detail in exc.value.details} == {"collection_id", "keyword", "sort", "page"}


# trace: FR-011
def test_search_items_accepts_page_one_boundary(db, supplier):
    """ページ番号の下限は1である（境界値）。"""
    item = _helpers.make_item("ITEM-001", "商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    assert catalog.search_items(raw_page="1")["page"] == 1


# trace: FR-012
def test_get_item_detail_returns_item_and_stock_units_in_sku_order(db, supplier):
    """商品詳細は在庫単位を SKU 昇順で返し、仕入先情報を含めない。"""
    item = _helpers.make_item("ITEM-001", "商品", description="説明")
    _helpers.make_stock_unit(item, supplier, sku="SKU-B", price=1000, quantity=0)
    _helpers.make_stock_unit(item, supplier, sku="SKU-A", price=999, quantity=3)

    detail = catalog.get_item_detail(item.item_id)

    assert detail["item_code"] == "ITEM-001"
    assert detail["description"] == "説明"
    assert [unit["sku"] for unit in detail["stock_units"]] == ["SKU-A", "SKU-B"]
    assert detail["stock_units"][0]["price_incl_tax"] == 1098
    assert detail["stock_units"][0]["in_stock"] is True
    assert detail["stock_units"][1]["in_stock"] is False
    assert "supplier_id" not in detail["stock_units"][0]


# trace: FR-012
def test_get_item_detail_rejects_private_item(db, supplier):
    """非公開の商品は対象なしとする（E-012-01）。"""
    item = _helpers.make_item("ITEM-001", "非公開商品", is_public=False)
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    with pytest.raises(NotFoundError) as exc:
        catalog.get_item_detail(item.item_id)

    assert exc.value.http_status == 404


# trace: FR-012
def test_get_item_detail_rejects_item_without_stock_unit(db):
    """在庫単位を1件も持たない商品は対象なしとする。"""
    item = _helpers.make_item("ITEM-001", "在庫単位なし")

    with pytest.raises(NotFoundError):
        catalog.get_item_detail(item.item_id)


# trace: FR-012
@pytest.mark.parametrize("raw_item_id", ["abc", "", None, "999999"])
def test_get_item_detail_rejects_unknown_identifier(db, raw_item_id):
    """識別子として解釈できない値・存在しない商品IDは対象なしとする。"""
    with pytest.raises(NotFoundError):
        catalog.get_item_detail(raw_item_id)


# trace: FR-012
def test_get_item_detail_returns_collections(db, supplier):
    """商品詳細は所属分類（分類ID・分類名）を返す。"""
    books = _helpers.make_collection("books", "書籍")
    item = _helpers.make_item("ITEM-001", "商品", collections=[books])
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    detail = catalog.get_item_detail(item.item_id)

    assert detail["collections"] == [{"collection_id": books.collection_id, "name": "書籍"}]
