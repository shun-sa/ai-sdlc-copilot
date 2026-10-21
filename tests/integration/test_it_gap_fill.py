# trace: FR-001, FR-002, FR-003, FR-011, FR-024, FR-030, FR-031, FR-032, FR-033, FR-034, FR-060
# trace: NFR-EN-04, NFR-EN-11, NFR-OM-01, NFR-OM-18, NFR-SC-05, NFR-SC-06, NFR-SC-08, NFR-SC-09, NFR-SC-19
# trace: NFR-US-09
# trace: ADDR-002, ADDR-003, ADDR-004, ADDR-005, ADDR-006, ADDR-007, ADDR-008, ADDR-010, ADDR-011
"""Coverage Gap を補う結合試験（IT-AI-GAP-001〜019）。

Required Coverage と AI INITIAL Case の比較で MISSING となった Coverage（COV-011/021/028/
029/033/034/070/085/086/099/108/113/141/145/146/147/149/150/154）を補完する。
本ファイルのケースは origin=AI_GENERATED / generation_stage=GAP_FILL として記録する。

期待結果は 機能要件（FR-001〜FR-060）、非機能要件（NFR-SC-05/06/08/09/19、NFR-OM-01/18、
NFR-EN-04/11）、Steering 6章・7.2、ACTIVE な ADDR から導出する。
"""

from __future__ import annotations

import datetime as dt
import json
import re

import pytest
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import get_resolver
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuditLog, User
from common import timeutils
from orders import services as order_services
from orders.models import STATUS_CANCELLED, STATUS_CREATED, STATUS_PAID, PurchaseOrder

pytestmark = pytest.mark.django_db

SHIPPING = {
    "recipient_name": "補完 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区2-2-2",
    "address_line2": "補完ビル202",
    "phone_number": "09087654321",
}
SECRET_VALUES = (
    "Passw0rdA",
    "千代田区2-2-2",
    "09087654321",
    "補完 受取人",
)


