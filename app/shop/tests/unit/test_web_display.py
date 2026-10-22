# trace: FR-020, FR-024, FR-026, FR-030, FR-033, FR-040, FR-042, NFR-SC-04, ADDR-004
"""表示整形（UI-23〜UI-27、UI-32、UI-33）と共通レイアウト情報の単体テスト。

期待値は画面要件の表示仕様（金額・税込価格・状態表示名・都道府県・郵便番号・未設定）から導出する。
"""
import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from shop.services import carts
from shop.web import session
from shop.web.context_processors import layout
from shop.web.prefectures import PREFECTURES
from shop.web.templatetags import display


# trace: FR-026
@pytest.mark.parametrize(("value", "expected"), [(0, "0円"), (1234, "1,234円"), (1000000, "1,000,000円"), (None, "－")])
def test_yen_filter(value, expected):
    """金額は3桁区切りに「円」を付けて表示する（未設定は「－」）。"""
    assert display.yen(value) == expected


# trace: FR-026
@pytest.mark.parametrize(("value", "expected"), [(1000, "1,100円"), (999, "1,098円"), (None, "－")])
def test_tax_included_filter(value, expected):
    """税抜価格から税込価格（1円未満切り捨て）を求めて表示する。"""
    assert display.tax_included(value) == expected


# trace: FR-033
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("created", "注文受付"),
        ("paid", "支払済"),
        ("shipped", "出荷済"),
        ("delivered", "配達完了"),
        ("cancelled", "キャンセル済"),
        ("unknown", "－"),
    ],
)
def test_order_status_filter(value, expected):
    """注文状態は CD-02 の表示名で表示する。"""
    assert display.order_status(value) == expected


# trace: FR-042
@pytest.mark.parametrize(
    ("value", "expected"), [("approved", "承認"), ("declined", "否認"), ("error", "連携エラー"), (None, "－")]
)
def test_payment_result_filter(value, expected):
    """決済結果は CD-05 の表示名で表示する。"""
    assert display.payment_result(value) == expected


# trace: FR-024
@pytest.mark.parametrize(("value", "expected"), [("fixed", "定額"), ("percentage", "定率"), (None, "－")])
def test_discount_type_filter(value, expected):
    """割引方式は CD-03 の表示名で表示する。"""
    assert display.discount_type(value) == expected


# trace: FR-042
@pytest.mark.parametrize(("value", "expected"), [("buyer", "購入者"), ("admin", "管理者"), ("", "－")])
def test_actor_role_filter(value, expected):
    """実行者の利用者区分は CD-01 の表示名で表示する。"""
    assert display.actor_role(value) == expected


# trace: FR-030
@pytest.mark.parametrize(("value", "expected"), [("01", "北海道"), ("13", "東京都"), ("47", "沖縄県"), ("99", "－")])
def test_prefecture_filter(value, expected):
    """都道府県コードは JIS X 0401 の都道府県名で表示する。"""
    assert display.prefecture(value) == expected


# trace: FR-030
def test_prefectures_cover_all_47_codes():
    """都道府県の選択肢は01〜47の47件である。"""
    assert len(PREFECTURES) == 47
    assert PREFECTURES[0][0] == "01"
    assert PREFECTURES[-1][0] == "47"


# trace: FR-033
@pytest.mark.parametrize(
    ("value", "expected"),
    [("1234567", "123-4567"), ("123456", "123456"), ("", "－"), (None, "－")],
)
def test_postal_code_filter(value, expected):
    """郵便番号は「123-4567」の形式で表示する。"""
    assert display.postal_code(value) == expected


# trace: FR-026
@pytest.mark.parametrize(("value", "expected"), [(None, "－"), ("", "－"), ([], "－"), (0, 0), ("値", "値")])
def test_unset_filter(value, expected):
    """未設定の値は「－」で表示する。"""
    assert display.unset(value) == expected


# trace: NFR-SC-04
def test_field_errors_filter():
    """項目ごとの入力エラー理由を取り出す（項目の近傍表示）。"""
    details = [{"field": "email", "reason": "必須です。"}, {"field": "password", "reason": "8文字以上です。"}]

    assert display.field_errors(details, "email") == ["必須です。"]
    assert display.field_errors(details, "full_name") == []
    assert display.field_errors(None, "email") == []


# trace: FR-020
@pytest.mark.django_db
def test_layout_shows_cart_quantity_for_buyer(buyer, stock_unit):
    """共通ヘッダーは購入者のカート合計点数を表示する（UI-06）。"""
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    request = RequestFactory().get("/")
    SessionMiddleware(lambda req: HttpResponse()).process_request(request)
    request.session.save()
    session.login(request, buyer)

    context = layout(request)

    assert context["current_user"].user_id == buyer.user_id
    assert context["is_admin"] is False
    assert context["cart_total_quantity"] == 2


# trace: FR-040
@pytest.mark.django_db
def test_layout_hides_cart_quantity_for_admin(admin_user):
    """管理者にはカートの合計点数を表示しない。"""
    request = RequestFactory().get("/")
    SessionMiddleware(lambda req: HttpResponse()).process_request(request)
    request.session.save()
    session.login(request, admin_user)

    context = layout(request)

    assert context["is_admin"] is True
    assert context["cart_total_quantity"] == 0


# trace: FR-026
@pytest.mark.django_db
def test_layout_pops_flash_message():
    """共通レイアウトは完了メッセージを1回だけ渡す。"""
    request = RequestFactory().get("/")
    SessionMiddleware(lambda req: HttpResponse()).process_request(request)
    request.session.save()
    session.set_flash(request, "保存しました。")

    assert layout(request)["flash_message"] == "保存しました。"
    assert layout(request)["flash_message"] is None
