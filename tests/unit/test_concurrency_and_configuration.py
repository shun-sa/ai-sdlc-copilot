# trace: FR-001, FR-003, FR-021, FR-022, FR-023, FR-030, FR-031, FR-033, FR-042, FR-060
# trace: NFR-OM-17, NFR-SC-02, NFR-SC-03, NFR-SC-09, NFR-SC-10, ADDR-003, ADDR-005, ADDR-006, ADDR-011
"""同時実行時の再判定（7章 排他・同時実行）、設定の環境変数読み取り、
画面の共通エラー応答、応答表現の未設定値の扱いに関する単体テスト。

期待結果は各機能要件の「排他・同時実行」節（競合時の振る舞い）、NFR-OM-17（環境ごとに
異なる設定を環境変数で与える）、ADDR-006 INV-005（Cookie の Secure 属性の既定値）、
NFR-SC-10（内部情報の非表示）、提供済みAPI契約（未適用のクーポン・未登録の配送先は null）
から導出する。
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import os

import pytest
from _helpers import make_item, make_stock_unit, shipping_input
from carts import services as cart_services
from carts.models import CART_CONVERTED, DISCOUNT_FIXED, DISCOUNT_PERCENTAGE, Cart
from common.exceptions import (
    CartEmpty,
    InvalidStatusTransition,
    NotFoundError,
    business_error_for_integrity,
)
from config import settings as settings_module
from django.db import IntegrityError
from django.test import RequestFactory
from orders import serializers as order_serializers
from orders import services as order_services
from orders.models import PurchaseOrder
from payments import services as payment_services
from web.views import cart_views, error_views


# trace: NFR-OM-17
@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        ("true", False, True),
        ("YES", False, True),
        ("1", False, True),
        ("on", False, True),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("0", True, False),
        ("unknown", True, True),
        ("", True, True),
        ("  ", False, False),
        (None, True, True),
        (None, False, False),
    ],
)
def test_env_flag_falls_back_to_default(monkeypatch, raw, default, expected):
    """ADDR-006 INV-005：未設定・空・解釈できない値は既定値とする。"""
    if raw is None:
        monkeypatch.delenv("TEST_FLAG", raising=False)
    else:
        monkeypatch.setenv("TEST_FLAG", raw)

    assert settings_module.env_flag("TEST_FLAG", default=default) is expected


# trace: NFR-OM-17
def test_env_list_splits_comma_separated_values(monkeypatch):
    """NFR-OM-17：カンマ区切りの環境変数を一覧として読み取る。"""
    monkeypatch.setenv("TEST_LIST", " a , b ,, c ")

    assert settings_module.env_list("TEST_LIST") == ["a", "b", "c"]

    monkeypatch.delenv("TEST_LIST", raising=False)
    assert settings_module.env_list("TEST_LIST", default="x,y") == ["x", "y"]


# trace: NFR-OM-17
@pytest.mark.parametrize(("raw", "expected"), [("5", 5), (" 7 ", 7), ("abc", 10), ("", 10), (None, 10)])
def test_env_int_falls_back_to_default(monkeypatch, raw, expected):
    """NFR-OM-17：整数として解釈できない環境変数は既定値とする。"""
    if raw is None:
        monkeypatch.delenv("TEST_INT", raising=False)
    else:
        monkeypatch.setenv("TEST_INT", raw)

    assert settings_module.env_int("TEST_INT", default=10) == expected


# trace: NFR-SC-09
def test_session_cookie_settings_follow_security_requirements(settings):
    """NFR-SC-09：ログインセッションは無操作30分で無効化し、Cookie に HttpOnly を付与する。"""
    assert settings.SESSION_COOKIE_AGE == 1800
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


# trace: NFR-SC-02, NFR-SC-09
@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, True), ("", True), ("unknown", True), ("true", True), ("false", False)],
)
def test_cookie_secure_settings_fall_back_to_secure(monkeypatch, raw, expected):
    """ADDR-006 DD-003／INV-005：Secure 属性は環境変数が未設定・空・解釈できない値のとき真とする。"""
    original = os.environ.get("DJANGO_SECURE_COOKIES")
    try:
        if raw is None:
            monkeypatch.delenv("DJANGO_SECURE_COOKIES", raising=False)
        else:
            monkeypatch.setenv("DJANGO_SECURE_COOKIES", raw)

        reloaded = importlib.reload(settings_module)

        assert reloaded.SECURE_COOKIES is expected
        assert reloaded.SESSION_COOKIE_SECURE is expected
        assert reloaded.CSRF_COOKIE_SECURE is expected
    finally:
        if original is None:
            monkeypatch.delenv("DJANGO_SECURE_COOKIES", raising=False)
        else:
            monkeypatch.setenv("DJANGO_SECURE_COOKIES", original)
        importlib.reload(settings_module)


# trace: NFR-OM-17
def test_static_delivery_route_is_not_wired_when_serving_is_disabled(settings):
    """NFR-OM-17／VUL-08・NFR-EN-08：静的ファイルの配信経路は環境変数の設定に従って結線する（無効時は結線しない）。"""
    import config.urls as urls_module
    from django.urls import clear_url_caches

    try:
        settings.SERVE_STATIC_FILES = False
        disabled = importlib.reload(urls_module)
        disabled_patterns = [str(pattern.pattern) for pattern in disabled.urlpatterns]

        settings.SERVE_STATIC_FILES = True
        enabled = importlib.reload(urls_module)
        enabled_patterns = [str(pattern.pattern) for pattern in enabled.urlpatterns]

        assert not any("static" in pattern for pattern in disabled_patterns)
        assert any("static" in pattern for pattern in enabled_patterns)
    finally:
        settings.SERVE_STATIC_FILES = True
        importlib.reload(urls_module)
        clear_url_caches()


# trace: NFR-SC-03
def test_api_defaults_deny_unauthenticated_requests(settings):
    """VUL-01／NFR-SC-03：API の既定を拒否（ログイン必須）とし、認証不要APIだけが上書きする。"""
    framework = settings.REST_FRAMEWORK

    assert framework["DEFAULT_PERMISSION_CLASSES"] == ["common.permissions.IsAuthenticated"]
    assert framework["DEFAULT_AUTHENTICATION_CLASSES"] == ["common.authentication.BearerTokenAuthentication"]
    assert framework["UNAUTHENTICATED_USER"] is None
    assert framework["EXCEPTION_HANDLER"] == "common.exception_handler.api_exception_handler"


# trace: NFR-SC-10
@pytest.mark.parametrize(
    ("handler", "expected_status", "expected_heading"),
    [
        (error_views.bad_request, 400, "お探しのページ・データが見つかりません"),
        (error_views.permission_denied, 403, "この画面・操作を利用する権限がありません"),
        (error_views.not_found, 404, "お探しのページ・データが見つかりません"),
    ],
)
@pytest.mark.django_db
def test_screen_error_handlers_render_error_page(handler, expected_status, expected_heading):
    """SCR-901：画面の共通エラー応答は利用者向けの文言だけを表示する。"""
    from django.contrib.sessions.backends.db import SessionStore

    request = RequestFactory().get("/missing/")
    request.session = SessionStore()

    response = handler(request, None)

    assert response.status_code == expected_status
    assert expected_heading in response.content.decode()


# trace: NFR-SC-10
@pytest.mark.django_db
def test_server_error_handler_hides_internal_details(caplog):
    """NFR-SC-10：システムエラー画面にスタックトレース・SQL を表示しない。"""
    from django.contrib.sessions.backends.db import SessionStore

    request = RequestFactory().get("/boom/")
    request.session = SessionStore()

    response = error_views.server_error(request)

    body = response.content.decode()
    assert response.status_code == 500
    assert "システムエラーが発生しました" in body
    assert "Traceback" not in body
    assert "SELECT" not in body


# trace: FR-033
def test_order_coupon_payload_is_null_when_not_applied():
    """提供済みAPI契約：クーポン未適用の注文は coupon を null とする。"""
    order = PurchaseOrder(coupon_code=None)

    assert order_serializers.order_coupon_payload(order) is None


# trace: FR-033, FR-042
def test_order_coupon_payload_returns_snapshot_of_applied_coupon():
    """FR-033 6.18.5⑦／FR-042 6.22.5⑦：適用した注文は注文確定時のクーポンコード・割引方式・割引値を返す。"""
    order = PurchaseOrder(
        coupon_code="SNAP-FIX-1000",
        coupon_discount_type=DISCOUNT_FIXED,
        coupon_discount_value=1000,
    )

    assert order_serializers.order_coupon_payload(order) == {
        "code": "SNAP-FIX-1000",
        "discount_type": "fixed",
        "discount_value": 1000,
    }


# trace: FR-033, FR-042
def test_order_coupon_payload_keeps_percentage_discount_type():
    """CD-03：定率のクーポンは割引方式 percentage・割引値（％）をそのまま返す。"""
    order = PurchaseOrder(
        coupon_code="SNAP-PCT-15",
        coupon_discount_type=DISCOUNT_PERCENTAGE,
        coupon_discount_value=15,
    )

    assert order_serializers.order_coupon_payload(order) == {
        "code": "SNAP-PCT-15",
        "discount_type": "percentage",
        "discount_value": 15,
    }


# trace: FR-042
def test_shipping_address_payload_is_null_when_absent():
    """配送先が取得できない場合は shipping_address を null とする。"""
    assert order_serializers.shipping_address_payload(PurchaseOrder()) is None


# trace: FR-021
def test_added_message_falls_back_without_matching_line():
    """SCR-002-OP01：対象の明細を特定できない場合も追加した旨だけを表示する。"""
    assert cart_views.added_message({"lines": []}, 1, 1) == "カートに追加しました。"


# trace: FR-001
def test_known_constraint_name_without_mapping_returns_no_business_error():
    """対応表にない制約名は業務エラーへ変換しない（システムエラーとして扱う）。"""

    class Diagnostic:
        constraint_name = "uq_auth_token_hash"

    class DriverError(Exception):
        diag = Diagnostic()

    error = IntegrityError("wrapped")
    error.__cause__ = DriverError()

    assert business_error_for_integrity(error) is None


# trace: FR-003
@pytest.mark.django_db
def test_logout_api_requires_token(api_client, buyer, token_for, monkeypatch):
    """FR-003：認証トークンを特定できない要求は認証エラーとする。"""
    from accounts import views as account_views

    token = token_for(buyer)
    monkeypatch.setattr(account_views.services, "logout", lambda token: None)

    class TokenlessAuthentication:
        def authenticate(self, request):
            return buyer, None

        def authenticate_header(self, request):
            return "Bearer"

    monkeypatch.setattr(
        account_views.LogoutView, "authentication_classes", [TokenlessAuthentication]
    )

    response = api_client.post("/api/auth/logout", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.data["error"]["code"] == "AUTHENTICATION_REQUIRED"


# trace: FR-021
@pytest.mark.django_db
def test_open_cart_creation_failure_is_propagated(buyer, monkeypatch):
    """E-021-07：利用中カートを作成できない障害はシステムエラーとして伝播する。"""

    def fail_create(**kwargs):
        raise IntegrityError("database failure")

    monkeypatch.setattr(Cart.objects, "create", fail_create)

    with pytest.raises(IntegrityError):
        cart_services.get_or_create_open_cart(buyer)


# trace: FR-022
@pytest.mark.django_db
def test_change_line_quantity_rejects_cart_converted_concurrently(buyer, monkeypatch):
    """FR-022 6.10.9：数量変更の途中で注文確定された場合は対象なしとする。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    original_lock = cart_services.lock_cart

    def lock_and_convert(cart):
        locked = original_lock(cart)
        locked.status = CART_CONVERTED
        return locked

    monkeypatch.setattr(cart_services, "lock_cart", lock_and_convert)

    with pytest.raises(NotFoundError):
        cart_services.change_line_quantity(buyer, line.pk, {"quantity": 2})


