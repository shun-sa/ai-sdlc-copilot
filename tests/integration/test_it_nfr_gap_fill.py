# trace: NFR-EN-01, NFR-EN-02, NFR-SC-13, NFR-SC-14, NFR-SC-27, NFR-US-03, NFR-US-08, FR-OUT-11
# trace: FR-001, FR-002, FR-011, FR-021, FR-030, FR-031, FR-033
# trace: ADDR-002, ADDR-008, ADDR-010
"""非機能要件の Coverage を補う結合試験（IT-AI-GAP-024〜028）。

結合試験（画面・API → Service → ORM → PostgreSQL）で「実行中のシステムの振る舞い」として
確かめられる非機能要件だけを対象にする。ブラウザでの描画・操作（NFR-US-01/02/05/06/07/10）、
負荷計測（NFR-PF-*）、本番基盤・運用（NFR-AV-*／NFR-OM-*）、静的解析・診断（NFR-SC-07/11/21/29）は
本工程では判定できないため、ここでは扱わない。

期待結果は 非機能要件定義書（NFR-US-03、NFR-US-08、NFR-EN-01、NFR-EN-02、NFR-SC-13、NFR-SC-14、
NFR-SC-27）と、共通機能要件 CMN-05、ACTIVE な ADDR から導出する。
本ファイルのケースは origin=AI_GENERATED / generation_stage=GAP_FILL として記録する。
"""

from __future__ import annotations

import sys

import django
import pytest
import rest_framework
from django.db import connection
from rest_framework.test import APIClient

from accounts.models import EVENT_LOGIN_FAILURE, EVENT_LOGIN_SUCCESS, AuditLog, User
from orders.models import STATUS_PAID, PurchaseOrder

pytestmark = pytest.mark.django_db

# JIS X 0213 第3水準漢字（面1。𠮟=U+20B9F、俱=U+4FF1、剝=U+525D、頰=U+9830）。
JIS_LEVEL3_NAME = "𠮟俱 剝頰"
# JIS X 0213 第4水準漢字（面2。𠀋=U+2000B、𡈽=U+21235、𩸽=U+29E3D）。
JIS_LEVEL4_RECIPIENT = "𠀋𡈽 𩸽子"
JIS_LEVEL4_ADDRESS1 = "千代田区𠀋𡈽町1-1-1"
JIS_LEVEL4_ADDRESS2 = "𩸽ビル101"

BUYER_EMAIL = "nfr-us03-buyer@example.test"
BUYER_PASSWORD = "Passw0rdA"

SHIPPING_JIS = {
    "recipient_name": JIS_LEVEL4_RECIPIENT,
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": JIS_LEVEL4_ADDRESS1,
    "address_line2": JIS_LEVEL4_ADDRESS2,
    "phone_number": "09012345678",
}
SHIPPING_PLAIN = {
    "recipient_name": "補完 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区3-3-3",
    "address_line2": "補完ビル303",
    "phone_number": "09011112222",
}


# trace: NFR-US-03, FR-001, FR-002, FR-021, FR-030, FR-033, ADDR-008, ADDR-010
def test_it_ai_gap_024_screens_are_japanese_and_keep_jis_level3_and_level4_kanji(screen, f):
    """IT-AI-GAP-024 / COV-013・COV-108：第3・第4水準漢字を入力・保存・表示でき、表示言語は日本語のみ。

    NFR-US-03（文字範囲：UTF-8 で符号化できる文字／対応言語：日本語のみ）を、画面（SCR-003→
    SCR-004→SCR-002→SCR-006→SCR-010）と PostgreSQL への保存・読み出しを通して確認する。
    """
    unit = f.sellable(price=2000, quantity=5)

    # 1) 画面（SCR-003）から、氏名に JIS 第3水準漢字を入力して会員登録する。
    registered = screen.post(
        "/register/",
        {
            "email": BUYER_EMAIL,
            "password": BUYER_PASSWORD,
            "password_confirmation": BUYER_PASSWORD,
            "full_name": JIS_LEVEL3_NAME,
        },
    )
    assert registered.status_code == 302
    assert registered["Location"] == "/login/"

    # 2) 画面（SCR-004）からログインする。
    logged_in = screen.post("/login/", {"email": BUYER_EMAIL, "password": BUYER_PASSWORD})
    assert logged_in.status_code == 302
    assert logged_in["Location"] == "/"

    # 3) 画面（SCR-002）でカートへ入れ、注文手続き（SCR-006）で配送先に第4水準漢字を入力する。
    added = screen.post(
        "/cart/lines/add/",
        {"item_id": unit.item_id, "stock_unit_id": unit.pk, "quantity": 1},
    )
    assert added.status_code == 302
    ordered = screen.post("/checkout/", SHIPPING_JIS)
    assert ordered.status_code == 302
    purchase_order_id = ordered["Location"].strip("/").split("/")[1]

    # 4) 注文詳細（SCR-010）に、入力したものと同じ文字が表示される。
    detail = screen.get(f"/orders/{purchase_order_id}/")
    body = detail.content.decode("utf-8")

    assert detail.status_code == 200
    assert detail["Content-Type"] == "text/html; charset=utf-8"
    assert '<html lang="ja">' in body  # 表示言語は日本語のみ（言語切替を持たない）
    assert 'hreflang' not in body
    assert JIS_LEVEL3_NAME in body  # ヘッダーの氏名（第3水準）
    assert JIS_LEVEL4_RECIPIENT in body
    assert JIS_LEVEL4_ADDRESS1 in body
    assert JIS_LEVEL4_ADDRESS2 in body

    # 5) PostgreSQL から読み戻した値が、入力した符号位置と1文字ずつ一致する（外字を使わない）。
    user = User.objects.get(email=BUYER_EMAIL)
    with connection.cursor() as cursor:
        cursor.execute("SELECT full_name FROM users WHERE id = %s", [user.pk])
        stored_name = cursor.fetchone()[0]
        cursor.execute(
            "SELECT recipient_name, address_line1, address_line2 FROM shipping_addresses"
            " WHERE purchase_order_id = %s",
            [purchase_order_id],
        )
        stored_address = cursor.fetchone()

    assert [ord(char) for char in stored_name] == [ord(char) for char in JIS_LEVEL3_NAME]
    assert [ord(char) for char in stored_address[0]] == [ord(char) for char in JIS_LEVEL4_RECIPIENT]
    assert stored_address[1] == JIS_LEVEL4_ADDRESS1
    assert stored_address[2] == JIS_LEVEL4_ADDRESS2


