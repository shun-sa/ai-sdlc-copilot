# trace: FR-060, NFR-SC-04, ADDR-002, ADDR-008, ADDR-010, FILE-001
"""初期データ一括投入コマンド（FR-060）の結合試験。

期待結果は機能要件定義書 6.26（入力の条件・処理手順・例外 E-060-04/E-060-05、手順9 の全削除）と
ADDR-010（定義ファイルの構造）・ADDR-008（パスワードの保持方法）・
ADDR-002 DD-009〜DD-011（全削除時の認証トークン・ログインセッションの扱い）、
非機能要件定義書 NFR-SC-04（定義ファイルも外部入力として検証する）から導出する。
"""
import json
from io import StringIO

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client

from shop.models import (
    AuditEventType,
    AuditLog,
    AuthToken,
    Collection,
    Coupon,
    Item,
    ItemCollection,
    PurchaseOrder,
    Role,
    StockUnit,
    Supplier,
    User,
)
from tests.integration import _helpers

pytestmark = pytest.mark.django_db

DEFINITION = {
    "users": [
        {
            "email": " Buyer@Example.com ",
            "password": _helpers.TEST_PASSWORD,
            "full_name": "山田 太郎",
            "role": "buyer",
        },
        {
            "email": "admin@example.com",
            "password": _helpers.TEST_PASSWORD,
            "full_name": "管理 太郎",
            "role": "admin",
        },
    ],
    "suppliers": [{"supplier_code": "SUP-001", "name": "サンプル商事（架空）"}],
    "collections": [{"collection_code": "kitchen", "name": "キッチン", "sort_order": 10}],
    "items": [
        {
            "item_code": "ITEM-001",
            "name": "マグカップ",
            "description": "説明",
            "is_public": True,
            "collection_codes": ["kitchen"],
            "created_at": "2027-03-01T10:00:00+09:00",
        }
    ],
    "stock_units": [
        {
            "sku": "SKU-001",
            "item_code": "ITEM-001",
            "supplier_code": "SUP-001",
            "variant_name": "白",
            "price": 1000,
            "quantity": 10,
        }
    ],
    "coupons": [
        {
            "code": "SAVE500",
            "name": "500円割引",
            "discount_type": "fixed",
            "discount_value": 500,
            "min_spend": 3000,
            "valid_from": "2027-04-01T00:00:00+09:00",
            "valid_until": "2027-04-30T23:59:59+09:00",
        }
    ],
}


# trace: FR-060
def _definition_file(tmp_path, data):
    """定義ファイル（UTF-8 の JSON）を書き出してパスを返す。"""
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: FR-060
def _run(path):
    """初期データ一括投入コマンドを実行し、終了コードを返す。"""
    out, err = StringIO(), StringIO()
    try:
        call_command("load_initial_data", path, stdout=out, stderr=err)
    except SystemExit as exit_code:
        return int(exit_code.code), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# trace: FR-060
def _named_definition_file(tmp_path, data, name):
    """名前を指定して定義ファイル（UTF-8 の JSON）を書き出し、パスを返す。"""
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: FR-060
def _run_with_reset(path):
    """全削除指定（--reset）つきで初期データ一括投入コマンドを実行する（FR-060 手順9）。"""
    out, err = StringIO(), StringIO()
    try:
        call_command("load_initial_data", path, "--reset", stdout=out, stderr=err)
    except SystemExit as exit_code:
        return int(exit_code.code), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# trace: FR-060, ADDR-008, ADDR-010
@pytest.mark.case("IT-AI-054")
def test_initial_data_load_registers_all_data_with_hashed_password(tmp_path):
    """定義ファイルの各データが登録され、パスワードはハッシュで保持される（FR-060 手順8〜12）。"""
    path = _definition_file(tmp_path, DEFINITION)

    exit_code, stdout, _stderr = _run(path)

    assert exit_code == 0
    assert User.objects.count() == 2
    assert Supplier.objects.count() == 1
    assert Collection.objects.count() == 1
    assert Item.objects.count() == 1
    assert ItemCollection.objects.count() == 1
    assert StockUnit.objects.count() == 1
    assert Coupon.objects.count() == 1

    buyer = User.objects.get(email="buyer@example.com")
    assert buyer.role == Role.BUYER
    assert buyer.password_hash != _helpers.TEST_PASSWORD
    assert buyer.password_hash.startswith("pbkdf2_sha256$")
    assert User.objects.filter(role=Role.ADMIN).count() == 1

    unit = StockUnit.objects.get()
    assert unit.sku == "SKU-001"
    assert unit.item.item_code == "ITEM-001"
    assert unit.supplier.supplier_code == "SUP-001"
    assert unit.price == 1000

    audit = AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD)
    assert audit.result == "success"
    assert "利用者=2" in audit.detail
    assert "在庫単位=1" in audit.detail
    assert _helpers.TEST_PASSWORD not in (audit.detail or "")
    assert "利用者: 2 件" in stdout


