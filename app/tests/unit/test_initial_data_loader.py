# trace: FR-060, NFR-SC-01, NFR-SC-04, NFR-SC-06, NFR-SC-15, NFR-SC-23, NFR-EN-04
# trace: ADDR-002, ADDR-003, ADDR-004, ADDR-009, ADDR-010
"""初期データ一括投入（FR-060：initial_data.loader と管理コマンド load_initial_data）の単体テスト。

期待値は functional_requirements.md 6.26（入力の値域・一意性・参照整合性、処理手順1〜12、例外 E-060-01〜06、事後条件）、
NFR-SC-01（平文で保持しない）、NFR-SC-06（結果通知に値を出さない）、NFR-SC-23（監査ログを削除しない）、
NFR-EN-04（UTF-8 の定義ファイル）、ADDR-002 DD-006、ADDR-003 DD-002、ADDR-009・ADDR-010 から導出する。
DB Test Strategy：CONTAINER（一括登録・削除・一意制約・トランザクションのロールバックを含めて検証）。
障害の経路は DB 例外を差し込む（MOCK）。アドバイザリロックによる排他（複数プロセスの同時実行）は単体テストでは扱わず、
結合テスト工程（ADDR-011 DD-010：transaction=True の同時実行試験）で確認する。
"""

import io
import json
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, IntegrityError

from accounts.models import ApiLoginState, User
from audit.models import AuditLog
from carts.models import Cart, CartItem
from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
from initial_data import loader
from initial_data.management.commands.load_initial_data import Command
from orders.models import Order, OrderStatusHistory, PaymentRecord
from promotions.models import Coupon
from tests.unit.conftest import jst

pytestmark = pytest.mark.django_db
STARTED = jst(2027, 4, 1, 9, 0, 0)
ADMIN_PASSWORD = "AdminPass1"


# trace: FR-060
def _document(**overrides):
    document = {
        "users": [
            {"email": "  Admin@Example.TEST ", "password": ADMIN_PASSWORD, "name": " 管理 一郎 ", "user_type": "admin"},
        ],
        "suppliers": [{"supplier_code": "SUP-01", "name": "仕入先A"}],
        "categories": [
            {"category_code": "kitchen", "name": "キッチン", "display_order": 2},
            {"category_code": "mug", "name": "マグ", "parent_category_code": "kitchen"},
            {"category_code": "mug-large", "name": "大きいマグ", "parent_category_code": "mug"},
        ],
        "products": [
            {
                "product_code": "MUG-001",
                "name": "マグカップ",
                "description": "陶器",
                "visibility": "public",
                "category_codes": ["mug", "kitchen"],
                "registered_at": "2027-03-01T10:00:00+09:00",
            },
            {"product_code": "HIDDEN-1", "name": "非公開品", "visibility": "private"},
        ],
        "stock_units": [
            {
                "sku": "MUG-001-BL",
                "product_code": "MUG-001",
                "supplier_code": "SUP-01",
                "variant_name": "青",
                "price_excluding_tax": 1200,
                "stock_quantity": 10,
            }
        ],
        "coupons": [
            {
                "coupon_code": "SPRING",
                "name": "春",
                "discount_type": "percentage",
                "discount_value": 10,
                "valid_from": "2027-04-01T00:00:00",
                "valid_to": "2027-04-30T23:59:59+09:00",
            }
        ],
    }
    document.update(overrides)
    return document


# trace: FR-060
def _write(tmp_path, document, *, raw: bytes | None = None, name: str = "data.json"):
    path = tmp_path / name
    path.write_bytes(raw if raw is not None else json.dumps(document).encode("utf-8"))
    return str(path)


# trace: FR-060
def _violations(error):
    return [(v.data, v.row, v.field_key, v.reason) for v in error.violations]


# trace: FR-060
def _run_command(*args):
    out, err = io.StringIO(), io.StringIO()
    try:
        call_command("load_initial_data", *args, stdout=out, stderr=err)
        code = 0
    except CommandError as exc:
        code = exc.returncode
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# 正常終了（手順2〜12）
# ---------------------------------------------------------------------------