# trace: NFR-US-08, FR-011, FR-021, FR-030, FR-031, FR-033, ADDR-010
def test_it_ai_gap_025_purchase_flow_passes_seven_screens_or_fewer(screen_as, buyer, f):
    """IT-AI-GAP-025 / COV-045・COV-059・COV-088・COV-100・COV-108：商品一覧から支払完了までを7画面以内で行える。

    NFR-US-08（画面遷移数 7画面以内：SCR-001→SCR-002→SCR-005→SCR-006→SCR-007→SCR-008→SCR-010）を、
    ログイン済み購入者が各画面から次の画面へ直接到達できることを確かめながら数える。
    """
    unit = f.sellable(price=1500, quantity=3)
    client = screen_as(buyer)
    visited: list[str] = []

    # 1画面目 SCR-001 商品一覧。商品詳細へのリンクを持つ。
    item_list = client.get("/")
    assert item_list.status_code == 200
    visited.append("SCR-001")
    item_path = f"/items/{unit.item_id}/"
    assert item_path in item_list.content.decode("utf-8")

    # 2画面目 SCR-002 商品詳細。カート投入は同じ画面へ戻るため、画面数は増えない。
    item_detail = client.get(item_path)
    assert item_detail.status_code == 200
    visited.append("SCR-002")
    added = client.post(
        "/cart/lines/add/",
        {"item_id": unit.item_id, "stock_unit_id": unit.pk, "quantity": 1},
    )
    assert added.status_code == 302
    assert added["Location"] == item_path
    assert "/cart/" in client.get(item_path).content.decode("utf-8")  # ヘッダーからカートへ直接進める

    # 3画面目 SCR-005 カート。注文手続きへのリンクを持つ。
    cart = client.get("/cart/")
    assert cart.status_code == 200
    visited.append("SCR-005")
    assert "/checkout/" in cart.content.decode("utf-8")

    # 4画面目 SCR-006 注文手続き。確定すると注文完了へ直接遷移する。
    checkout = client.get("/checkout/")
    assert checkout.status_code == 200
    visited.append("SCR-006")
    ordered = client.post("/checkout/", SHIPPING_PLAIN)
    assert ordered.status_code == 302
    complete_path = ordered["Location"]
    purchase_order_id = complete_path.strip("/").split("/")[1]
    assert complete_path == f"/orders/{purchase_order_id}/complete/"

    # 5画面目 SCR-007 注文完了。支払画面へのリンクを持つ。
    complete = client.get(complete_path)
    assert complete.status_code == 200
    visited.append("SCR-007")
    pay_path = f"/orders/{purchase_order_id}/pay/"
    assert pay_path in complete.content.decode("utf-8")

    # 6画面目 SCR-008 支払。支払うと注文詳細へ直接遷移する。
    payment = client.get(pay_path)
    assert payment.status_code == 200
    visited.append("SCR-008")
    paid = client.post(pay_path, {"mock_result": "approve"})
    assert paid.status_code == 302
    detail_path = f"/orders/{purchase_order_id}/"
    assert paid["Location"] == detail_path

    # 7画面目 SCR-010 注文詳細。支払済を表示する。
    detail = client.get(detail_path)
    assert detail.status_code == 200
    visited.append("SCR-010")
    assert "支払済" in detail.content.decode("utf-8")

    assert PurchaseOrder.objects.get(pk=purchase_order_id).status == STATUS_PAID
    assert visited == ["SCR-001", "SCR-002", "SCR-005", "SCR-006", "SCR-007", "SCR-008", "SCR-010"]
    assert len(visited) == len(set(visited))
    assert len(visited) <= 7


