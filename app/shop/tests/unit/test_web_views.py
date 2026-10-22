# trace: FR-001, FR-002, FR-003, FR-011, FR-012, FR-020, FR-021, FR-022
# trace: FR-023, FR-024, FR-025, NFR-SC-04, NFR-SC-06, ADDR-002
"""画面（SCR-001〜SCR-005、SCR-901）の単体テスト。

期待値は各FRの画面表示・例外の振る舞い（UI-34、MSG-01〜MSG-04）から導出する。
ビュー関数を直接呼び出し、要求はテスト用に組み立てる（外部通信を行わない）。
"""
from datetime import timedelta

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from shop.common import timeutils
from shop.models import User
from shop.services import carts
from shop.tests.unit import _helpers
from shop.web import session, views_cart, views_catalog, views_error

pytestmark = pytest.mark.django_db


# trace: ADDR-002
def _tag(body, marker):
    """画面本文から marker を含むタグ1個分（`<` 〜 `>`）を取り出す。

    属性（type・min・disabled・checked など）を文字列一致ではなくタグ単位で検証するために使う。
    """
    position = body.index(marker)
    start = body.rindex("<", 0, position)
    end = body.index(">", position)
    return body[start : end + 1]


# trace: ADDR-002
def _form_block(body, action):
    """画面本文から指定した action の `<form>` 〜 `</form>` の範囲を取り出す。

    入力項目の「近傍」に表示する文言（SCR-005-OP03）を、
    メッセージ領域の表示と区別して確認するために使う。
    """
    position = body.index(f'action="{action}"')
    start = body.rindex("<form", 0, position)
    end = body.index("</form>", start)
    return body[start:end]


# trace: ADDR-002
def _request(path, method="get", data=None, user=None):
    """セッションを持つ要求を組み立て、必要ならログイン状態にする。"""
    factory = RequestFactory()
    request = getattr(factory, method)(path, data or {})
    SessionMiddleware(lambda req: HttpResponse()).process_request(request)
    request.session.save()
    if user is not None:
        session.login(request, user)
    return request


# trace: FR-011
def test_item_list_screen_shows_items(supplier):
    """商品一覧（SCR-001）は検索結果を表示する。"""
    item = _helpers.make_item("ITEM-001", "サンプル商品")
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    response = views_catalog.item_list(_request("/"))

    assert response.status_code == 200
    assert "サンプル商品" in response.content.decode("utf-8")


# trace: FR-011
def test_item_list_screen_shows_input_errors(db):
    """検索条件の不備は入力エラーとして画面に表示する（400）。"""
    response = views_catalog.item_list(_request("/?sort=unknown"))

    assert response.status_code == 400


