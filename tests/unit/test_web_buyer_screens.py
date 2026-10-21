# trace: FR-001, FR-002, FR-003, FR-010, FR-011, FR-012, FR-020, FR-021, FR-022, FR-023
# trace: FR-024, FR-025, NFR-SC-03, NFR-SC-10, NFR-US-04, ADDR-006, ADDR-010, ADDR-011
"""購入者向け画面（SCR-001〜SCR-005、SCR-901）の単体テスト。

期待結果は画面・帳票要件の各画面定義（SCR-001 商品一覧、SCR-002 商品詳細、SCR-003 会員登録、
SCR-004 ログイン、SCR-005 カート、SCR-901 エラー）と、対応する機能要件の処理内容・例外、
NFR-US-04（入力エラーは項目の近傍に全項目分を表示し入力値を保持する）、
NFR-SC-03（未ログイン・権限なしの判定）から導出する。
"""

from __future__ import annotations

import pytest
from _helpers import (
    add_cart_line,
    field_error_reasons,
    input_element,
    make_collection,
    make_coupon,
    make_item,
    make_open_cart,
    make_stock_unit,
    make_user,
    message_area_error,
)
from accounts.models import ROLE_ADMIN, AuthToken, User
from carts import services as cart_services
from carts.models import Cart, CartLine
from web.support import SESSION_FLASH, SESSION_NEXT_PATH, SESSION_USER_ID

pytestmark = pytest.mark.django_db


