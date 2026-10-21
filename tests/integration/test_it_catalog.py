# trace: FR-010, FR-011, FR-012, FR-021, NFR-EN-04, NFR-PF-08
# trace: ADDR-006, ADDR-008, ADDR-010, ADDR-011
"""商品分類・商品一覧・商品詳細の結合試験（IT-AI-INIT-033〜045）。

検証対象の連携は API(DRF View) → Serializer → Service → ORM → PostgreSQL、
商品分類階層 → 商品検索 → DB、共通ページング基盤 → 一覧API、画面 → Service → DB。

期待結果は FR-010〜FR-012 の処理内容・出力・例外、CMN-18/CMN-30/CMN-32/CMN-35/CMN-36、
提供済みAPI契約 6.1（ページング形式・認証不要API）、ADDR-008（算出項目は参照時に算出）
から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest

from common import timeutils

pytestmark = pytest.mark.django_db


# trace: FR-010, NFR-PF-08
def test_it_ai_init_033_collection_list_returns_all_without_paging(api, f):
    """IT-AI-INIT-033 / COV-035：商品分類一覧はページングなしの全件配列を階層順で返す。"""
    parent = f.collection(collection_code="cat-parent", name="親分類", sort_order=1)
    child = f.collection(collection_code="cat-child", name="子分類", parent=parent, sort_order=1)
    grandchild = f.collection(collection_code="cat-grand", name="孫分類", parent=child, sort_order=1)
    second = f.collection(collection_code="cat-second", name="次の親", sort_order=2)

    response = api.get("/api/collections")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert [item["collection_id"] for item in body] == [parent.pk, child.pk, grandchild.pk, second.pk]
    assert [item["depth"] for item in body] == [1, 2, 3, 1]
    assert body[1]["parent_collection_id"] == parent.pk
    assert body[0]["name"] == "親分類"


# trace: FR-010
def test_it_ai_init_033b_collection_list_is_empty_array_without_data(api):
    """IT-AI-INIT-033 / COV-035：商品分類が0件の場合は空配列を返す。"""
    response = api.get("/api/collections")

    assert response.status_code == 200
    assert response.json() == []


# trace: FR-011
def test_it_ai_init_034_item_list_returns_public_items_with_stock_units(api, f):
    """IT-AI-INIT-034 / COV-036：公開かつ在庫単位を持つ商品だけを返し、全数量0は in_stock=false とする。"""
    visible = f.item(name="公開在庫あり商品")
    f.stock_unit(visible, price=1000, quantity=3)
    zero_stock = f.item(name="公開在庫なし商品")
    f.stock_unit(zero_stock, price=2000, quantity=0)
    hidden = f.item(name="非公開商品", is_public=False)
    f.stock_unit(hidden, price=3000, quantity=5)
    f.item(name="在庫単位なし商品")

    response = api.get("/api/items")

    assert response.status_code == 200
    results = {item["item_id"]: item for item in response.json()["results"]}
    assert set(results) == {visible.pk, zero_stock.pk}
    assert results[visible.pk]["in_stock"] is True
    assert results[zero_stock.pk]["in_stock"] is False


# trace: FR-011
def test_it_ai_init_035_collection_filter_includes_descendants_without_duplicates(api, f):
    """IT-AI-INIT-035 / COV-037：分類指定は配下の全階層を重複なく含み、キーワードと AND になる。"""
    parent = f.collection(name="家電")
    child = f.collection(name="生活家電", parent=parent)
    grandchild = f.collection(name="掃除機", parent=child)
    on_parent = f.item(name="親分類ノート", collections=[parent])
    on_child = f.item(name="子分類ノート", collections=[child])
    on_grandchild = f.item(name="孫分類メモ", collections=[grandchild])
    multiple = f.item(name="重複所属ノート", collections=[parent, child, grandchild])
    outside = f.item(name="対象外ノート", collections=[f.collection(name="書籍")])
    for item in (on_parent, on_child, on_grandchild, multiple, outside):
        f.stock_unit(item, price=1000, quantity=2)

    filtered = api.get(f"/api/items?collection_id={parent.pk}")
    combined = api.get(f"/api/items?collection_id={parent.pk}&keyword=ノート")

    assert filtered.status_code == 200
    ids = [item["item_id"] for item in filtered.json()["results"]]
    assert sorted(ids) == sorted([on_parent.pk, on_child.pk, on_grandchild.pk, multiple.pk])
    assert len(ids) == len(set(ids))
    assert filtered.json()["total_count"] == 4
    assert sorted(item["item_id"] for item in combined.json()["results"]) == sorted(
        [on_parent.pk, on_child.pk, multiple.pk]
    )


# trace: FR-011
def test_it_ai_init_036_keyword_is_trimmed_and_case_insensitive(api, f):
    """IT-AI-INIT-036 / COV-038：キーワードは前後空白除去・大文字小文字非区別の部分一致で絞り込む。"""
    by_name = f.item(name="Note PC", description="説明")
    by_description = f.item(name="周辺機器", description="NOTE 用スタンド")
    symbol = f.item(name="型番 A-100%", description="記号入り")
    other = f.item(name="関係ない商品", description="対象外")
    for item in (by_name, by_description, symbol, other):
        f.stock_unit(item, price=1000, quantity=1)

    expected = sorted([by_name.pk, by_description.pk])
    for keyword in ("  Note  ", "note", "NOTE"):
        response = api.get("/api/items", {"keyword": keyword})
        assert response.status_code == 200
        assert sorted(item["item_id"] for item in response.json()["results"]) == expected, keyword

    symbol_response = api.get("/api/items", {"keyword": "A-100%"})
    assert [item["item_id"] for item in symbol_response.json()["results"]] == [symbol.pk]


# trace: FR-011
def test_it_ai_init_037_item_list_sort_orders(api, f):
    """IT-AI-INIT-037 / COV-039：4種の並び順と同値時の商品ID順で並べる。"""
    base = timeutils.now()
    older = f.item(name="BBB商品", created_at=base - dt.timedelta(days=1))
    newer_first = f.item(name="AAA商品", created_at=base)
    newer_second = f.item(name="AAA商品", created_at=base)
    f.stock_unit(older, price=3000, quantity=1)
    f.stock_unit(newer_first, price=1000, quantity=1)
    f.stock_unit(newer_second, price=1000, quantity=1)

    def ids(sort: str) -> list[int]:
        response = api.get("/api/items", {"sort": sort})
        assert response.status_code == 200
        return [item["item_id"] for item in response.json()["results"]]

    assert ids("new") == [newer_second.pk, newer_first.pk, older.pk]
    assert ids("price_asc") == [newer_first.pk, newer_second.pk, older.pk]
    assert ids("price_desc") == [older.pk, newer_first.pk, newer_second.pk]
    assert ids("name") == [newer_first.pk, newer_second.pk, older.pk]
    assert ids("new") == [item["item_id"] for item in api.get("/api/items").json()["results"]]


# trace: FR-011, NFR-PF-08
def test_it_ai_init_038_item_list_pagination(api, f):
    """IT-AI-INIT-038 / COV-040：商品一覧は1ページ20件で、総ページ数超過は空配列を返す（CMN-35）。"""
    for index in range(21):
        item = f.item(name=f"ページング商品{index:02d}")
        f.stock_unit(item, price=1000 + index, quantity=1)

    first = api.get("/api/items").json()
    second = api.get("/api/items", {"page": 2}).json()
    beyond = api.get("/api/items", {"page": 3})

    assert first["page"] == 1 and first["page_size"] == 20
    assert first["total_count"] == 21 and first["total_pages"] == 2
    assert len(first["results"]) == 20
    assert len(second["results"]) == 1
    assert beyond.status_code == 200
    assert beyond.json()["results"] == []
    assert beyond.json()["total_count"] == 21


# trace: FR-011, ADDR-011
def test_it_ai_init_039_item_list_rejects_invalid_conditions(api, f, err):
    """IT-AI-INIT-039 / COV-041：不正な検索条件は入力エラーとし、複数不備は全項目を列挙する。"""
    collection = f.collection(name="検索条件分類")
    item = f.item(name="検索条件商品", collections=[collection])
    f.stock_unit(item, price=1000, quantity=1)

    single_cases = [
        ({"sort": "invalid"}, "sort"),
        ({"page": 0}, "page"),
        ({"page": "abc"}, "page"),
        ({"collection_id": 999999}, "collection_id"),
        ({"collection_id": "abc"}, "collection_id"),
        ({"keyword": "あ" * 51}, "keyword"),
    ]
    for params, field in single_cases:
        response = api.get("/api/items", params)
        assert response.status_code == 400, params
        assert err.code(response) == "VALIDATION_ERROR"
        assert field in err.fields(response)

    combined = api.get("/api/items", {"sort": "invalid", "page": 0, "keyword": "あ" * 51})
    assert combined.status_code == 400
    assert set(err.fields(combined)) >= {"sort", "page", "keyword"}

    ok = api.get("/api/items", {"keyword": "あ" * 50})
    assert ok.status_code == 200


# trace: FR-011
def test_it_ai_init_040_min_price_and_tax_are_calculated(api, f):
    """IT-AI-INIT-040 / COV-039：最低価格と最低税込価格（×110÷100の1円未満切り捨て）を返す。"""
    item = f.item(name="税計算商品")
    f.stock_unit(item, price=1500, quantity=2)
    f.stock_unit(item, price=999, quantity=2)

    response = api.get("/api/items")

    summary = next(row for row in response.json()["results"] if row["item_id"] == item.pk)
    assert summary["min_price"] == 999
    assert summary["min_price_incl_tax"] == 1098


# trace: FR-012
def test_it_ai_init_041_item_detail_lists_stock_units_by_sku(api, f):
    """IT-AI-INIT-041 / COV-042：商品詳細は在庫単位をSKU昇順で返し、仕入先情報を含めない。"""
    collection = f.collection(name="詳細分類")
    item = f.item(name="詳細商品", description="説明本文", collections=[collection])
    f.stock_unit(item, sku="SKU-B", variant_name="青", price=2000, quantity=0)
    f.stock_unit(item, sku="SKU-A", variant_name="赤", price=1000, quantity=3)

    response = api.get(f"/api/items/{item.pk}")

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == item.pk
    assert body["name"] == "詳細商品"
    assert body["collections"] == [{"collection_id": collection.pk, "name": "詳細分類"}]
    assert [unit["sku"] for unit in body["stock_units"]] == ["SKU-A", "SKU-B"]
    first = body["stock_units"][0]
    assert first["variant_name"] == "赤"
    assert first["price"] == 1000
    assert first["price_incl_tax"] == 1100
    assert first["quantity"] == 3
    assert first["in_stock"] is True
    assert body["stock_units"][1]["in_stock"] is False
    assert "supplier_id" not in first and "supplier_name" not in first
    assert "supplier" not in str(body)


# trace: FR-012
def test_it_ai_init_042_item_detail_hides_unavailable_items(api, f, err):
    """IT-AI-INIT-042 / COV-043：非公開・在庫単位なし・存在しない商品は対象なしとする（CMN-18）。"""
    hidden = f.item(name="非公開詳細", is_public=False)
    f.stock_unit(hidden, price=1000, quantity=1)
    without_units = f.item(name="在庫単位なし詳細")

    responses = [
        api.get(f"/api/items/{hidden.pk}"),
        api.get(f"/api/items/{without_units.pk}"),
        api.get("/api/items/999999"),
        api.get("/api/items/abc"),
    ]

    messages = set()
    for response in responses:
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"
        messages.add(err.message(response))
    assert len(messages) == 1


# trace: FR-011, FR-012
def test_it_ai_init_043_catalog_is_same_for_every_role(api, api_as, buyer, admin_user, f):
    """IT-AI-INIT-043 / COV-044：商品一覧・詳細は認証状態によらず同一の結果を返す。"""
    item = f.item(name="共通表示商品")
    f.stock_unit(item, price=1000, quantity=1)
    clients = [api, api_as(buyer), api_as(admin_user)]

    list_bodies = [client.get("/api/items").json() for client in clients]
    detail_bodies = [client.get(f"/api/items/{item.pk}").json() for client in clients]

    assert all(body == list_bodies[0] for body in list_bodies)
    assert all(body == detail_bodies[0] for body in detail_bodies)
    assert list_bodies[0]["total_count"] == 1


# trace: FR-011, FR-012, ADDR-010
def test_it_ai_init_044_screens_show_catalog_with_tax_and_paging(screen, f):
    """IT-AI-INIT-044 / COV-045：画面は税込価格を主に税抜を併記し、ページ移動できる。"""
    for index in range(21):
        item = f.item(name=f"画面商品{index:02d}")
        f.stock_unit(item, price=1000, quantity=2)
    detail_item = f.item(name="画面詳細商品")
    f.stock_unit(detail_item, sku="SKU-SCREEN", variant_name="青", price=2000, quantity=3)

    first_page = screen.get("/")
    second_page = screen.get("/?page=2")
    detail = screen.get(f"/items/{detail_item.pk}/")

    assert first_page.status_code == 200
    body = first_page.content.decode()
    assert "1,100円" in body and "1,000円" in body
    assert "在庫あり" in body
    assert "page=2" in body
    assert second_page.status_code == 200
    assert "画面商品" in second_page.content.decode()

    detail_body = detail.content.decode()
    assert detail.status_code == 200
    assert "SKU-SCREEN" in detail_body
    assert "2,200円" in detail_body and "2,000円" in detail_body
    assert "在庫あり" in detail_body


# trace: FR-012, FR-021, ADDR-006
def test_it_ai_init_045_anonymous_add_to_cart_returns_to_item_detail(screen, f):
    """IT-AI-INIT-045 / COV-046：未ログインのカート投入はログイン画面へ誘導し、ログイン後に元の画面へ戻す（CMN-02）。"""
    item = f.item(name="未ログイン投入商品")
    unit = f.stock_unit(item, price=1000, quantity=5)
    buyer = f.user(email="return-path@example.test", password="Passw0rdA")

    attempt = screen.post("/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": unit.pk, "quantity": 1})

    assert attempt.status_code == 302
    assert attempt["Location"] == "/login/"

    login = screen.post("/login/", {"email": buyer.email, "password": "Passw0rdA"})

    assert login.status_code == 302
    assert login["Location"] == f"/items/{item.pk}/"
    assert not buyer.carts.exists()
