# trace: FR-060, NFR-SC-06, NFR-SC-23, NFR-OM-13, ADDR-004, ADDR-005
"""初期データ一括投入（FR-060）の単体テスト。

期待結果は機能要件 6.26（入力の値域・一意性・参照整合性、違反が1件でもあれば何も登録しない）、
NFR-OM-13（異常終了時は何も削除・投入せず、違反を全件出力し、監査ログへ失敗を1件記録する）、
NFR-SC-06（標準出力へ項目の値を出力しない）、ADDR-004（トップレベルのキーは6種類）、
ADDR-005（値域→一意性→参照整合性の順に全件の違反を収集する）から導出する。
"""

from __future__ import annotations

import json

import pytest
from _helpers import make_collection, make_item, make_supplier, make_user
from accounts.models import EVENT_INITIAL_DATA_LOAD, RESULT_FAILURE, RESULT_SUCCESS, ROLE_ADMIN, AuditLog, User
from carts.models import Coupon
from catalog.models import Collection, Item, ItemCollection, StockUnit, Supplier
from django.core.management import call_command
from django.db import DatabaseError
from orders.models import PurchaseOrder
from seeding import services

pytestmark = pytest.mark.django_db

VALID_DOCUMENT = {
    "users": [
        {
            "email": " Admin@Example.TEST ",
            "password": "passw0rd!",
            "full_name": " 試験 管理者 ",
            "role": "admin",
        },
        {
            "email": "buyer@example.test",
            "password": "passw0rd!",
            "full_name": "試験 購入者",
            "role": "buyer",
        },
    ],
    "suppliers": [{"supplier_code": "SUP-01", "name": "試験仕入先"}],
    "collections": [
        {"collection_code": "root", "name": "ルート", "sort_order": 1},
        {"collection_code": "child", "name": "子", "parent_collection_code": "root"},
    ],
    "items": [
        {
            "item_code": "ITEM-01",
            "name": "試験商品",
            "description": "説明",
            "is_public": True,
            "collection_codes": ["child"],
            "created_at": "2027-04-10T10:00:00+09:00",
        }
    ],
    "stock_units": [
        {
            "sku": "SKU-01",
            "item_code": "ITEM-01",
            "supplier_code": "SUP-01",
            "variant_name": "青",
            "price": 1000,
            "quantity": 10,
        }
    ],
    "coupons": [
        {
            "code": "SAVE-1000",
            "name": "1000円引き",
            "discount_type": "fixed",
            "discount_value": 1000,
            "min_spend": 3000,
            "valid_from": "2027-04-01T00:00:00+09:00",
            "valid_until": "2027-04-30T23:59:59+09:00",
        }
    ],
}


# trace: FR-060
def write_document(tmp_path, document, *, encoding: str = "utf-8", name: str = "initial_data.json") -> str:
    """定義ファイルを一時ディレクトリへ書き出す（テスト補助）。"""
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding=encoding)
    return str(path)


# trace: FR-060
def document(**overrides):
    """既定の正しい定義ファイル内容を複製して一部を差し替える（テスト補助）。"""
    data = json.loads(json.dumps(VALID_DOCUMENT))
    data.update(overrides)
    return data


# trace: FR-060
def test_load_initial_data_registers_every_dataset(tmp_path):
    """FR-060：6種類のデータを登録し、投入件数を返す。"""
    result = services.load_initial_data(write_document(tmp_path, document()), reset=False)

    assert result.counts == {
        "users": 2,
        "suppliers": 1,
        "collections": 2,
        "items": 1,
        "item_collections": 1,
        "stock_units": 1,
        "coupons": 1,
    }
    assert User.objects.count() == 2
    assert Supplier.objects.count() == 1
    assert Collection.objects.count() == 2
    assert Item.objects.count() == 1
    assert ItemCollection.objects.count() == 1
    assert StockUnit.objects.count() == 1
    assert Coupon.objects.count() == 1
    assert "users=2" in result.summary()


# trace: FR-060
def test_load_initial_data_normalizes_and_hashes_user_values(tmp_path):
    """FR-060 6.26.3：メールアドレスは正規化し、パスワードはハッシュ値で保持する。"""
    services.load_initial_data(write_document(tmp_path, document()), reset=False)

    admin = User.objects.get(role=ROLE_ADMIN)
    assert admin.email == "admin@example.test"
    assert admin.full_name == "試験 管理者"
    assert admin.password_hash != "passw0rd!"
    assert admin.registered_at is not None


