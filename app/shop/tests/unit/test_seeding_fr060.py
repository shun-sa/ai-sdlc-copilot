# trace: FR-060, NFR-SC-01, FILE-001, ADDR-010
"""初期データ一括投入（FR-060）の単体テスト。

期待値は FR-060 6.26.3（値域・一意性・参照整合性）・6.26.4（処理手順）・例外（E-060-01〜06）と
ADDR-010（定義ファイルの構造・参照項目名）から導出する。
"""
import json

import pytest

from shop.common import timeutils
from shop.models import (
    AuditEventType,
    AuditLog,
    Collection,
    Coupon,
    Item,
    ItemCollection,
    Role,
    StockUnit,
    Supplier,
    User,
)
from shop.services import seeding
from shop.services.seeding import SeedFileError, SeedLoader, read_definition_file

pytestmark = pytest.mark.django_db

MINIMAL_DATA = {
    "users": [
        {
            "email": "buyer@example.com",
            "password": "Passw0rd",
            "full_name": "山田 太郎",
            "role": "buyer",
        }
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
def _data(**overrides):
    """定義ファイルの内容に上書きを適用して返す。"""
    data = json.loads(json.dumps(MINIMAL_DATA))
    data.update(overrides)
    return data


# trace: FR-060
def _loader(data=None, reset=False):
    """検証済みの SeedLoader を返す。"""
    loader = SeedLoader(data if data is not None else _data(), reset=reset)
    loader.validate()
    return loader


# trace: FR-060
def test_load_inserts_all_data():
    """定義ファイルの全データを登録し、データ別の件数を返す。"""
    loader = _loader()

    result = loader.load()

    assert loader.violations == []
    assert result.counts == {
        "users": 1,
        "suppliers": 1,
        "collections": 1,
        "items": 1,
        "item_collections": 1,
        "stock_units": 1,
        "coupons": 1,
    }
    assert User.objects.get().role == Role.BUYER
    assert Supplier.objects.count() == 1
    assert Collection.objects.get().depth == 1
    assert Item.objects.get().item_code == "ITEM-001"
    assert ItemCollection.objects.count() == 1
    assert StockUnit.objects.get().price == 1000
    assert Coupon.objects.get().min_spend == 3000


# trace: FR-060
def test_load_applies_default_values_for_omitted_optional_fields():
    """省略した任意項目には手順4の既定値を設定する（AC-UC-013-003）。

    商品説明＝0文字、公開状態＝公開、商品の登録日時＝投入時刻、表示順＝0、最低購入金額＝0。
    """
    data = _data()
    for field in ("description", "is_public", "created_at"):
        data["items"][0].pop(field)
    data["collections"][0].pop("sort_order")
    data["coupons"][0].pop("min_spend")

    loader = _loader(data)
    loader.load()

    assert loader.violations == []
    item = Item.objects.get(item_code="ITEM-001")
    assert item.description == ""
    assert item.is_public is True
    assert item.created_at == loader.loaded_at
    assert Collection.objects.get(collection_code="kitchen").sort_order == 0
    assert Coupon.objects.get(code="SAVE500").min_spend == 0


# trace: FR-060
def test_load_keeps_specified_values_for_optional_fields():
    """任意項目を指定した場合は既定値ではなく指定値で登録する（AC-UC-013-003 の対の確認）。"""
    data = _data()
    data["items"][0]["is_public"] = False

    loader = _loader(data)
    loader.load()

    item = Item.objects.get(item_code="ITEM-001")
    assert item.is_public is False
    assert item.description == "説明"
    assert timeutils.to_iso(item.created_at) == "2027-03-01T10:00:00+09:00"
    assert Collection.objects.get(collection_code="kitchen").sort_order == 10
    assert Coupon.objects.get(code="SAVE500").min_spend == 3000


# trace: FR-060, NFR-SC-01
def test_load_stores_password_as_hash():
    """利用者のパスワードはソルト付き一方向ハッシュで保持し、平文を保持しない（CMN-06）。"""
    _loader().load()

    user = User.objects.get()
    assert user.password_hash != "Passw0rd"
    assert user.password_hash.startswith("pbkdf2_sha256$")


# trace: FR-060
def test_load_records_audit_log():
    """投入の成功を監査ログへ1件記録する（利用者IDは空）。"""
    _loader().load()

    log = AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD)
    assert log.result == "success"
    assert log.user_id_value is None
    assert "利用者=1" in log.detail


# trace: FR-060
def test_record_failure_writes_audit_log():
    """失敗時も監査ログを1件記録する（CMN-21）。"""
    seeding.record_failure("定義ファイルに違反があります")

    log = AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD)
    assert log.result == "failure"
    assert log.detail == "定義ファイルに違反があります"


