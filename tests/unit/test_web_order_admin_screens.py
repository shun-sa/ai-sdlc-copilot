# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044
# trace: FR-045, FR-024, NFR-SC-03, NFR-US-04, ADDR-010, ADDR-011
"""注文手続き〜注文詳細（SCR-006〜SCR-010）と管理者画面（SCR-101〜SCR-103）の単体テスト。

期待結果は画面・帳票要件の各画面定義と、対応する機能要件（FR-030〜FR-034、FR-040〜FR-045）の
処理内容・例外、NFR-US-04（入力エラーの表示）、NFR-SC-03（権限判定）から導出する。
"""

from __future__ import annotations

import pytest
from _helpers import (
    field_error_reasons,
    input_element,
    make_coupon,
    make_item,
    make_stock_unit,
    make_supplier,
    make_user,
    shipping_input,
)
from carts import services as cart_services
from carts.models import DISCOUNT_FIXED, DISCOUNT_PERCENTAGE
from orders import services as order_services
from orders.models import PurchaseOrder
from web.support import SESSION_FLASH

pytestmark = pytest.mark.django_db


# trace: FR-030
def fill_cart(user, *, price: int = 3000, quantity: int = 2, stock: int = 10):
    """注文手続きの前提となるカートを用意する（テスト補助）。"""
    unit = make_stock_unit(make_item(name="注文画面商品"), price=price, quantity=stock, variant_name="青")
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": quantity})
    return unit


# trace: FR-030
def place_order(user):
    """注文を1件作成する（テスト補助）。"""
    unit = fill_cart(user)
    return order_services.checkout(user, shipping_input()), unit


# trace: FR-024, FR-030
def place_order_with_coupon(user, *, code: str, discount_type: str = DISCOUNT_FIXED, discount_value: int = 1000):
    """クーポンを適用した注文を1件作成する（テスト補助）。"""
    fill_cart(user, price=5000, quantity=1)
    coupon = make_coupon(code=code, discount_type=discount_type, discount_value=discount_value, min_spend=0)
    cart_services.apply_coupon(user, {"code": code})
    return order_services.checkout(user, shipping_input()), coupon