# trace: FR-023
@pytest.mark.django_db
def test_delete_line_rejects_line_removed_concurrently(buyer, monkeypatch):
    """FR-023 6.11.9：削除の途中で同じ明細が削除された場合は対象なしとする。"""
    unit = make_stock_unit(make_item(), quantity=10)
    line = cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})["lines"][0]
    original_lock = cart_services.lock_cart

    def lock_and_clear(cart):
        locked = original_lock(cart)
        locked.lines.all().delete()
        return locked

    monkeypatch.setattr(cart_services, "lock_cart", lock_and_clear)

    with pytest.raises(NotFoundError):
        cart_services.delete_line(buyer, line.pk)


# trace: FR-030
@pytest.mark.django_db
def test_checkout_rejects_cart_converted_concurrently(buyer, monkeypatch):
    """FR-030 6.15.9：注文確定の途中でカートが注文済になった場合は空として扱う。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    original_lock = cart_services.lock_cart

    def lock_and_convert(cart):
        locked = original_lock(cart)
        locked.status = CART_CONVERTED
        return locked

    monkeypatch.setattr(cart_services, "lock_cart", lock_and_convert)

    with pytest.raises(CartEmpty):
        order_services.checkout(buyer, shipping_input())


# trace: FR-030
@pytest.mark.django_db
def test_checkout_rejects_cart_emptied_concurrently(buyer, monkeypatch):
    """FR-030 6.15.9：ロック後に明細が0件になった場合は空として扱う。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    original_load = cart_services.load_lines
    calls = {"count": 0}

    def load_then_empty(cart):
        calls["count"] += 1
        if calls["count"] == 1:
            return original_load(cart)
        return []

    monkeypatch.setattr(cart_services, "load_lines", load_then_empty)

    with pytest.raises(CartEmpty):
        order_services.checkout(buyer, shipping_input())


