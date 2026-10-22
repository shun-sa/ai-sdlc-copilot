# trace: NFR-EN-01, NFR-EN-02, NFR-EN-04, NFR-EN-05, NFR-OM-11, NFR-OM-13, NFR-OM-18
# trace: NFR-PF-08, NFR-PF-16, NFR-US-03, NFR-US-04, NFR-LG-02, NFR-LG-09, NFR-LG-10
# trace: NFR-MG-01, NFR-MG-07, FR-001, FR-002, FR-004, FR-010, FR-011, FR-012, FR-020
# trace: FR-021, FR-026, FR-030, FR-031, FR-032, FR-033, FR-040, FR-041, FR-043, FR-044, FR-060
# trace: ADDR-001, ADDR-002, ADDR-004, ADDR-005, ADDR-006, ADDR-009, ADDR-010, ADDR-011, ADDR-012
"""実行基盤・ログ・一覧件数・画面表示に関する非機能要件の結合試験。

期待結果は非機能要件定義書 10章（NFR-EN-01 開発言語、NFR-EN-02 データベース、NFR-EN-04 タイムゾーン・
文字コード、NFR-EN-05 外部サービスの利用制約）、6章（NFR-OM-11 ログの出力・保管、NFR-OM-13 異常終了時の
再実行、NFR-OM-18 障害調査の容易さ）、5章（NFR-PF-08 一覧の応答件数上限、NFR-PF-16 業務量増加への対応）、
9章（NFR-US-03 使用可能文字、NFR-US-04 入力エラーの表示）、7章（NFR-MG-01 移行対象データ、NFR-MG-07
切戻し）、11章（NFR-LG-02 総額表示義務、NFR-LG-09 都道府県コード、NFR-LG-10 外部サービスとの契約）の
「要件内容」「目標値」「検証方法」欄から導出する。

本番環境でのみ測定できる指標（応答時間・稼働率・保管期間など）は対象とせず、
ENV-01 の結合試験で判定できる状態・形式・件数・文字の扱いだけを確認する。
"""
import json
import re
import socket
import sys
from datetime import timedelta
from io import StringIO
from pathlib import Path

import django
import pytest
import rest_framework
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import connection
from django.test import Client

from shop.common import timeutils
from shop.common.logging import JsonLinesFormatter
from shop.models import (
    AuditEventType,
    AuditLog,
    AuthToken,
    Cart,
    CartLine,
    Collection,
    Coupon,
    Item,
    ItemCollection,
    PaymentRecord,
    PurchaseOrder,
    PurchaseOrderStatusHistory,
    ShippingAddress,
    StockUnit,
    Supplier,
    User,
)
from shop.services import catalog as catalog_service
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

# 1ページ件数（NFR-PF-08 の目標値）。
ITEM_PAGE_SIZE = 20
ORDER_PAGE_SIZE = 20
STOCK_UNIT_PAGE_SIZE = 50

# JIS 第3・第4水準の漢字（NFR-US-03 の検証方法）。𠮟 は BMP 外の文字。
KANJI_LEVEL3 = "﨑"
KANJI_LEVEL4 = "𠮟"

# 画面が参照してはならない外部 URL（NFR-EN-05）。
EXTERNAL_URL = re.compile(r'(?:src|href)="(https?:)?//', re.I)

# X-Request-ID として受理しない値（ADDR-005 ASM-001 の形式外）。
INVALID_REQUEST_ID = "bad request id!"