# trace: FR-011
def test_item_list_shows_public_items_and_collections(screen_client):
    """SCR-001：商品一覧は商品分類と検索結果（税込価格を主表示）を表示する。"""
    collection = make_collection(collection_code="scr-col", name="画面分類")
    item = make_item(name="画面商品", collections=[collection])
    make_stock_unit(item, price=1000, quantity=3)

    response = screen_client.get("/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "画面商品" in body
    assert "画面分類" in body
    assert "1,100円" in body


# trace: FR-011
def test_item_list_shows_validation_error_and_keeps_conditions(screen_client):
    """E-011-01：検索条件に誤りがある場合は入力値を保持して再表示する（400）。"""
    response = screen_client.get("/?sort=unknown&keyword=テスト")

    assert response.status_code == 400
    body = response.content.decode()
    assert "検索条件に誤りがあります" in body
    assert "テスト" in body


# trace: FR-011
def test_item_list_paginates_results(screen_client):
    """SCR-001：ページ移動のために件数とページ番号を表示する。"""
    for index in range(21):
        item = make_item(name=f"一覧商品{index:02d}")
        make_stock_unit(item)

    response = screen_client.get("/?page=2")

    assert response.status_code == 200
    assert "21" in response.content.decode()


# trace: FR-012
def test_item_detail_shows_stock_units(screen_client):
    """SCR-002：商品詳細は規格（在庫単位）と在庫有無を表示する。"""
    item = make_item(name="詳細画面商品", description="商品の説明")
    make_stock_unit(item, sku="SKU-SCR", variant_name="青", price=2000, quantity=2)

    response = screen_client.get(f"/items/{item.pk}/")

    body = response.content.decode()
    assert response.status_code == 200
    assert "詳細画面商品" in body
    assert "青" in body
    assert "2,200円" in body


# trace: FR-012
def test_item_detail_returns_error_screen_for_hidden_item(screen_client):
    """E-012-01：非公開商品は SCR-901（対象なし）を表示する。"""
    item = make_item(is_public=False)
    make_stock_unit(item)

    response = screen_client.get(f"/items/{item.pk}/")

    assert response.status_code == 404
    assert "お探しのページ・データが見つかりません" in response.content.decode()


# trace: FR-012
def test_item_detail_hides_add_to_cart_for_admin(screen_client, admin_user, logged_in_screen_client):
    """SCR-002：管理者にはカートに入れる操作を提供しない（権限表 5.1）。"""
    item = make_item(name="管理者閲覧商品")
    make_stock_unit(item, quantity=3)
    client = logged_in_screen_client(admin_user)

    response = client.get(f"/items/{item.pk}/")

    assert response.status_code == 200
    assert "カートに入れる" not in response.content.decode()


# trace: FR-001
def test_register_screen_is_displayed(screen_client):
    """SCR-003：会員登録画面を表示する。"""
    response = screen_client.get("/register/")

    assert response.status_code == 200
    assert "会員登録" in response.content.decode()


# trace: FR-001
def test_register_screen_creates_user_and_redirects_to_login(screen_client):
    """FR-001：登録後は SCR-004 へ遷移し、完了した旨をメッセージ領域へ表示する。"""
    response = screen_client.post(
        "/register/",
        {
            "email": "screen@example.test",
            "password": "passw0rd",
            "password_confirmation": "passw0rd",
            "full_name": "画面 太郎",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert User.objects.filter(email="screen@example.test").exists()
    assert AuthToken.objects.count() == 0
    assert "会員登録が完了しました" in screen_client.session[SESSION_FLASH]


# trace: NFR-US-04
def test_register_screen_shows_field_errors_and_keeps_input(screen_client):
    """E-001-01／NFR-US-04：全項目分の理由を表示し、入力値（パスワードを除く）を保持する。"""
    response = screen_client.post(
        "/register/",
        {"email": "invalid", "password": "short", "password_confirmation": "x", "full_name": ""},
    )

    body = response.content.decode()
    assert response.status_code == 400
    assert "メールアドレスの形式で入力してください。" in body
    assert "氏名を入力してください。" in body
    assert "invalid" in body
    assert "short" not in body


# trace: FR-001
def test_register_screen_shows_business_error_for_duplicate_email(screen_client):
    """E-001-02：登録済みメールアドレスは409で業務エラーの文言を表示する。"""
    make_user(email="dup-screen@example.test")

    response = screen_client.post(
        "/register/",
        {
            "email": "dup-screen@example.test",
            "password": "passw0rd",
            "password_confirmation": "passw0rd",
            "full_name": "画面 太郎",
        },
    )

    assert response.status_code == 409
    assert "既に登録されています" in response.content.decode()


# trace: FR-002
def test_login_screen_starts_session_and_redirects_to_items(screen_client):
    """FR-002：購入者のログイン成功後は SCR-001 へ遷移する。"""
    user = make_user(email="screen-login@example.test", password="passw0rd")

    response = screen_client.post(
        "/login/", {"email": "screen-login@example.test", "password": "passw0rd"}
    )

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert screen_client.session[SESSION_USER_ID] == user.pk


# trace: FR-002
def test_login_screen_redirects_admin_to_admin_orders(screen_client):
    """FR-002：管理者のログイン成功後は SCR-102（注文一覧（管理））へ遷移する。"""
    make_user(email="screen-admin@example.test", password="passw0rd", role=ROLE_ADMIN)

    response = screen_client.post(
        "/login/", {"email": "screen-admin@example.test", "password": "passw0rd"}
    )

    assert response["Location"] == "/admin-console/orders/"


# trace: NFR-SC-03
def test_login_screen_returns_to_remembered_path(screen_client, buyer):
    """UI-17：ログイン後は未ログインで要求した画面へ戻す。"""
    make_user(email="next-path@example.test", password="passw0rd")
    session = screen_client.session
    session[SESSION_NEXT_PATH] = "/cart/"
    session.save()

    response = screen_client.post(
        "/login/", {"email": "next-path@example.test", "password": "passw0rd"}
    )

    assert response["Location"] == "/cart/"


# trace: FR-002
def test_login_screen_shows_invalid_credentials(screen_client):
    """E-002-02：資格情報の照合に失敗した場合は401で同じ文言を表示する。"""
    make_user(email="ng-login@example.test", password="passw0rd")

    response = screen_client.post("/login/", {"email": "ng-login@example.test", "password": "wrong123"})

    assert response.status_code == 401
    assert "メールアドレスまたはパスワードが正しくありません" in response.content.decode()


# trace: NFR-US-04
def test_login_screen_shows_validation_error_for_missing_input(screen_client):
    """E-002-01：未入力は400で項目別の理由を表示する。"""
    response = screen_client.post("/login/", {"email": "", "password": ""})

    assert response.status_code == 400
    assert "メールアドレスを入力してください。" in response.content.decode()


# trace: FR-002
def test_login_screen_is_displayed(screen_client):
    """SCR-004：ログイン画面を表示する。"""
    assert screen_client.get("/login/").status_code == 200


# trace: FR-003
def test_logout_discards_session(screen_client, buyer, logged_in_screen_client):
    """FR-003：ログアウトでログインセッションを破棄し、SCR-001 へ遷移する。"""
    client = logged_in_screen_client(buyer)

    response = client.post("/logout/")

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert SESSION_USER_ID not in client.session


# trace: FR-003
def test_logout_without_session_is_accepted(screen_client):
    """未ログインのログアウト要求も画面を壊さない。"""
    response = screen_client.post("/logout/")

    assert response.status_code == 302


# trace: NFR-SC-03
def test_cart_screen_requires_login(screen_client):
    """E-020-01：未ログインの場合は SCR-004 へ遷移する。"""
    response = screen_client.get("/cart/")

    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert screen_client.session[SESSION_NEXT_PATH] == "/cart/"


# trace: NFR-SC-03
def test_cart_screen_rejects_admin(screen_client, admin_user, logged_in_screen_client):
    """E-020-02：管理者が購入者専用画面を要求した場合は SCR-901（権限なし）を表示する。"""
    client = logged_in_screen_client(admin_user)

    response = client.get("/cart/")

    assert response.status_code == 403
    assert "権限がありません" in response.content.decode()


# trace: FR-020
def test_cart_screen_shows_lines_and_amounts(buyer, logged_in_screen_client):
    """SCR-005：カートの明細・金額内訳を表示する。"""
    unit = make_stock_unit(make_item(name="カート画面商品"), price=3000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 2})
    client = logged_in_screen_client(buyer)

    response = client.get("/cart/")

    body = response.content.decode()
    assert response.status_code == 200
    assert "カート画面商品" in body
    assert "6,000円" in body


# trace: FR-020
def test_cart_screen_marks_shortage_lines(buyer, logged_in_screen_client):
    """SCR-005：在庫数量を超える明細は在庫不足である旨を表示する。"""
    unit = make_stock_unit(make_item(name="在庫不足商品"), price=1000, quantity=5)
    cart = make_open_cart(buyer)
    add_cart_line(cart, unit, quantity=3)
    unit.quantity = 1
    unit.save(update_fields=["quantity"])
    client = logged_in_screen_client(buyer)

    response = client.get("/cart/")

    assert response.status_code == 200
    assert "在庫" in response.content.decode()


# trace: FR-021
def test_add_line_from_item_detail_sets_flash_message(buyer, logged_in_screen_client):
    """SCR-002-OP01：カート追加後は「カートに追加しました（規格名、n個）。」を表示する。"""
    unit = make_stock_unit(make_item(name="追加商品"), quantity=5, variant_name="青")
    client = logged_in_screen_client(buyer)

    response = client.post(
        "/cart/lines/add/",
        {"item_id": str(unit.item_id), "stock_unit_id": str(unit.pk), "quantity": "2"},
    )

    assert response.status_code == 302
    assert response["Location"] == f"/items/{unit.item_id}/"
    assert client.session[SESSION_FLASH] == "カートに追加しました（青、2個）。"
    assert CartLine.objects.filter(stock_unit=unit).count() == 1


# trace: FR-021, NFR-US-04
def test_add_line_shows_business_error_message(buyer, logged_in_screen_client):
    """E-021-06／SCR-002-OP01：在庫不足はメッセージ領域へ現在の在庫数量を添えて表示し、
    本画面（SCR-002）に留まって入力値を保持する（カートは変更しない。CMN-17、UI-19）。"""
    unit = make_stock_unit(make_item(), quantity=1)
    client = logged_in_screen_client(buyer)

    response = client.post(
        "/cart/lines/add/",
        {"item_id": str(unit.item_id), "stock_unit_id": str(unit.pk), "quantity": "3"},
    )

    body = response.content.decode()
    assert response.status_code == 409
    assert message_area_error(body) == "在庫が不足しています（現在の在庫数量：1個）。"
    assert 'name="quantity" value="3"' in input_element(body, "quantity")
    assert "checked" in input_element(body, "stock_unit_id", value=str(unit.pk))
    assert CartLine.objects.count() == 0
    assert SESSION_FLASH not in client.session


# trace: FR-021, NFR-US-04
@pytest.mark.parametrize("entered", ["", "0", "-1", "1.5", "abc"])
def test_add_line_shows_quantity_field_error_and_keeps_input(buyer, logged_in_screen_client, entered):
    """E-021-03／SCR-002-OP01：数量の未入力・0以下・整数以外は数量欄の近傍に理由を表示し、
    本画面に留まって入力値と選択した規格を保持する（カートは変更しない。CMN-16、CMN-17、UI-19）。"""
    item = make_item(name="数量エラー商品")
    first = make_stock_unit(item, sku="SKU-QTY-A", variant_name="赤", quantity=5)
    selected = make_stock_unit(item, sku="SKU-QTY-B", variant_name="青", quantity=5)
    client = logged_in_screen_client(buyer)

    response = client.post(
        "/cart/lines/add/",
        {"item_id": str(item.pk), "stock_unit_id": str(selected.pk), "quantity": entered},
    )

    body = response.content.decode()
    quantity_input = input_element(body, "quantity")
    assert response.status_code == 400
    assert f'value="{entered}"' in quantity_input
    assert field_error_reasons(body, after=quantity_input) == ["数量は1以上の整数で入力してください。"]
    assert "checked" in input_element(body, "stock_unit_id", value=str(selected.pk))
    assert "checked" not in input_element(body, "stock_unit_id", value=str(first.pk))
    assert CartLine.objects.count() == 0


# trace: FR-021, NFR-US-04
def test_add_line_shows_quantity_limit_message_and_keeps_input(buyer, logged_in_screen_client):
    """E-021-05／SCR-002-OP01：合算数量が10を超える場合はメッセージ領域へ現在のカート内数量を
    添えて表示し、入力値を保持して本画面に留まる（既存の明細の数量はそのまま）。"""
    unit = make_stock_unit(make_item(name="上限超過商品"), quantity=20)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 8})
    client = logged_in_screen_client(buyer)

    response = client.post(
        "/cart/lines/add/",
        {"item_id": str(unit.item_id), "stock_unit_id": str(unit.pk), "quantity": "3"},
    )

    body = response.content.decode()
    assert response.status_code == 409
    assert message_area_error(body) == "同じ規格は1注文につき10個までです（現在のカート内数量：8個）。"
    assert 'value="3"' in input_element(body, "quantity")
    assert "checked" in input_element(body, "stock_unit_id", value=str(unit.pk))
    assert CartLine.objects.get(stock_unit=unit).quantity == 8