# trace: FR-060
def test_load_initial_data_computes_collection_depth(tmp_path):
    """FR-060 6.26.3：深さは最上位が1、それ以外は親分類の深さ＋1とする。"""
    services.load_initial_data(write_document(tmp_path, document()), reset=False)

    assert Collection.objects.get(collection_code="root").depth == 1
    child = Collection.objects.get(collection_code="child")
    assert child.depth == 2
    assert child.parent.collection_code == "root"


# trace: NFR-SC-23
def test_load_initial_data_records_success_audit_log(tmp_path):
    """監査ログへ初期データ一括投入の成功を1件記録する。"""
    services.load_initial_data(write_document(tmp_path, document()), reset=False)

    log = AuditLog.objects.get(event_type=EVENT_INITIAL_DATA_LOAD)
    assert log.result == RESULT_SUCCESS
    assert log.user_id is None
    assert "users=2" in log.detail


# trace: FR-060
def test_load_initial_data_uses_defaults_for_optional_fields(tmp_path):
    """FR-060 6.26.3：商品説明0文字・公開・登録日時＝投入時刻・表示順0を既定とする。"""
    data = document(
        items=[{"item_code": "ITEM-02", "name": "既定値の商品"}],
        stock_units=[],
        collections=[{"collection_code": "only", "name": "単独"}],
    )

    services.load_initial_data(write_document(tmp_path, data), reset=False)

    item = Item.objects.get(item_code="ITEM-02")
    assert item.description == ""
    assert item.is_public is True
    assert item.created_at is not None
    assert Collection.objects.get(collection_code="only").sort_order == 0


# trace: FR-060
def test_load_initial_data_accepts_bom_prefixed_utf8(tmp_path):
    """FR-060：BOM付き UTF-8 の定義ファイルを受け付ける。"""
    path = write_document(tmp_path, document(), encoding="utf-8-sig")

    assert services.load_initial_data(path, reset=False).counts["users"] == 2


# trace: NFR-OM-13
def test_reset_deletes_everything_except_audit_logs(tmp_path, buyer):
    """FR-060：全削除指定では監査ログ以外の全データを削除してから投入する。"""
    make_supplier(supplier_code="OLD-SUP")
    make_item(item_code="OLD-ITEM")
    before_logs = AuditLog.objects.count()

    services.load_initial_data(write_document(tmp_path, document()), reset=True)

    assert Supplier.objects.filter(supplier_code="OLD-SUP").count() == 0
    assert Item.objects.filter(item_code="OLD-ITEM").count() == 0
    assert User.objects.filter(pk=buyer.pk).count() == 0
    assert PurchaseOrder.objects.count() == 0
    assert AuditLog.objects.count() == before_logs + 1


# trace: FR-060
def test_existing_business_key_is_a_violation_without_reset(tmp_path):
    """FR-060：全削除指定がない場合、登録済みデータと業務キーが重複する行は違反とする。"""
    make_user(email="buyer@example.test")

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(write_document(tmp_path, document()), reset=False)

    assert error.value.code == services.ERROR_VALUE_RANGE
    assert any(violation.field_name == "email" for violation in error.value.violations)
    assert Supplier.objects.count() == 0


# trace: FR-060
def test_existing_collection_can_be_referenced_as_parent(tmp_path):
    """FR-060：全削除指定がない場合は登録済みの分類を親分類として参照できる。"""
    make_collection(collection_code="existing", name="既存")
    data = document(
        collections=[{"collection_code": "new-child", "name": "新しい子", "parent_collection_code": "existing"}],
        items=[{"item_code": "ITEM-03", "name": "商品", "collection_codes": ["new-child"]}],
        stock_units=[],
    )

    services.load_initial_data(write_document(tmp_path, data), reset=False)

    assert Collection.objects.get(collection_code="new-child").depth == 2


# trace: NFR-OM-13
def test_unreadable_file_is_reported(tmp_path):
    """E-060-02：定義ファイルを読み取れない場合は何も投入しない。"""
    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(str(tmp_path / "missing.json"), reset=False)

    assert error.value.code == services.ERROR_FILE_NOT_READABLE
    assert User.objects.count() == 0