# trace: FR-002
def _buyer(api, email="buyer@example.com", full_name="山田 太郎"):
    """購入者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_user(email=email, full_name=full_name)
    return api.login(email)


# trace: FR-002
def _admin(api, email="admin@example.com"):
    """管理者を1件作成してログインし、認証トークンを返す。"""
    _helpers.make_admin(email=email)
    return api.login(email)


# trace: FR-030
def _place_order(api, token, unit, quantity=1, address=None):
    """カート投入から注文確定までを行い、注文IDを返す。"""
    added = api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": quantity}, token=token)
    assert added.status_code == 200, added.content
    created = api.post("/api/checkout", address or dict(_helpers.VALID_ADDRESS), token=token)
    assert created.status_code == 201, created.content
    return created.json()["purchase_order_id"]


# trace: NFR-OM-11
def _log_entries(records):
    """ログレコードを実際の出力形式（JSON Lines）へ整形し、JSON として解析した一覧を返す。"""
    formatter = JsonLinesFormatter()
    entries = []
    for record in records:
        line = formatter.format(record)
        assert "\n" not in line, "1イベント1行でない"
        entries.append(json.loads(line))
    return entries


# trace: NFR-EN-05
def _block_external_network(monkeypatch):
    """外部ネットワークへの接続を遮断する（接続を試みた時点で失敗させる）。"""

    def refuse(*args, **kwargs):
        """接続要求を拒否する。"""
        raise AssertionError(f"外部ネットワークへ接続しようとした: {args[1:]}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# trace: FR-060
def _run_seed(path, reset=False):
    """初期データ一括投入コマンドを実行し、(終了コード, 標準出力, 標準エラー) を返す。"""
    out, err = StringIO(), StringIO()
    arguments = [path, "--reset"] if reset else [path]
    try:
        call_command("load_initial_data", *arguments, stdout=out, stderr=err)
    except SystemExit as exit_code:
        return int(exit_code.code), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# trace: NFR-MG-07
def _definition(quantity=5):
    """最小構成の初期データ定義（利用者2名・マスタ各1件）を返す。"""
    return {
        "users": [
            {
                "email": "seed-admin@example.com",
                "password": _helpers.TEST_PASSWORD,
                "full_name": "初期 管理者",
                "role": "admin",
            },
            {
                "email": "seed-buyer@example.com",
                "password": _helpers.TEST_PASSWORD,
                "full_name": "初期 購入者",
                "role": "buyer",
            },
        ],
        "suppliers": [{"supplier_code": "SUP-MG", "name": "架空商事"}],
        "collections": [{"collection_code": "mg-col", "name": "分類", "sort_order": 1}],
        "items": [
            {
                "item_code": "ITEM-MG",
                "name": "初期商品",
                "description": "説明",
                "is_public": True,
                "collection_codes": ["mg-col"],
                "created_at": "2027-03-01T10:00:00+09:00",
            }
        ],
        "stock_units": [
            {
                "sku": "SKU-MG",
                "item_code": "ITEM-MG",
                "supplier_code": "SUP-MG",
                "variant_name": "標準",
                "price": 1000,
                "quantity": quantity,
            }
        ],
        "coupons": [],
    }


# trace: NFR-MG-07
def _write(tmp_path, name, definition):
    """定義ファイル（UTF-8 の JSON）を書き出してパスを返す。"""
    path = tmp_path / name
    path.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: NFR-EN-01, NFR-EN-02, ADDR-011, ADDR-012
@pytest.mark.case("IT-AI-GF-056")
def test_runtime_platform_matches_required_versions():
    """app・db が目標値の言語・フレームワーク・DB 製品の版で動作している（NFR-EN-01、NFR-EN-02）。"""
    assert sys.version_info[:2] == (3, 12)
    assert django.VERSION[:2] == (5, 2)
    assert tuple(int(part) for part in rest_framework.VERSION.split(".")[:2]) >= (3, 15)

    assert connection.vendor == "postgresql"
    assert connection.pg_version >= 160000
    with connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        assert "PostgreSQL 16" in cursor.fetchone()[0]


# trace: NFR-EN-04, FR-001, FR-002, FR-030, FR-031, ADDR-004
@pytest.mark.case("IT-AI-GF-057")
def test_timezone_is_jst_and_encoding_is_utf8(api):
    """app・db のタイムゾーンが Asia/Tokyo、文字コードが UTF-8 である（NFR-EN-04）。"""
    assert settings.TIME_ZONE == "Asia/Tokyo"
    assert settings.USE_TZ is True
    with connection.cursor() as cursor:
        # db のタイムゾーン設定（コンテナの既定値）。接続中のセッションは Django が
        # timestamptz を扱うため UTC に設定する（保存は UTC、表示・API は JST）。
        cursor.execute("SELECT reset_val FROM pg_settings WHERE name = 'TimeZone'")
        assert cursor.fetchone()[0] == "Asia/Tokyo"
        cursor.execute("SHOW server_encoding")
        assert cursor.fetchone()[0] == "UTF8"

    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _place_order(api, token, unit)
    paid = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token)
    assert paid.status_code == 200, paid.content

    detail = api.get(f"/api/purchase-orders/{order_id}", token=token).json()
    for field in ("ordered_at", "paid_at"):
        assert detail[field].endswith("+09:00"), field
    for entry in detail["status_history"]:
        assert entry["changed_at"].endswith("+09:00")
    login = api.post("/api/auth/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD})
    assert login.json()["expires_at"].endswith("+09:00")

    # 日本語（UTF-8）が画面・API・DB を通して同じ文字で扱われる。
    screen = Client()
    response = screen.get("/")
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    assert "商品一覧" in response.content.decode("utf-8")


# trace: NFR-EN-05, NFR-LG-10, FR-001, FR-011, FR-021, FR-030, FR-031, FR-043, FR-044, ADDR-009
@pytest.mark.case("IT-AI-GF-058")
def test_all_functions_work_without_external_network_access(api, monkeypatch):
    """外部ネットワークへ接続せずに全機能を操作でき、画面が外部 URL を参照しない（NFR-EN-05、NFR-LG-10）。"""
    admin_token = _admin(api)
    item, unit = _helpers.catalog(quantity=10)
    _block_external_network(monkeypatch)

    registered = api.post(
        "/api/auth/register",
        {
            "email": "offline@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": "切断 太郎",
        },
    )
    assert registered.status_code == 201, registered.content
    token = api.login("offline@example.com")
    assert api.get("/api/items").status_code == 200
    order_id = _place_order(api, token, unit)
    assert api.post(
        f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token
    ).status_code == 200
    assert api.post(
        f"/api/admin/purchase-orders/{order_id}/ship", {"tracking_number": "TRK-0005"}, token=admin_token
    ).status_code == 200
    assert api.post(f"/api/admin/purchase-orders/{order_id}/deliver", token=admin_token).status_code == 200

    screen = Client()
    for path in ("/", f"/items/{item.item_id}", "/login", "/register"):
        response = screen.get(path)
        assert response.status_code == 200, path
        assert not EXTERNAL_URL.search(response.content.decode()), path


# trace: NFR-OM-11, FR-011, FR-020, FR-031, ADDR-005
@pytest.mark.case("IT-AI-GF-059")
def test_application_logs_are_emitted_as_json_lines_with_required_fields(api, monkeypatch, caplog):
    """LOG-01〜LOG-04・LOG-06・LOG-07 が定めた内容で出力・記録される（NFR-OM-11）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _place_order(api, token, unit)

    caplog.clear()
    with caplog.at_level("INFO"):
        assert api.get("/api/items", {"keyword": "サンプル"}).status_code == 200
        assert api.get("/api/cart").status_code == 401
        assert api.post(
            f"/api/purchase-orders/{order_id}/pay", {"mock_result": "approve"}, token=token
        ).status_code == 200
    entries = _log_entries(caplog.records)

    # LOG-03 アクセスログ（応答送信時に1行。path にクエリ文字列を含めない）。
    access = [entry for entry in entries if entry.get("event") == "request"]
    assert len(access) == 3
    for entry in access:
        assert set(entry) >= {"timestamp", "level", "request_id", "method", "path", "status", "duration_ms"}
        assert entry["timestamp"].endswith("+09:00")
        assert "?" not in entry["path"] and "keyword" not in entry["path"]
        assert isinstance(entry["duration_ms"], int)
    # LOG-01 業務エラーの記録（エラーコードを含む）。
    business = [entry for entry in entries if entry.get("event") == "business_error"]
    assert [entry["error_code"] for entry in business] == ["AUTHENTICATION_REQUIRED"]
    # LOG-06 外部連携ログ（注文番号・結果・所要時間）。
    payments = [entry for entry in entries if entry.get("event") == "payment_authorize"]
    assert len(payments) == 1
    assert payments[0]["order_number"] == PurchaseOrder.objects.get(purchase_order_id=order_id).order_number
    assert payments[0]["result"] == "approved"
    assert isinstance(payments[0]["duration_ms"], int)

    # LOG-02 エラーログ（例外の種類と発生箇所のみ。例外メッセージを出力しない）。
    caplog.clear()
    secret = "SELECT * FROM collection -- /app/shop/services/catalog.py"

    def explode(*args, **kwargs):
        """未捕捉例外を発生させる。"""
        raise RuntimeError(secret)

    monkeypatch.setattr(catalog_service, "list_collections", explode)
    with caplog.at_level("INFO"):
        failing = _helpers.ApiClient(Client(raise_request_exception=False))
        assert failing.get("/api/collections").status_code == 500
    error_entries = [entry for entry in _log_entries(caplog.records) if entry["level"] == "ERROR"]
    assert len(error_entries) == 1
    assert error_entries[0]["error_code"] == "INTERNAL_ERROR"
    assert error_entries[0]["exception_class"] == "RuntimeError"
    assert all(" in " in frame for frame in error_entries[0]["stack_trace"])
    assert secret not in json.dumps(error_entries, ensure_ascii=False)

    # LOG-04 監査ログ・LOG-07 注文状態履歴は DB に記録する。
    assert AuditLog.objects.filter(event_type=AuditEventType.LOGIN_SUCCESS).count() == 1
    assert PurchaseOrderStatusHistory.objects.filter(purchase_order_id=order_id).count() == 2


