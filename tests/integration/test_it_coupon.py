# trace: FR-024, FR-025, FR-026
# trace: ADDR-003, ADDR-008, ADDR-010
"""クーポン適用・解除と割引計算の結合試験（IT-AI-INIT-069〜086）。

検証対象の連携は API → カートService → 注文金額計算 → ORM → PostgreSQL、
権限判定 → 業務機能API、画面 → Service → DB。

期待結果は FR-024・FR-025・FR-026 の処理内容・例外・判定順序、CMN-29（日時は秒単位）、
CMN-30（1円未満切り捨て）、提供済みAPI契約 6.2/6.3（クーポン関連のエラーコードと context）
から導出する。
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from carts.models import DISCOUNT_PERCENTAGE, Cart
from common import timeutils

pytestmark = pytest.mark.django_db


# trace: FR-024, FR-026
def fill(client, stock_unit, quantity: int) -> dict:
    """カートへ明細を1件追加する（試験前提データの準備）。"""
    response = client.post(
        "/api/cart/lines", {"stock_unit_id": stock_unit.pk, "quantity": quantity}, format="json"
    )
    assert response.status_code == 200
    return response.json()


# trace: FR-024, FR-026
def test_it_ai_init_069_percentage_coupon_discount(api_as, buyer, f):
    """IT-AI-INIT-069 / COV-060：定率10%クーポンの割引額と合計金額を算出する。"""
    unit = f.sellable(price=5550, quantity=5)
    coupon = f.percentage_coupon(percent=10, code="RATE10")
    client = api_as(buyer)
    fill(client, unit, 1)

    response = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["coupon"]["code"] == "RATE10"
    assert body["coupon"]["discount_type"] == DISCOUNT_PERCENTAGE
    assert body["coupon"]["is_applicable"] is True
    assert body["amounts"] == {
        "subtotal": 5550,
        "discount_amount": 555,
        "discounted_subtotal": 4995,
        "shipping_fee": 500,
        "tax_amount": 549,
        "total": 6044,
    }


# trace: FR-024, FR-026
def test_it_ai_init_070_percentage_discount_is_floored(api_as, buyer, f):
    """IT-AI-INIT-070 / COV-060：定率クーポンの割引額は1円未満を切り捨てる（CMN-30）。"""
    unit = f.sellable(price=1999, quantity=5)
    coupon = f.percentage_coupon(percent=15, code="RATE15")
    client = api_as(buyer)
    fill(client, unit, 1)

    response = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    amounts = response.json()["amounts"]
    assert amounts["discount_amount"] == 299
    assert amounts["discounted_subtotal"] == 1700
    assert amounts["total"] == 2420


# trace: FR-024, FR-026
def test_it_ai_init_071_fixed_coupon_enables_free_shipping(api_as, buyer, f):
    """IT-AI-INIT-071 / COV-061：定額1,000円クーポンで割引後小計5,000円・送料0円となる。"""
    unit = f.sellable(price=6000, quantity=5)
    coupon = f.coupon(code="FLAT1000", discount_value=1000)
    client = api_as(buyer)
    fill(client, unit, 1)

    response = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert response.json()["amounts"] == {
        "subtotal": 6000,
        "discount_amount": 1000,
        "discounted_subtotal": 5000,
        "shipping_fee": 0,
        "tax_amount": 500,
        "total": 5500,
    }


# trace: FR-024, FR-026
def test_it_ai_init_072_fixed_discount_never_exceeds_subtotal(api_as, buyer, f):
    """IT-AI-INIT-072 / COV-061：定額クーポンの割引額は小計を超えない。"""
    unit = f.sellable(price=800, quantity=5)
    coupon = f.coupon(code="FLAT1000B", discount_value=1000, min_spend=500)
    client = api_as(buyer)
    fill(client, unit, 1)

    response = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert response.json()["amounts"] == {
        "subtotal": 800,
        "discount_amount": 800,
        "discounted_subtotal": 0,
        "shipping_fee": 500,
        "tax_amount": 50,
        "total": 550,
    }


# trace: FR-024, ADDR-008
def test_it_ai_init_073_coupon_code_is_normalized(api_as, buyer, f):
    """IT-AI-INIT-073 / COV-062：クーポンコードは前後空白除去・英大文字化して照合する。"""
    unit = f.sellable(price=3000, quantity=5)
    f.coupon(code="SAVE10", discount_value=500)
    client = api_as(buyer)
    fill(client, unit, 1)

    lower = client.post("/api/cart/apply-coupon", {"code": "  save10  "}, format="json")
    assert lower.status_code == 200
    assert lower.json()["coupon"]["code"] == "SAVE10"

    client.post("/api/cart/remove-coupon", format="json")
    mixed = client.post("/api/cart/apply-coupon", {"code": "Save10"}, format="json")

    assert mixed.status_code == 200
    assert mixed.json()["coupon"]["code"] == "SAVE10"


# trace: FR-024
def test_it_ai_init_074_coupon_code_format(api_as, buyer, f, err):
    """IT-AI-INIT-074 / COV-062：クーポンコードは英大文字・数字・ハイフンの20文字以内とする。"""
    unit = f.sellable(price=3000, quantity=5)
    code20 = "A" * 19 + "1"
    f.coupon(code=code20, discount_value=100)
    client = api_as(buyer)
    fill(client, unit, 1)

    ok = client.post("/api/cart/apply-coupon", {"code": code20}, format="json")
    assert ok.status_code == 200
    client.post("/api/cart/remove-coupon", format="json")

    for invalid in ("A" * 21, "SAVE@10", "   ", None):
        payload = {} if invalid is None else {"code": invalid}
        response = client.post("/api/cart/apply-coupon", payload, format="json")

        assert response.status_code == 400, invalid
        assert err.code(response) == "VALIDATION_ERROR"
        assert "code" in err.fields(response)
    assert client.get("/api/cart").json()["coupon"] is None


# trace: FR-024
def test_it_ai_init_075_empty_cart_coupon_is_business_error(api_as, buyer, f, err):
    """IT-AI-INIT-075 / COV-063：形式判定を先に行い、形式が正しい場合は空カートの業務エラーとする。"""
    f.coupon(code="EMPTYCART1", discount_value=100)
    client = api_as(buyer)
    client.get("/api/cart")

    invalid_format = client.post("/api/cart/apply-coupon", {"code": "bad code!"}, format="json")
    valid_format = client.post("/api/cart/apply-coupon", {"code": "EMPTYCART1"}, format="json")

    assert invalid_format.status_code == 400
    assert err.code(invalid_format) == "VALIDATION_ERROR"
    assert valid_format.status_code == 409
    assert err.code(valid_format) == "CART_EMPTY"


# trace: FR-024
def test_it_ai_init_076_applied_coupon_cannot_be_replaced(api_as, buyer, f, err):
    """IT-AI-INIT-076 / COV-064：適用中の再適用・別コード適用は業務エラーとする。"""
    unit = f.sellable(price=3000, quantity=5)
    f.coupon(code="SAVE10", discount_value=500)
    f.coupon(code="OTHER10", discount_value=700)
    client = api_as(buyer)
    fill(client, unit, 1)
    applied = client.post("/api/cart/apply-coupon", {"code": "SAVE10"}, format="json").json()

    for code in ("OTHER10", "SAVE10"):
        response = client.post("/api/cart/apply-coupon", {"code": code}, format="json")

        assert response.status_code == 409, code
        assert err.code(response) == "COUPON_ALREADY_APPLIED"

    current = client.get("/api/cart").json()
    assert current["coupon"]["code"] == "SAVE10"
    assert current["amounts"] == applied["amounts"]


# trace: FR-024
def test_it_ai_init_077_unknown_coupon_code(api_as, buyer, f, err):
    """IT-AI-INIT-077 / COV-065：登録されていないクーポンコードは対象なしの業務エラーとする。"""
    unit = f.sellable(price=3000, quantity=5)
    client = api_as(buyer)
    fill(client, unit, 1)

    response = client.post("/api/cart/apply-coupon", {"code": "NOTEXIST01"}, format="json")

    assert response.status_code == 409
    assert err.code(response) == "COUPON_NOT_FOUND"
    assert client.get("/api/cart").json()["coupon"] is None


# trace: FR-024
def test_it_ai_init_078_coupon_valid_from_boundary(api_as, buyer, f, fixed_now, err):
    """IT-AI-INIT-078 / COV-066：有効開始日時の1秒前は開始前、ちょうどは適用成功とする（CMN-29）。"""
    start = dt.datetime(2027, 4, 1, 10, 0, 0, tzinfo=timeutils.JST)
    fixed_now(start - dt.timedelta(minutes=1))
    unit = f.sellable(price=3000, quantity=5)
    coupon = f.coupon(
        code="FUTURE01",
        discount_value=300,
        valid_from=start,
        valid_until=start + dt.timedelta(days=1),
    )
    client = api_as(buyer)
    fill(client, unit, 1)

    fixed_now(start - dt.timedelta(seconds=1))
    before = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert before.status_code == 409
    assert err.code(before) == "COUPON_NOT_YET_VALID"
    assert err.context(before) == {
        "valid_from": timeutils.to_iso(coupon.valid_from),
        "valid_until": timeutils.to_iso(coupon.valid_until),
    }

    fixed_now(start)
    exactly = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert exactly.status_code == 200
    assert exactly.json()["coupon"]["is_applicable"] is True


# trace: FR-024
def test_it_ai_init_079_coupon_valid_until_boundary(api_as, buyer, f, monkeypatch, err):
    """IT-AI-INIT-079 / COV-066：有効終了日時ちょうど（ミリ秒を含む同一秒）は有効、1秒後は期限切れとする。"""
    end = dt.datetime(2027, 4, 30, 23, 59, 59, tzinfo=timeutils.JST)
    clock = {"value": end - dt.timedelta(minutes=1)}
    monkeypatch.setattr(timezone, "now", lambda: clock["value"])
    unit = f.sellable(price=3000, quantity=5)
    coupon = f.coupon(
        code="ENDBOUND01",
        discount_value=300,
        valid_from=end - dt.timedelta(days=10),
        valid_until=end,
    )
    client = api_as(buyer)
    fill(client, unit, 1)

    clock["value"] = end
    exactly = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")
    assert exactly.status_code == 200
    client.post("/api/cart/remove-coupon", format="json")

    clock["value"] = end.replace(microsecond=500000)
    with_milliseconds = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")
    assert with_milliseconds.status_code == 200
    client.post("/api/cart/remove-coupon", format="json")

    clock["value"] = end + dt.timedelta(seconds=1)
    expired = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")

    assert expired.status_code == 409
    assert err.code(expired) == "COUPON_EXPIRED"
    assert err.context(expired)["valid_until"] == timeutils.to_iso(coupon.valid_until)


# trace: FR-024
def test_it_ai_init_080_minimum_spend_boundary(api_as, buyer, other_buyer, f, err):
    """IT-AI-INIT-080 / COV-067：最低購入金額と一致する小計は適用でき、1円不足は業務エラーとする。"""
    f.coupon(code="MINSPEND01", discount_value=500, min_spend=5000)
    equal_unit = f.sellable(price=5000, quantity=5)
    short_unit = f.sellable(price=4999, quantity=5)
    equal_client = api_as(buyer)
    short_client = api_as(other_buyer)
    fill(equal_client, equal_unit, 1)
    fill(short_client, short_unit, 1)

    equal = equal_client.post("/api/cart/apply-coupon", {"code": "MINSPEND01"}, format="json")
    short = short_client.post("/api/cart/apply-coupon", {"code": "MINSPEND01"}, format="json")

    assert equal.status_code == 200
    assert equal.json()["amounts"]["discount_amount"] == 500
    assert short.status_code == 409
    assert err.code(short) == "COUPON_MIN_SPEND_NOT_MET"
    assert err.context(short) == {"min_spend": 5000, "subtotal": 4999}


# trace: FR-025
def test_it_ai_init_081_remove_coupon(api_as, buyer, other_buyer, f):
    """IT-AI-INIT-081 / COV-068：クーポン解除で割引額は0円となり、未適用時の解除も成功する。"""
    unit = f.sellable(price=6000, quantity=5)
    f.coupon(code="REMOVE01", discount_value=1000)
    client = api_as(buyer)
    fill(client, unit, 1)
    client.post("/api/cart/apply-coupon", {"code": "REMOVE01"}, format="json")

    removed = client.post("/api/cart/remove-coupon", format="json")

    assert removed.status_code == 200
    body = removed.json()
    assert body["coupon"] is None
    assert body["amounts"]["discount_amount"] == 0
    assert body["amounts"]["total"] == 6600

    other_client = api_as(other_buyer)
    not_applied = other_client.post("/api/cart/remove-coupon", format="json")

    assert not_applied.status_code == 200
    assert not_applied.json()["coupon"] is None
    assert not_applied.json()["amounts"]["total"] == 0


# trace: FR-024, FR-026
def test_it_ai_init_082_applicability_follows_cart_changes(api_as, buyer, f):
    """IT-AI-INIT-082 / COV-069：適用後に条件を割った場合は適用可否のみ変わり、回復時は再適用なしで割引する。"""
    unit = f.sellable(price=1000, quantity=10)
    f.coupon(code="KEEPMIN01", discount_value=500, min_spend=5000)
    client = api_as(buyer)
    line_id = fill(client, unit, 5)["lines"][0]["cart_line_id"]
    client.post("/api/cart/apply-coupon", {"code": "KEEPMIN01"}, format="json")

    reduced = client.patch(f"/api/cart/lines/{line_id}", {"quantity": 4}, format="json").json()

    assert reduced["coupon"]["code"] == "KEEPMIN01"
    assert reduced["coupon"]["is_applicable"] is False
    assert reduced["coupon"]["not_applicable_reason"] == "COUPON_MIN_SPEND_NOT_MET"
    assert reduced["amounts"]["discount_amount"] == 0
    assert reduced["amounts"]["subtotal"] == 4000

    restored = client.patch(f"/api/cart/lines/{line_id}", {"quantity": 5}, format="json").json()

    assert restored["coupon"]["is_applicable"] is True
    assert restored["coupon"]["not_applicable_reason"] is None
    assert restored["amounts"]["discount_amount"] == 500
    assert restored["amounts"]["discounted_subtotal"] == 4500


# trace: FR-024, FR-026
def test_it_ai_init_083_applied_coupon_expires_after_period(api_as, buyer, f, fixed_now):
    """IT-AI-INIT-083 / COV-069：適用中クーポンが期限切れになると適用不可・割引額0円で返す。"""
    end = dt.datetime(2027, 5, 31, 23, 59, 59, tzinfo=timeutils.JST)
    fixed_now(end - dt.timedelta(minutes=1))
    unit = f.sellable(price=6000, quantity=5)
    coupon = f.coupon(
        code="EXPIRING01", discount_value=1000, valid_from=end - dt.timedelta(days=10), valid_until=end
    )
    client = api_as(buyer)
    fill(client, unit, 1)
    applied = client.post("/api/cart/apply-coupon", {"code": coupon.code}, format="json")
    assert applied.json()["amounts"]["discount_amount"] == 1000

    fixed_now(end + dt.timedelta(seconds=1))
    response = client.get("/api/cart")

    body = response.json()
    assert body["coupon"]["code"] == "EXPIRING01"
    assert body["coupon"]["is_applicable"] is False
    assert body["coupon"]["not_applicable_reason"] == "COUPON_EXPIRED"
    assert body["amounts"]["discount_amount"] == 0
    assert body["amounts"]["subtotal"] == 6000


# trace: FR-024, FR-025
def test_it_ai_init_084_coupon_operations_require_buyer(api, api_as, admin_user, err):
    """IT-AI-INIT-084 / COV-071：未ログインは認証エラー、管理者は権限エラーとする。"""
    admin_client = api_as(admin_user)

    for path in ("/api/cart/apply-coupon", "/api/cart/remove-coupon"):
        anonymous = api.post(path, {"code": "ANY01"}, format="json")
        administrator = admin_client.post(path, {"code": "ANY01"}, format="json")

        assert anonymous.status_code == 401, path
        assert err.code(anonymous) == "AUTHENTICATION_REQUIRED"
        assert administrator.status_code == 403, path
        assert err.code(administrator) == "PERMISSION_DENIED"


# trace: FR-024
def test_it_ai_init_085_coupon_error_priority(api_as, buyer, other_buyer, f, fixed_now, err):
    """IT-AI-INIT-085 / COV-072：適用中→コード不存在→有効期間→最低購入金額の順に先に該当したエラーを返す。"""
    now = dt.datetime(2027, 6, 1, 12, 0, 0, tzinfo=timeutils.JST)
    fixed_now(now)
    unit = f.sellable(price=4999, quantity=5)
    f.coupon(code="APPLIED01", discount_value=100)
    f.coupon(
        code="EXPMIN01",
        discount_value=100,
        min_spend=5000,
        valid_from=now - dt.timedelta(days=10),
        valid_until=now - dt.timedelta(days=1),
    )
    applied_client = api_as(buyer)
    fill(applied_client, unit, 1)
    applied_client.post("/api/cart/apply-coupon", {"code": "APPLIED01"}, format="json")

    already = applied_client.post("/api/cart/apply-coupon", {"code": "NOTEXIST01"}, format="json")

    assert already.status_code == 409
    assert err.code(already) == "COUPON_ALREADY_APPLIED"

    other_client = api_as(other_buyer)
    fill(other_client, unit, 1)
    expired_first = other_client.post("/api/cart/apply-coupon", {"code": "EXPMIN01"}, format="json")

    assert expired_first.status_code == 409
    assert err.code(expired_first) == "COUPON_EXPIRED"


# trace: FR-024, ADDR-010
def test_it_ai_init_086_screen_shows_coupon_result_and_error(screen_as, buyer, f):
    """IT-AI-INIT-086 / COV-073：画面は適用中クーポンと割引後金額、最低購入金額エラーを表示する。"""
    item = f.item(name="画面クーポン商品")
    unit = f.stock_unit(item, price=6000, quantity=5)
    f.coupon(code="SCRCPN01", name="画面クーポン", discount_value=1000)
    f.coupon(code="SCRMIN01", name="最低金額クーポン", discount_value=500, min_spend=10000)
    client = screen_as(buyer)
    client.post("/cart/lines/add/", {"item_id": item.pk, "stock_unit_id": unit.pk, "quantity": 1})

    applied = client.post("/cart/coupon/apply/", {"code": "SCRCPN01"}, follow=True)
    body = applied.content.decode()

    assert applied.status_code == 200
    assert "SCRCPN01" in body
    assert "適用中" in body
    assert "1,000円" in body  # 割引額
    assert "5,000円" in body  # 割引後小計
    assert "5,500円" in body  # 合計（税込）

    client.post("/cart/coupon/remove/")
    rejected = client.post("/cart/coupon/apply/", {"code": "SCRMIN01"})
    rejected_body = rejected.content.decode()

    assert "最低購入金額" in rejected_body
    assert "10,000円" in rejected_body
    assert "6,000円" in rejected_body
    assert Cart.objects.get(user=buyer).coupon_id is None
