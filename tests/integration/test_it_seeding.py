# trace: FR-002, FR-011, FR-012, FR-060, NFR-SC-01, NFR-SC-06
# trace: NFR-MG-01, NFR-MG-02, NFR-MG-03, NFR-MG-04, NFR-MG-07, NFR-OM-04
# trace: ADDR-002, ADDR-004, ADDR-005, ADDR-007, FILE-001
"""初期データ一括投入（FR-060）の結合試験（IT-AI-INIT-149〜155）。

検証対象の連携は 初期データ一括投入コマンド → PostgreSQL、投入データ → ログインAPI・
商品一覧API、ログ出力基盤 → 監査ログ(DB)。

期待結果は FR-060 の処理内容・例外（E-060-02〜E-060-05）、ファイル定義 FILE-001、
CMN-06/CMN-21/CMN-24/CMN-25、NFR-SC-01/NFR-SC-06 から導出する。
"""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command

from accounts.models import EVENT_INITIAL_DATA_LOAD, ROLE_ADMIN, ROLE_BUYER, AuditLog, User
from carts.models import Cart, CartLine, Coupon
from catalog.models import Collection, Item, StockUnit, Supplier
from orders.models import PurchaseOrder

pytestmark = pytest.mark.django_db

SEED_PASSWORD = "Seedpw0rd"


# trace: FR-060
def definition() -> dict:
    """正当な定義ファイルの内容（架空のテストデータ）。"""
    return {
        "users": [
            {
                "email": "seed-admin@example.test",
                "password": SEED_PASSWORD,
                "full_name": "初期 管理者",
                "role": "admin",
            },
            {
                "email": "seed-buyer@example.test",
                "password": SEED_PASSWORD,
                "full_name": "初期 購入者",
                "role": "buyer",
            },
        ],
        "suppliers": [{"supplier_code": "SEED-SUP-1", "name": "初期仕入先"}],
        "collections": [
            {"collection_code": "seed-root", "name": "初期分類", "sort_order": 1},
            {"collection_code": "seed-child", "name": "初期子分類", "parent_collection_code": "seed-root"},
        ],
        "items": [
            {
                "item_code": "SEED-ITEM-1",
                "name": "初期商品1",
                "description": "説明",
                "is_public": True,
                "collection_codes": ["seed-root"],
            },
            {
                "item_code": "SEED-ITEM-2",
                "name": "初期商品2",
                "is_public": False,
                "collection_codes": ["seed-child"],
            },
        ],
        "stock_units": [
            {
                "sku": "SEED-SKU-1",
                "item_code": "SEED-ITEM-1",
                "supplier_code": "SEED-SUP-1",
                "variant_name": "標準",
                "price": 1000,
                "quantity": 10,
            },
            {
                "sku": "SEED-SKU-2",
                "item_code": "SEED-ITEM-2",
                "supplier_code": "SEED-SUP-1",
                "variant_name": "標準",
                "price": 2000,
                "quantity": 5,
            },
        ],
        "coupons": [
            {
                "code": "SEEDCPN1",
                "name": "初期クーポン",
                "discount_type": "fixed",
                "discount_value": 500,
                "min_spend": 0,
                "valid_from": "2027-01-01T00:00:00+09:00",
                "valid_until": "2030-12-31T23:59:59+09:00",
            }
        ],
    }


# trace: FR-060
def write_definition(tmp_path, document: dict, name: str = "seed.json") -> str:
    """定義ファイルを書き出してパスを返す。"""
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: FR-060
def run_load(path: str, *, reset: bool = False) -> tuple[str, str]:
    """初期データ一括投入コマンドを実行し、標準出力・標準エラー出力を返す。"""
    out, error = StringIO(), StringIO()
    call_command("load_initial_data", path, *(["--reset"] if reset else []), stdout=out, stderr=error)
    return out.getvalue(), error.getvalue()


# trace: FR-060, ADDR-004, ADDR-005, NFR-MG-02, NFR-OM-04
def test_it_ai_init_149_load_initial_data_counts(tmp_path):
    """IT-AI-INIT-149 / COV-135：定義ファイルの件数どおりに登録し、データ別の件数を出力する。"""
    document = definition()
    path = write_definition(tmp_path, document)

    output, _error = run_load(path)

    assert User.objects.count() == len(document["users"])
    assert Supplier.objects.count() == len(document["suppliers"])
    assert Collection.objects.count() == len(document["collections"])
    assert Item.objects.count() == len(document["items"])
    assert StockUnit.objects.count() == len(document["stock_units"])
    assert Coupon.objects.count() == len(document["coupons"])
    assert "users=2" in output
    assert "suppliers=1" in output
    assert "collections=2" in output
    assert "items=2" in output
    assert "stock_units=2" in output
    assert "coupons=1" in output
    child = Collection.objects.get(collection_code="seed-child")
    assert child.parent.collection_code == "seed-root"
    assert child.depth == 2