# trace: NFR-OM-18, FR-031, ADDR-005
@pytest.mark.case("IT-AI-GF-060")
def test_request_id_is_inherited_or_generated_and_returned(api, caplog):
    """1件の要求の全ログ行に同じ request_id を出力し、応答ヘッダーへ付与する（NFR-OM-18）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    order_id = _place_order(api, token, unit)
    given = "req-20261022-0001"

    caplog.clear()
    with caplog.at_level("INFO"):
        inherited = api.client.post(
            f"/api/purchase-orders/{order_id}/pay",
            data=json.dumps({"mock_result": "approve"}),
            content_type="application/json",
            headers={"authorization": f"Bearer {token}", "x-request-id": given},
        )
    assert inherited.status_code == 200, inherited.content
    assert inherited.headers["X-Request-ID"] == given
    entries = [entry for entry in _log_entries(caplog.records) if entry["request_id"] is not None]
    assert entries
    assert {entry["request_id"] for entry in entries} == {given}
    assert {entry.get("event") for entry in entries} >= {"payment_authorize", "request"}

    caplog.clear()
    with caplog.at_level("INFO"):
        generated = api.get("/api/items")
    assert generated.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", generated.headers["X-Request-ID"])
    generated_ids = {
        entry["request_id"] for entry in _log_entries(caplog.records) if entry.get("event") == "request"
    }
    assert generated_ids == {generated.headers["X-Request-ID"]}

    invalid = api.client.get("/api/items", headers={"x-request-id": INVALID_REQUEST_ID})
    assert invalid.headers["X-Request-ID"] != INVALID_REQUEST_ID
    assert re.fullmatch(r"[0-9a-f]{32}", invalid.headers["X-Request-ID"])


# trace: NFR-PF-08, FR-010, FR-011, FR-032, FR-040, FR-041, ADDR-006
@pytest.mark.case("IT-AI-GF-061")
def test_list_apis_return_at_most_the_defined_page_size(api):
    """ページングを持つ一覧APIの応答件数が上限以下で、分類一覧は全件を返す（NFR-PF-08）。"""
    buyer_token = _buyer(api)
    admin_token = _admin(api)
    supplier = _helpers.make_supplier()
    for index in range(1, 26):
        item = _helpers.make_item(item_code=f"ITEM-{index:03d}", name=f"商品{index:03d}")
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-{index:03d}", price=1000, quantity=50)
    for index in range(1, 46):
        _helpers.make_collection(collection_code=f"col-{index:03d}", name=f"分類{index:03d}", sort_order=index)

    first_page = api.get("/api/items").json()
    second_page = api.get("/api/items", {"page": 2}).json()
    assert first_page["page_size"] == ITEM_PAGE_SIZE
    assert len(first_page["results"]) == ITEM_PAGE_SIZE
    assert first_page["total_count"] == 25
    assert len(second_page["results"]) == 5

    collections = api.get("/api/collections").json()
    assert isinstance(collections, list)
    assert len(collections) == 45

    unit = StockUnit.objects.order_by("sku").first()
    for _ in range(21):
        _place_order(api, buyer_token, unit)
    orders_first = api.get("/api/purchase-orders", token=buyer_token).json()
    orders_second = api.get("/api/purchase-orders", {"page": 2}, token=buyer_token).json()
    assert orders_first["page_size"] == ORDER_PAGE_SIZE
    assert len(orders_first["results"]) == ORDER_PAGE_SIZE
    assert len(orders_second["results"]) == 1

    admin_orders = api.get("/api/admin/purchase-orders", token=admin_token).json()
    assert admin_orders["page_size"] == ORDER_PAGE_SIZE
    assert len(admin_orders["results"]) == ORDER_PAGE_SIZE

    item = Item.objects.order_by("item_id").first()
    for index in range(26, 77):
        _helpers.make_stock_unit(item, supplier, sku=f"SKU-X{index:03d}", price=1000, quantity=1)
    stock_first = api.get("/api/admin/stock-units", token=admin_token).json()
    stock_last = api.get("/api/admin/stock-units", {"page": 2}, token=admin_token).json()
    assert stock_first["page_size"] == STOCK_UNIT_PAGE_SIZE
    assert len(stock_first["results"]) == STOCK_UNIT_PAGE_SIZE
    assert stock_first["total_count"] == 76
    assert len(stock_last["results"]) == 26


# trace: NFR-PF-16, FR-002, FR-004, FR-020, FR-021, ADDR-002
@pytest.mark.case("IT-AI-GF-062")
def test_user_state_is_kept_in_database_not_in_process_memory(api):
    """ログインセッション・認証トークン・カートを app の内部メモリではなく DB に保持する（NFR-PF-16）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token
    ).status_code == 200

    # 認証トークンとカートは DB の行として存在する。
    token_row = AuthToken.objects.get()
    assert Cart.objects.count() == 1 and CartLine.objects.count() == 1

    # 別のクライアント（別の処理）からも同じ状態を参照できる。
    other = _helpers.ApiClient(Client())
    assert other.get("/api/auth/me", token=token).status_code == 200
    assert other.get("/api/cart", token=token).json()["lines"][0]["quantity"] == 2

    # DB の行を取り除くと状態も失われる（プロセス内に複製を持たない）。
    token_row.delete()
    assert api.get("/api/auth/me", token=token).status_code == 401

    screen = Client()
    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    assert Session.objects.count() >= 1
    assert screen.get("/cart").status_code == 200
    Session.objects.all().delete()
    after_delete = screen.get("/cart")
    assert after_delete.status_code == 302
    assert after_delete["Location"].startswith("/login")
    assert CartLine.objects.count() == 1