# trace: FR-060, NFR-SC-01, NFR-SC-15, ADDR-003, ADDR-009
def test_load_registers_all_data_in_file_order_with_defaults(tmp_path):
    result = loader.run_load(_write(tmp_path, _document()), False, STARTED)
    assert result.counts == {
        "users": 1,
        "suppliers": 1,
        "categories": 3,
        "products": 2,
        "product_categories": 2,
        "stock_units": 1,
        "coupons": 1,
    }
    admin = User.objects.get()
    assert (admin.email, admin.name, admin.user_type, admin.registered_at) == (
        "admin@example.test",
        "管理 一郎",
        "admin",
        STARTED,
    )
    assert admin.password.startswith("pbkdf2_sha256_sha256hex$") and ADMIN_PASSWORD not in admin.password
    assert admin.check_password(ADMIN_PASSWORD)  # 記載したパスワードでログインできる
    depths = dict(Category.objects.values_list("category_code", "depth"))
    assert depths == {"kitchen": 1, "mug": 2, "mug-large": 3}
    assert Category.objects.get(category_code="kitchen").display_order == 2
    assert Category.objects.get(category_code="mug").display_order == 0  # 省略時0
    mug = Product.objects.get(product_code="MUG-001")
    assert mug.is_public and mug.registered_at == jst(2027, 3, 1, 10, 0, 0)
    hidden = Product.objects.get(product_code="HIDDEN-1")
    assert not hidden.is_public and hidden.description == "" and hidden.registered_at == STARTED
    assert list(
        ProductCategory.objects.filter(product=mug).order_by("pk").values_list("category__category_code", flat=True)
    ) == ["mug", "kitchen"]
    unit = StockUnit.objects.get()
    assert (unit.price_excluding_tax, unit.stock_quantity, unit.updated_at) == (1200, 10, STARTED)
    coupon = Coupon.objects.get()
    assert coupon.minimum_purchase_amount == 0  # 省略時0
    assert coupon.valid_from == jst(2027, 4, 1) and coupon.valid_to == jst(2027, 4, 30, 23, 59, 59)
    log = AuditLog.objects.get()
    assert (log.event_type, log.result, log.target_user_id, log.occurred_at) == (
        "initial_data_load",
        "success",
        None,
        STARTED,
    )
    assert json.loads(log.detail) == result.counts
    assert "admin@example.test" not in log.detail and ADMIN_PASSWORD not in log.detail


# trace: FR-060, NFR-EN-04
def test_load_accepts_utf8_with_bom_and_missing_data_as_zero_rows(tmp_path):
    raw = b"\xef\xbb\xbf" + json.dumps({"suppliers": [{"supplier_code": "S-1", "name": "日本語の名前"}]}).encode()
    result = loader.run_load(_write(tmp_path, None, raw=raw), False, STARTED)
    assert result.counts["suppliers"] == 1 and result.counts["users"] == 0
    assert Supplier.objects.get().name == "日本語の名前"


# trace: FR-060
def test_load_without_reset_can_reference_registered_data(tmp_path):
    loader.run_load(_write(tmp_path, _document()), False, STARTED)
    addition = {
        "categories": [{"category_code": "child", "name": "子", "parent_category_code": "mug"}],
        "products": [{"product_code": "NEW-1", "name": "新商品", "category_codes": ["mug-large"]}],
        "stock_units": [
            {
                "sku": "NEW-1-A",
                "product_code": "MUG-001",
                "supplier_code": "SUP-01",
                "variant_name": "A",
                "price_excluding_tax": 0,
                "stock_quantity": 0,
            }
        ],
    }
    loader.run_load(_write(tmp_path, addition, name="add.json"), False, STARTED)
    assert Category.objects.get(category_code="child").depth == 3
    assert StockUnit.objects.count() == 2 and Product.objects.count() == 3