# trace: FR-021, FR-012
@pytest.mark.parametrize("entered", ["2", "0"])
def test_add_line_returns_error_screen_when_item_is_hidden(buyer, logged_in_screen_client, entered):
    """E-021-04／SCR-002-OP01：商品が非公開になっていた場合は、数量の入力エラーの有無にかかわらず
    SCR-901（対象なし）を表示する（入力値の再表示は行わない。カートは変更しない）。"""
    item = make_item(name="非公開商品", is_public=False)
    unit = make_stock_unit(item, quantity=5)
    client = logged_in_screen_client(buyer)

    response = client.post(
        "/cart/lines/add/",
        {"item_id": str(item.pk), "stock_unit_id": str(unit.pk), "quantity": entered},
    )

    body = response.content.decode()
    assert response.status_code == 404
    assert "お探しのページ・データが見つかりません" in body
    assert "非公開商品" not in body
    assert CartLine.objects.count() == 0


# trace: NFR-SC-03
def test_add_line_remembers_item_detail_for_anonymous_visitor(screen_client):
    """UI-17：来訪者がカート追加を操作した場合はログイン後に SCR-002 へ戻す。"""
    unit = make_stock_unit(make_item(), quantity=5)

    response = screen_client.post(
        "/cart/lines/add/",
        {"item_id": str(unit.item_id), "stock_unit_id": str(unit.pk), "quantity": "1"},
    )

    assert response["Location"] == "/login/"
    assert screen_client.session[SESSION_NEXT_PATH] == f"/items/{unit.item_id}/"