# trace: NFR-US-03, FR-001, FR-030, FR-033, ADDR-006
@pytest.mark.case("IT-AI-GF-063")
def test_jis_level3_and_level4_characters_are_stored_and_displayed(api):
    """JIS 第3・第4水準の漢字を入力・保存・表示できる（NFR-US-03）。"""
    full_name = f"{KANJI_LEVEL3}山 {KANJI_LEVEL4}太郎"
    recipient = f"{KANJI_LEVEL4}田 {KANJI_LEVEL3}子"
    registered = api.post(
        "/api/auth/register",
        {
            "email": "kanji@example.com",
            "password": _helpers.TEST_PASSWORD,
            "password_confirmation": _helpers.TEST_PASSWORD,
            "full_name": full_name,
        },
    )
    assert registered.status_code == 201, registered.content
    assert registered.json()["full_name"] == full_name
    assert User.objects.get(email="kanji@example.com").full_name == full_name

    token = api.login("kanji@example.com")
    _item, unit = _helpers.catalog(quantity=10)
    address = dict(_helpers.VALID_ADDRESS, recipient_name=recipient, address_line1=f"{KANJI_LEVEL3}町1-1")
    order_id = _place_order(api, token, unit, address=address)

    detail = api.get(f"/api/purchase-orders/{order_id}", token=token).json()
    assert detail["shipping_address"]["recipient_name"] == recipient
    assert ShippingAddress.objects.get().recipient_name == recipient

    screen = Client()
    assert screen.post("/login", {"email": "kanji@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    html = screen.get(f"/purchase-orders/{order_id}").content.decode("utf-8")
    assert recipient in html
    assert full_name in html


# trace: NFR-US-04, FR-001
@pytest.mark.case("IT-AI-GF-064")
def test_input_errors_are_shown_next_to_each_field_and_values_are_kept(api):
    """入力エラーを該当項目の近傍へ全件表示し、パスワード以外の入力値を保持する（NFR-US-04）。"""
    long_name = "あ" * 60
    screen = Client()

    response = screen.post(
        "/register",
        {
            "email": "bad-format",
            "password": "Zq3",
            "password_confirmation": "Zq9",
            "full_name": long_name,
        },
    )
    html = response.content.decode("utf-8")

    assert response.status_code == 400
    reasons = {
        "email": "メールアドレスの形式で入力してください。",
        "password": "パスワードは8文字以上64文字以下で入力してください。",
        "password_confirmation": "パスワードとパスワード（確認）が一致しません。",
        "full_name": "氏名は50文字以下で入力してください。",
    }
    # 4項目分の理由が1回の応答にまとめて表示される。
    for field, reason in reasons.items():
        assert reason in html, field
    # 各理由は該当する入力項目の直後（次の入力項目より前）に表示される。
    order = ["email", "password", "password_confirmation", "full_name"]
    for index, field in enumerate(order):
        field_position = html.index(f'id="{field}"')
        reason_position = html.index(reasons[field])
        assert field_position < reason_position, field
        if index + 1 < len(order):
            assert reason_position < html.index(f'id="{order[index + 1]}"'), field
    # 入力値を保持する（パスワードは保持しない）。
    assert 'value="bad-format"' in html
    assert f'value="{long_name}"' in html
    assert 'type="password" name="password">' in html
    assert "Zq3" not in html and "Zq9" not in html
    assert User.objects.count() == 0


# trace: NFR-LG-02, FR-011, FR-012, FR-020, FR-026
@pytest.mark.case("IT-AI-GF-065")
def test_prices_are_displayed_tax_included_with_tax_excluded_alongside(api):
    """価格は税込を主表示し税抜を併記、内訳に消費税額と税込合計を表示する（NFR-LG-02）。"""
    token = _buyer(api)
    item, unit = _helpers.catalog(price=1000, quantity=10)
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 2}, token=token
    ).status_code == 200
    amounts = api.get("/api/cart", token=token).json()["amounts"]

    screen = Client()
    assert screen.post("/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}).status_code == 302
    list_html = screen.get("/").content.decode("utf-8")
    detail_html = screen.get(f"/items/{item.item_id}").content.decode("utf-8")
    cart_html = screen.get("/cart").content.decode("utf-8")

    # 税込価格＝税抜価格×110÷100 の1円未満切り捨て。
    assert "1,100円（税込）／1,000円（税抜）" in list_html
    assert "1,100円（税込）／1,000円（税抜）" in detail_html
    # 金額内訳に消費税額と税込の合計を表示する。
    assert "消費税額" in cart_html
    assert "合計（税込）" in cart_html
    assert f"{amounts['tax_amount']:,}円" in cart_html
    assert f"{amounts['total']:,}円" in cart_html
    assert amounts["tax_amount"] == (amounts["discounted_subtotal"] + amounts["shipping_fee"]) * 10 // 100


# trace: NFR-LG-09, FR-030
@pytest.mark.case("IT-AI-GF-066")
def test_prefecture_is_accepted_only_as_jis_x0401_code(api):
    """配送先の都道府県は JIS X 0401 のコード（01〜47）だけを受け付ける（NFR-LG-09）。"""
    token = _buyer(api)
    _item, unit = _helpers.catalog(quantity=10)
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token
    ).status_code == 200

    for invalid in ("00", "48", "1", "047", "ab", ""):
        rejected = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS, prefecture_code=invalid), token=token)
        assert rejected.status_code == 400, invalid
        assert "prefecture_code" in _helpers.error_fields(rejected), invalid
    assert PurchaseOrder.objects.count() == 0

    accepted = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS, prefecture_code="47"), token=token)
    assert accepted.status_code == 201, accepted.content
    assert ShippingAddress.objects.get().prefecture_code == "47"

    second_token = _buyer(api, email="buyer2@example.com")
    assert api.post(
        "/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=second_token
    ).status_code == 200
    first_code = api.post(
        "/api/checkout", dict(_helpers.VALID_ADDRESS, prefecture_code="01"), token=second_token
    )
    assert first_code.status_code == 201, first_code.content
    assert set(ShippingAddress.objects.values_list("prefecture_code", flat=True)) == {"01", "47"}