# trace: NFR-OM-13
def test_non_utf8_file_is_reported(tmp_path):
    """E-060-03：UTF-8 として解釈できない定義ファイルは投入しない。"""
    path = tmp_path / "sjis.json"
    path.write_bytes(json.dumps(document(), ensure_ascii=False).encode("shift_jis"))

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(str(path), reset=False)

    assert error.value.code == services.ERROR_FILE_NOT_PARSABLE


# trace: NFR-OM-13
def test_invalid_json_is_reported(tmp_path):
    """E-060-03：JSON として解釈できない定義ファイルは投入しない。"""
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(str(path), reset=False)

    assert error.value.code == services.ERROR_FILE_NOT_PARSABLE


# trace: FR-060, ADDR-004
@pytest.mark.parametrize(
    "content",
    [[], "文字列", 1],
)
def test_top_level_must_be_an_object(content):
    """ADDR-004 INV-001：最上位がオブジェクトでない定義ファイルは解釈できない。"""
    with pytest.raises(services.SeedError) as error:
        services.extract_datasets(content)

    assert error.value.code == services.ERROR_FILE_NOT_PARSABLE


# trace: FR-060, ADDR-004
def test_unknown_top_level_key_is_rejected():
    """ADDR-004 INV-001：トップレベルのキーは6種類に限る。"""
    with pytest.raises(services.SeedError) as error:
        services.extract_datasets({"users": [], "unknown": []})

    assert "unknown" in error.value.message


# trace: FR-060, ADDR-004
def test_dataset_must_be_a_list_of_objects():
    """定義ファイルの各データは行の並び（オブジェクトの配列）とする。"""
    with pytest.raises(services.SeedError):
        services.extract_datasets({"users": {"email": "a@example.test"}})
    with pytest.raises(services.SeedError):
        services.extract_datasets({"users": ["行ではない"]})


# trace: FR-060, ADDR-004
def test_missing_dataset_is_treated_as_empty():
    """省略されたデータは0行として扱う。"""
    datasets = services.extract_datasets({})

    assert set(datasets) == set(services.TOP_LEVEL_KEYS)
    assert all(rows == [] for rows in datasets.values())