# trace: FR-060, ADDR-002, NFR-SC-23
def test_reset_deletes_all_business_data_and_login_states_but_keeps_audit_logs(
    tmp_path, buyer, catalog, make_order, make_cart, bearer, login_web
):
    unit = catalog.stock_unit()
    order = make_order(buyer, [(unit, 1)])
    PaymentRecord.objects.create(order=order, result="declined", amount=1, processed_at=STARTED)
    make_cart(buyer, [(unit, 1)])
    bearer(buyer)
    login_web(buyer)
    from audit import services as audit

    audit.record_logout(buyer.pk, STARTED)
    loader.run_load(_write(tmp_path, _document()), True, STARTED)
    for model in (Order, OrderStatusHistory, PaymentRecord, Cart, CartItem, ApiLoginState, Session):
        assert not model.objects.exists(), model.__name__
    assert not User.objects.filter(pk=buyer.pk).exists()
    assert User.objects.count() == 1 and Supplier.objects.count() == 1 and StockUnit.objects.count() == 1
    assert list(AuditLog.objects.order_by("pk").values_list("event_type", flat=True)) == ["logout", "initial_data_load"]


# trace: FR-060
def test_reset_rerun_produces_same_state(tmp_path):
    path = _write(tmp_path, _document(users=[]))
    loader.run_load(path, True, STARTED)
    first = sorted(StockUnit.objects.values_list("sku", "price_excluding_tax"))
    loader.run_load(path, True, STARTED)
    assert sorted(StockUnit.objects.values_list("sku", "price_excluding_tax")) == first
    assert Supplier.objects.count() == 1 and AuditLog.objects.count() == 2


# ---------------------------------------------------------------------------
# 読込み・記載形式（E-060-02・E-060-03）
# ---------------------------------------------------------------------------


# trace: FR-060
def test_missing_file_is_e_060_02(tmp_path):
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(str(tmp_path / "nothing.json"), False, STARTED)
    assert info.value.code == "E-060-02" and "nothing.json" in info.value.message


# trace: FR-060, NFR-EN-04
@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ('{"suppliers": [{"supplier_code": "S", "name": "日本"}]}'.encode("cp932"), "文字コードの誤り"),
        (b"{not json", "記載形式の誤り"),
        (b'{"suppliers": [], "suppliers": []}', "記載形式の誤り"),
        (b'{"stock_units": [{"price_excluding_tax": NaN}]}', "記載形式の誤り"),
        (b"[]", "記載形式の誤り"),
        (b'{"unknown": []}', "記載形式の誤り"),
        (b'{"users": {}}', "記載形式の誤り"),
        (b'{"users": [1]}', "記載形式の誤り"),
        (b'{"users": [{"email": "a@b.c", "nickname": "x"}]}', "記載形式の誤り"),
        (b"[" * 100000 + b"]" * 100000, "記載形式の誤り"),
    ],
    ids=[
        "cp932",
        "broken",
        "dup-key",
        "nan",
        "array",
        "unknown-data",
        "not-array",
        "row-not-object",
        "unknown-column",
        "deep",
    ],
)
def test_unparseable_files_are_e_060_03(tmp_path, raw, reason):
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, None, raw=raw), False, STARTED)
    assert info.value.code == "E-060-03" and reason in info.value.message


# ---------------------------------------------------------------------------
# 値域（E-060-04）
# ---------------------------------------------------------------------------


# trace: FR-060, NFR-SC-04, NFR-SC-06
def test_value_violations_are_collected_for_all_rows_and_items_without_values(tmp_path):
    document = _document(
        users=[
            {"email": "bad-email", "password": "short1", "name": "", "user_type": "owner"},
            {"email": "ok@example.test", "password": "OK@EXAMPLE.TEST1", "name": "名" * 51, "user_type": "buyer"},
        ],
        suppliers=[{"supplier_code": "sup-lower", "name": "x"}],
    )
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, document), True, STARTED)
    error = info.value
    assert error.code == "E-060-04"
    found = [(d, r, f) for d, r, f, _ in _violations(error)]
    assert found == [
        ("users", 1, "email"),
        ("users", 1, "password"),
        ("users", 1, "name"),
        ("users", 1, "user_type"),
        ("users", 2, "name"),
        ("suppliers", 1, "supplier_code"),
        ("stock_units", 1, "supplier_code"),  # 値域違反の仕入先は参照先として存在しない（E-060-05 もまとめて示す）
    ]
    text = "\n".join(v.text() for v in error.violations)
    assert "bad-email" not in text and "short1" not in text and "sup-lower" not in text
    assert "利用者 1行目 メールアドレス（email）" in text
    assert User.objects.count() == 0 and Supplier.objects.count() == 0  # 削除指定があっても何も変えない