# trace: FR-060
def test_load_builds_collection_hierarchy():
    """商品分類の深さは最上位1、以降は親分類の深さ＋1とする。"""
    data = _data(
        collections=[
            {"collection_code": "kitchen-cup", "name": "カップ", "parent_collection_code": "kitchen"},
            {"collection_code": "kitchen", "name": "キッチン"},
        ]
    )
    data["items"][0]["collection_codes"] = ["kitchen-cup"]

    _loader(data).load()

    assert Collection.objects.get(collection_code="kitchen").depth == 1
    assert Collection.objects.get(collection_code="kitchen-cup").depth == 2


# trace: FR-060
def test_validate_rejects_collection_depth_over_three():
    """深さが4以上になる商品分類は違反とする（境界の外側）。"""
    data = _data(
        collections=[
            {"collection_code": "l1", "name": "第1"},
            {"collection_code": "l2", "name": "第2", "parent_collection_code": "l1"},
            {"collection_code": "l3", "name": "第3", "parent_collection_code": "l2"},
            {"collection_code": "l4", "name": "第4", "parent_collection_code": "l3"},
        ]
    )
    data["items"][0]["collection_codes"] = ["l1"]

    loader = _loader(data)

    assert any(violation.field_name == "parent_collection_code" for violation in loader.violations)


# trace: FR-060
def test_validate_accepts_collection_depth_three():
    """深さ3の商品分類は受け付ける（境界値）。"""
    data = _data(
        collections=[
            {"collection_code": "l1", "name": "第1"},
            {"collection_code": "l2", "name": "第2", "parent_collection_code": "l1"},
            {"collection_code": "l3", "name": "第3", "parent_collection_code": "l2"},
        ]
    )
    data["items"][0]["collection_codes"] = ["l3"]

    loader = _loader(data)

    assert loader.violations == []


# trace: FR-060
def test_validate_detects_circular_parent_reference():
    """親分類の参照が循環する商品分類は違反とする。"""
    data = _data(
        collections=[
            {"collection_code": "a", "name": "A", "parent_collection_code": "b"},
            {"collection_code": "b", "name": "B", "parent_collection_code": "a"},
        ]
    )
    data["items"][0]["collection_codes"] = ["a"]

    loader = _loader(data)

    assert any("循環" in violation.reason for violation in loader.violations)


# trace: FR-060
@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("email", "invalid", "email"),
        ("email", "", "email"),
        ("password", "short1", "password"),
        ("password", "passwordonly", "password"),
        ("password", "buyer@example.com", "password"),
        ("full_name", "", "full_name"),
        ("full_name", "あ" * 51, "full_name"),
        ("role", "owner", "role"),
    ],
)
def test_validate_user_rows(field, value, expected_field):
    """利用者の値域違反を行番号・項目名つきで通知する。"""
    data = _data()
    data["users"][0][field] = value

    loader = _loader(data)

    assert any(
        violation.field_name == expected_field and violation.line_number == 1
        for violation in loader.violations
    )


# trace: FR-060
@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("suppliers", "supplier_code", "sup-001"),
        ("suppliers", "name", ""),
        ("collections", "collection_code", "KITCHEN"),
        ("items", "item_code", "item-001"),
        ("stock_units", "sku", "sku-001"),
        ("stock_units", "price", -1),
        ("stock_units", "price", 10000000),
        ("stock_units", "quantity", 100000),
        ("coupons", "code", "save500"),
        ("coupons", "discount_type", "amount"),
        ("coupons", "discount_value", 0),
    ],
)
def test_validate_value_ranges(key, field, value):
    """各データの値域・使用できる文字の違反を検出する。"""
    data = _data()
    data[key][0][field] = value

    loader = _loader(data)

    assert any(violation.field_name == field for violation in loader.violations)


# trace: FR-060
def test_validate_percentage_discount_upper_bound():
    """定率クーポンの割引値は1以上100以下とする（境界値）。"""
    valid = _data()
    valid["coupons"][0].update(discount_type="percentage", discount_value=100)
    invalid = _data()
    invalid["coupons"][0].update(discount_type="percentage", discount_value=101)

    assert _loader(valid).violations == []
    assert any(violation.field_name == "discount_value" for violation in _loader(invalid).violations)