# trace: FR-002, FR-060, ADDR-002, NFR-SC-01, NFR-MG-03
def test_it_ai_init_150_seeded_users_can_login(tmp_path, api):
    """IT-AI-INIT-150 / COV-136：投入した利用者でログインでき、パスワードはハッシュで保存される。"""
    run_load(write_definition(tmp_path, definition()))

    for email, role in (("seed-admin@example.test", ROLE_ADMIN), ("seed-buyer@example.test", ROLE_BUYER)):
        response = api.post("/api/auth/login", {"email": email, "password": SEED_PASSWORD}, format="json")

        assert response.status_code == 200, email
        assert response.json()["user"]["role"] == role

    hashes = list(User.objects.values_list("password_hash", flat=True))
    assert all(SEED_PASSWORD not in value for value in hashes)
    assert len(set(hashes)) == len(hashes)


# trace: FR-011, FR-012, FR-060, ADDR-004
def test_it_ai_init_151_optional_fields_use_defaults(tmp_path, api):
    """IT-AI-INIT-151 / COV-137：省略した任意項目は既定値で登録され、公開状態がAPIへ反映される。"""
    document = definition()
    document["items"] = [
        {
            "item_code": "SEED-MIN-1",
            "name": "既定値商品",
            "collection_codes": [],
        }
    ]
    document["stock_units"] = [
        {
            "sku": "SEED-MIN-SKU",
            "item_code": "SEED-MIN-1",
            "supplier_code": "SEED-SUP-1",
            "variant_name": "標準",
            "price": 1200,
            "quantity": 4,
        }
    ]
    document["collections"] = [{"collection_code": "seed-root", "name": "初期分類"}]

    run_load(write_definition(tmp_path, document))

    item = Item.objects.get(item_code="SEED-MIN-1")
    assert item.is_public is True  # 既定値
    assert item.description == ""
    assert item.created_at is not None
    assert Collection.objects.get(collection_code="seed-root").sort_order == 0

    listed = api.get("/api/items")
    assert [row["item_code"] for row in listed.json()["results"]] == ["SEED-MIN-1"]
    detail = api.get(f"/api/items/{item.pk}")
    assert detail.status_code == 200

    Item.objects.filter(pk=item.pk).update(is_public=False)
    assert api.get("/api/items").json()["results"] == []
    assert api.get(f"/api/items/{item.pk}").status_code == 404


# trace: FR-060, ADDR-005, NFR-MG-01, NFR-MG-04, NFR-OM-04
def test_it_ai_init_152_reset_deletes_existing_data(tmp_path, f, api_as):
    """IT-AI-INIT-152 / COV-138：全削除オプションは注文・カートを含む既存データを削除してから投入する。"""
    buyer = f.user(email="before-reset@example.test")
    unit = f.sellable(price=1000, quantity=5)
    client = api_as(buyer)
    client.post("/api/cart/lines", {"stock_unit_id": unit.pk, "quantity": 1}, format="json")
    client.post(
        "/api/checkout",
        {
            "recipient_name": "結合 受取人",
            "postal_code": "1234567",
            "prefecture_code": "13",
            "address_line1": "千代田区1-1-1",
            "address_line2": "",
            "phone_number": "09012345678",
        },
        format="json",
    )
    assert PurchaseOrder.objects.exists()
    document = definition()

    run_load(write_definition(tmp_path, document), reset=True)

    assert PurchaseOrder.objects.count() == 0
    assert Cart.objects.count() == 0
    assert CartLine.objects.count() == 0
    assert User.objects.count() == len(document["users"])
    assert not User.objects.filter(email="before-reset@example.test").exists()
    assert StockUnit.objects.count() == len(document["stock_units"])