# trace: FR-060, NFR-SC-04
@pytest.mark.parametrize(
    ("data", "row", "field", "ok"),
    [
        ("stock_units", {"price_excluding_tax": 0}, "price_excluding_tax", True),
        ("stock_units", {"price_excluding_tax": 9_999_999}, "price_excluding_tax", True),
        ("stock_units", {"price_excluding_tax": -1}, "price_excluding_tax", False),
        ("stock_units", {"price_excluding_tax": 10_000_000}, "price_excluding_tax", False),
        ("stock_units", {"price_excluding_tax": "100"}, "price_excluding_tax", False),
        ("stock_units", {"price_excluding_tax": True}, "price_excluding_tax", False),
        ("stock_units", {"price_excluding_tax": 1.5}, "price_excluding_tax", False),
        ("stock_units", {"stock_quantity": 99_999}, "stock_quantity", True),
        ("stock_units", {"stock_quantity": 100_000}, "stock_quantity", False),
        ("stock_units", {"sku": "S" * 32}, "sku", True),
        ("stock_units", {"sku": "S" * 33}, "sku", False),
        ("stock_units", {"sku": "sku-lower"}, "sku", False),
        ("stock_units", {"variant_name": ""}, "variant_name", False),
        ("stock_units", {"variant_name": 5}, "variant_name", False),
        ("stock_units", {"variant_name": "a\x00"}, "variant_name", False),
        ("coupons", {"discount_value": 100}, "discount_value", True),
        ("coupons", {"discount_value": 101}, "discount_value", False),
        ("coupons", {"discount_value": 0}, "discount_value", False),
        ("coupons", {"discount_type": "fixed_amount", "discount_value": 9_999_999}, "discount_value", True),
        ("coupons", {"discount_type": "fixed_amount", "discount_value": 10_000_000}, "discount_value", False),
        ("coupons", {"discount_type": "free"}, "discount_type", False),
        ("coupons", {"minimum_purchase_amount": 9_999_999}, "minimum_purchase_amount", True),
        ("coupons", {"minimum_purchase_amount": -1}, "minimum_purchase_amount", False),
        ("coupons", {"valid_from": "2027-04-30T23:59:59", "valid_to": "2027-04-30T23:59:59"}, "valid_from", True),
        ("coupons", {"valid_from": "2027-05-01T00:00:00"}, "valid_from", False),
        ("coupons", {"valid_from": "2027-04-01 00:00:00"}, "valid_from", False),
        ("coupons", {"valid_from": "2027-02-30T00:00:00"}, "valid_from", False),
        ("coupons", {"valid_from": "2027-04-01T00:00:00+00:00"}, "valid_from", False),
        ("coupons", {"valid_from": "0001-01-01T00:00:00"}, "valid_from", False),
        ("coupons", {"valid_to": 20270430}, "valid_to", False),
        ("coupons", {"name": "名" * 50}, "name", True),
        ("coupons", {"name": "名" * 51}, "name", False),
        ("categories", {"display_order": 999}, "display_order", True),
        ("categories", {"display_order": 1000}, "display_order", False),
        ("categories", {"category_code": "UPPER"}, "category_code", False),
        ("products", {"visibility": "hidden"}, "visibility", False),
        ("products", {"visibility": 1}, "visibility", False),
        ("products", {"description": "説" * 2000}, "description", True),
        ("products", {"description": "説" * 2001}, "description", False),
        ("products", {"category_codes": "kitchen"}, "category_codes", False),
        ("products", {"category_codes": ["Kitchen"]}, "category_codes", False),
        ("products", {"category_codes": [1]}, "category_codes", False),
        ("products", {"registered_at": "yesterday"}, "registered_at", False),
        ("users", {"user_type": None}, "user_type", False),
        ("users", {"email": None}, "email", False),
        ("users", {"email": 5}, "email", False),
        ("users", {"email": "a@b\x00"}, "email", False),
        ("users", {"email": "a" * 250 + "@b.cd"}, "email", False),
        ("users", {"password": None}, "password", False),
        ("users", {"password": 12345678}, "password", False),
        ("users", {"password": "Passw0rd\ud800"}, "password", False),
        ("users", {"password": " Spaced1 "}, "password", True),
        ("users", {"name": None}, "name", False),
        ("users", {"name": 1}, "name", False),
        ("users", {"name": "a\x00"}, "name", False),
        ("suppliers", {"name": None}, "name", False),
    ],
)
def test_value_range_rules(tmp_path, data, row, field, ok):
    document = _document() if data == "users" else _document(users=[])
    document[data][0] = {**document[data][0], **row}
    if ok:
        loader.run_load(_write(tmp_path, document), False, STARTED)
    else:
        with pytest.raises(loader.LoadError) as info:
            loader.run_load(_write(tmp_path, document), False, STARTED)
        assert info.value.code == "E-060-04"
        assert (data, 1, field) in [(d, r, f) for d, r, f, _ in _violations(info.value)]
        assert AuditLog.objects.count() == 0  # 失敗の監査ログは呼出し側（管理コマンド）が記録する