# trace: FR-060
def test_validate_coupon_period_order():
    """有効開始日時が有効終了日時より後のクーポンは違反とする。"""
    data = _data()
    data["coupons"][0]["valid_from"] = "2027-05-01T00:00:00+09:00"
    data["coupons"][0]["valid_until"] = "2027-04-30T23:59:59+09:00"

    loader = _loader(data)

    assert any(violation.field_name == "valid_until" for violation in loader.violations)


# trace: FR-060
@pytest.mark.parametrize("value", ["2027-04-01", "not-a-date", 20270401, "2027/04/01T00:00:00"])
def test_validate_rejects_invalid_datetime(value):
    """日時として解釈できない値は違反とする。"""
    data = _data()
    data["coupons"][0]["valid_from"] = value

    loader = _loader(data)

    assert any(violation.field_name == "valid_from" for violation in loader.violations)


# trace: FR-060
def test_validate_detects_duplicate_business_keys():
    """定義ファイル内で業務キーが重複する行は違反とする。"""
    data = _data()
    data["suppliers"].append({"supplier_code": "SUP-001", "name": "重複仕入先"})

    loader = _loader(data)

    assert any(
        violation.field_name == "supplier_code" and violation.line_number == 2 for violation in loader.violations
    )


# trace: FR-060
def test_validate_detects_duplicate_collection_name_under_same_parent():
    """同じ親分類の中で分類名が重複する行は違反とする。"""
    data = _data(
        collections=[
            {"collection_code": "kitchen", "name": "キッチン"},
            {"collection_code": "kitchen2", "name": "キッチン"},
        ]
    )
    data["items"][0]["collection_codes"] = ["kitchen"]

    loader = _loader(data)

    assert any(violation.field_name == "name" for violation in loader.violations)


# trace: FR-060
def test_validate_detects_duplicate_collection_name_with_existing_sibling_without_reset():
    """全削除指定が無い場合、同じ親分類を持つ登録済みの分類と分類名が重複する行は違反とする。

    FR-060 手順6後段。登録済みの最上位分類「キッチン」がある状態で、
    分類コードが異なる最上位分類「キッチン」を投入しようとした場合を判定する。
    """
    _loader().load()

    data = _data(
        collections=[{"collection_code": "kitchen-2", "name": "キッチン"}],
        users=[],
        suppliers=[],
        items=[],
        stock_units=[],
        coupons=[],
    )
    loader = _loader(data, reset=False)

    assert any(
        violation.field_name == "name"
        and violation.line_number == 1
        and "登録済み" in violation.reason
        for violation in loader.violations
    )


# trace: FR-060
def test_validate_allows_same_collection_name_under_different_parent_without_reset():
    """親分類が異なれば、登録済みの分類と分類名が同じでも違反としない（手順6後段の判定範囲）。"""
    _loader().load()

    data = _data(
        collections=[{"collection_code": "kitchen-child", "name": "キッチン", "parent_collection_code": "kitchen"}],
        users=[],
        suppliers=[],
        items=[],
        stock_units=[],
        coupons=[],
    )
    loader = _loader(data, reset=False)

    assert loader.violations == []


# trace: FR-060
def test_validate_ignores_existing_collection_names_when_reset_specified():
    """全削除指定がある場合は登録済みの分類との分類名重複を判定しない（手順6後段の適用条件）。"""
    _loader().load()

    data = _data(
        collections=[{"collection_code": "kitchen-2", "name": "キッチン"}],
        users=[],
        suppliers=[],
        items=[],
        stock_units=[],
        coupons=[],
    )
    loader = _loader(data, reset=True)

    assert loader.violations == []


# trace: FR-060
def test_validate_detects_duplicate_collection_codes_in_item():
    """同じ商品に同じ分類コードを重複指定した行は違反とする。"""
    data = _data()
    data["items"][0]["collection_codes"] = ["kitchen", "kitchen"]

    loader = _loader(data)

    assert any(violation.field_name == "collection_codes" for violation in loader.violations)