# trace: NFR-EN-01, NFR-EN-02, FR-001, ADDR-002, ADDR-008
def test_it_ai_gap_026_runtime_platform_matches_language_framework_and_database(api):
    """IT-AI-GAP-026 / COV-001：要求を処理した実行基盤が Python 3.12・Django 5.2 LTS・DRF 3.15以上・PostgreSQL 16。

    NFR-EN-01（開発言語・フレームワークの版）と NFR-EN-02（主データストアは PostgreSQL 16）を、
    実際に API 要求を処理して DB へ保存した実行時の構成として確認する。
    """
    email = "nfr-en01-buyer@example.test"

    registered = api.post(
        "/api/auth/register",
        {
            "email": email,
            "password": "Passw0rdA",
            "password_confirmation": "Passw0rdA",
            "full_name": "基盤 確認",
        },
        format="json",
    )

    assert registered.status_code == 201

    # NFR-EN-01：要求を処理した実行時の言語・フレームワークの版。
    assert sys.version_info[:2] == (3, 12)
    assert django.VERSION[:2] == (5, 2)
    drf_version = tuple(int(part) for part in rest_framework.VERSION.split(".")[:2])
    assert drf_version >= (3, 15)

    # NFR-EN-02：登録した1件が主データストア（PostgreSQL 16）へ保存されている。
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        server_version = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM users WHERE email = %s", [email])
        stored = cursor.fetchone()[0]

    assert server_version.split(".")[0] == "16"
    assert stored == 1


# trace: NFR-SC-13, NFR-SC-14, FR-002, ADDR-002, FR-OUT-11
def test_it_ai_gap_027_login_is_single_factor_and_never_locks_the_account(api, screen, f):
    """IT-AI-GAP-027 / COV-015・COV-032：連続した認証失敗でロックせず、1要素だけでログインが完了する。

    NFR-SC-14（認証失敗時のロック：該当なし。CMN-05）と NFR-SC-13（多要素認証：該当なし）を、
    API と画面の両方のログインで確認する。
    """
    user = f.user(email="nfr-sc14-buyer@example.test", password="Passw0rdA")

    for _ in range(10):
        failed = api.post(
            "/api/auth/login",
            {"email": user.email, "password": "WrongPass9"},
            format="json",
        )
        assert failed.status_code == 401

    assert AuditLog.objects.filter(event_type=EVENT_LOGIN_FAILURE, user_id=user.pk).count() == 10

    # 試行回数の制限・アカウントロックを行わず、正しい資格情報で引き続きログインできる。
    succeeded = api.post(
        "/api/auth/login",
        {"email": user.email, "password": "Passw0rdA"},
        format="json",
    )
    body = succeeded.json()

    assert succeeded.status_code == 200
    assert AuditLog.objects.filter(event_type=EVENT_LOGIN_SUCCESS, user_id=user.pk).count() == 1
    # 第2の認証要素（確認コード等）の提示を求めず、その場で認証トークンを発行する。
    assert set(body) == {"token", "expires_at", "user"}
    assert body["token"]

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['token']}")
    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["user_id"] == user.pk

    # 画面のログインも1要素で完了し、追加の認証画面を経由しない。
    screen_login = screen.post("/login/", {"email": user.email, "password": "Passw0rdA"})

    assert screen_login.status_code == 302
    assert screen_login["Location"] == "/"


# trace: NFR-SC-27, FR-002, FR-011, ADDR-002
def test_it_ai_gap_028_no_request_rate_limit_is_applied_per_client(api, f):
    """IT-AI-GAP-028 / COV-032：同一クライアントからの連続要求を、送信元単位で制限しない。

    NFR-SC-27（大量アクセス対策：該当なし。アプリケーションでは送信元単位のリクエスト数の制限を
    行わない）を、照会要求と認証失敗要求の連続実行で確認する。
    """
    f.sellable(price=1000, quantity=10)
    user = f.user(email="nfr-sc27-buyer@example.test", password="Passw0rdA")

    search_statuses = {api.get("/api/items").status_code for _ in range(60)}
    failure_statuses = {
        api.post(
            "/api/auth/login",
            {"email": user.email, "password": "WrongPass9"},
            format="json",
        ).status_code
        for _ in range(20)
    }

    # 制限（429 Too Many Requests／503）を返さず、業務上の応答だけを返す。
    assert search_statuses == {200}
    assert failure_statuses == {401}

    allowed = api.post(
        "/api/auth/login",
        {"email": user.email, "password": "Passw0rdA"},
        format="json",
    )

    assert allowed.status_code == 200