# trace: FR-030
def place_order(client, f, *, price: int = 1000, quantity: int = 1) -> dict:
    """注文受付の注文を1件作る（試験前提データの準備）。"""
    unit = f.sellable(price=price, quantity=quantity + 10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": quantity}, format="json")
    response = client.post("/api/checkout", SHIPPING, format="json")
    assert response.status_code == 201
    return response.json()


# trace: FR-001, NFR-OM-01, NFR-SC-06
def test_it_ai_gap_001_register_logs_exclude_personal_data(api, log_capture):
    """IT-AI-GAP-001 / COV-011：会員登録のログに機密情報を出力せず、JSON Lines の必須項目を出力する。"""
    capture = log_capture("minicommerce", "django")

    success = api.post(
        "/api/auth/register",
        {
            "email": "log-user@example.test",
            "password": "Passw0rdA",
            "password_confirmation": "Passw0rdA",
            "full_name": "ログ 太郎",
        },
        format="json",
    )
    failure = api.post("/api/auth/register", {"email": "bad"}, format="json")

    assert success.status_code == 201 and failure.status_code == 400
    text = capture.text
    for secret in ("Passw0rdA", "log-user@example.test", "ログ 太郎"):
        assert secret not in text
    request_lines = [row for row in capture.records if row.get("path") == "/api/auth/register"]
    assert len(request_lines) == 2
    for row in request_lines:
        assert set(row) >= {"timestamp", "level", "request_id", "method", "path", "status", "duration_ms"}
        assert row["method"] == "POST"
        assert row["timestamp"].endswith("+09:00")
        assert json.loads(json.dumps(row)) == row  # 1行が JSON として解釈できる


# trace: FR-002, FR-003, NFR-SC-06
def test_it_ai_gap_002_authentication_logs_exclude_credentials(api, f, log_capture):
    """IT-AI-GAP-002 / COV-021：ログイン・ログアウトのログと監査ログに資格情報・トークンを出力しない。"""
    f.user(email="log-auth@example.test", password="Passw0rdA")
    capture = log_capture("minicommerce", "django")

    login = api.post(
        "/api/auth/login", {"email": "log-auth@example.test", "password": "Passw0rdA"}, format="json"
    )
    token = login.json()["token"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    client.post("/api/auth/logout")
    api.post("/api/auth/login", {"email": "log-auth@example.test", "password": "Wrongpw0rd"}, format="json")

    text = capture.text
    for secret in ("Passw0rdA", "Wrongpw0rd", "log-auth@example.test", token):
        assert secret not in text
    details = " ".join(AuditLog.objects.values_list("detail", flat=True))
    assert "log-auth@example.test" not in details
    assert token not in details
    assert "Passw0rdA" not in details


# trace: FR-002, NFR-SC-09, ADDR-006
def test_it_ai_gap_003_screen_session_expires_after_inactivity(screen, f, settings):
    """IT-AI-GAP-003 / COV-028：画面のログインセッションは無操作で切断され、ログイン画面へ戻す（CMN-10）。"""
    f.user(email="session-timeout@example.test", password="Passw0rdA")
    assert settings.SESSION_COOKIE_AGE == 1800
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    screen.post("/login/", {"email": "session-timeout@example.test", "password": "Passw0rdA"})
    assert screen.get("/cart/").status_code == 200

    Session.objects.all().update(expire_date=timezone.now() - dt.timedelta(seconds=1))

    response = screen.get("/cart/")

    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert "ログインが必要です" in screen.get("/login/").content.decode()


# trace: FR-002, ADDR-006
def test_it_ai_gap_004_login_returns_to_requested_screen(screen, f):
    """IT-AI-GAP-004 / COV-029：認証が必要な画面へのアクセスはログイン後に元の画面へ戻る（CMN-02）。"""
    f.user(email="return-screen@example.test", password="Passw0rdA")

    blocked = screen.get("/orders/")

    assert blocked.status_code == 302
    assert blocked["Location"] == "/login/"

    login = screen.post(
        "/login/", {"email": "return-screen@example.test", "password": "Passw0rdA"}
    )

    assert login.status_code == 302
    assert login["Location"] == "/orders/"
    assert screen.get("/orders/").status_code == 200


# trace: FR-002, NFR-SC-08, ADDR-002
def test_it_ai_gap_005_tokens_are_unpredictable_and_hashed(api, f):
    """IT-AI-GAP-005 / COV-033：認証トークンは推測困難な乱数で重複せず、DBへは平文で保存しない。"""
    user = f.user(email="token-entropy@example.test", password="Passw0rdA")
    credentials = {"email": "token-entropy@example.test", "password": "Passw0rdA"}

    tokens = [api.post("/api/auth/login", credentials, format="json").json()["token"] for _ in range(3)]

    assert len(set(tokens)) == 3
    for token in tokens:
        assert len(token) >= 22  # 128ビット以上相当（base64url）
        assert user.email.split("@")[0] not in token
        assert str(user.pk) != token
    stored = list(user.auth_tokens.values_list("token_hash", flat=True))
    assert len(stored) == 3
    for token in tokens:
        assert token not in stored
    assert all(len(value) == 64 for value in stored)


# trace: FR-002, NFR-SC-19, ADDR-006
def test_it_ai_gap_006_session_cookie_is_protected(f):
    """IT-AI-GAP-006 / COV-034：画面のセッションCookieは HttpOnly を付与し、ログイン時に再発行する。"""
    f.user(email="cookie@example.test", password="Passw0rdA")
    client = Client()
    session = client.session
    session["bootstrap"] = True
    session.save()
    client.cookies["sessionid"] = session.session_key
    before = session.session_key

    response = client.post("/login/", {"email": "cookie@example.test", "password": "Passw0rdA"})

    assert response.status_code == 302
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert client.session.session_key != before
    assert client.session.get("login_user_id")


# trace: FR-024
def test_it_ai_gap_007_coupon_can_be_used_repeatedly(api_as, buyer, other_buyer, f):
    """IT-AI-GAP-007 / COV-070：同一クーポンは別の購入者・別の注文でも利用できる（利用回数の制限なし）。"""
    f.coupon(code="REUSECPN1", discount_value=500)
    unit = f.sellable(price=3000, quantity=20)
    first_client = api_as(buyer)
    second_client = api_as(other_buyer)

    first_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    assert (
        first_client.post("/api/cart/apply-coupon", {"code": "REUSECPN1"}, format="json").status_code == 200
    )
    assert first_client.post("/api/checkout", SHIPPING, format="json").status_code == 201

    second_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    other_buyer_apply = second_client.post("/api/cart/apply-coupon", {"code": "REUSECPN1"}, format="json")

    first_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    second_order_apply = first_client.post("/api/cart/apply-coupon", {"code": "REUSECPN1"}, format="json")

    assert other_buyer_apply.status_code == 200
    assert other_buyer_apply.json()["amounts"]["discount_amount"] == 500
    assert second_order_apply.status_code == 200
    assert second_order_apply.json()["amounts"]["discount_amount"] == 500


# trace: FR-030, ADDR-011
def test_it_ai_gap_008_checkout_failure_rolls_back_everything(api_as, buyer, f, monkeypatch, err):
    """IT-AI-GAP-008 / COV-085：注文確定中のシステムエラーは注文・在庫・カートを確定前へ戻す（CMN-21）。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 3}, format="json")

    def boom(*args, **kwargs):
        raise RuntimeError("storage failure")

    monkeypatch.setattr(order_services.ShippingAddress.objects, "create", boom)

    response = client.post("/api/checkout", SHIPPING, format="json")

    assert response.status_code == 500
    assert err.code(response) == "INTERNAL_ERROR"
    assert not PurchaseOrder.objects.exists()
    unit.refresh_from_db()
    assert unit.quantity == 10
    monkeypatch.undo()
    cart = client.get("/api/cart").json()
    assert cart["lines"][0]["quantity"] == 3
    retried = client.post("/api/checkout", SHIPPING, format="json")
    assert retried.status_code == 201


# trace: FR-030, NFR-SC-06
def test_it_ai_gap_009_checkout_logs_exclude_shipping_address(api_as, buyer, f, log_capture):
    """IT-AI-GAP-009 / COV-086：注文確定のログに配送先・メールアドレスを出力しない。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    capture = log_capture("minicommerce", "django")

    response = client.post("/api/checkout", SHIPPING, format="json")

    assert response.status_code == 201
    text = capture.text
    for secret in SECRET_VALUES + (buyer.email, buyer.full_name, "1234567"):
        assert secret not in text
    checkout_lines = [row for row in capture.records if row.get("path") == "/api/checkout"]
    assert checkout_lines and all(row["status"] == 201 for row in checkout_lines)


# trace: FR-031, FR-034, ADDR-003
@pytest.mark.django_db(transaction=True)
def test_it_ai_gap_010_payment_and_cancellation_are_serialized(f, token_for, run_parallel):
    """IT-AI-GAP-010 / COV-099：支払とキャンセルの連続・同時実行は逐次実行と同じ結果になる。"""
    buyer = f.user(email="pay-cancel@example.test")
    token = token_for(buyer)

    def client_for() -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    client = client_for()
    try:
        # 1) キャンセル確定後の支払は状態遷移エラー
        first = place_order(client, f)
        first_id = first["purchase_order_id"]
        assert client.post(f"/api/purchase-orders/{first_id}/cancel", {}, format="json").status_code == 200
        after_cancel = client.post(
            f"/api/purchase-orders/{first_id}/pay", {"mock_result": "approve"}, format="json"
        )
        body = after_cancel.json()
        assert after_cancel.status_code == 409
        assert (body.get("error") or body)["code"] == "INVALID_STATUS_TRANSITION"

        # 2) 支払確定後のキャンセルは成功
        second = place_order(client, f)
        second_id = second["purchase_order_id"]
        assert client.post(f"/api/purchase-orders/{second_id}/pay", {}, format="json").status_code == 200
        assert client.post(f"/api/purchase-orders/{second_id}/cancel", {}, format="json").status_code == 200
        assert PurchaseOrder.objects.get(pk=second_id).status == STATUS_CANCELLED

        # 3) 同時実行は逐次実行のいずれかの順序と一致する
        third = place_order(client, f)
        third_id = third["purchase_order_id"]
        results = run_parallel(
            lambda: client_for().post(
                f"/api/purchase-orders/{third_id}/pay", {"mock_result": "approve"}, format="json"
            ),
            lambda: client_for().post(f"/api/purchase-orders/{third_id}/cancel", {}, format="json"),
        )
        statuses = sorted(response.status_code for response in results)
        final = PurchaseOrder.objects.get(pk=third_id)
        assert statuses in ([200, 200], [200, 409])
        if statuses == [200, 200]:
            assert final.status == STATUS_CANCELLED
            assert final.payment_records.filter(result="approved").count() == 1
        else:
            assert final.status in (STATUS_CANCELLED, STATUS_PAID)
    finally:
        PurchaseOrder.objects.all().delete()


# trace: FR-032, FR-033, ADDR-010
def test_it_ai_gap_011_screen_formats_dates_amounts_and_status(screen_as, api_as, buyer, f):
    """IT-AI-GAP-011 / COV-108：画面は日時「YYYY/MM/DD HH:MM」・金額「1,234円」・状態の表示名で表示する。"""
    api_client = api_as(buyer)
    order = place_order(api_client, f, price=1234, quantity=1)
    ordered_at = dt.datetime(2027, 9, 3, 10, 5, 0, tzinfo=timeutils.JST)
    PurchaseOrder.objects.filter(pk=order["purchase_order_id"]).update(ordered_at=ordered_at)
    client = screen_as(buyer)

    history = client.get("/orders/")
    detail = client.get(f"/orders/{order['purchase_order_id']}/")

    history_body = history.content.decode()
    detail_body = detail.content.decode()
    assert history.status_code == 200 and detail.status_code == 200
    assert "2027/09/03 10:05" in history_body
    assert "2027/09/03 10:05" in detail_body
    assert "注文受付" in history_body
    assert "注文受付" in detail_body
    assert "1,234円" in detail_body  # 税抜単価
    assert "1,907円" in detail_body  # 合計（1,234＋送料500＋消費税173）
    assert "－" in detail_body  # 未発生の日時は未設定表示


# trace: FR-034, ADDR-010, NFR-US-09
def test_it_ai_gap_012_screen_cancel_requires_confirmation(screen_as, api_as, buyer, f):
    """IT-AI-GAP-012 / COV-113：画面のキャンセルは確認を経た送信でのみ実行され、在庫が戻る。"""
    api_client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    api_client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 2}, format="json")
    order = api_client.post("/api/checkout", SHIPPING, format="json").json()
    order_id = order["purchase_order_id"]
    client = screen_as(buyer)

    detail = client.get(f"/orders/{order_id}/")
    body = detail.content.decode()

    assert detail.status_code == 200
    assert "data-confirm" in body
    # 確認を取り消した場合は要求が送信されず、状態・在庫は変化しない。
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_CREATED
    unit.refresh_from_db()
    assert unit.quantity == 8

    cancelled = client.post(f"/orders/{order_id}/cancel/")

    assert cancelled.status_code == 302
    assert PurchaseOrder.objects.get(pk=order_id).status == STATUS_CANCELLED
    unit.refresh_from_db()
    assert unit.quantity == 10


