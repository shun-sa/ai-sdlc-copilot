# trace: NFR-SC-08, NFR-SC-10, NFR-SC-12, NFR-SC-15, NFR-SC-19, NFR-SC-22, NFR-SC-23, NFR-SC-24
# trace: NFR-LG-01, NFR-LG-05, FR-001, FR-002, FR-003, FR-004, FR-010, FR-011, FR-012, FR-030
# trace: FR-031, FR-033, FR-034, FR-042, FR-043, FR-044, FR-060
# trace: ADDR-001, ADDR-002, ADDR-005, ADDR-007, ADDR-008, ADDR-009, ADDR-010
"""セキュリティテストで検証する非機能要件（非機能要件定義書 8章・11章）の結合試験。

期待結果は非機能要件定義書 8.1 の NFR-SC-08（認証トークンの保護）、NFR-SC-10（内部情報の非表示）、
NFR-SC-12（認証方式）、NFR-SC-15（特権の管理）、NFR-SC-19（セッション識別子の保護）、
NFR-SC-22（記録対象操作）、NFR-SC-23（改ざん防止）、NFR-SC-24（個人情報の取扱い方針）と、
11章 NFR-LG-01（個人情報保護法への対応方針）・NFR-LG-05（クレジットカード番号を扱わない）の
「要件内容」「目標値」「検証方法」欄から導出する。

いずれも Web API・画面・DB・監査ログ・決済サービス（模擬）の連携経路を実際に通して確認する。
"""
import hashlib
import json
from dataclasses import asdict
from datetime import timedelta
from io import StringIO

import pytest
from django.apps import apps
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client

from shop.common import timeutils
from shop.common.logging import JsonLinesFormatter
from shop.models import (
    AuditEventType,
    AuditLog,
    AuthToken,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseOrderStatusHistory,
    Role,
    User,
)
from shop.payments import mock as payment_mock
from shop.services import catalog as catalog_service
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

# NFR-SC-08 の目標値（発行から24時間）。
TOKEN_LIFETIME = timedelta(hours=24)

# NFR-SC-10 で応答・画面に含めてはならない内部情報の手がかり。
INTERNAL_INFO_MARKERS = [
    "Traceback",
    "SELECT ",
    "INSERT ",
    "/app/shop",
    "site-packages",
    "Django",
    "psycopg",
    "RuntimeError",
]

# 検証に用いる架空の個人情報（NFR-SC-24、NFR-LG-01）。
PERSONAL_VALUES = [
    "buyer-sc24@example.com",
    "個人 太郎",
    "受取 花子",
    "1234567",
    "09012345678",
    "千代田区一番町1-1",
]

# NFR-LG-05 の確認に用いる架空のカード番号（実在のカード番号ではない）。
FAKE_CARD_NUMBER = "4111111111111111"


# trace: FR-002
def _buyer(api, email="buyer@example.com"):
    """購入者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_user(email=email)
    return api.login(email)


# trace: FR-002
def _admin(api, email="admin@example.com"):
    """管理者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_admin(email=email)
    return api.login(email)


# trace: FR-030, FR-031
def _paid_order(api, token, unit, quantity=1):
    """カート投入から支払までを行い、注文IDを返す。"""
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]
    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200, paid.content
    return order_id