# trace: NFR-MG-01, FR-060, ADDR-010
@pytest.mark.case("IT-AI-GF-067")
def test_initial_data_contains_no_transactional_data():
    """稼働開始時の初期データに注文・カート・決済記録・注文状態履歴を含まない（NFR-MG-01）。"""
    path = Path(settings.BASE_DIR) / "seed" / "initial_data.json"
    definition = json.loads(path.read_text(encoding="utf-8"))

    assert set(definition) <= {"users", "suppliers", "collections", "items", "stock_units", "coupons"}
    for key in ("purchase_orders", "carts", "payment_records", "status_history"):
        assert key not in definition, key

    exit_code, stdout, stderr = _run_seed(str(path))

    assert exit_code == 0, stderr
    assert User.objects.count() == len(definition["users"])
    assert Item.objects.count() == len(definition["items"])
    assert StockUnit.objects.count() == len(definition["stock_units"])
    assert "利用者:" in stdout.replace(" ", "")
    # 稼働開始時の注文関連データ・カート・監査対象の業務データは0件。
    assert PurchaseOrder.objects.count() == 0
    assert ShippingAddress.objects.count() == 0
    assert PaymentRecord.objects.count() == 0
    assert PurchaseOrderStatusHistory.objects.count() == 0
    assert Cart.objects.count() == 0
    assert CartLine.objects.count() == 0