# trace: FR-060, ADDR-003
def test_user_password_with_spaces_is_stored_as_written(tmp_path):
    document = _document(
        users=[{"email": "s@example.test", "password": " Spaced1 ", "name": "s", "user_type": "buyer"}]
    )
    loader.run_load(_write(tmp_path, document), False, STARTED)
    user = User.objects.get()
    assert user.check_password(" Spaced1 ") and not user.check_password("Spaced1")


# ---------------------------------------------------------------------------
# 一意性・参照整合性（E-060-05）
# ---------------------------------------------------------------------------


# trace: FR-060
def test_integrity_violations_report_second_and_later_duplicates_and_missing_references(tmp_path):
    document = _document(
        suppliers=[
            {"supplier_code": "SUP-01", "name": "A"},
            {"supplier_code": "SUP-01", "name": "B"},
            {"supplier_code": "SUP-01", "name": "C"},
        ],
        categories=[
            {"category_code": "a", "name": "同名"},
            {"category_code": "b", "name": "同名"},
            {"category_code": "c", "name": "子", "parent_category_code": "nope"},
        ],
        products=[
            {"product_code": "P-1", "name": "p", "category_codes": ["a", "a"]},
            {"product_code": "P-2", "name": "q", "category_codes": ["zz"]},
        ],
        stock_units=[
            {
                "sku": "X-1",
                "product_code": "NOPE",
                "supplier_code": "NOPE",
                "variant_name": "v",
                "price_excluding_tax": 1,
                "stock_quantity": 1,
            }
        ],
    )
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, document), False, STARTED)
    assert info.value.code == "E-060-05"
    assert _violations(info.value) == [
        ("suppliers", 2, "supplier_code", loader.R_DUP_FILE),
        ("suppliers", 3, "supplier_code", loader.R_DUP_FILE),
        ("categories", 2, "name", loader.R_DUP_NAME),
        ("categories", 3, "parent_category_code", loader.R_MISSING_REF),
        ("products", 1, "category_codes", loader.R_DUP_CATEGORY),
        ("products", 2, "category_codes", loader.R_MISSING_REF),
        ("stock_units", 1, "product_code", loader.R_MISSING_REF),
        ("stock_units", 1, "supplier_code", loader.R_MISSING_REF),
    ]
    assert Supplier.objects.count() == 0


# trace: FR-060
def test_duplicates_with_registered_data_only_without_reset(tmp_path):
    path = _write(tmp_path, _document(users=[]))
    loader.run_load(path, False, STARTED)
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(path, False, STARTED)  # 同じ定義ファイルの再実行は全行が業務キーの重複
    assert info.value.code == "E-060-05"
    keys = {(d, f) for d, _r, f, reason in _violations(info.value) if reason == loader.R_DUP_DB}
    assert keys == {
        ("suppliers", "supplier_code"),
        ("categories", "category_code"),
        ("products", "product_code"),
        ("stock_units", "sku"),
        ("coupons", "coupon_code"),
    }
    assert Supplier.objects.count() == 1
    loader.run_load(path, True, STARTED)  # 削除指定ありなら重複としない


