# trace: FR-010, FR-011, FR-012, ADDR-001, ADDR-006, ADDR-012
"""結合試験：商品カタログ（Web API／画面→業務処理→DB）。

IT-011〜IT-015（AI INITIAL）。期待結果は FR-010〜FR-012、CMN-18/32/35/36/39、UI-25、MSG-04、
ADDR-001（項目キー・ページング・検索条件の外部値）から導出する。
"""

from datetime import timedelta

import pytest

from tests.integration._helpers import api, body, error_of, field_names, jst, text

pytestmark = pytest.mark.django_db


# trace: FR-010, ADDR-001
def test_it_011_category_tree_order(api_client, catalog):
    """IT-011 商品分類一覧の木構造順・階層。"""
    a = catalog.category("A", display_order=2)
    b = catalog.category("B", display_order=1)
    c = catalog.category("C", display_order=1)
    b1 = catalog.category("B1", parent=b, display_order=1)
    b2 = catalog.category("B2", parent=b, display_order=0)
    b2a = catalog.category("B2a", parent=b2, display_order=5)

    response = api(api_client, "get", "/api/categories/")
    assert response.status_code == 200
    items = body(response)["items"]
    assert [i["category_id"] for i in items] == [b.pk, b2.pk, b2a.pk, b1.pk, c.pk, a.pk]
    by_id = {i["category_id"]: i for i in items}
    assert by_id[b2a.pk]["depth"] == 3 and by_id[b2a.pk]["parent_category_id"] == b2.pk
    assert by_id[b.pk]["depth"] == 1 and by_id[b.pk]["parent_category_id"] is None
    assert by_id[b1.pk]["display_order"] == 1 and by_id[b1.pk]["name"] == "B1"


# trace: FR-011, ADDR-001
def test_it_012_product_search_filter_sort_paging(api_client, catalog):
    """IT-012 商品一覧検索の対象・分類配下・キーワード・並び順・ページング。"""
    parent = catalog.category("親")
    child = catalog.category("子", parent=parent)
    grand = catalog.category("孫", parent=child)
    other = catalog.category("他")
    supplier = catalog.supplier()
    expected = []  # (product, min_price, registered_at, name)
    for i in range(1, 24):
        if i <= 3:
            cats = (parent,)
        elif i <= 5:
            cats = (child,)
        elif i == 6:
            cats = (grand,)
        elif i == 7:
            cats = (child, grand)
        else:
            cats = (other,)
        name = "Ceramic MUG" if i == 8 else f"商品{i % 7:02d}"
        description = "持ちやすい%マグ" if i == 8 else ""
        registered = jst(2027, 1, 1) + timedelta(minutes=i)
        product = catalog.product(name, description=description, registered_at=registered, categories=cats)
        price = 1000 + (i % 5) * 100
        catalog.stock_unit(product, price=price, supplier=supplier, stock=0 if i == 10 else 5)
        if i == 9:
            catalog.stock_unit(product, price=800, supplier=supplier)
            price = 800
        expected.append((product, price, registered, name))
    hidden = catalog.product("非公開品", is_public=False, categories=(parent,), registered_at=jst(2027, 2, 1))
    catalog.stock_unit(hidden, supplier=supplier)
    catalog.product("在庫単位なし", categories=(parent,), registered_at=jst(2027, 2, 2))

    def ids(query):
        collected, page = [], 1
        while True:
            data = body(api(api_client, "get", f"/api/products/?{query}&page={page}"))
            collected += [i["product_id"] for i in data["items"]]
            if page >= data["total_pages"]:
                return collected, data
            page += 1

    first = body(api(api_client, "get", "/api/products/"))
    assert first["total_count"] == 23 and first["page"] == 1 and first["page_size"] == 20
    assert first["total_pages"] == 2 and len(first["items"]) == 20
    newest = sorted(expected, key=lambda e: e[2], reverse=True)
    assert [i["product_id"] for i in first["items"]] == [e[0].pk for e in newest[:20]]
    item9 = next(i for i in first["items"] if i["product_id"] == expected[8][0].pk)
    assert item9["min_price_excluding_tax"] == 800 and item9["min_price_including_tax"] == 880
    item10 = next(i for i in first["items"] if i["product_id"] == expected[9][0].pk)
    assert item10["is_in_stock"] is False

    second = body(api(api_client, "get", "/api/products/?page=2"))
    assert [i["product_id"] for i in second["items"]] == [e[0].pk for e in newest[20:]]
    third = body(api(api_client, "get", "/api/products/?page=3"))
    assert third["items"] == [] and third["total_count"] == 23 and third["total_pages"] == 2

    in_parent, _ = ids(f"category_id={parent.pk}")
    assert sorted(in_parent) == sorted(e[0].pk for e in expected[:7])
    assert len(in_parent) == len(set(in_parent))

    by_keyword, _ = ids("keyword=%20%20mug%20")
    assert by_keyword == [expected[7][0].pk]
    by_symbol, _ = ids("keyword=%25")
    assert by_symbol == [expected[7][0].pk]
    combined, _ = ids(f"category_id={parent.pk}&keyword=mug")
    assert combined == []

    orders = {
        "price_asc": sorted(expected, key=lambda e: (e[1], e[2])),
        "price_desc": sorted(expected, key=lambda e: (-e[1], e[2])),
        "name": sorted(expected, key=lambda e: (e[3], e[2])),
        "newest": newest,
    }
    for sort, order in orders.items():
        got, _ = ids(f"sort={sort}")
        assert got == [e[0].pk for e in order], sort