# trace: NFR-OM-13, NFR-MG-07, FR-060, ADDR-010
@pytest.mark.case("IT-AI-GF-068")
def test_failed_initial_data_load_changes_nothing_and_can_be_rerun(tmp_path):
    """投入が失敗した場合は何も投入せず、修正後の再実行で重複なくやり直せる（NFR-OM-13、NFR-MG-07）。"""
    broken = _definition()
    broken["stock_units"][0]["price"] = -1
    broken_path = _write(tmp_path, "broken.json", broken)

    exit_code, _stdout, stderr = _run_seed(broken_path)

    assert exit_code != 0
    assert "price" in stderr
    assert User.objects.count() == 0
    assert Supplier.objects.count() == 0
    assert Collection.objects.count() == 0
    assert Item.objects.count() == 0
    assert ItemCollection.objects.count() == 0
    assert StockUnit.objects.count() == 0
    assert Coupon.objects.count() == 0
    failures = AuditLog.objects.filter(event_type=AuditEventType.INITIAL_DATA_LOAD, result="failure")
    assert failures.count() == 1

    fixed_path = _write(tmp_path, "fixed.json", _definition())
    exit_code, stdout, stderr = _run_seed(fixed_path, reset=True)

    assert exit_code == 0, stderr
    assert User.objects.count() == 2
    assert StockUnit.objects.count() == 1
    assert "在庫単位:1件" in stdout.replace(" ", "")

    # 同じ定義ファイルで再実行してもデータが重複せず、監査ログは削除されず追記される。
    exit_code, _stdout, stderr = _run_seed(fixed_path, reset=True)

    assert exit_code == 0, stderr
    assert User.objects.count() == 2
    assert Item.objects.count() == 1
    assert StockUnit.objects.count() == 1
    assert failures.count() == 1
    assert AuditLog.objects.filter(event_type=AuditEventType.INITIAL_DATA_LOAD).count() == 3
    assert StockUnit.objects.get().quantity == 5
    assert timeutils.now() - AuditLog.objects.order_by("-audit_log_id").first().occurred_at < timedelta(minutes=5)