# trace: FR-060
def test_category_name_duplicate_with_registered_sibling(tmp_path):
    loader.run_load(_write(tmp_path, _document(users=[])), True, STARTED)
    document = {
        "categories": [
            {"category_code": "other-top", "name": "キッチン"},
            {"category_code": "other-child", "name": "マグ", "parent_category_code": "kitchen"},
            {"category_code": "ok-child", "name": "マグ", "parent_category_code": "mug"},
        ]
    }
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, document, name="b.json"), False, STARTED)
    assert [(r, f) for _d, r, f, _ in _violations(info.value)] == [(1, "name"), (2, "name")]


# trace: FR-060
def test_category_depth_over_3_and_cycles_are_violations(tmp_path):
    document = {
        "categories": [
            {"category_code": "l1", "name": "1"},
            {"category_code": "l2", "name": "2", "parent_category_code": "l1"},
            {"category_code": "l3", "name": "3", "parent_category_code": "l2"},
            {"category_code": "l4", "name": "4", "parent_category_code": "l3"},
            {"category_code": "x", "name": "x", "parent_category_code": "y"},
            {"category_code": "y", "name": "y", "parent_category_code": "x"},
        ]
    }
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, document), False, STARTED)
    assert _violations(info.value) == [
        ("categories", 4, "parent_category_code", loader.R_TOO_DEEP),
        ("categories", 5, "parent_category_code", loader.R_CYCLE),
        ("categories", 6, "parent_category_code", loader.R_CYCLE),
    ]


# trace: FR-060
def test_value_and_integrity_violations_are_reported_together(tmp_path):
    document = _document(
        users=[],
        suppliers=[{"supplier_code": "SUP-01", "name": ""}, {"supplier_code": "SUP-01", "name": "B"}],
    )
    with pytest.raises(loader.LoadError) as info:
        loader.run_load(_write(tmp_path, document), False, STARTED)
    assert info.value.code == "E-060-04"
    assert {v.kind for v in info.value.violations} == {"value", "integrity"}


# ---------------------------------------------------------------------------
# システム障害（E-060-06）・同時登録の競合
# ---------------------------------------------------------------------------


# trace: FR-060, ADDR-004
def test_database_failure_rolls_back_everything(tmp_path, catalog):
    existing = catalog.supplier("KEEP-1")
    with mock.patch.object(StockUnit.objects, "bulk_create", side_effect=DatabaseError("x")):
        with pytest.raises(loader.LoadError) as info:
            loader.run_load(_write(tmp_path, _document(users=[])), True, STARTED)
    assert info.value.code == "E-060-06"
    assert list(Supplier.objects.values_list("pk", flat=True)) == [existing.pk]  # 削除も取り消す
    assert not AuditLog.objects.exists()


# trace: FR-060, ADDR-004
def test_concurrent_registration_conflict_becomes_e_060_05(tmp_path, make_user):
    document = _document()

    def register_then_conflict(objs):
        make_user("admin@example.test")
        raise IntegrityError("duplicate key")

    with mock.patch.object(User.objects, "bulk_create", side_effect=register_then_conflict):
        with pytest.raises(loader.LoadError) as info:
            loader.run_load(_write(tmp_path, document), False, STARTED)
    assert info.value.code == "E-060-05"


# trace: FR-060
def test_concurrent_conflicts_lists_emails_already_registered(make_user):
    make_user("taken@example.test")
    parsed = loader.check_values(
        {
            "users": [
                {"email": "taken@example.test", "password": "Passw0rd", "name": "a", "user_type": "buyer"},
                {"email": "free@example.test", "password": "Passw0rd", "name": "b", "user_type": "buyer"},
            ],
            "suppliers": [],
            "categories": [],
            "products": [],
            "stock_units": [],
            "coupons": [],
        },
        STARTED,
    )
    assert [(v.row, v.reason) for v in loader._concurrent_conflicts(parsed)] == [(1, loader.R_DUP_DB)]
    with mock.patch.object(User.objects, "filter", side_effect=DatabaseError("x")):
        assert loader._concurrent_conflicts(parsed) == []