# trace: FR-012
def test_item_detail_screen_shows_stock_units(supplier):
    """商品詳細（SCR-002）は在庫単位の一覧と規格の単一選択・数量入力・カート投入の操作を表示する。

    SCR-002-IN01：規格は在庫単位一覧の各行から1つ選ぶ（単一選択）。
    SCR-002-IN02：数量は数値入力で1以上、初期値1。
    SCR-002-OP01：在庫数量1以上の在庫単位があれば「カートに入れる」を押下できる。
    """
    item = _helpers.make_item("ITEM-001", "サンプル商品")
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-001", variant_name="赤")

    response = views_catalog.item_detail(_request(f"/items/{item.item_id}"), str(item.item_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "赤" in body
    radio = _tag(body, f'id="stock-unit-{unit.stock_unit_id}"')
    assert 'type="radio"' in radio
    assert 'name="stock_unit_id"' in radio
    assert f'value="{unit.stock_unit_id}"' in radio
    assert "disabled" not in radio
    quantity = _tag(body, 'id="quantity"')
    assert 'type="number"' in quantity
    assert 'name="quantity"' in quantity
    assert 'min="1"' in quantity
    assert 'value="1"' in quantity
    assert "disabled" not in quantity
    assert "disabled" not in _tag(body, "カートに入れる")
    assert "すべての規格が在庫切れ" not in body


# trace: FR-012
def test_item_detail_screen_preselects_first_in_stock_unit_by_sku(supplier):
    """規格の初期値は在庫数量1以上の在庫単位のうち SKU 昇順で先頭の行とする（SCR-002-IN01）。"""
    item = _helpers.make_item("ITEM-001", "サンプル商品")
    sold_out = _helpers.make_stock_unit(item, supplier, sku="SKU-001", variant_name="赤", quantity=0)
    first_in_stock = _helpers.make_stock_unit(item, supplier, sku="SKU-002", variant_name="青", quantity=1)
    _helpers.make_stock_unit(item, supplier, sku="SKU-003", variant_name="緑", quantity=5)

    response = views_catalog.item_detail(_request(f"/items/{item.item_id}"), str(item.item_id))

    body = response.content.decode("utf-8")
    assert "checked" in _tag(body, f'id="stock-unit-{first_in_stock.stock_unit_id}"')
    assert "checked" not in _tag(body, f'id="stock-unit-{sold_out.stock_unit_id}"')


# trace: FR-012
def test_item_detail_screen_disables_only_sold_out_rows(supplier):
    """一部の規格だけが在庫切れの場合は、その行のみ選択不可とする（SCR-002-NT02）。"""
    item = _helpers.make_item("ITEM-001", "サンプル商品")
    sold_out = _helpers.make_stock_unit(item, supplier, sku="SKU-001", variant_name="赤", quantity=0)
    in_stock = _helpers.make_stock_unit(item, supplier, sku="SKU-002", variant_name="青", quantity=1)

    response = views_catalog.item_detail(_request(f"/items/{item.item_id}"), str(item.item_id))

    body = response.content.decode("utf-8")
    assert "disabled" in _tag(body, f'id="stock-unit-{sold_out.stock_unit_id}"')
    assert "disabled" not in _tag(body, f'id="stock-unit-{in_stock.stock_unit_id}"')
    assert "disabled" not in _tag(body, 'id="quantity"')
    assert "disabled" not in _tag(body, "カートに入れる")
    assert "すべての規格が在庫切れ" not in body


# trace: FR-012
def test_item_detail_screen_blocks_cart_input_when_all_units_sold_out(supplier):
    """全規格が在庫切れの場合は選択・数量入力・カート投入を不可とし、在庫切れの案内を表示する。

    SCR-002-V11 の案内文と SCR-002-NT02 の表示切替を確認する。
    """
    item = _helpers.make_item("ITEM-001", "サンプル商品")
    first = _helpers.make_stock_unit(item, supplier, sku="SKU-001", variant_name="赤", quantity=0)
    second = _helpers.make_stock_unit(item, supplier, sku="SKU-002", variant_name="青", quantity=0)

    response = views_catalog.item_detail(_request(f"/items/{item.item_id}"), str(item.item_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "この商品は現在すべての規格が在庫切れのため、カートに入れられません。" in body
    assert "disabled" in _tag(body, f'id="stock-unit-{first.stock_unit_id}"')
    assert "disabled" in _tag(body, f'id="stock-unit-{second.stock_unit_id}"')
    assert "disabled" in _tag(body, 'id="quantity"')
    assert "disabled" in _tag(body, "カートに入れる")


# trace: FR-012
def test_item_detail_screen_returns_not_found_for_private_item(supplier):
    """非公開商品の商品詳細は対象なしの画面（404）を表示する。"""
    item = _helpers.make_item("ITEM-001", "非公開", is_public=False)
    _helpers.make_stock_unit(item, supplier, sku="SKU-001")

    response = views_catalog.item_detail(_request(f"/items/{item.item_id}"), str(item.item_id))

    assert response.status_code == 404


# trace: FR-001
def test_register_screen_creates_user_and_redirects_to_login(db):
    """会員登録（SCR-003）は登録後にログイン画面へ遷移する（自動ログインしない）。"""
    request = _request(
        "/register",
        method="post",
        data={
            "email": "new.user@example.com",
            "password": "Newpass12",
            "password_confirmation": "Newpass12",
            "full_name": "新規 利用者",
        },
    )

    response = views_catalog.register(request)

    assert response.status_code == 302
    assert response["Location"] == "/login"
    assert User.objects.filter(email="new.user@example.com").exists()
    assert session.SESSION_USER_KEY not in request.session
    assert request.session[session.FLASH_KEY] == "会員登録が完了しました。ログインしてください。"


# trace: FR-001
def test_register_screen_keeps_input_on_validation_error(db):
    """入力エラー時は入力値を保持して再表示する（400。パスワードは保持しない）。"""
    request = _request(
        "/register",
        method="post",
        data={
            "email": "invalid",
            "password": "short",
            "password_confirmation": "short",
            "full_name": "新規 利用者",
        },
    )

    response = views_catalog.register(request)
    body = response.content.decode("utf-8")

    assert response.status_code == 400
    assert "invalid" in body
    assert "short" not in body


# trace: FR-001
def test_register_screen_shows_duplicate_email_error(db):
    """登録済みメールアドレスの場合は SCR-003-OP01 の文言を表示する（409）。

    SCR-003-OP01：メールアドレスが登録済み（EMAIL_ALREADY_REGISTERED）の場合はメッセージ領域に
    「このメールアドレスは既に登録されています。」を表示する。
    """
    _helpers.make_user(email="hanako.sato@example.com")
    request = _request(
        "/register",
        method="post",
        data={
            "email": "hanako.sato@example.com",
            "password": "Newpass12",
            "password_confirmation": "Newpass12",
            "full_name": "佐藤 花子",
        },
    )

    response = views_catalog.register(request)

    assert response.status_code == 409
    assert "このメールアドレスは既に登録されています。" in response.content.decode("utf-8")


# trace: FR-002
def test_login_screen_starts_session_for_buyer(buyer):
    """ログイン（SCR-004）成功時は購入者を商品一覧へ遷移させる。"""
    request = _request("/login", method="post", data={"email": buyer.email, "password": "Passw0rd"})

    response = views_catalog.login(request)

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert request.session[session.SESSION_USER_KEY] == buyer.user_id


# trace: FR-002
def test_login_screen_redirects_admin_to_admin_screen(admin_user):
    """管理者のログイン後は管理者の注文一覧へ遷移する。"""
    request = _request("/login", method="post", data={"email": admin_user.email, "password": "Adminpass1"})

    response = views_catalog.login(request)

    assert response["Location"] == "/admin/purchase-orders"


# trace: FR-002, NFR-SC-04
def test_login_screen_ignores_external_next(buyer):
    """ログイン後の遷移先は自サイト内に限定する。"""
    request = _request(
        "/login", method="post", data={"email": buyer.email, "password": "Passw0rd", "next": "https://example.net"}
    )

    response = views_catalog.login(request)

    assert response["Location"] == "/"


# trace: FR-002
def test_login_screen_shows_invalid_credentials(buyer):
    """認証失敗時は401で SCR-004-OP01 の文言を表示する。

    SCR-004-OP01：認証失敗（INVALID_CREDENTIALS）はメッセージ領域に
    「メールアドレスまたはパスワードが正しくありません。」を表示する（どちらが誤りかを区別しない）。
    """
    request = _request("/login", method="post", data={"email": buyer.email, "password": "Wr0ngpass"})

    response = views_catalog.login(request)

    assert response.status_code == 401
    assert "メールアドレスまたはパスワードが正しくありません。" in response.content.decode("utf-8")


# trace: FR-002
def test_login_screen_shows_validation_error(db):
    """未入力は400でログイン画面を再表示する。"""
    request = _request("/login", method="post", data={"email": "", "password": ""})

    response = views_catalog.login(request)

    assert response.status_code == 400


# trace: FR-003
def test_logout_screen_clears_session(buyer):
    """ログアウトでセッションを破棄し、商品一覧へ遷移する。"""
    request = _request("/logout", method="post", user=buyer)

    response = views_catalog.logout(request)

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert session.SESSION_USER_KEY not in request.session


# trace: FR-020
def test_cart_screen_requires_login(db):
    """未ログインのカート画面はログイン画面へ遷移させる。"""
    response = views_cart.cart(_request("/cart"))

    assert response.status_code == 302
    assert response["Location"].startswith("/login?next=")


# trace: FR-020
def test_cart_screen_rejects_admin(admin_user):
    """管理者のカート画面は権限なし（403）とする。"""
    response = views_cart.cart(_request("/cart", user=admin_user))

    assert response.status_code == 403


# trace: FR-021
def test_cart_add_line_screen_redirects_with_flash(buyer, stock_unit):
    """カート追加の成功時はカート画面へ遷移し、完了メッセージを表示する。"""
    request = _request(
        "/cart/lines",
        method="post",
        data={"stock_unit_id": str(stock_unit.stock_unit_id), "quantity": "2", "item_id": str(stock_unit.item_id)},
        user=buyer,
    )

    response = views_cart.add_line(request)

    assert response.status_code == 302
    assert response["Location"] == "/cart"
    assert "カートに追加しました" in request.session[session.FLASH_KEY]


# trace: FR-021
def test_cart_add_line_screen_shows_stock_error_on_item_detail(buyer, item, supplier):
    """在庫不足時は商品詳細画面へエラーを表示し、入力値（規格・数量）を保持する（SCR-002-OP01）。"""
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=1)
    request = _request(
        "/cart/lines",
        method="post",
        data={"stock_unit_id": str(unit.stock_unit_id), "quantity": "2", "item_id": str(item.item_id)},
        user=buyer,
    )

    response = views_cart.add_line(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "在庫が不足しています" in body
    assert "checked" in _tag(body, f'id="stock-unit-{unit.stock_unit_id}"')
    assert 'value="2"' in _tag(body, 'id="quantity"')
    from shop.models import CartLine

    assert CartLine.objects.count() == 0


# trace: FR-021
def test_cart_add_line_screen_shows_insufficient_stock_message_of_scr_002(buyer, item, supplier):
    """在庫不足のメッセージ領域の表示は SCR-002-OP01 の定めどおりとする。

    SCR-002-OP01：在庫不足（INSUFFICIENT_STOCK）はメッセージ領域に
    「在庫が不足しています（現在の在庫数量：n個）。」を表示する。
    """
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=1)
    request = _request(
        "/cart/lines",
        method="post",
        data={"stock_unit_id": str(unit.stock_unit_id), "quantity": "2", "item_id": str(item.item_id)},
        user=buyer,
    )

    response = views_cart.add_line(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "在庫が不足しています（現在の在庫数量：1個）。" in body


# trace: FR-020
def test_cart_screen_shows_quantity_input_with_current_quantity(buyer, stock_unit):
    """カート画面（SCR-005）は明細ごとに数量入力欄を表示し、初期値を現在のカート内数量とする。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 3)
    from shop.models import CartLine

    line = CartLine.objects.get()

    response = views_cart.cart(_request("/cart", user=buyer))

    body = response.content.decode("utf-8")
    assert response.status_code == 200
    quantity = _tag(body, f'id="quantity-{line.cart_line_id}"')
    assert 'type="number"' in quantity
    assert 'name="quantity"' in quantity
    assert 'min="1"' in quantity
    assert 'value="3"' in quantity


# trace: FR-022
def test_cart_update_line_screen_shows_error_and_keeps_quantity(buyer, stock_unit):
    """数量変更の失敗時はカート画面で入力値を保持して再表示し、カートを変更しない（SCR-005-OP01）。

    数量上限超過（QUANTITY_LIMIT_EXCEEDED、D-09-04／DQ-19）のメッセージを表示し、
    数量欄には入力した値（11）を保持する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()
    request = _request(
        f"/cart/lines/{line.cart_line_id}/update", method="post", data={"quantity": "11"}, user=buyer
    )

    response = views_cart.update_line(request, str(line.cart_line_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert 'class="message error"' in body
    quantity = _tag(body, f'id="quantity-{line.cart_line_id}"')
    assert 'type="number"' in quantity
    assert 'value="11"' in quantity
    assert CartLine.objects.get(pk=line.pk).quantity == 1


# trace: FR-022
def test_cart_update_line_screen_shows_quantity_limit_message_of_scr_005(buyer, stock_unit):
    """数量上限超過のメッセージ領域の表示は SCR-005-OP01 の定めどおりとする。

    SCR-005-OP01：数量上限超過（QUANTITY_LIMIT_EXCEEDED）はメッセージ領域に
    「同じ規格は1注文につき10個までです（現在のカート内数量：n個）。」を表示する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()
    request = _request(
        f"/cart/lines/{line.cart_line_id}/update", method="post", data={"quantity": "11"}, user=buyer
    )

    response = views_cart.update_line(request, str(line.cart_line_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "同じ規格は1注文につき10個までです（現在のカート内数量：1個）。" in body


# trace: FR-022
def test_cart_update_line_screen_keeps_other_lines_quantity_on_error(buyer, item, supplier):
    """数量変更の失敗時、入力値を保持するのは対象明細だけとし、他の明細は現在の数量を表示する。"""
    other_unit = _helpers.make_stock_unit(item, supplier, sku="SKU-020", quantity=50)
    target_unit = _helpers.make_stock_unit(item, supplier, sku="SKU-021", quantity=50)
    carts.add_line(buyer, other_unit.stock_unit_id, 2)
    carts.add_line(buyer, target_unit.stock_unit_id, 1)
    from shop.models import CartLine

    other_line = CartLine.objects.get(stock_unit=other_unit)
    target_line = CartLine.objects.get(stock_unit=target_unit)
    request = _request(
        f"/cart/lines/{target_line.cart_line_id}/update", method="post", data={"quantity": "11"}, user=buyer
    )

    response = views_cart.update_line(request, str(target_line.cart_line_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert 'value="11"' in _tag(body, f'id="quantity-{target_line.cart_line_id}"')
    assert 'value="2"' in _tag(body, f'id="quantity-{other_line.cart_line_id}"')


# trace: FR-022
def test_cart_update_line_screen_shows_field_error_for_invalid_quantity(buyer, stock_unit):
    """数量の入力エラー（0以下・整数以外）は数量欄の近傍に入力エラーを表示する（SCR-005-OP01）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()
    request = _request(
        f"/cart/lines/{line.cart_line_id}/update", method="post", data={"quantity": "0"}, user=buyer
    )

    response = views_cart.update_line(request, str(line.cart_line_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 400
    assert "数量は1以上の整数で入力してください。" in body
    assert 'value="0"' in _tag(body, f'id="quantity-{line.cart_line_id}"')
    assert CartLine.objects.get(pk=line.pk).quantity == 1


# trace: FR-022
def test_cart_update_line_screen_shows_success_message_of_scr_005(buyer, stock_unit):
    """数量変更の成功時は SCR-005-OP01 の完了メッセージを表示し、カート画面を再表示する。

    SCR-005-OP01：【成功時】本画面を再表示し、メッセージ領域に「数量を変更しました。」を表示し、
    金額内訳とヘッダのカート合計点数を更新する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()
    request = _request(
        f"/cart/lines/{line.cart_line_id}/update", method="post", data={"quantity": "3"}, user=buyer
    )

    response = views_cart.update_line(request, str(line.cart_line_id))

    assert response.status_code == 302
    assert response["Location"] == "/cart"
    assert request.session[session.FLASH_KEY] == "数量を変更しました。"
    assert CartLine.objects.get(pk=line.pk).quantity == 3


# trace: FR-023
def test_cart_remove_line_screen_redirects(buyer, stock_unit):
    """明細削除後はカート画面へ遷移し、SCR-005-OP02 の文言を表示する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    from shop.models import CartLine

    line = CartLine.objects.get()
    request = _request(f"/cart/lines/{line.cart_line_id}/delete", method="post", user=buyer)

    response = views_cart.remove_line(request, str(line.cart_line_id))

    assert response.status_code == 302
    assert CartLine.objects.count() == 0
    assert request.session[session.FLASH_KEY] == "カートから削除しました。"


# trace: FR-024
def test_cart_apply_coupon_screen_shows_business_error(buyer, stock_unit):
    """該当するクーポンがない場合は SCR-005-OP03 の文言をカート画面に表示する。

    SCR-005-OP03：該当なし（COUPON_NOT_FOUND）は「入力したクーポンコードは存在しません。」を
    メッセージ領域に表示する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    request = _request("/cart/apply-coupon", method="post", data={"code": "NOTEXIST"}, user=buyer)

    response = views_cart.apply_coupon(request)

    assert response.status_code == 409
    assert "入力したクーポンコードは存在しません。" in response.content.decode("utf-8")


# trace: FR-024
def test_cart_apply_coupon_screen_shows_code_field_error_of_scr_005(buyer, stock_unit):
    """クーポンコードの入力エラーは、クーポンコード欄の近傍に SCR-005-OP03 の文言で表示する。

    SCR-005-OP03：入力エラーはクーポンコード欄の近傍に
    「クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。」を表示する。
    画面表示（SCR-005-OP03）と API 応答（api-contract 6.2）は別の要件であり、
    画面は同じ業務例外を捕捉して表示へ変換する（ADDR-007 DD-008）。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    request = _request("/cart/apply-coupon", method="post", data={"code": "INVALID@CODE"}, user=buyer)

    response = views_cart.apply_coupon(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 400
    form = _form_block(body, "/cart/apply-coupon")
    assert "クーポンコードは英字・数字・ハイフンの20文字以内で入力してください。" in form


# trace: FR-024
def test_cart_apply_coupon_screen_shows_cart_empty_message_of_scr_005(buyer):
    """カートが空のときのクーポン適用は SCR-005-OP03 の文言を表示する。

    SCR-005-OP03：カートが空（CART_EMPTY）は
    「カートに商品がないため、クーポンを適用できません。」を表示する。
    """
    request = _request("/cart/apply-coupon", method="post", data={"code": "SAVE500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    assert response.status_code == 409
    assert "カートに商品がないため、クーポンを適用できません。" in response.content.decode("utf-8")


# trace: FR-024
def _period_text(valid_from, valid_until):
    """SCR-005-OP03・SCR-006-OP01 が定める有効期間の併記文字列を組み立てる。

    形式は「有効期間：YYYY/MM/DD HH:MM〜YYYY/MM/DD HH:MM」とする。
    """
    pattern = "%Y/%m/%d %H:%M"
    return f"有効期間：{valid_from.strftime(pattern)}〜{valid_until.strftime(pattern)}"


# trace: FR-024
def test_cart_apply_coupon_screen_shows_success_message_of_scr_005(buyer, stock_unit):
    """クーポン適用の成功時は SCR-005-OP03 の完了メッセージを表示し、カート画面を再表示する。

    SCR-005-OP03：【成功時】本画面を再表示し、メッセージ領域に「クーポンを適用しました。」を表示し、
    適用中クーポンと金額内訳を更新する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    _helpers.make_coupon(code="SAVE500", name="500円割引", discount_value=500)
    request = _request("/cart/apply-coupon", method="post", data={"code": "SAVE500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    assert response.status_code == 302
    assert response["Location"] == "/cart"
    assert request.session[session.FLASH_KEY] == "クーポンを適用しました。"
    assert carts.view_cart(buyer)["coupon"]["code"] == "SAVE500"


# trace: FR-024
def test_cart_apply_coupon_screen_shows_already_applied_message_of_scr_005(buyer, stock_unit):
    """クーポン適用済みのときは SCR-005-OP03 の文言を適用中のクーポンコードつきで表示する。

    SCR-005-OP03：適用済み（COUPON_ALREADY_APPLIED）は
    「クーポンは1注文につき1枚までです（適用中のクーポン：クーポンコード）。
    別のクーポンを使う場合は、適用中のクーポンを解除してください。」を表示する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    _helpers.make_coupon(code="SAVE1000", name="1000円割引", discount_value=1000)
    _helpers.make_coupon(code="SAVE500", name="500円割引", discount_value=500)
    carts.apply_coupon(buyer, "SAVE1000")
    request = _request("/cart/apply-coupon", method="post", data={"code": "SAVE500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert (
        "クーポンは1注文につき1枚までです（適用中のクーポン：SAVE1000）。"
        "別のクーポンを使う場合は、適用中のクーポンを解除してください。"
    ) in body
    assert carts.view_cart(buyer)["coupon"]["code"] == "SAVE1000"


# trace: FR-024
def test_cart_apply_coupon_screen_shows_not_yet_valid_message_of_scr_005(buyer, stock_unit):
    """有効期間の開始前のクーポンは SCR-005-OP03 の文言を有効期間つきで表示する。

    SCR-005-OP03：開始前（COUPON_NOT_YET_VALID）は
    「このクーポンは有効期間の開始前です（有効期間：YYYY/MM/DD HH:MM〜YYYY/MM/DD HH:MM）。」を表示する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    valid_from = timeutils.now() + timedelta(days=1)
    valid_until = valid_from + timedelta(days=7)
    _helpers.make_coupon(code="FUTURE500", discount_value=500, valid_from=valid_from, valid_until=valid_until)
    request = _request("/cart/apply-coupon", method="post", data={"code": "FUTURE500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert f"このクーポンは有効期間の開始前です（{_period_text(valid_from, valid_until)}）。" in body
    assert carts.view_cart(buyer)["coupon"] is None


# trace: FR-024
def test_cart_apply_coupon_screen_shows_expired_message_of_scr_005(buyer, stock_unit):
    """有効期間が終了したクーポンは SCR-005-OP03 の文言を有効期間つきで表示する。

    SCR-005-OP03：期限切れ（COUPON_EXPIRED）は
    「このクーポンは有効期間が終了しています（有効期間：YYYY/MM/DD HH:MM〜YYYY/MM/DD HH:MM）。」を表示する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    valid_until = timeutils.now() - timedelta(days=1)
    valid_from = valid_until - timedelta(days=7)
    _helpers.make_coupon(code="PAST500", discount_value=500, valid_from=valid_from, valid_until=valid_until)
    request = _request("/cart/apply-coupon", method="post", data={"code": "PAST500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert f"このクーポンは有効期間が終了しています（{_period_text(valid_from, valid_until)}）。" in body
    assert carts.view_cart(buyer)["coupon"] is None


# trace: FR-024
def test_cart_apply_coupon_screen_shows_min_spend_not_met_message_of_scr_005(buyer, stock_unit):
    """最低購入金額に満たない場合は SCR-005-OP03 の文言を最低購入金額・小計つきで表示する。

    SCR-005-OP03：最低購入金額未達（COUPON_MIN_SPEND_NOT_MET）は
    「小計が最低購入金額に達していません（最低購入金額：n円、現在の小計：n円）。」を表示する。
    小計は税抜1,000円の在庫単位1点（SCR-005-V16）、最低購入金額は5,000円とする。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    _helpers.make_coupon(code="BIG500", discount_value=500, min_spend=5000)
    request = _request("/cart/apply-coupon", method="post", data={"code": "BIG500"}, user=buyer)

    response = views_cart.apply_coupon(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "小計が最低購入金額に達していません（最低購入金額：5,000円、現在の小計：1,000円）。" in body
    assert carts.view_cart(buyer)["coupon"] is None


# trace: FR-025
def test_cart_remove_coupon_screen_redirects(buyer, stock_unit):
    """クーポン解除後はカート画面へ遷移する。"""
    request = _request("/cart/remove-coupon", method="post", user=buyer)

    response = views_cart.remove_coupon(request)

    assert response.status_code == 302
    assert response["Location"] == "/cart"


# trace: NFR-SC-06
@pytest.mark.parametrize(
    ("handler", "status"),
    [
        (views_error.bad_request, 400),
        (views_error.permission_denied, 403),
        (views_error.page_not_found, 404),
    ],
)
def test_error_screens(handler, status):
    """エラー画面（SCR-901）は区分ごとの状態と利用者向けメッセージを表示する。"""
    response = handler(_request("/"), None)

    assert response.status_code == status
    assert "web/error.html" not in response.content.decode("utf-8")


# trace: NFR-SC-06
@pytest.mark.parametrize(
    ("handler", "status", "title", "message"),
    [
        (
            views_error.page_not_found,
            404,
            "お探しのページ・データが見つかりません",
            "指定されたページまたはデータは存在しないか、表示できません。一覧から選び直してください。",
        ),
        (
            views_error.permission_denied,
            403,
            "この画面・操作を利用する権限がありません",
            "権限のある利用者でログインしてください。",
        ),
    ],
)
def test_error_screens_show_scr_901_texts(handler, status, title, message):
    """SCR-901-V01・V02 の見出しとメッセージを表示する。"""
    response = handler(_request("/"), None)

    body = response.content.decode("utf-8")
    assert response.status_code == status
    assert title in body
    assert message in body


# trace: NFR-SC-06
def test_server_error_screen_hides_internal_details():
    """システムエラー画面は SCR-901-V03 の見出し・メッセージを表示し、内部情報を表示しない（UI-34）。"""
    response = views_error.server_error(_request("/"))

    body = response.content.decode("utf-8")
    assert response.status_code == 500
    assert "システムエラーが発生しました" in body
    assert "時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。" in body
    assert "Traceback" not in body
