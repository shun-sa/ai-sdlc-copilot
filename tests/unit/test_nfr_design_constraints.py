# trace: NFR-PF-16, NFR-PF-17, NFR-LG-05
# trace: ADDR-002, ADDR-006, ADDR-009
"""非機能要件のうち、単体テストで実際に振る舞い・構造を検証できる設計制約の単体テスト。

本ファイルが検証する範囲は以下に限定する（各テストの docstring にも明記する）。

- NFR-PF-16（業務量増加への対応）：要件内容の「利用者の状態（画面のログインセッション・
  API の認証トークン・カート）を app の内部メモリではなく DB に保持すること」の部分。
  ADDR-006 DD-001（セッションの保存先＝Django標準セッションのDBバックエンド）、
  ADDR-002 DD-005（認証トークンをDBテーブルで保持し、プロセスメモリへ保持しない）を根拠とする。
  目標値「現行想定の2倍まで構成追加のみで対応」は負荷テストでの確認事項であり、本ファイルの
  対象外とする。
- NFR-PF-17（将来の拡張）：検証方法「決済サービスとの連携部分が独立したモジュールであり、
  支払の処理が決済要求の項目（注文番号・決済金額・通貨・模擬決済指示）と応答の項目
  （結果・取引参照番号・処理日時）だけを介して連携部分を利用していること」の全範囲。
  ADDR-009 DD-001・DD-002 を根拠とする。
- NFR-LG-05（割賦販売法／カード番号の非保持化）：確認方法「カード情報の入力項目・保存項目が
  無いことを確認する」の全範囲、および要件の「入力・保存・送信しない」。

DBを使うテストは pytest-django が作成する使い捨てのテストDB（Dockerコンテナ上の
PostgreSQL 16）だけを使用する。
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import inspect
import re

import pytest
from _helpers import make_item, make_stock_unit, shipping_input
from accounts import services as account_services
from accounts.models import AuthToken
from carts import services as cart_services
from carts.models import CART_OPEN, Cart
from catalog import services as catalog_services
from common import timeutils
from django.apps import apps
from django.contrib.sessions.models import Session
from django.urls import reverse
from orders import services as order_services
from orders import views as order_views
from orders.models import STATUS_PAID, PaymentRecord
from payments.gateway import (
    CURRENCY_JPY,
    RESULT_APPROVED,
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
)
from web.views import order_views as web_order_views

#: カード情報を表す項目名・文言（NFR-LG-05 の確認対象）。
CARD_KEYWORDS = (
    "card_number",
    "cardnumber",
    "card-number",
    "cardholder",
    "credit_card",
    "creditcard",
    "security_code",
    "securitycode",
    "cvv",
    "cvc",
    "expiry",
    "exp_month",
    "exp_year",
)

#: 差し替え実装が受け取った決済要求（テストごとに clear する）。
RECORDED_REQUESTS: list[PaymentRequest] = []

TEST_TRANSACTION_REF = "MOCK-ZZZZZZZZZZZZZZZZ"


# trace: NFR-PF-17, ADDR-009
class ContractRecordingGateway(PaymentGateway):
    """決済ゲートウェイの差し替え実装（受け取った決済要求を記録して承認を返す）。

    NFR-PF-17 の「実決済サービスへの差し替えを連携部分に限定できること」を確かめるため、
    設定値 ``PAYMENT_GATEWAY`` から解決させる差し替え実装として用いる。
    """

    def authorize(self, request: PaymentRequest, *, timeout_seconds: int) -> PaymentResult:
        RECORDED_REQUESTS.append(request)
        return PaymentResult(
            result=RESULT_APPROVED,
            processed_at=timeutils.now(),
            transaction_ref=TEST_TRANSACTION_REF,
        )


# trace: NFR-PF-17, ADDR-009
def _created_order(user):
    """支払前（created）の注文を1件作る。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(user, {"stock_unit_id": unit.pk, "quantity": 1})
    return order_services.checkout(user, shipping_input())