# trace: FR-060, ADDR-004
def test_unknown_field_name_is_a_violation():
    """項目名の別名・大文字小文字違い・未知の項目名は値域違反とする。"""
    violations = services.unknown_field_violations(
        {"users": [{"email": "a@example.test", "Email": "a@example.test", "mail": "a@example.test"}]}
    )

    assert {violation.field_name for violation in violations} == {"Email", "mail"}
    assert violations[0].data_name == "users"
    assert violations[0].row_number == 1


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"email": ""}, "email"),
        ({"email": "invalid"}, "email"),
        ({"email": "a" * 250 + "@example.test"}, "email"),
        ({"email": 1}, "email"),
        ({"password": ""}, "password"),
        ({"password": 12345678}, "password"),
        ({"password": "short1"}, "password"),
        ({"full_name": ""}, "full_name"),
        ({"full_name": "あ" * 51}, "full_name"),
        ({"role": "operator"}, "role"),
        ({"role": ""}, "role"),
    ],
)
def test_user_value_range_violations(tmp_path, override, expected_field):
    """FR-060 6.26.3①〜④：利用者の値域違反を検出する。"""
    row = dict(VALID_DOCUMENT["users"][1])
    row.update(override)
    data = document(users=[row], items=[], stock_units=[], collections=[], coupons=[])

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(write_document(tmp_path, data), reset=False)

    assert expected_field in {violation.field_name for violation in error.value.violations}
    assert User.objects.count() == 0


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"supplier_code": "sup-01"}, "supplier_code"),
        ({"supplier_code": "A" * 21}, "supplier_code"),
        ({"supplier_code": ""}, "supplier_code"),
        ({"name": ""}, "name"),
        ({"name": "あ" * 101}, "name"),
    ],
)
def test_supplier_value_range_violations(override, expected_field):
    """FR-060 6.26.3：仕入先コードは英大文字・数字・ハイフン、仕入先名は1〜100文字。"""
    row = dict(VALID_DOCUMENT["suppliers"][0])
    row.update(override)
    violations: list[services.Violation] = []

    services.validate_suppliers([row], violations)

    assert expected_field in {violation.field_name for violation in violations}


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"collection_code": "ROOT"}, "collection_code"),
        ({"collection_code": "a" * 31}, "collection_code"),
        ({"name": "あ" * 51}, "name"),
        ({"parent_collection_code": "INVALID"}, "parent_collection_code"),
        ({"sort_order": 1000}, "sort_order"),
        ({"sort_order": -1}, "sort_order"),
        ({"sort_order": "1"}, "sort_order"),
        ({"sort_order": True}, "sort_order"),
    ],
)
def test_collection_value_range_violations(override, expected_field):
    """FR-060 6.26.3：分類コード・分類名・親分類・表示順の値域を判定する。"""
    row = dict(VALID_DOCUMENT["collections"][0])
    row.update(override)
    violations: list[services.Violation] = []

    services.validate_collections([row], violations)

    assert expected_field in {violation.field_name for violation in violations}


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"item_code": "item-01"}, "item_code"),
        ({"name": ""}, "name"),
        ({"description": "あ" * 2001}, "description"),
        ({"is_public": "true"}, "is_public"),
        ({"collection_codes": "child"}, "collection_codes"),
        ({"collection_codes": ["INVALID"]}, "collection_codes"),
        ({"collection_codes": [1]}, "collection_codes"),
        ({"created_at": "2027-13-01T00:00:00+09:00"}, "created_at"),
        ({"created_at": 20270410}, "created_at"),
    ],
)
def test_item_value_range_violations(override, expected_field):
    """FR-060 6.26.3：商品の値域（コード・名称・説明・公開状態・所属分類・登録日時）を判定する。"""
    row = dict(VALID_DOCUMENT["items"][0])
    row.update(override)
    violations: list[services.Violation] = []

    services.validate_items([row], violations, services.timeutils.now())

    assert expected_field in {violation.field_name for violation in violations}


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"sku": "sku-01"}, "sku"),
        ({"sku": "A" * 33}, "sku"),
        ({"item_code": ""}, "item_code"),
        ({"supplier_code": ""}, "supplier_code"),
        ({"variant_name": "あ" * 51}, "variant_name"),
        ({"price": -1}, "price"),
        ({"price": 10000000}, "price"),
        ({"price": None}, "price"),
        ({"price": "1000"}, "price"),
        ({"quantity": -1}, "quantity"),
        ({"quantity": 100000}, "quantity"),
    ],
)
def test_stock_unit_value_range_violations(override, expected_field):
    """FR-060 6.26.3：在庫単位の値域（SKU・参照・規格名・価格・数量）を判定する。"""
    row = dict(VALID_DOCUMENT["stock_units"][0])
    row.update(override)
    violations: list[services.Violation] = []

    services.validate_stock_units([row], violations)

    assert expected_field in {violation.field_name for violation in violations}


# trace: FR-060, ADDR-005
@pytest.mark.parametrize(
    ("override", "expected_field"),
    [
        ({"code": "save-1000"}, "code"),
        ({"name": ""}, "name"),
        ({"discount_type": "ratio"}, "discount_type"),
        ({"discount_value": 0}, "discount_value"),
        ({"discount_value": 10000000}, "discount_value"),
        ({"min_spend": -1}, "min_spend"),
        ({"valid_from": ""}, "valid_from"),
        ({"valid_until": "不正"}, "valid_until"),
    ],
)
def test_coupon_value_range_violations(override, expected_field):
    """FR-060 6.26.3：クーポンの値域（コード・表示名・割引方式・割引値・期間）を判定する。"""
    row = dict(VALID_DOCUMENT["coupons"][0])
    row.update(override)
    violations: list[services.Violation] = []

    services.validate_coupons([row], violations)

    assert expected_field in {violation.field_name for violation in violations}


# trace: FR-060, ADDR-005
def test_percentage_coupon_value_is_limited_to_100():
    """FR-060 6.26.3：定率の割引値は1以上100以下（境界値）。"""
    violations: list[services.Violation] = []
    row = dict(VALID_DOCUMENT["coupons"][0])
    row.update({"discount_type": "percentage", "discount_value": 101})

    services.validate_coupons([row], violations)

    assert any(violation.field_name == "discount_value" for violation in violations)

    accepted: list[services.Violation] = []
    row["discount_value"] = 100
    services.validate_coupons([row], accepted)
    assert accepted == []


# trace: FR-060, ADDR-005
def test_coupon_period_must_not_be_reversed():
    """FR-060 6.26.3：有効開始日時≦有効終了日時とする。"""
    violations: list[services.Violation] = []
    row = dict(VALID_DOCUMENT["coupons"][0])
    row.update({"valid_from": "2027-05-01T00:00:00+09:00", "valid_until": "2027-04-30T00:00:00+09:00"})

    services.validate_coupons([row], violations)

    assert any(violation.field_name == "valid_until" for violation in violations)