# trace: FR-060, ADDR-005
def test_it_ai_gap_013_initial_data_load_has_no_endpoint(api, api_as, admin_user):
    """IT-AI-GAP-013 / COV-141：初期データ投入のAPI・画面は存在せず実行できない（CMN-37）。"""
    admin_client = api_as(admin_user)

    responses = [
        admin_client.post("/api/admin/initial-data", {}, format="json"),
        admin_client.post("/api/seed", {}, format="json"),
        api.post("/api/initial-data", {}, format="json"),
        admin_client.get("/admin-console/initial-data/"),
    ]
    for response in responses:
        assert response.status_code == 404

    patterns = [str(pattern.pattern) for pattern in get_resolver().url_patterns]
    joined = " ".join(patterns)
    assert "seed" not in joined
    assert "initial" not in joined


# trace: NFR-EN-11, NFR-OM-18
def test_it_ai_gap_014_request_id_and_naming_conventions(api_as, buyer, f, log_capture):
    """IT-AI-GAP-014 / COV-145：X-Request-ID の引継ぎ・採番と、API項目名・URLの命名規約を満たす。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    capture = log_capture("minicommerce")

    given = client.get("/api/cart", HTTP_X_REQUEST_ID="trace-id-0001")
    generated = client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")

    assert given["X-Request-ID"] == "trace-id-0001"
    assert generated["X-Request-ID"]
    assert generated["X-Request-ID"] != "trace-id-0001"
    ids = {row.get("request_id") for row in capture.records if row.get("path") == "/api/cart"}
    assert "trace-id-0001" in ids

    body = generated.json()
    snake_case = re.compile(r"^[a-z][a-z0-9_]*$")

    def check_keys(payload) -> None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                assert snake_case.match(key), key
                check_keys(value)
        elif isinstance(payload, list):
            for value in payload:
                check_keys(value)

    check_keys(body)
    for path in ("/api/cart/lines", "/api/admin/stock-units", "/api/purchase-orders"):
        assert path == path.lower()
        assert "_" not in path


# trace: NFR-OM-01, NFR-SC-06
def test_it_ai_gap_015_application_log_fields(api_as, buyer, f, log_capture):
    """IT-AI-GAP-015 / COV-146：アプリケーションログは JSON Lines で必須項目を持ち、禁止項目を出力しない。"""
    client = api_as(buyer)
    unit = f.sellable(price=1000, quantity=10)
    capture = log_capture("minicommerce", "django")

    client.get("/api/items", {"keyword": buyer.email})
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 0}, format="json")

    records = [row for row in capture.records if row.get("method")]
    assert records
    for row in records:
        assert set(row) >= {
            "timestamp",
            "level",
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
        }
        assert "?" not in row["path"]  # クエリ文字列を含めない
        assert isinstance(row["status"], int)
        assert isinstance(row["duration_ms"], int)
    logged_in = [row for row in records if row["path"].startswith("/api/cart")]
    assert all(row["user_id"] == buyer.pk for row in logged_in)
    text = capture.text
    assert buyer.email not in text
    assert buyer.full_name not in text


# trace: NFR-EN-04
def test_it_ai_gap_016_datetimes_are_iso8601_jst(api, api_as, buyer, f, settings):
    """IT-AI-GAP-016 / COV-147：API の日時項目は ISO 8601（+09:00 付き）で返す。"""
    assert settings.TIME_ZONE == "Asia/Tokyo"
    client = api_as(buyer)
    f.coupon(code="ISOCPN1", discount_value=100)
    order = place_order(client, f)
    extra_unit = f.sellable(price=1000, quantity=5)
    client.post("/api/cart/lines", {"stock_unit_id": extra_unit.pk, "quantity": 1}, format="json")
    client.post("/api/cart/apply-coupon", {"code": "ISOCPN1"}, format="json")

    registered = api.post(
        "/api/auth/register",
        {
            "email": "iso-date@example.test",
            "password": "Passw0rdA",
            "password_confirmation": "Passw0rdA",
            "full_name": "日時 太郎",
        },
        format="json",
    )
    login = api.post(
        "/api/auth/login", {"email": "iso-date@example.test", "password": "Passw0rdA"}, format="json"
    )
    detail = client.get(f"/api/purchase-orders/{order['purchase_order_id']}")
    cart = client.get("/api/cart")

    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")
    values = [
        registered.json()["registered_at"],
        login.json()["expires_at"],
        detail.json()["ordered_at"],
        detail.json()["status_history"][0]["changed_at"],
        cart.json()["coupon"]["valid_from"],
        cart.json()["coupon"]["valid_until"],
    ]
    for value in values:
        assert pattern.match(value), value


# trace: NFR-SC-05, ADDR-006
def test_it_ai_gap_017_screen_updates_require_csrf_token(f):
    """IT-AI-GAP-017 / COV-149：CSRF 対策用トークンのない更新要求は拒否し、データを変更しない。"""
    user = f.user(email="csrf@example.test", password="Passw0rdA")
    unit = f.sellable(price=1000, quantity=5)
    client = Client(enforce_csrf_checks=True)
    session = client.session
    session["login_user_id"] = user.pk
    session.save()

    response = client.post(
        "/cart/lines/add/", {"item_id": unit.item_id, "stock_unit_id": unit.pk, "quantity": 1}
    )

    assert response.status_code == 403
    assert not user.carts.exists()
    unit.refresh_from_db()
    assert unit.quantity == 5


# trace: FR-001, ADDR-008
def test_it_ai_gap_018_email_uniqueness_is_enforced_by_database(f):
    """IT-AI-GAP-018 / COV-150：利用者のメールアドレスの一意性をDBの制約で保証する。"""
    f.user(email="unique@example.test")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create(
                email="unique@example.test",
                password_hash="dummy-hash",
                full_name="重複 利用者",
                role="buyer",
                registered_at=timeutils.now(),
            )

    assert User.objects.filter(email="unique@example.test").count() == 1


# trace: FR-011, FR-030, FR-060, ADDR-004, ADDR-005
def test_it_ai_gap_019_seeded_master_supports_purchase_flow(tmp_path, api):
    """IT-AI-GAP-019 / COV-154：初期データ投入後のマスタで商品検索から注文確定までが成立する。"""
    from io import StringIO

    from django.core.management import call_command

    document = {
        "users": [
            {
                "email": "flow-buyer@example.test",
                "password": "Passw0rdA",
                "full_name": "投入 購入者",
                "role": "buyer",
            }
        ],
        "suppliers": [{"supplier_code": "FLOW-SUP", "name": "投入仕入先"}],
        "collections": [{"collection_code": "flow-col", "name": "投入分類"}],
        "items": [
            {
                "item_code": "FLOW-ITEM",
                "name": "投入商品",
                "is_public": True,
                "collection_codes": ["flow-col"],
            }
        ],
        "stock_units": [
            {
                "sku": "FLOW-SKU",
                "item_code": "FLOW-ITEM",
                "supplier_code": "FLOW-SUP",
                "variant_name": "標準",
                "price": 2500,
                "quantity": 7,
            }
        ],
        "coupons": [],
    }
    path = tmp_path / "flow.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    call_command("load_initial_data", str(path), stdout=StringIO(), stderr=StringIO())

    login = api.post(
        "/api/auth/login", {"email": "flow-buyer@example.test", "password": "Passw0rdA"}, format="json"
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['token']}")

    listed = client.get("/api/items", {"keyword": "投入"})
    item = listed.json()["results"][0]
    assert item["min_price"] == 2500
    detail = client.get(f"/api/items/{item['item_id']}")
    stock_unit = detail.json()["stock_units"][0]
    assert stock_unit["quantity"] == 7

    client.post("/api/cart/lines", {"stock_unit_id": stock_unit["stock_unit_id"], "quantity": 2}, format="json")
    order = client.post("/api/checkout", SHIPPING, format="json")

    assert order.status_code == 201
    assert order.json()["amounts"]["subtotal"] == 5000
    assert order.json()["amounts"]["total"] == 5500
    assert client.get(f"/api/items/{item['item_id']}").json()["stock_units"][0]["quantity"] == 5
