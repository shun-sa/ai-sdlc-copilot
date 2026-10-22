# trace: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-041, FR-042, FR-043, FR-044, FR-045, ADDR-001, ADDR-002
"""注文画面（SCR-006〜SCR-010）と管理者画面（SCR-101〜SCR-103）の単体テスト。

期待値は FR-030〜FR-034・FR-040〜FR-045 の画面表示と例外の振る舞いから導出する。
"""
from datetime import timedelta

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from shop.common import timeutils
from shop.models import PurchaseOrder, PurchaseOrderStatus
from shop.payments import client as payment_client
from shop.payments.gateway import PaymentGatewayError
from shop.services import carts
from shop.tests.unit import _helpers
from shop.web import session, views_admin, views_orders

pytestmark = pytest.mark.django_db


# trace: ADDR-002
def _form_block(body, action):
    """画面本文から指定した action の `<form>` 〜 `</form>` の範囲を取り出す。

    入力項目の「近傍」に表示する文言（SCR-008-OP01、SCR-103-OP01）を、
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


# trace: FR-030
def test_checkout_form_screen_shows_cart(buyer, stock_unit):
    """注文手続き（SCR-006）はカート内容と配送先入力欄を表示する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)

    response = views_orders.checkout_form(_request("/checkout", user=buyer))

    assert response.status_code == 200
    assert "配送先" in response.content.decode("utf-8")


# trace: FR-030
def test_checkout_screen_creates_order_and_redirects(buyer, stock_unit):
    """注文確定の成功時は注文完了画面へ遷移する。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    order = PurchaseOrder.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/purchase-orders/{order.purchase_order_id}/complete"


# trace: FR-030
def test_checkout_screen_shows_validation_errors(buyer, stock_unit):
    """配送先の入力エラーは注文手続き画面に表示する（400）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    data = dict(_helpers.VALID_ADDRESS)
    data["postal_code"] = "abc"
    request = _request("/checkout/confirm", method="post", data=data, user=buyer)

    response = views_orders.checkout(request)

    assert response.status_code == 400
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_screen_redirects_to_cart_when_empty(buyer):
    """カートが空の場合はカート画面へ戻し、メッセージを表示する。"""
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    assert response.status_code == 302
    assert response["Location"] == "/cart"
    assert request.session[session.FLASH_KEY] == "カートに商品がありません。"


# trace: FR-030
def test_checkout_screen_shows_stock_error(buyer, item, supplier):
    """在庫不足は注文手続き画面に SCR-006-OP01 の文言で表示する（409）。

    SCR-006-OP01：在庫不足（INSUFFICIENT_STOCK）は
    「在庫が不足している商品があります。カートで数量を変更してください。」と、
    不足するすべての規格の SKU と現在の在庫数量の一覧をメッセージ領域に表示する。
    """
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-010", quantity=2)
    carts.add_line(buyer, unit.stock_unit_id, 2)
    unit.quantity = 1
    unit.save(update_fields=["quantity"])
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "在庫が不足している商品があります。カートで数量を変更してください。" in body
    assert "SKU-010（現在の在庫数量：1個）" in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_screen_shows_item_not_available_message_of_scr_006(buyer, item, supplier):
    """販売終了の商品を含む注文確定は SCR-006-OP01 の文言と該当明細の一覧を表示する（409）。

    SCR-006-OP01：販売終了（ITEM_NOT_AVAILABLE）は
    「販売を終了した商品がカートに含まれています。カートから削除してください。」と、
    該当するすべての明細の商品名（規格名）の一覧をメッセージ領域に表示する。
    """
    unit = _helpers.make_stock_unit(item, supplier, sku="SKU-030", variant_name="赤", quantity=5)
    carts.add_line(buyer, unit.stock_unit_id, 1)
    item.is_public = False
    item.save(update_fields=["is_public"])
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert "販売を終了した商品がカートに含まれています。カートから削除してください。" in body
    assert f"<li>{item.name}（赤）</li>" in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def _apply_coupon_then(buyer, stock_unit, **changes):
    """適用条件を満たすクーポンを適用した後、注文確定時に条件を満たさなくなる状態を作る。

    SCR-006-OP01 のクーポン条件不成立は、カートへの適用後に条件が変わった場合に発生する。
    """
    carts.add_line(buyer, stock_unit.stock_unit_id, 1)
    coupon = _helpers.make_coupon(code="SAVE500", name="500円割引", discount_value=500)
    carts.apply_coupon(buyer, coupon.code)
    for field, value in changes.items():
        setattr(coupon, field, value)
    coupon.save(update_fields=list(changes))
    return coupon