# trace: FR-011, ADDR-001
def test_it_013_product_search_input_errors(api_client, catalog):
    """IT-013 商品一覧検索の入力エラー全項目通知。"""
    catalog.category()
    response = api(api_client, "get", "/api/products/?sort=cheap&page=0&category_id=999999&keyword=" + "a" * 51)
    assert response.status_code == 400
    assert error_of(response)["type"] == "input_error"
    assert {"sort", "page", "category_id", "keyword"} <= field_names(response)


# trace: FR-012, ADDR-001, ADDR-006
def test_it_014_product_detail_contract_and_not_found(api_client, catalog):
    """IT-014 商品詳細の内容（SKU 昇順・税込価格・仕入先非表示）と対象なし。"""
    supplier = catalog.supplier(code="SUP-SECRET", name="秘密の仕入先")
    category = catalog.category("食器")
    product = catalog.product("湯のみ", description="説明\n2行目", categories=(category,))
    catalog.stock_unit(product, sku="B-2", price=1500, stock=0, supplier=supplier)
    catalog.stock_unit(product, sku="A-1", price=999, stock=3, supplier=supplier)
    catalog.stock_unit(product, sku="C-3", price=2000, stock=7, supplier=supplier)
    hidden = catalog.product(is_public=False)
    catalog.stock_unit(hidden, supplier=supplier)
    empty = catalog.product()

    response = api(api_client, "get", f"/api/products/{product.pk}/")
    assert response.status_code == 200
    data = body(response)
    assert data["product_id"] == product.pk and data["name"] == "湯のみ" and data["description"] == "説明\n2行目"
    assert [s["sku"] for s in data["stock_units"]] == ["A-1", "B-2", "C-3"]
    first = data["stock_units"][0]
    assert first["price_excluding_tax"] == 999 and first["price_including_tax"] == 1098
    assert first["stock_quantity"] == 3 and first["is_in_stock"] is True
    assert data["stock_units"][1]["is_in_stock"] is False
    assert data["categories"] == [{"category_id": category.pk, "name": "食器"}]
    raw = response.content.decode("utf-8")
    assert "supplier" not in raw and "SUP-SECRET" not in raw and "秘密の仕入先" not in raw

    for target in (hidden.pk, empty.pk, 99999999, "abc", "1.5"):
        missing = api(api_client, "get", f"/api/products/{target}/")
        assert missing.status_code == 404, target
        assert error_of(missing)["type"] == "not_found"
    assert error_of(api(api_client, "get", f"/api/products/{hidden.pk}/")) == error_of(
        api(api_client, "get", "/api/products/99999999/")
    )


# trace: FR-011, FR-012, ADDR-001, ADDR-012
def test_it_015_same_result_all_actors_and_screen_price(api_client, catalog, buyer, admin, bearer, web):
    """IT-015 来訪者・購入者・管理者で同一の閲覧結果と画面の総額表示。"""
    product = catalog.product("急須")
    catalog.stock_unit(product, price=1000, stock=4)
    tokens = [None, bearer(buyer), bearer(admin)]
    for path in ("/api/products/", f"/api/products/{product.pk}/"):
        bodies = [api(api_client, "get", path, token).content for token in tokens]
        assert bodies[0] == bodies[1] == bodies[2], path

    visitor = web()
    page = text(visitor.get(f"/products/{product.pk}/"))
    assert "1,100円（税込）／1,000円（税抜）" in page
    assert "カートに入れる" in page
    listing = text(visitor.get("/"))
    assert "1,100円（税込）" in listing and "1,000円（税抜）" in listing

    admin_client = web()
    admin_client.force_login(admin, backend="accounts.backends.SessionUserBackend")
    admin_page = admin_client.get(f"/products/{product.pk}/")
    assert admin_page.status_code == 200
    assert "1,100円（税込）／1,000円（税抜）" in text(admin_page)
    assert "カートに入れる" not in text(admin_page)