# trace: FR-022
def test_update_line_changes_quantity_and_shows_message(buyer, logged_in_screen_client):
    """SCR-005-OP01：数量変更後はカートを再表示し、変更した旨を表示する。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{line.pk}/update/", {"quantity": "3"})

    assert response.status_code == 200
    assert CartLine.objects.get(pk=line.pk).quantity == 3


# trace: NFR-US-04
def test_update_line_shows_field_error_for_invalid_quantity(buyer, logged_in_screen_client):
    """E-022-03：数量の入力エラーはカート画面に項目別の理由を表示する。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{line.pk}/update/", {"quantity": "0"})

    assert response.status_code == 200
    assert "数量は1以上の整数で入力してください。" in response.content.decode()
    assert CartLine.objects.get(pk=line.pk).quantity == 1


# trace: FR-022
def test_update_line_shows_business_error(buyer, logged_in_screen_client):
    """E-022-06：在庫不足はカート画面にエラーメッセージを表示する。"""
    unit = make_stock_unit(make_item(), quantity=2)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{line.pk}/update/", {"quantity": "5"})

    assert response.status_code == 200
    assert "在庫が不足しています" in response.content.decode()


# trace: FR-022, NFR-US-04
@pytest.mark.parametrize("target_index", [0, 1])
def test_update_line_keeps_entered_quantity_only_for_target_line(buyer, logged_in_screen_client, target_index):
    """E-022-03／SCR-005-OP01：数量の入力エラーは該当明細の入力値だけを差し替え、理由も該当明細の
    近傍1か所にだけ表示する（明細の並び順によらない。他の明細は保存されている数量のまま。
    CMN-16、CMN-17、UI-19）。"""
    first_unit = make_stock_unit(make_item(name="1件目の明細商品"), quantity=10)
    second_unit = make_stock_unit(make_item(name="2件目の明細商品"), quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": first_unit.pk, "quantity": 1})
    cart_services.add_line(buyer, {"stock_unit_id": second_unit.pk, "quantity": 2})
    lines = cart_services.show_cart(buyer)["lines"]
    target, other = lines[target_index], lines[1 - target_index]
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{target.pk}/update/", {"quantity": "0"})

    body = response.content.decode()
    target_form = f"/cart/lines/{target.pk}/update/"
    other_form = f"/cart/lines/{other.pk}/update/"
    assert response.status_code == 200
    assert 'value="0"' in input_element(body, "quantity", after=target_form)
    assert f'value="{other.quantity}"' in input_element(body, "quantity", after=other_form)
    assert field_error_reasons(body, after=target_form) == ["数量は1以上の整数で入力してください。"]
    assert body.count("数量は1以上の整数で入力してください。") == 1
    assert CartLine.objects.get(pk=target.pk).quantity == target.quantity
    assert CartLine.objects.get(pk=other.pk).quantity == other.quantity


# trace: FR-022, NFR-US-04
def test_update_line_judges_quantity_before_line_existence(buyer, logged_in_screen_client):
    """FR-022 6.10.4 手順3→手順4／E-022-03：数量の判定は明細の存在判定より前に行う。

    既に削除された明細への数量変更でも、数量が入力エラーであれば SCR-901（対象なし）ではなく
    入力エラーとして SCR-005 を再表示し、カートは変更しない（6.10.6 異常終了）。残っている明細は
    保存されている数量のまま表示する（CMN-17、UI-19）。削除済みの明細の数量欄は画面に存在しない
    ため、その近傍へ表示する理由（CMN-16）は要件が定める表示位置を持たない。
    """
    remaining_unit = make_stock_unit(make_item(name="残る明細商品"), quantity=10)
    deleted_unit = make_stock_unit(make_item(name="削除済み明細商品"), quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": remaining_unit.pk, "quantity": 2})
    cart_services.add_line(buyer, {"stock_unit_id": deleted_unit.pk, "quantity": 1})
    remaining = CartLine.objects.get(stock_unit=remaining_unit)
    deleted_line_id = CartLine.objects.get(stock_unit=deleted_unit).pk
    cart_services.delete_line(buyer, deleted_line_id)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{deleted_line_id}/update/", {"quantity": "0"})

    body = response.content.decode()
    assert response.status_code == 200
    assert "お探しのページ・データが見つかりません" not in body
    assert "残る明細商品" in body
    assert "削除済み明細商品" not in body
    assert 'value="2"' in input_element(body, "quantity", after=f"/cart/lines/{remaining.pk}/update/")
    assert CartLine.objects.get(pk=remaining.pk).quantity == 2
    assert CartLine.objects.filter(pk=deleted_line_id).count() == 0


# trace: FR-022, NFR-US-04
def test_update_line_keeps_entered_quantity_for_target_line_on_business_error(buyer, logged_in_screen_client):
    """E-022-06／SCR-005-OP01：在庫不足はメッセージ領域へ現在の在庫数量を添えて表示し、
    該当明細の入力値だけを保持する（カートは変更しない）。"""
    target_unit = make_stock_unit(make_item(name="在庫不足明細商品"), quantity=2)
    other_unit = make_stock_unit(make_item(name="他明細商品"), quantity=10)
    target = cart_services.add_line(buyer, {"stock_unit_id": target_unit.pk, "quantity": 1})["lines"][0]
    cart_services.add_line(buyer, {"stock_unit_id": other_unit.pk, "quantity": 2})
    other = CartLine.objects.get(stock_unit=other_unit)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{target.pk}/update/", {"quantity": "5"})

    body = response.content.decode()
    assert response.status_code == 200
    assert message_area_error(body) == "在庫が不足しています（現在の在庫数量：2個）。"
    assert 'value="5"' in input_element(body, "quantity", after=f"/cart/lines/{target.pk}/update/")
    assert 'value="2"' in input_element(body, "quantity", after=f"/cart/lines/{other.pk}/update/")
    assert CartLine.objects.get(pk=target.pk).quantity == 1
    assert CartLine.objects.get(pk=other.pk).quantity == 2


# trace: FR-023
def test_delete_line_removes_line_and_redirects(buyer, logged_in_screen_client):
    """SCR-005-OP02：明細削除後はカート画面へ戻り、削除した旨を表示する。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    client = logged_in_screen_client(buyer)

    response = client.post(f"/cart/lines/{line.pk}/delete/")

    assert response["Location"] == "/cart/"
    assert CartLine.objects.filter(pk=line.pk).count() == 0
    assert client.session[SESSION_FLASH] == "カートから削除しました。"


# trace: FR-024
def test_apply_coupon_from_screen(buyer, logged_in_screen_client):
    """SCR-005-OP03：クーポン適用後はカート画面へ戻り、適用した旨を表示する。"""
    make_coupon(code="SCR-1000", discount_value=1000, min_spend=0)
    unit = make_stock_unit(make_item(), price=6000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "scr-1000"})

    assert response["Location"] == "/cart/"
    assert client.session[SESSION_FLASH] == "クーポンを適用しました。"
    assert Cart.objects.get(user=buyer, status="open").coupon.code == "SCR-1000"


# trace: NFR-US-04
def test_apply_coupon_shows_field_error_for_invalid_code(buyer, logged_in_screen_client):
    """E-024-03：クーポンコードの形式違反は項目別の理由を表示する。"""
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "invalid code"})

    assert response.status_code == 200
    assert "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。" in response.content.decode()


# trace: FR-024
def test_apply_coupon_shows_cart_empty_message(buyer, logged_in_screen_client):
    """E-024-04：カートが空の場合は専用の文言を表示する。"""
    make_coupon(code="SCR-EMPTY")
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "SCR-EMPTY"})

    assert response.status_code == 200
    assert "カートに商品がないため、クーポンを適用できません。" in response.content.decode()


# trace: FR-024
def test_apply_coupon_shows_already_applied_with_current_code(buyer, logged_in_screen_client):
    """SCR-005-OP03：適用済みの場合は適用中のクーポンコードを添えて表示する。"""
    make_coupon(code="SCR-FIRST")
    make_coupon(code="SCR-SECOND")
    unit = make_stock_unit(make_item(), price=6000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    cart_services.apply_coupon(buyer, {"code": "SCR-FIRST"})
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "SCR-SECOND"})

    assert response.status_code == 200
    assert "適用中のクーポン：SCR-FIRST" in response.content.decode()


# trace: FR-024
def test_apply_coupon_shows_business_error(buyer, logged_in_screen_client):
    """E-024-09：最低購入金額未達はカート画面にエラーメッセージを表示する。"""
    make_coupon(code="SCR-MIN", min_spend=100000)
    unit = make_stock_unit(make_item(), price=1000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "SCR-MIN"})

    assert response.status_code == 200
    assert "小計が最低購入金額に達していません" in response.content.decode()


# trace: FR-024, NFR-US-04
def test_apply_coupon_keeps_entered_code_on_validation_error(buyer, logged_in_screen_client):
    """E-024-03／SCR-005-OP03：クーポンコードの入力エラーでも入力した値を保持して再表示する
    （CMN-17、UI-19）。"""
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "invalid code"})

    body = response.content.decode()
    code_input = input_element(body, "code")
    assert response.status_code == 200
    assert 'value="invalid code"' in code_input
    assert field_error_reasons(body, after=code_input) == [
        "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。"
    ]


# trace: FR-024, NFR-US-04
def test_apply_coupon_keeps_entered_code_on_business_error(buyer, logged_in_screen_client):
    """E-024-09／SCR-005-OP03：業務エラー（最低購入金額未達）でも入力した値をそのまま保持する
    （英小文字での入力も入力どおりに戻す。CMN-17、UI-19）。"""
    make_coupon(code="SCR-KEEP", min_spend=100000)
    unit = make_stock_unit(make_item(), price=1000, quantity=5)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "scr-keep"})

    body = response.content.decode()
    assert response.status_code == 200
    assert "小計が最低購入金額に達していません" in message_area_error(body)
    assert 'value="scr-keep"' in input_element(body, "code")
    assert Cart.objects.get(user=buyer, status="open").coupon_id is None


# trace: FR-024, NFR-US-04
def test_apply_coupon_keeps_entered_code_when_cart_is_empty(buyer, logged_in_screen_client):
    """E-024-04／SCR-005-OP03：カートが空の場合もメッセージ領域へ表示し、入力値を保持する。"""
    make_coupon(code="SCR-EMPTY-KEEP")
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/apply/", {"code": "SCR-EMPTY-KEEP"})

    body = response.content.decode()
    assert response.status_code == 200
    assert message_area_error(body) == "カートに商品がないため、クーポンを適用できません。"
    assert 'value="SCR-EMPTY-KEEP"' in input_element(body, "code")


# trace: FR-025
def test_remove_coupon_from_screen(buyer, logged_in_screen_client):
    """SCR-005-OP04：クーポン解除後はカート画面へ戻り、解除した旨を表示する。"""
    coupon = make_coupon(code="SCR-REMOVE")
    cart = make_open_cart(buyer, coupon=coupon)
    add_cart_line(cart, make_stock_unit(make_item(), quantity=5))
    client = logged_in_screen_client(buyer)

    response = client.post("/cart/coupon/remove/")

    assert response["Location"] == "/cart/"
    assert client.session[SESSION_FLASH] == "クーポンを解除しました。"
    assert Cart.objects.get(pk=cart.pk).coupon_id is None


# trace: FR-020
def test_header_shows_cart_total_quantity_for_buyer(buyer, logged_in_screen_client):
    """共通ヘッダーにカートの合計点数を表示する（購入者のみ）。"""
    unit = make_stock_unit(make_item(), quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 3})
    client = logged_in_screen_client(buyer)

    response = client.get("/")

    assert response.status_code == 200
    assert response.context["cart_total_quantity"] == 3


# trace: FR-020
def test_header_shows_zero_cart_quantity_without_cart(buyer, logged_in_screen_client):
    """利用中カートがない購入者の合計点数は0とする。"""
    client = logged_in_screen_client(buyer)

    response = client.get("/")

    assert response.context["cart_total_quantity"] == 0


# trace: FR-010
def test_header_hides_cart_quantity_for_admin(admin_user, logged_in_screen_client):
    """管理者にはカートの合計点数を表示しない。"""
    client = logged_in_screen_client(admin_user)

    response = client.get("/")

    assert response.context["cart_total_quantity"] is None
    assert response.context["is_admin"] is True


# trace: NFR-SC-10
def test_unknown_path_returns_error_screen(screen_client):
    """SCR-901：存在しない画面は対象なしのエラー画面を表示し、内部情報を含めない。"""
    response = screen_client.get("/unknown-page/")

    body = response.content.decode()
    assert response.status_code == 404
    assert "お探しのページ・データが見つかりません" in body
    assert "Traceback" not in body


# trace: NFR-SC-03
def test_update_operations_reject_get_method(buyer, logged_in_screen_client):
    """更新操作は POST のみを受け付ける。"""
    client = logged_in_screen_client(buyer)

    assert client.get("/cart/coupon/remove/").status_code == 405