# trace: FR-030
def test_checkout_screen_shows_coupon_expired_message_of_scr_006(buyer, stock_unit):
    """有効期間が終了したクーポンの注文確定は SCR-006-OP01 の文言と有効期間を表示する（409）。

    SCR-006-OP01：クーポン条件不成立は「適用中のクーポンは利用できません（理由）。
    カートでクーポンを解除するか、条件を満たしてから注文してください。」を表示し、
    理由には「有効期間：YYYY/MM/DD HH:MM〜YYYY/MM/DD HH:MM」を含める。
    """
    valid_until = timeutils.now() - timedelta(days=1)
    valid_from = valid_until - timedelta(days=7)
    _apply_coupon_then(buyer, stock_unit, valid_from=valid_from, valid_until=valid_until)
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    body = response.content.decode("utf-8")
    pattern = "%Y/%m/%d %H:%M"
    period = f"有効期間：{valid_from.strftime(pattern)}〜{valid_until.strftime(pattern)}"
    assert response.status_code == 409
    assert (
        f"適用中のクーポンは利用できません（{period}）。"
        "カートでクーポンを解除するか、条件を満たしてから注文してください。"
    ) in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_screen_shows_coupon_not_yet_valid_message_of_scr_006(buyer, stock_unit):
    """有効期間の開始前のクーポンの注文確定は SCR-006-OP01 の文言と有効期間を表示する（409）。"""
    valid_from = timeutils.now() + timedelta(days=1)
    valid_until = valid_from + timedelta(days=7)
    _apply_coupon_then(buyer, stock_unit, valid_from=valid_from, valid_until=valid_until)
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    body = response.content.decode("utf-8")
    pattern = "%Y/%m/%d %H:%M"
    period = f"有効期間：{valid_from.strftime(pattern)}〜{valid_until.strftime(pattern)}"
    assert response.status_code == 409
    assert (
        f"適用中のクーポンは利用できません（{period}）。"
        "カートでクーポンを解除するか、条件を満たしてから注文してください。"
    ) in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_checkout_screen_shows_coupon_min_spend_message_of_scr_006(buyer, stock_unit):
    """最低購入金額に満たないクーポンの注文確定は SCR-006-OP01 の文言と条件を表示する（409）。

    SCR-006-OP01：最低購入金額未達の理由には「最低購入金額：n円、現在の小計：n円」を含める。
    小計は税抜1,000円の在庫単位1点、最低購入金額は5,000円とする。
    """
    _apply_coupon_then(buyer, stock_unit, min_spend=5000)
    request = _request("/checkout/confirm", method="post", data=dict(_helpers.VALID_ADDRESS), user=buyer)

    response = views_orders.checkout(request)

    body = response.content.decode("utf-8")
    assert response.status_code == 409
    assert (
        "適用中のクーポンは利用できません（最低購入金額：5,000円、現在の小計：1,000円）。"
        "カートでクーポンを解除するか、条件を満たしてから注文してください。"
    ) in body
    assert PurchaseOrder.objects.count() == 0


# trace: FR-030
def test_order_complete_screen_shows_order_number(buyer, stock_unit):
    """注文完了（SCR-007）は注文番号と合計を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_orders.order_complete(_request("/", user=buyer), str(order.purchase_order_id))

    assert "PO-00000001" in response.content.decode("utf-8")


# trace: FR-031
def test_pay_screen_shows_payment_form(buyer, stock_unit):
    """支払（SCR-008）は模擬決済の結果選択を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_orders.pay(_request("/pay", user=buyer), str(order.purchase_order_id))

    assert response.status_code == 200