# trace: FR-060
def _seed_definition(tmp_path, suffix="X"):
    """初期データ定義ファイル（管理者1名・購入者1名・最小マスタ）を書き出す。

    コード項目は英大文字・数字・ハイフン、商品分類コードは英小文字・数字・ハイフンで作る
    （FR-060 の入力条件）。
    """
    upper = suffix.upper()
    lower = suffix.lower()
    definition = {
        "users": [
            {
                "email": f"seed-admin-{lower}@example.com",
                "password": _helpers.TEST_PASSWORD,
                "full_name": "初期 管理者",
                "role": "admin",
            },
            {
                "email": f"seed-buyer-{lower}@example.com",
                "password": _helpers.TEST_PASSWORD,
                "full_name": "初期 購入者",
                "role": "buyer",
            },
        ],
        "suppliers": [{"supplier_code": f"SUP-{upper}", "name": "架空商事"}],
        "collections": [{"collection_code": f"col-{lower}", "name": "分類", "sort_order": 1}],
        "items": [
            {
                "item_code": f"ITEM-{upper}",
                "name": "初期商品",
                "description": "説明",
                "is_public": True,
                "collection_codes": [f"col-{lower}"],
                "created_at": "2027-03-01T10:00:00+09:00",
            }
        ],
        "stock_units": [
            {
                "sku": f"SKU-{upper}",
                "item_code": f"ITEM-{upper}",
                "supplier_code": f"SUP-{upper}",
                "variant_name": "標準",
                "price": 1000,
                "quantity": 5,
            }
        ],
        "coupons": [],
    }
    path = tmp_path / f"seed-{lower}.json"
    path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    return str(path), definition


# trace: FR-060
def _run_seed(path):
    """初期データ一括投入コマンドを実行し、終了コードを返す。"""
    out, err = StringIO(), StringIO()
    try:
        call_command("load_initial_data", path, stdout=out, stderr=err)
    except SystemExit as exit_code:
        return int(exit_code.code), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# trace: NFR-SC-24
def _formatted_logs(records):
    """ログレコードを実際の出力形式（JSON Lines）へ整形した文字列の一覧を返す。"""
    formatter = JsonLinesFormatter()
    return [formatter.format(record) for record in records]