# trace: FR-060, ADDR-005, NFR-MG-07
def test_it_ai_init_153_violations_prevent_any_insert(tmp_path):
    """IT-AI-INIT-153 / COV-139：違反がある定義ファイルは1件も投入せず、違反を全件出力する。"""
    run_load(write_definition(tmp_path, definition()))
    baseline = {
        "users": User.objects.count(),
        "items": Item.objects.count(),
        "stock_units": StockUnit.objects.count(),
    }

    duplicated = definition()
    value_range = definition()
    value_range["users"] = [
        {"email": "bad-address", "password": "short", "full_name": "", "role": "owner"}
    ]
    missing_reference = definition()
    missing_reference["stock_units"] = [
        {
            "sku": "SEED-SKU-9",
            "item_code": "NOT-EXIST",
            "supplier_code": "NOT-EXIST",
            "variant_name": "標準",
            "price": 100,
            "quantity": 1,
        }
    ]
    in_file_duplicate = definition()
    in_file_duplicate["suppliers"] = [
        {"supplier_code": "DUP-SUP", "name": "重複1"},
        {"supplier_code": "DUP-SUP", "name": "重複2"},
    ]

    cases = {
        "duplicated": duplicated,
        "value_range": value_range,
        "missing_reference": missing_reference,
        "in_file_duplicate": in_file_duplicate,
    }
    for name, document in cases.items():
        path = write_definition(tmp_path, document, name=f"{name}.json")

        with pytest.raises(SystemExit) as exit_info:
            run_load(path)

        assert exit_info.value.code != 0, name
        assert User.objects.count() == baseline["users"], name
        assert Item.objects.count() == baseline["items"], name
        assert StockUnit.objects.count() == baseline["stock_units"], name

    with pytest.raises(SystemExit):
        run_load(str(tmp_path / "not-exists.json"))

    assert User.objects.count() == baseline["users"]
    assert Item.objects.count() == baseline["items"]


# trace: FR-060, ADDR-005
def test_it_ai_init_153b_violations_are_reported_for_every_row(tmp_path):
    """IT-AI-INIT-153 / COV-139：違反は全件（データ名・行番号・項目名・理由）を出力する。"""
    document = definition()
    document["coupons"] = [
        {
            "code": "bad code",
            "name": "",
            "discount_type": "unknown",
            "discount_value": 0,
            "valid_from": "2027-01-01T00:00:00+09:00",
            "valid_until": "2026-01-01T00:00:00+09:00",
        }
    ]
    path = write_definition(tmp_path, document, name="violations.json")
    out, error = StringIO(), StringIO()

    with pytest.raises(SystemExit):
        call_command("load_initial_data", path, stdout=out, stderr=error)

    messages = error.getvalue()
    assert "coupons 行1 code" in messages
    assert "coupons 行1 name" in messages
    assert "coupons 行1 discount_type" in messages
    assert "coupons 行1 discount_value" in messages
    assert "何も投入しませんでした" in messages
    assert Coupon.objects.count() == 0


# trace: FR-060, ADDR-005, NFR-MG-07
def test_it_ai_init_154_reset_with_violations_keeps_existing_data(tmp_path):
    """IT-AI-INIT-154 / COV-139：全削除オプション指定でも違反があれば既存データを削除しない（CMN-21）。"""
    run_load(write_definition(tmp_path, definition()))
    before = {
        "users": set(User.objects.values_list("email", flat=True)),
        "items": set(Item.objects.values_list("item_code", flat=True)),
        "stock_units": set(StockUnit.objects.values_list("sku", flat=True)),
        "coupons": set(Coupon.objects.values_list("code", flat=True)),
    }
    invalid = definition()
    invalid["items"][0]["item_code"] = "invalid code"
    path = write_definition(tmp_path, invalid, name="reset-invalid.json")

    with pytest.raises(SystemExit) as exit_info:
        run_load(path, reset=True)

    assert exit_info.value.code != 0
    assert set(User.objects.values_list("email", flat=True)) == before["users"]
    assert set(Item.objects.values_list("item_code", flat=True)) == before["items"]
    assert set(StockUnit.objects.values_list("sku", flat=True)) == before["stock_units"]
    assert set(Coupon.objects.values_list("code", flat=True)) == before["coupons"]


# trace: FR-060, ADDR-007, NFR-SC-06
def test_it_ai_init_155_initial_data_load_is_audited(tmp_path):
    """IT-AI-INIT-155 / COV-140：初期データ投入は監査ログへ記録し、個人情報・パスワードを含めない。"""
    AuditLog.objects.all().delete()
    document = definition()

    output, _error = run_load(write_definition(tmp_path, document))

    logs = list(AuditLog.objects.filter(event_type=EVENT_INITIAL_DATA_LOAD))
    assert len(logs) == 1
    log = logs[0]
    assert log.result == "success"
    assert log.occurred_at is not None
    assert "users=2" in log.detail
    assert "stock_units=2" in log.detail
    for secret in (SEED_PASSWORD, "seed-admin@example.test", "初期 管理者"):
        assert secret not in log.detail
        assert secret not in output