# trace: FR-031
def test_pay_screen_redirects_on_approval(buyer, stock_unit):
    """承認時は注文詳細画面へ遷移し、完了メッセージを表示する。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/pay", method="post", data={"mock_result": "approve"}, user=buyer)

    response = views_orders.pay(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert response["Location"] == f"/purchase-orders/{order.purchase_order_id}"
    assert request.session[session.FLASH_KEY] == "支払が完了しました。"


# trace: FR-031
def test_pay_screen_shows_declined_message(buyer, stock_unit):
    """否認時は支払画面に留まり、SCR-008-OP01 の文言を表示する（409）。

    SCR-008-OP01：否認（PAYMENT_DECLINED）は本画面に留まり
    「決済が承認されませんでした。お支払いは完了していません。再度お支払いください。」を表示する
    （状態は注文受付のまま）。
    """
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/pay", method="post", data={"mock_result": "decline"}, user=buyer)

    response = views_orders.pay(request, str(order.purchase_order_id))

    assert response.status_code == 409
    assert (
        "決済が承認されませんでした。お支払いは完了していません。再度お支払いください。"
        in response.content.decode("utf-8")
    )
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CREATED


# trace: FR-031
def test_pay_screen_shows_payment_service_error_message(buyer, stock_unit, monkeypatch):
    """連携エラー時は支払画面に留まり、SCR-008-OP01 の文言を表示する。

    SCR-008-OP01：連携エラー（PAYMENT_SERVICE_ERROR）は本画面に留まり
    「決済サービスとの通信でエラーが発生しました。お支払いは完了していません。時間をおいて再度お支払いください。」
    を表示する（状態は注文受付のまま）。
    """
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    def raise_gateway_error(payment_request):
        raise PaymentGatewayError("連携エラー")

    monkeypatch.setattr(payment_client, "authorize", raise_gateway_error)
    request = _request("/pay", method="post", data={"mock_result": "approve"}, user=buyer)

    response = views_orders.pay(request, str(order.purchase_order_id))

    assert response.status_code == 502
    assert (
        "決済サービスとの通信でエラーが発生しました。お支払いは完了していません。時間をおいて再度お支払いください。"
        in response.content.decode("utf-8")
    )
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CREATED


# trace: FR-031, FR-033
def test_pay_screen_redirects_to_order_detail_on_invalid_status(buyer, stock_unit):
    """状態不正のときは SCR-010 へ遷移し、SCR-008-OP01 の文言を表示する。

    SCR-008-OP01：状態不正（INVALID_STATUS_TRANSITION。二重送信の2回目以降、キャンセル済を含む）は
    SCR-010 へ遷移し「この注文は支払できません（現在の状態：状態の表示名）。」を表示する。
    """
    order = _helpers.make_order(
        buyer, stock_unit, status=PurchaseOrderStatus.CANCELLED, order_number="PO-00000001"
    )
    request = _request("/pay", method="post", data={"mock_result": "approve"}, user=buyer)

    response = views_orders.pay(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert response["Location"] == f"/purchase-orders/{order.purchase_order_id}"
    assert request.session[session.FLASH_KEY] == "この注文は支払できません（現在の状態：キャンセル済）。"


# trace: FR-031
def test_pay_screen_shows_mock_result_field_error(buyer, stock_unit):
    """模擬決済の結果の入力エラーは、その入力欄の近傍に SCR-008-OP01 の文言で表示する。

    SCR-008-OP01：入力エラーは模擬決済の結果の近傍に「模擬決済の結果を選択してください。」を表示する。
    """
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/pay", method="post", data={"mock_result": "unknown"}, user=buyer)

    response = views_orders.pay(request, str(order.purchase_order_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 400
    form = _form_block(body, f"/purchase-orders/{order.purchase_order_id}/pay")
    assert "模擬決済の結果を選択してください。" in form
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CREATED


# trace: FR-032
def test_order_list_screen_shows_orders(buyer, stock_unit):
    """注文履歴（SCR-009）は本人の注文を表示する。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_orders.order_list(_request("/purchase-orders", user=buyer))

    assert "PO-00000001" in response.content.decode("utf-8")


# trace: FR-032
def test_order_list_screen_shows_page_error(buyer):
    """ページ番号の不備は入力エラーとして表示する（400）。"""
    response = views_orders.order_list(_request("/purchase-orders?page=0", user=buyer))

    assert response.status_code == 400


# trace: FR-033
def test_order_detail_screen_shows_detail(buyer, stock_unit):
    """注文詳細（SCR-010）は注文内容を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_orders.order_detail(_request("/", user=buyer), str(order.purchase_order_id))

    assert "PO-00000001" in response.content.decode("utf-8")


# trace: FR-033
def test_order_detail_screen_rejects_other_buyer(buyer, other_buyer, stock_unit):
    """他の購入者の注文詳細は対象なし（404）とする。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_orders.order_detail(_request("/", user=other_buyer), str(order.purchase_order_id))

    assert response.status_code == 404