# trace: FR-060, ADDR-005
def test_duplicate_business_key_in_file_is_a_violation(tmp_path):
    """FR-060：定義ファイル内で業務キーが重複する行は違反とする。"""
    data = document(suppliers=[{"supplier_code": "SUP-01", "name": "A"}, {"supplier_code": "SUP-01", "name": "B"}])

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(write_document(tmp_path, data), reset=False)

    assert any(violation.field_name == "supplier_code" for violation in error.value.violations)


# trace: FR-060, ADDR-005
def test_duplicate_collection_name_under_same_parent_is_a_violation():
    """FR-060 6.26.3：同じ親分類の中で分類名は一意とする。"""
    violations: list[services.Violation] = []
    collections = [
        {"row": 1, "collection_code": "a", "name": "同名", "parent_collection_code": None, "sort_order": 0},
        {"row": 2, "collection_code": "b", "name": "同名", "parent_collection_code": None, "sort_order": 0},
    ]

    services.check_collection_structure(collections, {}, set(), violations)

    assert any(violation.field_name == "name" for violation in violations)


# trace: FR-060, ADDR-005
def test_collection_depth_over_three_is_a_violation():
    """FR-060 6.26.3：深さが4以上になる分類は違反とする（境界値：3は可）。"""
    rows = [
        {"row": 1, "collection_code": "l1", "name": "1", "parent_collection_code": None, "sort_order": 0},
        {"row": 2, "collection_code": "l2", "name": "2", "parent_collection_code": "l1", "sort_order": 0},
        {"row": 3, "collection_code": "l3", "name": "3", "parent_collection_code": "l2", "sort_order": 0},
    ]
    violations: list[services.Violation] = []
    depths = services.check_collection_structure(rows, {}, set(), violations)

    assert violations == []
    assert depths == {"l1": 1, "l2": 2, "l3": 3}

    rows.append({"row": 4, "collection_code": "l4", "name": "4", "parent_collection_code": "l3", "sort_order": 0})
    deep_violations: list[services.Violation] = []
    services.check_collection_structure(rows, {}, set(), deep_violations)

    assert any("深さ" in violation.reason for violation in deep_violations)


# trace: FR-060, ADDR-005
def test_cyclic_parent_is_a_violation():
    """FR-060 6.26.3：親分類をたどって最上位に到達しない（循環する）分類は違反とする。"""
    rows = [
        {"row": 1, "collection_code": "a", "name": "A", "parent_collection_code": "b", "sort_order": 0},
        {"row": 2, "collection_code": "b", "name": "B", "parent_collection_code": "a", "sort_order": 0},
    ]
    violations: list[services.Violation] = []

    services.check_collection_structure(rows, {}, set(), violations)

    assert any("循環" in violation.reason for violation in violations)


# trace: FR-060, ADDR-005
def test_missing_parent_collection_is_a_violation():
    """FR-060 6.26.3：存在しない親分類を指定した行は違反とする。"""
    rows = [{"row": 1, "collection_code": "a", "name": "A", "parent_collection_code": "missing", "sort_order": 0}]
    violations: list[services.Violation] = []

    services.check_collection_structure(rows, {}, set(), violations)

    assert any("参照先の分類" in violation.reason for violation in violations)


# trace: FR-060, ADDR-005
def test_reference_violations_are_collected():
    """FR-060 6.26.3：商品の所属分類、在庫単位の商品・仕入先の参照整合性を判定する。"""
    items = [{"row": 1, "collection_codes": ["known", "missing", "known"]}]
    stock_units = [{"row": 1, "item_code": "NO-ITEM", "supplier_code": "NO-SUP"}]
    violations: list[services.Violation] = []

    services.check_references(items, stock_units, {"known"}, {"ITEM-01"}, {"SUP-01"}, violations)

    reasons = [violation.reason for violation in violations]
    assert "参照先の分類が存在しません。" in reasons
    assert "同じ分類が重複しています。" in reasons
    assert "参照先の商品が存在しません。" in reasons
    assert "参照先の仕入先が存在しません。" in reasons