# ---------------------------------------------------------------------------
# NFR-PF-17 将来の拡張（決済連携部分の分離）
# ---------------------------------------------------------------------------


# trace: NFR-PF-17, ADDR-009
def test_payment_request_carries_only_the_four_contract_items():
    """NFR-PF-17：決済要求の項目は注文番号・決済金額・通貨・模擬決済指示だけとする。"""
    names = tuple(field.name for field in dataclasses.fields(PaymentRequest))

    assert names == ("order_number", "amount", "currency", "mock_result")


# trace: NFR-PF-17, ADDR-009
def test_payment_result_carries_only_the_response_contract_items():
    """NFR-PF-17：決済応答の項目は結果・処理日時・取引参照番号（＋否認理由コード）だけとする。"""
    names = tuple(field.name for field in dataclasses.fields(PaymentResult))

    assert names == ("result", "processed_at", "transaction_ref", "decline_reason_code")


# trace: NFR-PF-17, ADDR-009
@pytest.mark.parametrize(
    "module",
    [order_services, order_views, web_order_views, cart_services, catalog_services],
)
def test_order_stock_and_amount_modules_do_not_reference_the_gateway_implementation(module):
    """NFR-PF-17／ADDR-009 DD-002：注文・在庫・金額計算は模擬実装を直接参照しない。"""
    source = inspect.getsource(module)

    assert "payments.mock" not in source
    assert "MockPaymentGateway" not in source
    assert "get_payment_gateway" not in source

    for value in vars(module).values():
        assert getattr(value, "__module__", "") != "payments.mock"


# trace: NFR-PF-17, ADDR-009
@pytest.mark.django_db
def test_gateway_implementation_is_replaceable_without_changing_order_processing(buyer, settings):
    """NFR-PF-17：設定値の差し替えだけで別の決済実装を使え、注文処理は変更不要であること。

    注文処理（orders.services.pay）へ一切手を入れずに、設定値の実装だけを差し替えて支払が
    成立すること、そのとき連携部分へ渡る項目が契約どおりの4項目だけであることを確かめる。
    """
    RECORDED_REQUESTS.clear()
    order = _created_order(buyer)
    settings.PAYMENT_GATEWAY = "test_nfr_design_constraints.ContractRecordingGateway"

    paid = order_services.pay(buyer, order.pk, {"mock_result": "approve"})

    assert paid.status == STATUS_PAID
    assert len(RECORDED_REQUESTS) == 1
    assert dataclasses.asdict(RECORDED_REQUESTS[0]) == {
        "order_number": order.order_number,
        "amount": order.total,
        "currency": CURRENCY_JPY,
        "mock_result": "approve",
    }
    record = PaymentRecord.objects.get(purchase_order_id=order.pk)
    assert record.transaction_ref == TEST_TRANSACTION_REF
    assert isinstance(record.processed_at, dt.datetime)


# ---------------------------------------------------------------------------
# NFR-PF-16 業務量増加への対応（利用者の状態をDBへ保持する）
# ---------------------------------------------------------------------------


# trace: NFR-PF-16, ADDR-006
@pytest.mark.django_db
def test_login_session_state_is_held_only_in_the_database(buyer, logged_in_screen_client, settings):
    """NFR-PF-16／ADDR-006 DD-001：画面のログインセッションをDBだけで保持すること。

    DB のセッション行を削除するとログイン状態が失われることで、app のプロセス内に複製を
    保持していないことを確かめる。
    """
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    client = logged_in_screen_client(buyer)
    session_key = client.session.session_key

    assert Session.objects.filter(session_key=session_key).exists()
    assert client.get(reverse("web-orders")).status_code == 200

    Session.objects.filter(session_key=session_key).delete()
    response = client.get(reverse("web-orders"))

    assert response.status_code == 302
    assert response["Location"] == reverse("web-login")