# trace: FR-030
@pytest.mark.django_db
def test_checkout_relocks_stock_units_added_after_first_lock(buyer, monkeypatch):
    """FR-030 6.15.9：ロック後に明細が増えた場合は在庫単位を取得し直して判定する。"""
    first = make_stock_unit(make_item(name="先の商品"), price=1000, quantity=10)
    second = make_stock_unit(make_item(name="後の商品"), price=2000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": first.pk, "quantity": 1})
    original_load = cart_services.load_lines
    calls = {"count": 0}

    def load_then_add(cart):
        calls["count"] += 1
        lines = original_load(cart)
        if calls["count"] == 1:
            return [line for line in lines if line.stock_unit_id == first.pk]
        return lines

    cart_services.add_line(buyer, {"stock_unit_id": second.pk, "quantity": 1})
    monkeypatch.setattr(cart_services, "load_lines", load_then_add)

    order = order_services.checkout(buyer, shipping_input())

    assert order.lines.count() == 2
    assert order.subtotal == 3000


# trace: FR-031
@pytest.mark.django_db
def test_pay_rejects_order_cancelled_during_payment(buyer, monkeypatch):
    """FR-031 6.16.9：決済要求中に注文が変更された場合は状態不正とする。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    order = order_services.checkout(buyer, shipping_input())
    original_authorize = payment_services.authorize

    def authorize_then_cancel(order_number, amount, mock_result):
        result = original_authorize(order_number, amount, mock_result)
        PurchaseOrder.objects.filter(pk=order.pk).update(status="cancelled")
        return result

    monkeypatch.setattr(payment_services, "authorize", authorize_then_cancel)

    with pytest.raises(InvalidStatusTransition) as error:
        order_services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert error.value.context == {"current_status": "cancelled"}


# trace: FR-060
@pytest.mark.django_db
def test_collections_are_registered_regardless_of_row_order(tmp_path):
    """FR-060：親分類が後の行にあっても親子関係どおりに登録する。"""
    from seeding import services as seeding_services

    document = {
        "collections": [
            {"collection_code": "child-first", "name": "子", "parent_collection_code": "parent-later"},
            {"collection_code": "parent-later", "name": "親"},
        ]
    }
    path = tmp_path / "ordered.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    seeding_services.load_initial_data(str(path), reset=False)

    from catalog.models import Collection

    child = Collection.objects.get(collection_code="child-first")
    assert child.parent.collection_code == "parent-later"
    assert child.depth == 2


# trace: FR-060, ADDR-005
def test_collection_structure_skips_rows_without_code_or_name():
    """値域違反で値が確定しない行があっても、残りの行の判定を続ける。"""
    from seeding import services as seeding_services

    violations: list = []
    rows = [
        {"row": 1, "collection_code": None, "name": "名前のみ", "parent_collection_code": None},
        {"row": 2, "collection_code": "code-only", "name": None, "parent_collection_code": None},
    ]

    depths = seeding_services.check_collection_structure(rows, {}, set(), violations)

    assert depths == {"code-only": 1}
    assert violations == []


# trace: FR-033
@pytest.mark.django_db
def test_status_history_and_payment_labels_use_display_names(buyer, admin_user):
    """FR-042 出力：注文状態履歴・決済記録は表示名で確認できる。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    order = order_services.checkout(buyer, shipping_input())
    order_services.pay(buyer, order.pk, {"mock_result": "approve"})

    loaded = order_services.load_order(order.pk)
    histories = sorted(loaded.status_history.all(), key=lambda history: history.pk)
    record = loaded.payment_records.get()

    assert histories[0].from_status_label is None
    assert histories[0].to_status_label == "注文受付"
    assert histories[1].from_status_label == "注文受付"
    assert histories[1].to_status_label == "支払済"
    assert record.result_label == "承認"
    assert str(record).startswith("PaymentRecord(")
    assert str(histories[0]).startswith("PurchaseOrderStatusHistory(")


# trace: FR-030
@pytest.mark.django_db
def test_order_number_sequence_formats_eight_digits():
    """FR-030：注文番号は「PO-」＋通番8桁とする。"""
    from orders.models import OrderNumberSequence

    sequence = OrderNumberSequence.objects.create()

    assert sequence.order_number == f"PO-{sequence.pk:08d}"
    assert str(sequence) == f"OrderNumberSequence({sequence.pk})"


# trace: FR-033
@pytest.mark.django_db
def test_model_string_representations_use_business_keys(buyer):
    """データ要件：各データは業務キーまたは識別子で識別できる。"""
    from accounts.models import AuditLog, AuthToken
    from carts.models import CartLine
    from catalog.models import Collection, ItemCollection

    unit = make_stock_unit(make_item(item_code="STR-ITEM"), sku="STR-SKU")
    collection = Collection.objects.create(collection_code="str-col", name="表示名", depth=1, sort_order=0)
    link = ItemCollection.objects.create(item=unit.item, collection=collection)
    cart = cart_services.get_or_create_open_cart(buyer)
    line = CartLine.objects.create(
        cart=cart, stock_unit=unit, quantity=1, added_at=dt.datetime.now(dt.UTC)
    )
    token = AuthToken.objects.create(
        token_hash="x" * 64,
        user=buyer,
        issued_at=dt.datetime.now(dt.UTC),
        expires_at=dt.datetime.now(dt.UTC),
    )
    log = AuditLog.objects.create(
        occurred_at=dt.datetime.now(dt.UTC), event_type="logout", user_id=buyer.pk, result="success"
    )

    assert str(unit.item) == "STR-ITEM"
    assert str(unit) == "STR-SKU"
    assert str(unit.supplier) == unit.supplier.supplier_code
    assert str(collection) == "str-col"
    assert str(link) == f"ItemCollection({unit.item_id},{collection.pk})"
    assert str(cart) == f"Cart({cart.pk})"
    assert str(line) == f"CartLine({line.pk})"
    assert str(token) == f"AuthToken({token.pk})"
    assert str(log) == f"AuditLog({log.pk})"


# trace: FR-033
@pytest.mark.django_db
def test_order_models_string_representations(buyer):
    """注文・注文明細・配送先・クーポンの識別表現を確認する。"""
    from carts.models import Coupon

    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    order = order_services.checkout(buyer, shipping_input())
    coupon = Coupon.objects.create(
        code="STR-CPN",
        name="表示",
        discount_type="fixed",
        discount_value=1,
        min_spend=0,
        valid_from=dt.datetime.now(dt.UTC),
        valid_until=dt.datetime.now(dt.UTC),
    )

    assert str(order) == order.order_number
    assert str(order.lines.get()) == f"PurchaseOrderLine({order.lines.get().pk})"
    assert str(order.shipping_address) == f"ShippingAddress({order.shipping_address.pk})"
    assert str(coupon) == "STR-CPN"
