# trace: FR-004, FR-011, FR-021, FR-030, FR-031, FR-040, ADDR-005, ADDR-007
"""共通エラー応答の構造と判定順序（7章 CMN-14、10章 MSG-04）の結合試験。

期待結果は機能要件定義書 7.3（CMN-13・CMN-14）、10.1 エラー種別ごとの通知方針、
非機能要件（NFR-SC-10 内部情報の非開示）、api-contract 6.2 から導出する。
"""
import json

import pytest

from shop.services import catalog
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

FORBIDDEN_FRAGMENTS = (
    "Traceback",
    "File \"",
    "SELECT ",
    "INSERT ",
    "psycopg",
    "django.db",
    "shop/services",
    "password_hash",
)


# trace: FR-030
def _buyer_with_order(api, email="buyer@example.com", sku="SKU-001"):
    """購入者・在庫単位・注文を1件作成し、トークンと注文IDを返す。"""
    _helpers.make_user(email=email)
    token = api.login(email)
    supplier = _helpers.make_supplier(supplier_code=f"SUP-{sku}")
    item = _helpers.make_item(item_code=f"ITEM-{sku}", name=f"商品{sku}")
    unit = _helpers.make_stock_unit(item, supplier, sku=sku, quantity=5)
    api.post("/api/cart/lines", {"stock_unit_id": unit.stock_unit_id, "quantity": 1}, token=token)
    checkout = api.post("/api/checkout", dict(_helpers.VALID_ADDRESS), token=token)
    assert checkout.status_code == 201, checkout.content
    return token, checkout.json()["purchase_order_id"]


# trace: FR-004, FR-011, FR-021, FR-040, ADDR-005, ADDR-007
@pytest.mark.case("IT-AI-GF-009")
def test_error_responses_share_structure_without_internal_details(api, monkeypatch):
    """全エラー応答は共通構造で、内部情報（スタックトレース・SQL・資格情報）を含まない（MSG-04、NFR-SC-10）。"""
    token, order_id = _buyer_with_order(api)
    _helpers.make_admin(email="admin@example.com")

    responses = {
        "AUTHENTICATION_REQUIRED": api.get("/api/auth/me"),
        "PERMISSION_DENIED": api.get("/api/admin/stock-units", token=token),
        "NOT_FOUND": api.get("/api/purchase-orders/999999", token=token),
        "VALIDATION_ERROR": api.get("/api/items", {"sort": "unknown"}),
        "INVALID_STATUS_TRANSITION": None,
    }
    assert api.post(f"/api/purchase-orders/{order_id}/cancel", token=token).status_code == 200
    responses["INVALID_STATUS_TRANSITION"] = api.post(f"/api/purchase-orders/{order_id}/cancel", token=token)

    def broken_list_collections():
        """内部障害（内部情報を含む例外）を発生させる。"""
        raise RuntimeError("SELECT * FROM collection -- internal detail with password_hash")

    monkeypatch.setattr(catalog, "list_collections", broken_list_collections)
    responses["INTERNAL_ERROR"] = api.get("/api/collections")

    expected_status = {
        "AUTHENTICATION_REQUIRED": 401,
        "PERMISSION_DENIED": 403,
        "NOT_FOUND": 404,
        "VALIDATION_ERROR": 400,
        "INVALID_STATUS_TRANSITION": 409,
        "INTERNAL_ERROR": 500,
    }
    for code, response in responses.items():
        body = response.json()
        assert response.status_code == expected_status[code], code
        assert set(body) == {"error"}, code
        assert set(body["error"]) == {"code", "message", "details", "context"}, code
        assert body["error"]["code"] == code
        assert isinstance(body["error"]["message"], str) and body["error"]["message"]
        assert isinstance(body["error"]["details"], list)
        assert isinstance(body["error"]["context"], dict)
        serialized = json.dumps(body, ensure_ascii=False)
        for fragment in FORBIDDEN_FRAGMENTS:
            assert fragment not in serialized, f"{code} contains {fragment}"
        assert _helpers.TEST_PASSWORD not in serialized, code
        assert token not in serialized, code


# trace: FR-021, FR-030, FR-031, FR-040, ADDR-007
@pytest.mark.case("IT-AI-GF-010")
def test_error_precedence_follows_common_rule(api):
    """複数のエラー要因が同時に成立する場合、CMN-14 の順序で先に該当したエラーだけを通知する。"""
    token, order_id = _buyer_with_order(api)
    _helpers.make_admin(email="admin@example.com")
    admin_token = api.login("admin@example.com")

    # ①認証 が ③入力 に優先する
    unauthenticated = api.post("/api/cart/lines", {"stock_unit_id": "not-an-id"})
    # ②権限 が ④対象 に優先する
    forbidden = api.get("/api/admin/purchase-orders/999999", token=token)
    # ②権限 が ③入力 に優先する
    admin_on_buyer_api = api.post("/api/cart/lines", {"stock_unit_id": "not-an-id"}, token=admin_token)
    # ③入力 が ④対象 に優先する
    invalid_input = api.post("/api/purchase-orders/999999/pay", {"mock_result": "unknown"}, token=token)
    # ④対象 が ⑤状態 に優先する（他の購入者の注文は存在を明かさない）
    _other_token, other_order_id = _buyer_with_order(api, email="other@example.com", sku="SKU-002")
    not_found = api.post(f"/api/purchase-orders/{other_order_id}/pay", {}, token=token)
    # ⑤状態 が ⑥業務ルール（決済）に優先する
    assert api.post(f"/api/purchase-orders/{order_id}/cancel", token=token).status_code == 200
    invalid_status = api.post(f"/api/purchase-orders/{order_id}/pay", {"mock_result": "decline"}, token=token)

    assert (unauthenticated.status_code, _helpers.error_code(unauthenticated)) == (401, "AUTHENTICATION_REQUIRED")
    assert (forbidden.status_code, _helpers.error_code(forbidden)) == (403, "PERMISSION_DENIED")
    assert (admin_on_buyer_api.status_code, _helpers.error_code(admin_on_buyer_api)) == (403, "PERMISSION_DENIED")
    assert (invalid_input.status_code, _helpers.error_code(invalid_input)) == (400, "VALIDATION_ERROR")
    assert (not_found.status_code, _helpers.error_code(not_found)) == (404, "NOT_FOUND")
    assert (invalid_status.status_code, _helpers.error_code(invalid_status)) == (409, "INVALID_STATUS_TRANSITION")
    assert invalid_status.json()["error"]["context"] == {"current_status": "cancelled"}