# trace: NFR-PF-16, ADDR-002
@pytest.mark.django_db
def test_api_auth_token_state_is_held_only_in_the_database(buyer, token_for):
    """NFR-PF-16／ADDR-002 DD-005：APIの認証トークンをDBだけで保持すること。"""
    raw_token = token_for(buyer)

    assert AuthToken.objects.filter(user=buyer).exists()
    assert account_services.resolve_auth_token(raw_token) is not None

    AuthToken.objects.filter(user=buyer).delete()

    assert account_services.resolve_auth_token(raw_token) is None


# trace: NFR-PF-16
@pytest.mark.django_db
def test_cart_state_is_held_only_in_the_database(buyer):
    """NFR-PF-16：カートをDBだけで保持すること（プロセス内に複製を持たない）。"""
    unit = make_stock_unit(make_item(), price=1000, quantity=10)
    cart_services.add_line(buyer, {"stock_unit_id": unit.pk, "quantity": 1})
    cart = cart_services.get_open_cart(buyer)

    assert cart is not None
    assert Cart.objects.filter(pk=cart.pk, status=CART_OPEN).exists()

    Cart.objects.filter(pk=cart.pk).delete()

    assert cart_services.get_open_cart(buyer) is None


# ---------------------------------------------------------------------------
# NFR-LG-05 割賦販売法（クレジットカード番号を入力・保存・送信しない）
# ---------------------------------------------------------------------------


# trace: NFR-LG-05
@pytest.mark.django_db
def test_payment_screen_has_no_card_information_input_fields(buyer, logged_in_screen_client):
    """NFR-LG-05：支払画面（SCR-008）の入力項目は模擬決済指示だけで、カード情報の項目が無いこと。"""
    order = _created_order(buyer)
    client = logged_in_screen_client(buyer)

    response = client.get(reverse("web-order-pay", kwargs={"purchase_order_id": order.pk}))

    assert response.status_code == 200
    body = response.content.decode()
    form = re.search(r'<form method="post" action="[^"]*/pay/"[^>]*>(.*?)</form>', body, re.DOTALL)
    assert form is not None
    input_names = set(re.findall(r'<input[^>]*name="([^"]+)"', form.group(1)))
    assert input_names == {"csrfmiddlewaretoken", "mock_result"}
    lowered = body.lower()
    for keyword in CARD_KEYWORDS:
        assert keyword not in lowered


# trace: NFR-LG-05
def test_no_persisted_model_field_stores_card_information():
    """NFR-LG-05：いずれのテーブルにもカード情報の保存項目が無いこと。"""
    offenders = [
        f"{model._meta.db_table}.{field.name}"
        for model in apps.get_models()
        for field in model._meta.get_fields()
        for keyword in CARD_KEYWORDS
        if keyword in field.name.lower()
    ]

    assert offenders == []


# trace: NFR-LG-05, ADDR-009
@pytest.mark.django_db
def test_card_data_in_the_request_is_neither_sent_to_the_gateway_nor_stored(buyer, settings):
    """NFR-LG-05：支払要求にカード情報を混入させても、送信も保存もされないこと。"""
    RECORDED_REQUESTS.clear()
    order = _created_order(buyer)
    settings.PAYMENT_GATEWAY = "test_nfr_design_constraints.ContractRecordingGateway"
    card_number = "4111111111111111"

    order_services.pay(
        buyer,
        order.pk,
        {
            "mock_result": "approve",
            "card_number": card_number,
            "expiry": "12/30",
            "security_code": "123",
        },
    )

    assert dataclasses.asdict(RECORDED_REQUESTS[0]) == {
        "order_number": order.order_number,
        "amount": order.total,
        "currency": CURRENCY_JPY,
        "mock_result": "approve",
    }
    record = PaymentRecord.objects.get(purchase_order_id=order.pk)
    stored = {field.name: getattr(record, field.name) for field in PaymentRecord._meta.fields}
    assert card_number not in "".join(str(value) for value in stored.values())