# trace: FR-060, ADDR-004
def test_record_failure_writes_one_failure_audit_log_and_tolerates_db_error():
    loader.record_failure(STARTED)
    log = AuditLog.objects.get()
    assert (log.event_type, log.result, log.target_user_id) == ("initial_data_load", "failure", None)
    assert json.loads(log.detail) == loader.zero_counts()
    with mock.patch("audit.services.record_initial_data_load", side_effect=DatabaseError("x")):
        loader.record_failure(STARTED)  # 記録できない障害の場合は記録しない（例外にしない）
    assert AuditLog.objects.count() == 1


# ---------------------------------------------------------------------------
# 管理コマンド（手順1・12、E-060-01、通知、LOG-05）
# ---------------------------------------------------------------------------


# trace: FR-060, NFR-SC-06
def test_command_success_prints_counts_without_personal_values(tmp_path, app_logs):
    code, out, err = _run_command(_write(tmp_path, _document()))
    assert code == 0 and err == ""
    assert "初期データ一括投入が成功しました。" in out
    assert "利用者 1件、仕入先 1件、商品分類 3件、商品 2件、商品分類所属 2件、在庫単位 1件、クーポン 1件" in out
    assert ADMIN_PASSWORD not in out and "admin@example.test" not in out and "管理 一郎" not in out
    job = [r for r in app_logs.records() if r["log_type"] == "LOG-05"][-1]
    assert job["result"] == "success" and job["counts"]["users"] == 1


# trace: FR-060, NFR-SC-06
def test_command_failure_lists_violations_and_records_failure_audit(tmp_path, app_logs):
    document = _document(users=[{"email": "x", "password": "secretpw", "name": "氏名値", "user_type": "buyer"}])
    code, out, err = _run_command(_write(tmp_path, document))
    assert code == 1
    assert "初期データ一括投入は失敗しました。何も投入していません。" in err
    assert "違反（" in err and "利用者 1行目 メールアドレス（email）" in err
    assert "secretpw" not in err and "氏名値" not in err
    assert AuditLog.objects.get().result == "failure"
    job = [r for r in app_logs.records() if r["log_type"] == "LOG-05"][-1]
    assert job["result"] == "failure" and job["violations"][0]["data"] == "利用者"
    assert "secretpw" not in json.dumps(job, ensure_ascii=False)


# trace: FR-060
@pytest.mark.parametrize("args", [(), ("a.json", "b.json")])
def test_command_requires_exactly_one_file(args):
    code, _out, err = _run_command(*args)
    assert code == 1 and "実行時の指定が誤っています" in err
    assert AuditLog.objects.get().result == "failure"


# trace: FR-060
@pytest.mark.parametrize("argv", [["--bogus", "a.json"], ["--res", "a.json"], ["--reset=yes", "a.json"]])
def test_command_rejects_unknown_options_as_e_060_01(argv, capsys):
    command = Command()
    with pytest.raises(SystemExit) as info:
        command.run_from_argv(["manage.py", "load_initial_data", *argv])
    assert info.value.code == 1
    assert "実行時の指定が誤っています" in capsys.readouterr().err
    assert AuditLog.objects.get().result == "failure"


# trace: FR-060
def test_command_reset_option_is_accepted(tmp_path, catalog):
    catalog.supplier("OLD-1")
    code, _out, _err = _run_command(_write(tmp_path, _document(users=[])), "--reset")
    assert code == 0
    assert list(Supplier.objects.values_list("supplier_code", flat=True)) == ["SUP-01"]


# trace: FR-060
def test_violation_order_and_labels():
    violation = loader.Violation("coupons", 3, "unknown_key", "理由", "value")
    assert loader._violation_order(violation) == (5, 3, 99)
    assert violation.text() == "クーポン 3行目 unknown_key（unknown_key）：理由"
    assert violation.as_log()["field"] == "unknown_key（unknown_key）"
    assert loader.counts_text(loader.zero_counts()).startswith("利用者 0件")
    assert STARTED + timedelta(0) == STARTED