# trace: NFR-OM-13
def test_violations_are_collected_for_every_row(tmp_path):
    """ADDR-005 DD-003：違反は1件目で中断せず全件収集する。"""
    data = document(
        suppliers=[{"supplier_code": "bad", "name": ""}, {"supplier_code": "ALSO BAD", "name": "A"}]
    )

    with pytest.raises(services.SeedError) as error:
        services.load_initial_data(write_document(tmp_path, data), reset=False)

    assert len(error.value.violations) >= 3
    assert str(error.value) == "定義ファイルに違反があります。"


# trace: NFR-SC-06
def test_violation_message_does_not_contain_field_value():
    """NFR-SC-06：違反の出力にはデータ名・行番号・項目・理由だけを含め、値を含めない。"""
    violation = services.Violation("users", 2, "email", "メールアドレスの形式ではありません。")

    assert violation.format() == "users 行2 email: メールアドレスの形式ではありません。"
    assert "@" not in violation.format()


# trace: NFR-SC-23
def test_record_failure_writes_failure_audit_log():
    """NFR-OM-13：失敗時は監査ログへ失敗を1件記録する。"""
    services.record_failure()

    log = AuditLog.objects.get(event_type=EVENT_INITIAL_DATA_LOAD)
    assert log.result == RESULT_FAILURE
    assert log.detail == ""


# trace: FR-060
def test_command_loads_definition_file(tmp_path, capsys):
    """FR-060：コマンドは定義ファイルを投入し、投入件数を標準出力へ表示する。"""
    path = write_document(tmp_path, document())

    call_command("load_initial_data", path)

    captured = capsys.readouterr()
    assert "users=2" in captured.out
    assert User.objects.count() == 2


# trace: FR-060
def test_command_supports_reset_option(tmp_path):
    """FR-060：--reset は監査ログ以外の全データを削除してから投入する。"""
    make_supplier(supplier_code="OLD-SUP2")
    path = write_document(tmp_path, document())

    call_command("load_initial_data", path, "--reset")

    assert Supplier.objects.filter(supplier_code="OLD-SUP2").count() == 0
    assert Supplier.objects.count() == 1


# trace: NFR-OM-13
def test_command_without_path_reports_usage_and_records_failure(capsys):
    """E-060-01：定義ファイルのパスがない場合は何も投入せず失敗を記録する。"""
    with pytest.raises(SystemExit) as exit_info:
        call_command("load_initial_data")

    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert "定義ファイルのパスを指定してください" in captured.err
    assert AuditLog.objects.get(event_type=EVENT_INITIAL_DATA_LOAD).result == RESULT_FAILURE


# trace: NFR-OM-13
def test_command_reports_all_violations_and_records_failure(tmp_path, capsys):
    """NFR-OM-13：違反の全件（データ名・行番号・項目・理由）を出力し、何も投入しない。"""
    data = document(suppliers=[{"supplier_code": "bad", "name": ""}])
    path = write_document(tmp_path, data)

    with pytest.raises(SystemExit) as exit_info:
        call_command("load_initial_data", path)

    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert services.ERROR_VALUE_RANGE in captured.err
    assert "suppliers 行1" in captured.err
    assert "何も投入しませんでした。" in captured.err
    assert Supplier.objects.count() == 0
    assert AuditLog.objects.get(event_type=EVENT_INITIAL_DATA_LOAD).result == RESULT_FAILURE


# trace: NFR-OM-13
def test_command_reports_system_failure_as_command_error(tmp_path, monkeypatch):
    """E-060-06：データベース障害はシステム障害として通知する（何も投入しない）。"""
    from django.core.management.base import CommandError

    path = write_document(tmp_path, document())

    def raise_database_error(*args, **kwargs):
        raise DatabaseError("connection lost")

    monkeypatch.setattr(services, "load_initial_data", raise_database_error)

    with pytest.raises(CommandError):
        call_command("load_initial_data", path)


# trace: NFR-OM-13
def test_command_keeps_running_when_failure_audit_cannot_be_written(tmp_path, monkeypatch, capsys):
    """監査ログの記録自体が失敗しても、違反内容の出力は行う。"""

    def raise_database_error(*args, **kwargs):
        raise DatabaseError("connection lost")

    monkeypatch.setattr(services, "record_failure", raise_database_error)
    data = document(suppliers=[{"supplier_code": "bad", "name": ""}])
    path = write_document(tmp_path, data)

    with pytest.raises(SystemExit):
        call_command("load_initial_data", path)

    assert "suppliers 行1" in capsys.readouterr().err
