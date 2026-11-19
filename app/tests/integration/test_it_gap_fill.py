# trace: FR-001, FR-002, FR-021, FR-022, FR-023, FR-024, FR-030, FR-034, FR-040, FR-041, FR-043, FR-060
# trace: ADDR-001, ADDR-004, ADDR-009, ADDR-010, ADDR-011, ADDR-012
"""結合試験：AI GAP_FILL（Required Coverage の補完）。

Coverage Gap Analysis で MISSING、または実装時の照合で一部未検証と判明した Required Coverage を補う。

GF-001〜GF-011（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL（IT-001〜IT-061）は変更しない。
GF-002 は Security Review SR-IT-R1-001 により、再送したブラウザにログイン状態が付与されないことの確認を追加した
（期待結果は RC-023・ADDR-004 DD-016 のまま。GF-012 以降は test_it_gap_fill_*.py）。
期待結果は FR-001・FR-002・FR-021・FR-022・FR-024・FR-030・FR-034・FR-040・FR-041・FR-043・FR-060、CMN-17/22、UI-19/29、
ADDR-001・ADDR-004（送信トークン DD-013/016）・ADDR-009・ADDR-010・ADDR-012 から導出する。
"""

import copy
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.management import execute_from_command_line

from tests.integration._helpers import (
    ADDRESS,
    PASSWORD,
    add_item,
    api,
    body,
    error_of,
    field_names,
    form_fields,
    input_value,
    jst,
    order_of,
    pay,
    text,
)

pytestmark = pytest.mark.django_db
SEED = Path(__file__).resolve().parents[2] / "seed" / "initial_data.json"


# trace: FR-001, FR-002, ADDR-012, ADDR-004
def test_gf_001_web_register_and_login_error_display(web, buyer):
    """GF-001 画面の会員登録の入力エラー表示・ログイン失敗表示と入力値の保持。"""
    from accounts.models import User
    from audit.models import AuditLog

    users = User.objects.count()
    client = web()
    fields = form_fields(text(client.get("/register/")), "/register/")
    long_name = "長" * 51
    fields.update({"email": "bad-mail", "password": "short", "password_confirmation": "short", "name": long_name})
    page = client.post("/register/", fields)
    assert page.status_code == 400
    html = text(page)
    assert html.count('class="field-error"') >= 3
    assert input_value(html, "email") == "bad-mail" and input_value(html, "name") == long_name
    assert input_value(html, "password") == "" and input_value(html, "password_confirmation") == ""
    assert User.objects.count() == users

    fields = form_fields(text(client.get("/login/")), "/login/")
    fields.update({"email": buyer.email, "password": "Wrong0Password"})
    failed = client.post("/login/", fields)
    assert failed.status_code == 401
    html = text(failed)
    assert "メールアドレスまたはパスワード" in html
    assert input_value(html, "email") == buyer.email and input_value(html, "password") == ""
    assert AuditLog.objects.filter(event_type="login_failure", target_user_id=buyer.pk).count() == 1


# trace: FR-002, ADDR-004
def test_gf_002_web_login_double_submit_same_token(web, buyer):
    """GF-002 画面ログインの同じ送信トークンでの再送（照合・監査ログを重ねない）。"""
    from audit.models import AuditLog

    client = web()
    fields = form_fields(text(client.get("/login/")), "/login/")
    fields.update({"email": buyer.email, "password": PASSWORD})
    # 再送は先着の送信前に複製した Cookie・フォーム値（同じ送信トークン）で、先着の応答を受け取った後に逐次に送る
    # （使用済みトークンの判定経路。処理中の同時到着のログインは GF-043 が確認する）
    resending_browser = web()
    resending_browser.cookies = copy.deepcopy(client.cookies)
    first = client.post("/login/", fields)
    assert first.status_code == 302 and first["Location"] == "/"
    resend = dict(fields, password="Wrong0Password")
    second = resending_browser.post("/login/", resend)
    assert second.status_code == 302 and second["Location"] == "/"
    assert AuditLog.objects.filter(event_type="login_success").count() == 1
    assert AuditLog.objects.filter(event_type="login_failure").count() == 0
    # 誤ったパスワードで再送したブラウザ（ログイン前の Cookie）にはログイン状態が付与されない
    # （新たなログイン状態を開始しない）
    protected = resending_browser.get("/cart/")
    assert protected.status_code == 302 and protected["Location"].startswith("/login/?required=1")
    assert client.get("/cart/").status_code == 200