# trace: NFR-SC-08, FR-002, FR-003, FR-004, ADDR-002
@pytest.mark.case("IT-AI-GF-047")
def test_api_token_is_unpredictable_expires_in_24h_and_is_revoked_by_logout(api, monkeypatch):
    """認証トークンは推測困難で、発行から24時間で失効し、ログアウトで無効化される（NFR-SC-08）。"""
    _helpers.make_user(email="buyer@example.com")
    issued_at = timeutils.now()

    first = api.post("/api/auth/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})
    second = api.post("/api/auth/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})

    assert first.status_code == 200 and second.status_code == 200
    token = first.json()["token"]
    assert token != second.json()["token"]
    # 32バイト（256ビット）の乱数を URL-safe Base64 で表した 43 文字。128ビット以上相当。
    assert len(token) >= 43
    assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

    row = AuthToken.objects.get(token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest())
    assert AuthToken.objects.filter(token_hash=token).count() == 0
    assert abs((row.expires_at - (row.issued_at + TOKEN_LIFETIME)).total_seconds()) < 1
    assert abs((row.issued_at - issued_at).total_seconds()) < 60

    monkeypatch.setattr(timeutils, "now", lambda: row.expires_at - timedelta(seconds=1))
    assert api.get("/api/auth/me", token=token).status_code == 200

    # 有効期限日時ちょうどは無効（目標値「有効期限日時ちょうど以降は無効」）。
    monkeypatch.setattr(timeutils, "now", lambda: row.expires_at)
    at_expiry = api.get("/api/auth/me", token=token)
    assert at_expiry.status_code == 401
    assert _helpers.error_code(at_expiry) == "AUTHENTICATION_REQUIRED"

    monkeypatch.undo()
    assert api.post("/api/auth/logout", token=token).status_code == 204
    after_logout = api.get("/api/auth/me", token=token)
    assert after_logout.status_code == 401
    assert _helpers.error_code(after_logout) == "AUTHENTICATION_REQUIRED"
    assert AuthToken.objects.get(auth_token_id=row.auth_token_id).revoked_at is not None


# trace: NFR-SC-10, FR-010, FR-011, FR-012, ADDR-007
@pytest.mark.case("IT-AI-GF-048")
def test_error_responses_and_screens_do_not_expose_internal_information(api, monkeypatch, settings):
    """エラー応答・画面にスタックトレース・SQL・パス・ライブラリ名を含めない（NFR-SC-10）。"""
    assert settings.DEBUG is False
    _helpers.catalog()

    def explode(*args, **kwargs):
        """内部情報を含むメッセージの未捕捉例外を発生させる。"""
        raise RuntimeError(
            "SELECT * FROM collection WHERE 1=1 -- /app/shop/services/catalog.py psycopg Django 5.2.7"
        )

    monkeypatch.setattr(catalog_service, "list_collections", explode)
    failing_api = _helpers.ApiClient(Client(raise_request_exception=False))

    api_error = failing_api.get("/api/collections")
    body = api_error.json()

    assert api_error.status_code == 500
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert set(body["error"]) == {"code", "message", "details", "context"}
    assert body["error"]["details"] == [] and body["error"]["context"] == {}
    serialized = json.dumps(body, ensure_ascii=False)
    for marker in INTERNAL_INFO_MARKERS:
        assert marker not in serialized, marker

    screen_error = Client(raise_request_exception=False).get("/")
    html = screen_error.content.decode()
    assert screen_error.status_code == 500
    for marker in INTERNAL_INFO_MARKERS:
        assert marker not in html, marker

    monkeypatch.undo()
    not_found = api.get("/api/items/999999")
    invalid = api.get("/api/items", {"page": "'; DROP TABLE item; --"})
    assert not_found.status_code == 404 and invalid.status_code == 400
    for response in (not_found, invalid):
        text = response.content.decode()
        for marker in INTERNAL_INFO_MARKERS:
            assert marker not in text, marker


# trace: NFR-SC-12, FR-002, FR-004, ADDR-002, ADDR-008
@pytest.mark.case("IT-AI-GF-049")
def test_authentication_uses_email_password_with_token_or_session_only(api):
    """購入者・管理者はメールアドレスとパスワードで認証し、API はトークン、画面はセッションで識別する（NFR-SC-12）。"""
    _helpers.make_user(email="buyer@example.com")
    _helpers.make_admin(email="admin@example.com")

    for email, role in (("buyer@example.com", "buyer"), ("admin@example.com", "admin")):
        logged_in = api.post("/api/auth/login", {"email": email, "password": _helpers.TEST_PASSWORD})
        assert logged_in.status_code == 200, logged_in.content
        token = logged_in.json()["token"]
        assert api.get("/api/auth/me", token=token).json()["role"] == role
        # Authorization ヘッダー以外の経路（クエリ・Cookie）ではトークンを受け付けない。
        assert api.get("/api/auth/me", {"token": token}).status_code == 401
        cookie_client = Client()
        cookie_client.cookies["token"] = token
        assert cookie_client.get("/api/auth/me").status_code == 401

    wrong_password = api.post("/api/auth/login", {"email": "buyer@example.com", "password": "WrongPass1"})
    unknown_email = api.post("/api/auth/login", {"email": "nobody@example.com", "password": _helpers.TEST_PASSWORD})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()

    screen = Client()
    screen_wrong = screen.post("/login", {"email": "buyer@example.com", "password": "WrongPass1"})
    screen_unknown = screen.post("/login", {"email": "nobody@example.com", "password": _helpers.TEST_PASSWORD})
    assert screen_wrong.status_code == screen_unknown.status_code == 401
    for response in (screen_wrong, screen_unknown):
        html = response.content.decode()
        assert "メールアドレスまたはパスワードが正しくありません。" in html
        assert "パスワードが違います" not in html
        assert "登録されていないメールアドレス" not in html
    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    assert screen.get("/cart").status_code == 200


# trace: NFR-SC-15, FR-001, FR-060, ADDR-002, ADDR-010
@pytest.mark.case("IT-AI-GF-050")
def test_admin_role_is_granted_only_by_initial_data_load(api, tmp_path):
    """管理者ロールは初期データ一括投入でのみ付与し、画面・API に付与手段が無い（NFR-SC-15）。"""
    registered = api.post(
        "/api/auth/register",
        {
            "email": "role-test@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "ロール 確認",
            "role": "admin",
            "is_admin": True,
        },
    )
    assert registered.status_code == 201, registered.content
    assert registered.json()["role"] == "buyer"
    assert User.objects.get(email="role-test@example.com").role == Role.BUYER

    screen = Client()
    screen.post(
        "/register",
        {
            "email": "role-screen@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "画面 確認",
            "role": "admin",
        },
    )
    assert User.objects.get(email="role-screen@example.com").role == Role.BUYER
    assert set(User.objects.values_list("role", flat=True)) == {Role.BUYER}

    token = api.login("role-test@example.com")
    for method, path, body in [
        ("post", "/api/admin/users", {"email": "x@example.com", "role": "admin"}),
        ("patch", "/api/auth/me", {"role": "admin"}),
        ("post", "/api/users/1/role", {"role": "admin"}),
    ]:
        response = getattr(api, method)(path, body, token=token)
        assert response.status_code >= 400, f"{method.upper()} {path} -> {response.status_code}"
    assert set(User.objects.values_list("role", flat=True)) == {Role.BUYER}

    path, _definition = _seed_definition(tmp_path, suffix="sc15")
    exit_code, _stdout, stderr = _run_seed(path)
    assert exit_code == 0, stderr
    assert User.objects.get(email="seed-admin-sc15@example.com").role == Role.ADMIN


# trace: NFR-SC-19, FR-002, FR-003, ADDR-002
@pytest.mark.case("IT-AI-GF-051")
def test_session_identifier_is_reissued_on_login_and_destroyed_on_logout(api):
    """画面のログインセッション識別子はログインで再発行し、ログアウトで破棄する（NFR-SC-19）。"""
    _helpers.make_user(email="buyer@example.com")
    screen = Client()

    assert screen.get("/cart").status_code == 302  # 未ログインのためログイン画面へ（セッションが作られる）
    before = screen.cookies["sessionid"].value
    assert len(before) >= 32

    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    after = screen.cookies["sessionid"].value
    assert after != before
    assert screen.get("/cart").status_code == 200
    assert Session.objects.filter(session_key=before).count() == 0

    # ログイン前の識別子ではログイン後の画面を表示できない。
    stale = Client()
    stale.cookies["sessionid"] = before
    stale_response = stale.get("/cart")
    assert stale_response.status_code == 302
    assert stale_response["Location"].startswith("/login")

    assert screen.post("/logout").status_code == 302
    assert Session.objects.filter(session_key=after).count() == 0
    reused = Client()
    reused.cookies["sessionid"] = after
    assert reused.get("/cart").status_code == 302


# trace: NFR-SC-22, FR-002, FR-003, FR-030, FR-031, FR-043, FR-044, FR-060, ADDR-005
@pytest.mark.case("IT-AI-GF-052")
def test_audited_operations_and_status_changes_are_recorded(api, tmp_path):
    """ログイン成功・失敗・ログアウト・初期データ投入と注文状態の変更を記録する（NFR-SC-22）。"""
    assert AuditLog.objects.count() == 0
    path, _definition = _seed_definition(tmp_path, suffix="sc22")
    exit_code, _stdout, stderr = _run_seed(path)
    assert exit_code == 0, stderr

    buyer_token = _buyer(api)
    admin_token = _admin(api)
    failed = api.post("/api/auth/login", {"email": "buyer@example.com", "password": "WrongPass1"})
    assert failed.status_code == 401
    assert api.post("/api/auth/logout", token=buyer_token).status_code == 204

    counts = {
        event: AuditLog.objects.filter(event_type=event).count()
        for event in (
            AuditEventType.INITIAL_DATA_LOAD,
            AuditEventType.LOGIN_SUCCESS,
            AuditEventType.LOGIN_FAILURE,
            AuditEventType.LOGOUT,
        )
    }
    assert counts == {
        AuditEventType.INITIAL_DATA_LOAD: 1,
        AuditEventType.LOGIN_SUCCESS: 2,
        AuditEventType.LOGIN_FAILURE: 1,
        AuditEventType.LOGOUT: 1,
    }
    for log in AuditLog.objects.all():
        assert log.occurred_at is not None
        assert log.result in ("success", "failure")
        for value in ("buyer@example.com", _helpers.TEST_PASSWORD):
            assert value not in (log.detail or "")

    token = api.login("buyer@example.com")
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _paid_order(api, token, unit)
    assert api.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0003"}, token=admin_token
    ).status_code == 200
    assert api.post(f"/api/admin/purchase-orders/{order_id}/deliver", token=admin_token).status_code == 200

    history = list(
        PurchaseOrderStatusHistory.objects.filter(purchase_order_id=order_id).order_by("status_history_id")
    )
    assert [(entry.from_status, entry.to_status) for entry in history] == [
        (None, PurchaseOrderStatus.CREATED),
        (PurchaseOrderStatus.CREATED, PurchaseOrderStatus.PAID),
        (PurchaseOrderStatus.PAID, PurchaseOrderStatus.SHIPPED),
        (PurchaseOrderStatus.SHIPPED, PurchaseOrderStatus.DELIVERED),
    ]
    assert [entry.actor_role for entry in history] == [Role.BUYER, Role.BUYER, Role.ADMIN, Role.ADMIN]


# trace: NFR-SC-23, FR-031, FR-042, FR-043, ADDR-005
@pytest.mark.case("IT-AI-GF-053")
def test_audit_log_and_status_history_are_append_only(api):
    """監査ログ・注文状態履歴に画面・API からの更新・削除の手段が無い（NFR-SC-23）。"""
    buyer_token = _buyer(api)
    admin_token = _admin(api)
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _paid_order(api, buyer_token, unit)
    audit_before = list(AuditLog.objects.order_by("audit_log_id").values())
    history_before = list(PurchaseOrderStatusHistory.objects.order_by("status_history_id").values())
    assert audit_before and history_before

    for method, path, body in [
        ("get", "/api/admin/audit-logs", None),
        ("post", "/api/admin/audit-logs", {}),
        ("delete", "/api/admin/audit-logs/1", None),
        ("delete", f"/api/admin/purchase-orders/{order_id}/status-history", None),
        ("patch", f"/api/admin/purchase-orders/{order_id}/status-history/1", {"to_status": "created"}),
        ("patch", f"/api/admin/purchase-orders/{order_id}", {"status": "created"}),
        ("delete", f"/api/admin/purchase-orders/{order_id}", None),
    ]:
        caller = getattr(api, method)
        response = caller(path, token=admin_token) if body is None else caller(path, body, token=admin_token)
        assert response.status_code >= 400, f"{method.upper()} {path} -> {response.status_code}"

    screen = Client()
    assert screen.post("/login", {"email": "admin@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    for path in ("/admin/audit-logs", "/admin/purchase-orders/1/status-history"):
        assert screen.get(path).status_code == 404, path

    # 以降の正常な操作でも既存の記録は変わらず、追記だけが行われる。
    assert api.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0004"}, token=admin_token
    ).status_code == 200
    audit_after = list(AuditLog.objects.order_by("audit_log_id").values())
    history_after = list(PurchaseOrderStatusHistory.objects.order_by("status_history_id").values())
    assert audit_after[: len(audit_before)] == audit_before
    assert history_after[: len(history_before)] == history_before
    assert len(history_after) == len(history_before) + 1


# trace: NFR-SC-24, NFR-LG-01, FR-011, FR-012, FR-033, FR-042, FR-031, ADDR-009
@pytest.mark.case("IT-AI-GF-054")
def test_personal_information_is_limited_to_the_owner_and_administrators(api, monkeypatch, caplog):
    """個人情報は本人と管理者だけに返し、決済要求・ログへ出さない（NFR-SC-24、NFR-LG-01）。"""
    _helpers.make_user(email="buyer-sc24@example.com", full_name="個人 太郎")
    other_token = _buyer(api, email="other-buyer@example.com")
    admin_token = _admin(api)
    item, unit = _helpers.catalog(quantity=10)
    owner_token = api.login("buyer-sc24@example.com")
    address = dict(
        _helpers.VALID_ADDRESS,
        recipient_name="受取 花子",
        postal_code="1234567",
        phone_number="09012345678",
        address_line1="千代田区一番町1-1",
    )
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=owner_token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", address, token=owner_token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]

    captured = {}
    original = payment_mock.MockPaymentGateway.authorize

    def capture(self, request):
        """決済要求の項目を記録する。"""
        captured["request"] = request
        return original(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", capture)
    with caplog.at_level("INFO"):
        paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=owner_token)
    assert paid.status_code == 200, paid.content

    # 来訪者の照会には個人情報・社外秘（仕入先）を含めない。
    visitor_list = api.get("/api/items").content.decode()
    visitor_detail = api.get(f"/api/items/{item.item_id}").content.decode()
    for text in (visitor_list, visitor_detail):
        for value in PERSONAL_VALUES:
            assert value not in text, value
        assert "supplier" not in text

    # 他の購入者は参照できない。本人は自分の注文だけを参照でき、決済記録・購入者情報は含まない。
    assert api.get(f"/api/purchase-orders/{order_id}", token=other_token).status_code == 404
    owner_detail = api.get(f"/api/purchase-orders/{order_id}", token=owner_token).json()
    assert owner_detail["shipping_address"]["recipient_name"] == "受取 花子"
    assert "payment_records" not in owner_detail and "buyer" not in owner_detail

    admin_detail = api.get(f"/api/admin/purchase-orders/{order_id}", token=admin_token).json()
    assert admin_detail["buyer"]["email"] == "buyer-sc24@example.com"
    assert admin_detail["payment_records"][0]["result"] == "approved"

    # 決済要求（IF-01-DAT-01〜04）に個人情報を含めない。
    request_values = json.dumps(asdict(captured["request"]), ensure_ascii=False)
    for value in PERSONAL_VALUES:
        assert value not in request_values, value

    # ログ（LOG-01〜LOG-03、LOG-06）へ個人情報を出力しない。
    logs = "\n".join(_formatted_logs(caplog.records))
    assert logs
    for value in PERSONAL_VALUES:
        assert value not in logs, value


# trace: NFR-LG-05, FR-031, ADDR-009
@pytest.mark.case("IT-AI-GF-055")
def test_credit_card_data_is_never_accepted_or_stored(api, monkeypatch):
    """クレジットカード番号等を入力・保存・送信しない（NFR-LG-05）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    order_id = created.json()["purchase_order_id"]

    captured = {}
    original = payment_mock.MockPaymentGateway.authorize

    def capture(self, request):
        """決済要求の項目を記録する。"""
        captured["request"] = request
        return original(self, request)

    monkeypatch.setattr(payment_mock.MockPaymentGateway, "authorize", capture)
    paid = api.post(
        f"/api/purchase-orders/{order_id}/pay",
        {
            "mock_result": "approve",
            "card_number": FAKE_CARD_NUMBER,
            "card_expiry": "12/30",
            "security_code": "123",
        },
        token=token,
    )

    assert paid.status_code == 200, paid.content
    # 決済要求は4項目のみで、カード情報を送信しない。
    assert set(asdict(captured["request"])) == {"order_number", "amount", "currency", "mock_result"}
    assert FAKE_CARD_NUMBER not in json.dumps(asdict(captured["request"]))

    # カード情報を保持する項目を持たない。
    for model in apps.get_app_config("shop").get_models():
        for field in model._meta.get_fields():
            assert "card" not in field.name.lower(), f"{model.__name__}.{field.name}"
            assert "security_code" not in field.name.lower(), f"{model.__name__}.{field.name}"

    stored = json.dumps(
        {
            "orders": list(PurchaseOrder.objects.values()),
            "payments": list(PurchaseOrder.objects.get(purchase_order_id=order_id).payment_records.values()),
        },
        ensure_ascii=False,
        default=str,
    )
    assert FAKE_CARD_NUMBER not in stored

    # 支払画面（SCR-008）にカード情報の入力項目が無い。
    screen = Client()
    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    html = screen.get(f"/purchase-orders/{order_id}/pay").content.decode()
    assert "card" not in html.lower()
    for word in ("カード番号", "セキュリティコード", "有効期限"):
        assert word not in html, word