# trace: FR-034
def test_cancel_screen_cancels_order(buyer, stock_unit):
    """注文キャンセルの成功時は注文詳細画面へ戻し、SCR-010-OP02 の文言を表示する。

    SCR-010-OP02：成功時はメッセージ領域に「注文をキャンセルしました。」を表示する。
    """
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/cancel", method="post", user=buyer)

    response = views_orders.cancel(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CANCELLED
    assert request.session[session.FLASH_KEY] == "注文をキャンセルしました。"


# trace: FR-034
def test_cancel_screen_adds_refund_note_for_paid_order(buyer, stock_unit):
    """支払済だった注文のキャンセルでは返金の案内を併記する（SCR-010-OP02）。"""
    order = _helpers.make_order(
        buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001"
    )
    request = _request("/cancel", method="post", user=buyer)

    views_orders.cancel(request, str(order.purchase_order_id))

    assert request.session[session.FLASH_KEY] == "注文をキャンセルしました。返金は当社が5営業日以内に行います。"


# trace: FR-034
def test_cancel_screen_shows_status_error(buyer, stock_unit):
    """キャンセルできない状態では注文詳細画面に SCR-010-OP02 の文言を表示する（409）。

    SCR-010-OP02：状態不正（INVALID_STATUS_TRANSITION）は本画面を最新の内容で再表示し、
    メッセージ領域に「この注文はキャンセルできません（現在の状態：状態の表示名）。」を表示する。
    """
    order = _helpers.make_order(
        buyer, stock_unit, status=PurchaseOrderStatus.SHIPPED, order_number="PO-00000001"
    )
    request = _request("/cancel", method="post", user=buyer)

    response = views_orders.cancel(request, str(order.purchase_order_id))

    assert response.status_code == 409
    assert "この注文はキャンセルできません（現在の状態：出荷済）。" in response.content.decode("utf-8")


# trace: FR-040
def test_admin_stock_unit_list_screen(admin_user, stock_unit):
    """在庫単位一覧（SCR-101）は在庫単位を表示する。"""
    response = views_admin.stock_unit_list(_request("/admin/stock-units", user=admin_user))

    assert response.status_code == 200
    assert stock_unit.sku in response.content.decode("utf-8")


# trace: FR-040
def test_admin_stock_unit_list_screen_shows_errors(admin_user):
    """検索条件の不備は入力エラーとして表示する（400）。"""
    response = views_admin.stock_unit_list(_request("/admin/stock-units?page=0", user=admin_user))

    assert response.status_code == 400


# trace: FR-040
def test_admin_screens_reject_buyer(buyer):
    """購入者の管理者画面は権限なし（403）とする。"""
    response = views_admin.stock_unit_list(_request("/admin/stock-units", user=buyer))

    assert response.status_code == 403


# trace: FR-041
def test_admin_order_list_screen(admin_user, buyer, stock_unit):
    """注文一覧（SCR-102）は全購入者の注文を表示する。"""
    _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_admin.order_list(_request("/admin/purchase-orders", user=admin_user))

    assert "PO-00000001" in response.content.decode("utf-8")


# trace: FR-041
def test_admin_order_list_screen_shows_errors(admin_user):
    """検索条件の不備は入力エラーとして表示する（400）。"""
    response = views_admin.order_list(
        _request("/admin/purchase-orders?order_number=PO-1", user=admin_user)
    )

    assert response.status_code == 400


# trace: FR-042
def test_admin_order_detail_screen(admin_user, buyer, stock_unit):
    """注文詳細（SCR-103）は購入者情報を含む注文内容を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")

    response = views_admin.order_detail(_request("/", user=admin_user), str(order.purchase_order_id))

    body = response.content.decode("utf-8")
    assert "PO-00000001" in body
    assert buyer.email in body


# trace: FR-043
def test_admin_ship_screen_registers_shipment(admin_user, buyer, stock_unit):
    """出荷登録の成功時は注文詳細（管理）へ戻し、SCR-103-OP01 の文言を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")
    request = _request("/ship", method="post", data={"tracking_number": "TRACK-1"}, user=admin_user)

    response = views_admin.ship(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.SHIPPED
    assert request.session[session.FLASH_KEY] == "出荷登録しました。"


# trace: FR-043
def test_admin_ship_screen_shows_validation_error(admin_user, buyer, stock_unit):
    """配送伝票番号の不備は注文詳細（管理）に入力エラーとして表示する（400）。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")
    request = _request("/ship", method="post", data={"tracking_number": "TRACK 1"}, user=admin_user)

    response = views_admin.ship(request, str(order.purchase_order_id))

    assert response.status_code == 400
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.PAID


# trace: FR-043
def test_admin_ship_screen_shows_tracking_number_field_error_of_scr_103(admin_user, buyer, stock_unit):
    """配送伝票番号の入力エラーは、その入力欄の近傍に SCR-103-OP01 の文言で表示する。

    SCR-103-OP01：入力エラーは配送伝票番号欄の近傍に
    「配送伝票番号は英数字とハイフンの30文字以内で入力してください。」を表示する。
    """
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")
    request = _request("/ship", method="post", data={"tracking_number": "TRACK 1"}, user=admin_user)

    response = views_admin.ship(request, str(order.purchase_order_id))

    body = response.content.decode("utf-8")
    assert response.status_code == 400
    form = _form_block(body, f"/admin/purchase-orders/{order.purchase_order_id}/ship")
    assert "配送伝票番号は英数字とハイフンの30文字以内で入力してください。" in form


# trace: FR-043
def test_admin_ship_screen_shows_status_error(admin_user, buyer, stock_unit):
    """出荷登録できない状態では SCR-103-OP01 の文言を表示する（409）。"""
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/ship", method="post", data={"tracking_number": "TRACK-1"}, user=admin_user)

    response = views_admin.ship(request, str(order.purchase_order_id))

    assert response.status_code == 409
    assert "この注文は出荷登録できません（現在の状態：注文受付）。" in response.content.decode("utf-8")


# trace: FR-044
def test_admin_deliver_screen_registers_delivery(admin_user, buyer, stock_unit):
    """配達完了登録の成功時は注文詳細（管理）へ戻し、SCR-103-OP02 の文言を表示する。"""
    order = _helpers.make_order(
        buyer, stock_unit, status=PurchaseOrderStatus.SHIPPED, order_number="PO-00000001"
    )
    request = _request("/deliver", method="post", user=admin_user)

    response = views_admin.deliver(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.DELIVERED
    assert request.session[session.FLASH_KEY] == "配達完了を登録しました。"


# trace: FR-044
def test_admin_deliver_screen_shows_status_error(admin_user, buyer, stock_unit):
    """配達完了登録できない状態では SCR-103-OP02 の文言を表示する（409）。

    SCR-103-OP02：状態不正（INVALID_STATUS_TRANSITION）は本画面を最新の内容で再表示し、
    メッセージ領域に「この注文は配達完了登録できません（現在の状態：状態の表示名）。」を表示する。
    """
    order = _helpers.make_order(buyer, stock_unit, order_number="PO-00000001")
    request = _request("/deliver", method="post", user=admin_user)

    response = views_admin.deliver(request, str(order.purchase_order_id))

    assert response.status_code == 409
    assert "この注文は配達完了登録できません（現在の状態：注文受付）。" in response.content.decode("utf-8")


# trace: FR-045
def test_admin_cancel_screen_cancels_order(admin_user, buyer, stock_unit):
    """管理者のキャンセル成功時は注文詳細（管理）へ戻し、SCR-103-OP03 の文言を表示する。"""
    order = _helpers.make_order(buyer, stock_unit, status=PurchaseOrderStatus.PAID, order_number="PO-00000001")
    request = _request("/cancel", method="post", user=admin_user)

    response = views_admin.cancel(request, str(order.purchase_order_id))

    assert response.status_code == 302
    assert PurchaseOrder.objects.get(pk=order.pk).status == PurchaseOrderStatus.CANCELLED
    assert request.session[session.FLASH_KEY] == "注文をキャンセルしました。在庫を戻しました。"


# trace: FR-045
def test_admin_cancel_screen_shows_status_error(admin_user, buyer, stock_unit):
    """キャンセルできない状態では SCR-103-OP03 の文言を表示する（409）。"""
    order = _helpers.make_order(
        buyer, stock_unit, status=PurchaseOrderStatus.DELIVERED, order_number="PO-00000001"
    )
    request = _request("/cancel", method="post", user=admin_user)

    response = views_admin.cancel(request, str(order.purchase_order_id))

    assert response.status_code == 409
    assert "この注文はキャンセルできません（現在の状態：配達完了）。" in response.content.decode("utf-8")