# trace: FR-021, ADDR-004
def test_gf_003_web_cart_add_double_submit(web, buyer, catalog):
    """GF-003 画面「カートに入れる」の同じ送信トークンでの再送。"""
    from carts.models import CartItem

    product = catalog.product()
    unit = catalog.stock_unit(product, stock=20)
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    fields = form_fields(text(client.get(f"/products/{product.pk}/")), "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "3"})
    for _ in range(2):
        response = client.post("/cart/items/add/", fields)
        assert response.status_code == 302 and response["Location"] == f"/products/{product.pk}/"
    assert list(CartItem.objects.filter(cart__buyer=buyer).values_list("quantity", flat=True)) == [3]


# trace: FR-030, ADDR-012
def test_gf_004_web_checkout_input_error_retains_values(api_client, web, buyer, bearer, catalog):
    """GF-004 画面の注文手続きの配送先入力エラー表示と入力値の保持。"""
    from carts.models import CartItem
    from catalog.models import StockUnit
    from orders.models import Order

    unit = catalog.stock_unit(stock=5)
    add_item(api_client, bearer(buyer), unit.pk, 2)
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    fields = form_fields(text(client.get("/checkout/")), "/checkout/")
    fields.update(
        {
            **ADDRESS,
            "recipient_name": "山田 花子",
            "postal_code": "〒1234567",
            "phone_number": "03-1234",
            "address_line1": "千代田区1-1",
        }
    )
    page = client.post("/checkout/", fields)
    assert page.status_code == 400
    html = text(page)
    assert html.count('class="field-error"') >= 2
    assert input_value(html, "recipient_name") == "山田 花子"
    assert input_value(html, "postal_code") == "〒1234567" and input_value(html, "address_line1") == "千代田区1-1"
    assert input_value(html, "phone_number") == "03-1234"
    assert Order.objects.count() == 0 and StockUnit.objects.get(pk=unit.pk).stock_quantity == 5
    assert list(CartItem.objects.filter(cart__buyer=buyer).values_list("quantity", flat=True)) == [2]


# trace: FR-034, ADDR-012, ADDR-004
def test_gf_005_web_buyer_cancel(api_client, web, buyer, bearer, catalog):
    """GF-005 画面（SCR-010）での購入者キャンセル。"""
    from catalog.models import StockUnit
    from orders.models import OrderStatusHistory

    unit = catalog.stock_unit(stock=10)
    order = order_of(api_client, bearer(buyer), [(unit, 3)])
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 7
    client = web()
    client.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    path = f"/orders/{order['order_id']}/"
    fields = form_fields(text(client.get(path)), f"{path}cancel/")
    response = client.post(f"{path}cancel/", fields)
    assert response.status_code == 302 and response["Location"] == path
    html = text(client.get(path))
    assert "注文をキャンセルしました。" in html and "キャンセル済" in html
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 10
    last = OrderStatusHistory.objects.filter(order_id=order["order_id"]).order_by("pk").last()
    assert (last.to_status, last.actor_id, last.actor_user_type) == ("cancelled", buyer.pk, "buyer")


# trace: FR-040, ADDR-001
def test_gf_006_stock_unit_list_input_errors(api_client, admin, bearer, catalog):
    """GF-006 在庫単位一覧（管理）の入力エラー全項目。"""
    catalog.supplier("SUP-REAL")
    response = api(
        api_client,
        "get",
        "/api/admin/stock-units/?supplier_code=NOPE&low_stock_only=yes&page=abc&sku=" + "A" * 33,
        bearer(admin),
    )
    assert response.status_code == 400
    assert error_of(response)["type"] == "input_error"
    assert {"supplier_code", "low_stock_only", "page", "sku"} <= field_names(response)


# trace: FR-041, ADDR-001
def test_gf_007_admin_order_search_input_errors(api_client, admin, bearer):
    """GF-007 注文一覧検索（管理者）の入力エラー。"""
    token = bearer(admin)
    reversed_range = api(
        api_client, "get", "/api/admin/orders/?order_date_from=2027-04-10&order_date_to=2027-04-09", token
    )
    assert reversed_range.status_code == 400
    assert "invalid_range" in {f["reason"] for f in error_of(reversed_range)["fields"]}
    same_day = api(api_client, "get", "/api/admin/orders/?order_date_from=2027-04-10&order_date_to=2027-04-10", token)
    assert same_day.status_code == 200
    invalid = api(
        api_client, "get", "/api/admin/orders/?order_date_from=2027-02-30&order_number=PO-123&status=unknown", token
    )
    assert invalid.status_code == 400
    assert {"order_date_from", "order_number", "status"} <= field_names(invalid)


# trace: FR-043, ADDR-001
def test_gf_008_ship_tracking_number_validation(api_client, buyer, admin, bearer, catalog):
    """GF-008 出荷登録の配送伝票番号の検証（30文字可・31文字・不正文字）。"""
    from orders.models import Order, OrderStatusHistory

    unit = catalog.stock_unit(stock=10)
    token, admin_token = bearer(buyer), bearer(admin)
    first = order_of(api_client, token, [(unit, 1)])
    second = order_of(api_client, token, [(unit, 1)])
    pay(api_client, token, first["order_id"])
    pay(api_client, token, second["order_id"])
    history = OrderStatusHistory.objects.count()
    for value in ("A" * 31, "TRK 001", "伝票1", "TRK_001"):
        response = api(
            api_client, "post", f"/api/admin/orders/{first['order_id']}/ship/", admin_token, {"tracking_number": value}
        )
        assert response.status_code == 400, value
        assert "tracking_number" in field_names(response)
    assert Order.objects.get(pk=first["order_id"]).status == "paid" and OrderStatusHistory.objects.count() == history
    value = "Ab-" + "9" * 27
    ok = api(
        api_client,
        "post",
        f"/api/admin/orders/{second['order_id']}/ship/",
        admin_token,
        {"tracking_number": f"  {value} "},
    )
    assert ok.status_code == 200 and body(ok)["tracking_number"] == value
    assert Order.objects.get(pk=second["order_id"]).tracking_number == value


# trace: FR-060, ADDR-009, ADDR-010
@pytest.mark.django_db(transaction=True)
def test_gf_009_seed_file_loadable(capsys):
    """GF-009 提供済み定義ファイル（app/seed/initial_data.json）の投入。"""
    from accounts.models import User
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
    from promotions.models import Coupon

    definition = json.loads(SEED.read_text(encoding="utf-8-sig"))
    code = 0
    try:
        execute_from_command_line(["manage.py", "load_initial_data", str(SEED)])
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert User.objects.count() == len(definition.get("users", []))
    assert Supplier.objects.count() == len(definition.get("suppliers", []))
    assert Category.objects.count() == len(definition.get("categories", []))
    assert Product.objects.count() == len(definition.get("products", []))
    assert ProductCategory.objects.count() == sum(
        len(p.get("category_codes") or []) for p in definition.get("products", [])
    )
    assert StockUnit.objects.count() == len(definition.get("stock_units", []))
    assert Coupon.objects.count() == len(definition.get("coupons", []))


# trace: FR-024, ADDR-001, ADDR-011
def test_gf_010_coupon_not_found_format_and_end_boundary(api_client, buyer, bearer, catalog, make_coupon, set_state):
    """GF-010 クーポン適用のコード不存在・形式不正と有効終了日時ちょうど／1秒後の適用。"""
    end = jst(2027, 4, 30, 23, 59, 59)
    make_coupon("END-100", discount_value=100, valid_from=jst(2027, 4, 1), valid_to=end)
    unit = catalog.stock_unit(price=1000, stock=10)
    set_state(fixed_now=end)
    token = bearer(buyer)
    add_item(api_client, token, unit.pk, 1)

    def apply(code):
        return api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": code})

    missing = apply("NOPE-1")
    assert missing.status_code == 422 and error_of(missing)["reason"] == "coupon_not_found"
    for code in ("BAD CODE", "A" * 21, "", "クーポン"):
        invalid = apply(code)
        assert invalid.status_code == 400, code
        assert "coupon_code" in field_names(invalid)
    assert apply("END-100").status_code == 200
    assert api(api_client, "delete", "/api/cart/coupon/", token).status_code == 200

    set_state(fixed_now=end + timedelta(seconds=1))
    token = bearer(buyer)
    expired = apply("END-100")
    assert expired.status_code == 422 and error_of(expired)["reason"] == "coupon_expired"
    assert error_of(expired)["values"]["valid_to"] == "2027-04-30T23:59:59+09:00"
    assert body(api(api_client, "get", "/api/cart/", token))["coupon"] is None


# trace: FR-022, FR-023, ADDR-001
def test_gf_011_ordered_cart_item_not_found(api_client, buyer, bearer, catalog):
    """GF-011 注文済カートの明細を指定した数量変更・削除は対象なし。"""
    from carts.models import CartItem

    unit = catalog.stock_unit(stock=10)
    token = bearer(buyer)
    item_id = body(add_item(api_client, token, unit.pk, 2))["items"][0]["cart_item_id"]
    assert api(api_client, "post", "/api/orders/", token, {"shipping_address": ADDRESS}).status_code == 201
    for method, payload in (("patch", {"quantity": 1}), ("delete", None)):
        response = api(api_client, method, f"/api/cart/items/{item_id}/", token, payload)
        assert response.status_code == 404 and error_of(response)["type"] == "not_found"
    assert CartItem.objects.get(pk=item_id).quantity == 2