# trace: FR-060
@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("items", "collection_codes", ["unknown"]),
        ("stock_units", "item_code", "ITEM-999"),
        ("stock_units", "supplier_code", "SUP-999"),
    ],
)
def test_validate_detects_missing_references(key, field, value):
    """参照先が存在しない行は違反とする（参照整合性）。"""
    data = _data()
    data[key][0][field] = value

    loader = _loader(data)

    assert any(violation.field_name == field for violation in loader.violations)


# trace: FR-060
def test_validate_detects_conflict_with_existing_data_without_reset():
    """全削除指定が無い場合は登録済みデータとの業務キー重複を違反とする。"""
    _loader().load()

    loader = _loader(_data(), reset=False)

    assert any("登録済み" in violation.reason for violation in loader.violations)


# trace: FR-060
def test_reset_allows_same_business_keys_and_deletes_existing_data():
    """全削除指定では監査ログ以外の全データを削除してから投入する。"""
    _loader().load()
    before_logs = AuditLog.objects.count()

    loader = _loader(_data(), reset=True)
    loader.load()

    assert loader.violations == []
    assert User.objects.count() == 1
    assert Supplier.objects.count() == 1
    assert AuditLog.objects.count() == before_logs + 1


# trace: FR-060
def test_violation_format_excludes_values():
    """違反の出力はデータ名・行番号・項目名・理由とし、項目の値を含めない。"""
    data = _data()
    data["users"][0]["email"] = "secret-value@invalid"

    loader = _loader(data)
    formatted = [violation.format() for violation in loader.violations]

    assert formatted
    assert all("secret-value" not in text for text in formatted)
    assert "利用者 行1 項目=email" in formatted[0]


# trace: FR-060
def test_load_result_is_ok_when_no_violation():
    """違反が0件の場合のみ投入可能と判定する。"""
    loader = _loader()

    result = loader.load()

    assert result.ok is True


# trace: FR-060, ADDR-010
def test_read_definition_file_reads_utf8_json(tmp_path):
    """定義ファイルは UTF-8 の JSON として読み込む。"""
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(MINIMAL_DATA, ensure_ascii=False), encoding="utf-8")

    data = read_definition_file(str(path))

    assert data["users"][0]["email"] == "buyer@example.com"
    assert data["suppliers"][0]["supplier_code"] == "SUP-001"


# trace: FR-060
def test_read_definition_file_accepts_bom(tmp_path):
    """BOM 付き UTF-8 の定義ファイルも読み込める。"""
    path = tmp_path / "seed.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(MINIMAL_DATA, ensure_ascii=False).encode("utf-8"))

    assert read_definition_file(str(path))["items"][0]["item_code"] == "ITEM-001"


# trace: FR-060
def test_read_definition_file_treats_missing_keys_as_empty(tmp_path):
    """記載のないデータは0行として扱う。"""
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"suppliers": []}), encoding="utf-8")

    data = read_definition_file(str(path))

    assert data == {key: [] for key in ("users", "suppliers", "collections", "items", "stock_units", "coupons")}


# trace: FR-060
def test_read_definition_file_rejects_missing_file(tmp_path):
    """定義ファイルが存在しない場合は読み取りエラーとする（E-060-02）。"""
    with pytest.raises(FileNotFoundError):
        read_definition_file(str(tmp_path / "missing.json"))


# trace: FR-060
def test_read_definition_file_rejects_non_utf8(tmp_path):
    """UTF-8 として解釈できない定義ファイルは E-060-03 とする。"""
    path = tmp_path / "seed.json"
    path.write_bytes(json.dumps(MINIMAL_DATA, ensure_ascii=False).encode("shift_jis"))

    with pytest.raises(SeedFileError):
        read_definition_file(str(path))


# trace: FR-060
@pytest.mark.parametrize(
    "content",
    ['{"users": [1]}', '{"users": {}}', "[]", '{"unknown": []}', "{invalid json}"],
)
def test_read_definition_file_rejects_invalid_structure(tmp_path, content):
    """JSON として解釈できない・構造が異なる定義ファイルは E-060-03 とする。"""
    path = tmp_path / "seed.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SeedFileError):
        read_definition_file(str(path))


# trace: FR-060
def test_seed_file_of_repository_is_valid():
    """同梱の初期データ定義ファイルは値域・一意性・参照整合性を満たす（架空の値のみ）。"""
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "seed" / "initial_data.json"
    data = read_definition_file(str(path))

    loader = SeedLoader(data, reset=True)
    loader.validate()

    assert loader.violations == []
    assert all("@example.com" in row["email"] for row in loader.users)