# trace: FR-060, ADDR-010
@pytest.mark.case("IT-AI-GF-008")
def test_initial_data_load_rolls_back_all_rows_on_violation(tmp_path):
    """違反を1件含む定義ファイルでは1件も投入せず異常終了する（E-060-04、CMN-21）。"""
    invalid = json.loads(json.dumps(DEFINITION))
    invalid["coupons"][0]["discount_type"] = "unknown"
    path = _definition_file(tmp_path, invalid)

    exit_code, _stdout, stderr = _run(path)

    assert exit_code != 0
    assert User.objects.count() == 0
    assert Supplier.objects.count() == 0
    assert Collection.objects.count() == 0
    assert Item.objects.count() == 0
    assert StockUnit.objects.count() == 0
    assert Coupon.objects.count() == 0

    assert "クーポン" in stderr
    assert "discount_type" in stderr
    assert _helpers.TEST_PASSWORD not in stderr

    audit = AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD)
    assert audit.result == "failure"


# trace: FR-060, NFR-SC-04, ADDR-010
@pytest.mark.case("IT-AI-GF-018")
def test_initial_data_definition_file_handles_injection_strings(tmp_path):
    """定義ファイルの攻撃文字列は値域違反か文字列として扱われ、SQL として実行されない（NFR-SC-04、VUL-04）。"""
    invalid = json.loads(json.dumps(DEFINITION))
    invalid["suppliers"][0]["supplier_code"] = "SUP'; DROP TABLE item; --"
    invalid["collections"][0]["collection_code"] = "kitchen'; DELETE FROM stock_unit; --"

    exit_code, _stdout, stderr = _run(_named_definition_file(tmp_path, invalid, "attack.json"))

    assert exit_code != 0
    assert "supplier_code" in stderr
    assert "collection_code" in stderr
    assert User.objects.count() == 0
    assert Supplier.objects.count() == 0
    assert Collection.objects.count() == 0
    assert Item.objects.count() == 0
    assert StockUnit.objects.count() == 0

    literal = json.loads(json.dumps(DEFINITION))
    literal["users"][0]["full_name"] = "$(id) 太郎"
    literal["suppliers"][0]["name"] = "`id` 商事"
    literal["items"][0]["name"] = "' OR '1'='1 マグカップ"
    literal["items"][0]["description"] = "'; DROP TABLE item; --"

    exit_code, _stdout, _stderr = _run(_named_definition_file(tmp_path, literal, "literal.json"))

    assert exit_code == 0
    assert User.objects.get(email="buyer@example.com").full_name == "$(id) 太郎"
    assert Supplier.objects.get().name == "`id` 商事"
    stored = Item.objects.get()
    assert stored.name == "' OR '1'='1 マグカップ"
    assert stored.description == "'; DROP TABLE item; --"
    assert StockUnit.objects.count() == 1


# trace: FR-060, ADDR-002
@pytest.mark.case("IT-AI-GF-019")
def test_reset_invalidates_tokens_and_login_sessions(tmp_path):
    """全削除指定の実行後は旧トークン・旧ログインセッションが拒否される（FR-060 手順9、ADDR-002）。"""
    exit_code, _stdout, _stderr = _run(_named_definition_file(tmp_path, DEFINITION, "before.json"))
    assert exit_code == 0

    api = _helpers.ApiClient(Client())
    token = api.login("buyer@example.com")
    assert api.get("/api/auth/me", token=token).status_code == 200

    screen = Client()
    login_response = screen.post(
        "/login", {"email": "buyer@example.com", "password": _helpers.TEST_PASSWORD}
    )
    assert login_response.status_code == 302, login_response.content
    assert screen.get("/cart").status_code == 200
    assert AuthToken.objects.count() == 1
    assert Session.objects.count() == 1
    audit_before = AuditLog.objects.count()

    replacement = json.loads(json.dumps(DEFINITION))
    replacement["users"][0]["email"] = "other-buyer@example.com"
    exit_code, _stdout, _stderr = _run_with_reset(
        _named_definition_file(tmp_path, replacement, "after.json")
    )

    assert exit_code == 0
    assert User.objects.filter(email="buyer@example.com").count() == 0
    assert User.objects.filter(email="other-buyer@example.com").count() == 1
    assert PurchaseOrder.objects.count() == 0
    # 削除した利用者の認証トークンとログインセッションは、投入と同一トランザクションで消える。
    assert AuthToken.objects.count() == 0
    assert Session.objects.count() == 0
    # 監査ログは全削除指定でも削除しない（ADDR-002 DD-011）。
    assert AuditLog.objects.count() == audit_before + 1

    unauthorized = api.get("/api/auth/me", token=token)
    assert unauthorized.status_code == 401
    assert _helpers.error_code(unauthorized) == "AUTHENTICATION_REQUIRED"

    redirected = screen.get("/cart")
    assert redirected.status_code == 302
    assert redirected.headers["Location"].startswith("/login")