# trace: FR-030
def test_checkout_screen_shows_cart_and_prefectures(buyer, logged_in_screen_client):
    """SCR-006：注文手続きはカート内容と配送先入力（都道府県の選択肢）を表示する。"""
    fill_cart(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get("/checkout/")

    body = response.content.decode()
    assert response.status_code == 200
    assert "注文画面商品" in body
    assert "東京都" in body


# trace: FR-030
def test_checkout_screen_redirects_when_cart_is_empty(buyer, logged_in_screen_client):
    """E-030-04：カートが空の場合は SCR-005 へ戻す。"""
    client = logged_in_screen_client(buyer)

    response = client.get("/checkout/")

    assert response["Location"] == "/cart/"
    assert client.session[SESSION_FLASH] == "カートに商品がありません。"


# trace: FR-030
def test_checkout_screen_confirms_order_and_redirects_to_complete(buyer, logged_in_screen_client):
    """FR-030：注文確定後は SCR-007（注文完了）へ遷移する。"""
    fill_cart(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post("/checkout/", shipping_input())

    order = PurchaseOrder.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/orders/{order.pk}/complete/"


# trace: NFR-US-04
def test_checkout_screen_shows_field_errors(buyer, logged_in_screen_client):
    """E-030-03：配送先の入力エラーは項目別の理由を表示し、入力値を保持する。"""
    fill_cart(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post("/checkout/", shipping_input(postal_code="", recipient_name="受取 花子"))

    body = response.content.decode()
    assert response.status_code == 400
    assert "郵便番号を入力してください。" in body
    assert "受取 花子" in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_screen_shows_business_error(buyer, logged_in_screen_client):
    """E-030-07：在庫不足は注文手続き画面に不足する規格を表示する（409）。"""
    unit = fill_cart(buyer, quantity=3, stock=10)
    unit.quantity = 1
    unit.save(update_fields=["quantity"])
    client = logged_in_screen_client(buyer)

    response = client.post("/checkout/", shipping_input())

    assert response.status_code == 409
    assert "在庫が不足している商品があります" in response.content.decode()


# trace: FR-030
def test_checkout_screen_shows_coupon_error(buyer, logged_in_screen_client):
    """E-030-10：クーポンが利用できない場合は解除を促す文言を表示する。"""
    coupon = make_coupon(code="SCR-ORD-MIN", min_spend=100000)
    fill_cart(buyer, price=1000, quantity=1)
    cart = cart_services.get_open_cart(buyer)
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    client = logged_in_screen_client(buyer)

    response = client.post("/checkout/", shipping_input())

    assert response.status_code == 409
    assert "カートでクーポンを解除する" in response.content.decode()


# trace: FR-033
def test_order_complete_screen_shows_order(buyer, logged_in_screen_client):
    """SCR-007：注文完了は注文番号と金額を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get(f"/orders/{order.pk}/complete/")

    body = response.content.decode()
    assert response.status_code == 200
    assert order.order_number in body


# trace: FR-031
def test_payment_screen_shows_mock_result_options(buyer, logged_in_screen_client):
    """SCR-008：支払画面は注文番号・合計と模擬決済の結果の選択を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get(f"/orders/{order.pk}/pay/")

    body = response.content.decode()
    assert response.status_code == 200
    assert order.order_number in body
    assert "承認" in body


# trace: FR-031
def test_payment_screen_redirects_when_status_is_not_created(buyer, logged_in_screen_client):
    """SCR-008-OP01：注文受付以外の注文は支払できない旨を表示して SCR-010 へ戻す。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(buyer)

    response = client.get(f"/orders/{order.pk}/pay/")

    assert response["Location"] == f"/orders/{order.pk}/"
    assert client.session[SESSION_FLASH] == "この注文は支払できません（現在の状態：支払済）。"


# trace: FR-031
def test_payment_screen_approves_and_redirects_to_detail(buyer, logged_in_screen_client):
    """FR-031：承認後は SCR-010 へ遷移し、支払が完了した旨を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/pay/", {"mock_result": "approve"})

    order.refresh_from_db()
    assert response["Location"] == f"/orders/{order.pk}/"
    assert order.status == "paid"
    assert client.session[SESSION_FLASH] == "支払が完了しました。"


# trace: FR-031
def test_payment_screen_shows_declined_message(buyer, logged_in_screen_client):
    """E-031-06：否認は支払画面にメッセージを表示する（409）。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/pay/", {"mock_result": "decline"})

    assert response.status_code == 409
    assert "決済が承認されませんでした" in response.content.decode()


# trace: NFR-US-04
def test_payment_screen_shows_validation_error(buyer, logged_in_screen_client):
    """E-031-03：模擬決済指示が不正な場合は400で項目別の理由を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/pay/", {"mock_result": "APPROVE"})

    assert response.status_code == 400
    assert "模擬決済の結果を選択してください。" in response.content.decode()


# trace: FR-031
def test_payment_screen_shows_payment_service_error(buyer, logged_in_screen_client, monkeypatch):
    """E-031-07：連携エラーは502で決済が完了していない旨を表示する。"""
    from payments import services as payment_services
    from payments.gateway import PaymentGatewayError

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    def fail(order_number, amount, mock_result):
        raise PaymentGatewayError("timeout")

    monkeypatch.setattr(payment_services, "authorize", fail)

    response = client.post(f"/orders/{order.pk}/pay/", {"mock_result": "approve"})

    assert response.status_code == 502
    assert "決済サービスとの通信でエラーが発生しました" in response.content.decode()


# trace: FR-031
def test_payment_screen_reports_concurrent_status_change(buyer, logged_in_screen_client, monkeypatch):
    """SCR-008-OP01：支払操作中に状態が変わった場合は状態不正の文言で SCR-010 へ戻す。"""
    from common.exceptions import InvalidStatusTransition

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    def raise_invalid(user, order_id, payload):
        raise InvalidStatusTransition(context={"current_status": "cancelled"})

    monkeypatch.setattr(order_services, "pay", raise_invalid)

    response = client.post(f"/orders/{order.pk}/pay/", {"mock_result": "approve"})

    assert response["Location"] == f"/orders/{order.pk}/"
    assert client.session[SESSION_FLASH] == "この注文は支払できません（現在の状態：キャンセル済）。"


# trace: FR-032
def test_order_history_screen_lists_own_orders(buyer, logged_in_screen_client):
    """SCR-009：注文履歴一覧は本人の注文を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get("/orders/")

    assert response.status_code == 200
    assert order.order_number in response.content.decode()


# trace: FR-032
def test_order_history_screen_shows_error_for_invalid_page(buyer, logged_in_screen_client):
    """E-032-03：ページ番号の誤りは400で誤りがある旨を表示する。"""
    client = logged_in_screen_client(buyer)

    response = client.get("/orders/?page=0")

    assert response.status_code == 400
    assert "ページの指定に誤りがあります。" in response.content.decode()


# trace: FR-033
def test_order_detail_screen_shows_order(buyer, logged_in_screen_client):
    """SCR-010：注文詳細は明細・金額・配送先・状態履歴を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get(f"/orders/{order.pk}/")

    body = response.content.decode()
    assert response.status_code == 200
    assert order.order_number in body
    assert "123-4567" in body
    assert "注文受付" in body
    assert "クーポンなし" in body


# trace: FR-033
def test_order_detail_screen_shows_applied_fixed_coupon(buyer, logged_in_screen_client):
    """SCR-010-V10：クーポンを適用した注文はクーポンコードと割引内容（定額）を表示する。"""
    order, _coupon = place_order_with_coupon(buyer, code="SCR-FIX-1000", discount_value=1000)
    client = logged_in_screen_client(buyer)

    body = client.get(f"/orders/{order.pk}/").content.decode()

    assert "SCR-FIX-1000" in body
    assert "1,000円引き" in body
    assert "クーポンなし" not in body


# trace: FR-042
def test_admin_order_detail_screen_shows_applied_percentage_coupon(buyer, admin_user, logged_in_screen_client):
    """SCR-103-V07：管理者の注文詳細も同じ項目・形式でクーポン（定率）を表示する。"""
    order, _coupon = place_order_with_coupon(
        buyer, code="SCR-PCT-10", discount_type=DISCOUNT_PERCENTAGE, discount_value=10
    )
    client = logged_in_screen_client(admin_user)

    body = client.get(f"/admin-console/orders/{order.pk}/").content.decode()

    assert "SCR-PCT-10" in body
    assert "10%引き" in body
    assert "クーポンなし" not in body


# trace: NFR-SC-03
def test_order_detail_of_other_buyer_is_not_found(buyer, logged_in_screen_client):
    """PRM-01：他の購入者の注文は SCR-901（対象なし）を表示する。"""
    other = make_user(email="other-screen@example.test")
    order, _unit = place_order(other)
    client = logged_in_screen_client(buyer)

    response = client.get(f"/orders/{order.pk}/")

    assert response.status_code == 404


# trace: FR-034
def test_cancel_order_screen_shows_message(buyer, logged_in_screen_client):
    """SCR-010-OP02：キャンセル後は注文詳細へ戻り、キャンセルした旨を表示する。"""
    order, unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/cancel/")

    unit.refresh_from_db()
    assert response["Location"] == f"/orders/{order.pk}/"
    assert client.session[SESSION_FLASH] == "注文をキャンセルしました。"
    assert unit.quantity == 10


# trace: FR-034
def test_cancel_paid_order_adds_refund_notice(buyer, logged_in_screen_client):
    """SCR-010-OP02：支払済の注文をキャンセルした場合は返金の取り扱いを併記する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/cancel/")

    assert response.status_code == 302
    assert "返金は当社が5営業日以内に行います。" in client.session[SESSION_FLASH]


# trace: FR-034
def test_cancel_order_shows_status_error(buyer, admin_user, logged_in_screen_client):
    """SCR-010-OP02：出荷済以降はキャンセルできない旨を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    order_services.ship(admin_user, order.pk, {})
    client = logged_in_screen_client(buyer)

    response = client.post(f"/orders/{order.pk}/cancel/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "この注文はキャンセルできません（現在の状態：出荷済）。"


# trace: NFR-SC-03
def test_admin_screens_reject_buyer(buyer, logged_in_screen_client):
    """E-040-02：購入者が管理者専用画面を要求した場合は SCR-901（権限なし）を表示する。"""
    client = logged_in_screen_client(buyer)

    assert client.get("/admin-console/stock-units/").status_code == 403
    assert client.get("/admin-console/orders/").status_code == 403


# trace: FR-040
def test_admin_stock_unit_list_shows_results(admin_user, logged_in_screen_client):
    """SCR-101：在庫単位一覧は商品名・仕入先・税抜価格・低在庫を表示する。"""
    supplier = make_supplier(supplier_code="SUP-SCR", name="画面仕入先")
    make_stock_unit(make_item(name="管理画面商品"), supplier=supplier, sku="SKU-SCR-01", price=1000, quantity=3)
    client = logged_in_screen_client(admin_user)

    response = client.get("/admin-console/stock-units/?sku=sku-scr")

    body = response.content.decode()
    assert response.status_code == 200
    assert "管理画面商品" in body
    assert "画面仕入先" in body
    assert "1,000円" in body


# trace: NFR-US-04
def test_admin_stock_unit_list_shows_validation_error(admin_user, logged_in_screen_client):
    """E-040-03：検索条件の誤りは400で入力値を保持して再表示する。"""
    client = logged_in_screen_client(admin_user)

    response = client.get("/admin-console/stock-units/?low_stock_only=yes")

    assert response.status_code == 400
    assert "検索条件に誤りがあります" in response.content.decode()


# trace: FR-041
def test_admin_order_list_shows_orders(buyer, admin_user, logged_in_screen_client):
    """SCR-102：注文一覧は注文番号・購入者・状態・合計を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    response = client.get("/admin-console/orders/?status=created")

    body = response.content.decode()
    assert response.status_code == 200
    assert order.order_number in body
    assert buyer.email in body


# trace: NFR-US-04
def test_admin_order_list_shows_validation_error(admin_user, logged_in_screen_client):
    """E-041-03：検索条件の誤りは400で項目別の理由を表示する。"""
    client = logged_in_screen_client(admin_user)

    response = client.get("/admin-console/orders/?order_number=PO-1")

    assert response.status_code == 400
    assert "注文番号は「PO-」と数字8桁で入力してください。" in response.content.decode()


# trace: FR-042
def test_admin_order_detail_shows_payment_records(buyer, admin_user, logged_in_screen_client):
    """SCR-103：注文詳細（管理）は購入者情報・決済記録・配送先を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(admin_user)

    response = client.get(f"/admin-console/orders/{order.pk}/")

    body = response.content.decode()
    assert response.status_code == 200
    assert buyer.email in body
    assert "承認" in body


# trace: FR-043
def test_admin_ship_registers_tracking_number(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP01：出荷登録後は注文詳細へ戻り、登録した旨を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/ship/", {"tracking_number": "TRACK-1"})

    order.refresh_from_db()
    assert response["Location"] == f"/admin-console/orders/{order.pk}/"
    assert order.status == "shipped"
    assert order.tracking_number == "TRACK-1"
    assert client.session[SESSION_FLASH] == "出荷登録しました。"


# trace: NFR-US-04
def test_admin_ship_shows_validation_error(buyer, admin_user, logged_in_screen_client):
    """E-043-03：配送伝票番号の誤りは400で項目別の理由を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/ship/", {"tracking_number": "A" * 31})

    assert response.status_code == 400
    assert "配送伝票番号は英数字とハイフンの30文字以内で入力してください。" in response.content.decode()


# trace: FR-043, NFR-US-04
def test_admin_ship_keeps_entered_tracking_number_on_validation_error(buyer, admin_user, logged_in_screen_client):
    """E-043-03／SCR-103-OP01：配送伝票番号の入力エラーは欄の近傍へ理由を表示し、入力値を保持して
    本画面（SCR-103）を再表示する（データは変更しない。CMN-17、UI-19）。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    client = logged_in_screen_client(admin_user)
    entered = "TRACK-" + "9" * 30

    response = client.post(f"/admin-console/orders/{order.pk}/ship/", {"tracking_number": entered})

    body = response.content.decode()
    tracking_input = input_element(body, "tracking_number")
    order.refresh_from_db()
    assert response.status_code == 400
    assert f'value="{entered}"' in tracking_input
    assert field_error_reasons(body, after=tracking_input) == [
        "配送伝票番号は英数字とハイフンの30文字以内で入力してください。"
    ]
    assert order.status == "paid"
    assert order.tracking_number is None


# trace: FR-043
def test_admin_ship_shows_status_error(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP01：支払済以外の注文は出荷登録できない旨を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/ship/", {})

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "この注文は出荷登録できません（現在の状態：注文受付）。"


# trace: FR-044
def test_admin_deliver_registers_delivery(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP02：配達完了登録後は注文詳細へ戻り、登録した旨を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    order_services.ship(admin_user, order.pk, {})
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/deliver/")

    order.refresh_from_db()
    assert response.status_code == 302
    assert order.status == "delivered"
    assert client.session[SESSION_FLASH] == "配達完了を登録しました。"


# trace: FR-044
def test_admin_deliver_shows_status_error(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP02：出荷済以外の注文は配達完了登録できない旨を表示する。"""
    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/deliver/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "この注文は配達完了登録できません（現在の状態：注文受付）。"


# trace: FR-045
def test_admin_cancel_restores_stock_and_shows_message(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP03：管理者のキャンセル後は在庫を戻した旨を表示する。"""
    order, unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/cancel/")

    unit.refresh_from_db()
    assert response["Location"] == f"/admin-console/orders/{order.pk}/"
    assert unit.quantity == 10
    assert client.session[SESSION_FLASH] == "注文をキャンセルしました。在庫を戻しました。"


# trace: FR-045
def test_admin_cancel_shows_status_error(buyer, admin_user, logged_in_screen_client):
    """SCR-103-OP03：配達完了の注文はキャンセルできない旨を表示する。"""
    order, _unit = place_order(buyer)
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})
    order_services.ship(admin_user, order.pk, {})
    order_services.deliver(admin_user, order.pk)
    client = logged_in_screen_client(admin_user)

    response = client.post(f"/admin-console/orders/{order.pk}/cancel/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "この注文はキャンセルできません（現在の状態：配達完了）。"


# trace: FR-045
def test_admin_operations_show_business_error(buyer, admin_user, logged_in_screen_client, monkeypatch):
    """業務エラーは管理者画面のメッセージ領域へ表示する。"""
    from common.exceptions import InsufficientStock

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    def raise_business(admin, order_id):
        raise InsufficientStock(context={"shortages": []})

    monkeypatch.setattr(order_services, "cancel_by_admin", raise_business)

    response = client.post(f"/admin-console/orders/{order.pk}/cancel/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "在庫が不足しています。"


# trace: FR-043
def test_admin_ship_shows_business_error(buyer, admin_user, logged_in_screen_client, monkeypatch):
    """出荷登録の業務エラーもメッセージ領域へ表示する。"""
    from common.exceptions import InsufficientStock

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    def raise_business(admin, order_id, payload):
        raise InsufficientStock(context={"shortages": []})

    monkeypatch.setattr(order_services, "ship", raise_business)

    response = client.post(f"/admin-console/orders/{order.pk}/ship/", {})

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "在庫が不足しています。"


# trace: FR-044
def test_admin_deliver_shows_business_error(buyer, admin_user, logged_in_screen_client, monkeypatch):
    """配達完了登録の業務エラーもメッセージ領域へ表示する。"""
    from common.exceptions import InsufficientStock

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(admin_user)

    def raise_business(admin, order_id):
        raise InsufficientStock(context={"shortages": []})

    monkeypatch.setattr(order_services, "deliver", raise_business)

    response = client.post(f"/admin-console/orders/{order.pk}/deliver/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "在庫が不足しています。"


# trace: FR-034
def test_cancel_order_shows_business_error(buyer, logged_in_screen_client, monkeypatch):
    """購入者のキャンセルの業務エラーもメッセージ領域へ表示する。"""
    from common.exceptions import InsufficientStock

    order, _unit = place_order(buyer)
    client = logged_in_screen_client(buyer)

    def raise_business(user, order_id):
        raise InsufficientStock(context={"shortages": []})

    monkeypatch.setattr(order_services, "cancel_by_buyer", raise_business)

    response = client.post(f"/orders/{order.pk}/cancel/")

    assert response.status_code == 302
    assert client.session[SESSION_FLASH] == "在庫が不足しています。"


# trace: FR-030
def test_checkout_screen_redirects_when_cart_becomes_empty(buyer, logged_in_screen_client, monkeypatch):
    """E-030-04：確定操作時にカートが空になっていた場合は SCR-005 へ戻す。"""
    from common.exceptions import CartEmpty

    fill_cart(buyer)
    client = logged_in_screen_client(buyer)

    def raise_cart_empty(user, payload):
        raise CartEmpty()

    monkeypatch.setattr(order_services, "checkout", raise_cart_empty)

    response = client.post("/checkout/", shipping_input())

    assert response["Location"] == "/cart/"
    assert client.session[SESSION_FLASH] == "カートに商品がありません。"
