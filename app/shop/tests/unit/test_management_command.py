# trace: FR-060, NFR-OM-04, FILE-001, ADDR-010
"""初期データ一括投入コマンド（FR-060）の単体テスト。

期待値は FR-060 6.26.4 の手順1〜13、例外 E-060-01〜E-060-06 と終了コードの仕様から導出する。
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from shop.models import AuditEventType, AuditLog, Cart, CartLine, Collection, Item, StockUnit, Supplier, User
from shop.services import carts
from shop.tests.unit.test_seeding_fr060 import MINIMAL_DATA

pytestmark = pytest.mark.django_db


# trace: FR-060
def _run(*args):
    """コマンドを実行し、終了コードと標準出力・標準エラー出力を返す。"""
    out, err = StringIO(), StringIO()
    try:
        call_command("load_initial_data", *args, stdout=out, stderr=err)
    except SystemExit as exit_code:
        return int(exit_code.code), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# trace: FR-060
def _write(tmp_path, data):
    """定義ファイルを作成してパスを返す。"""
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


# trace: FR-060, NFR-OM-04
def test_command_loads_data_and_exits_with_zero(tmp_path):
    """正常終了時は終了コード0とし、データ別の件数を出力する。"""
    code, out, err = _run(_write(tmp_path, MINIMAL_DATA))

    assert code == 0
    assert "利用者: 1 件" in out
    assert err == ""
    assert User.objects.count() == 1
    assert AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD).result == "success"


# trace: FR-060
def test_command_requires_path():
    """定義ファイルのパス未指定は E-060-01 とし、終了コード0以外で終了する。"""
    code, _, err = _run()

    assert code != 0
    assert "コマンドの指定が誤っています" in err
    assert AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD).result == "failure"


# trace: FR-060
def test_command_reports_missing_file(tmp_path):
    """定義ファイルを読み取れない場合は E-060-02 とし、何も投入しない。"""
    code, _, err = _run(str(tmp_path / "missing.json"))

    assert code != 0
    assert "定義ファイルが見つからない" in err
    assert User.objects.count() == 0


# trace: FR-060
def test_command_reports_invalid_json(tmp_path):
    """JSON として解釈できない定義ファイルは E-060-03 とする。"""
    path = tmp_path / "seed.json"
    path.write_text("{invalid}", encoding="utf-8")

    code, _, err = _run(str(path))

    assert code != 0
    assert "定義ファイルを解釈できません" in err


# trace: FR-060
def test_command_reports_violations_without_loading(tmp_path):
    """違反がある場合は削除も投入も行わず、違反内容を標準エラー出力へ出す（E-060-04）。"""
    data = json.loads(json.dumps(MINIMAL_DATA))
    data["users"][0]["email"] = "invalid"

    code, _, err = _run(_write(tmp_path, data))

    assert code != 0
    assert "定義ファイルに違反があるため、削除も投入も行いませんでした。" in err
    assert "利用者 行1 項目=email" in err
    assert User.objects.count() == 0
    assert Supplier.objects.count() == 0
    assert AuditLog.objects.get(event_type=AuditEventType.INITIAL_DATA_LOAD).result == "failure"


# trace: FR-060, NFR-OM-04
def test_command_reset_option_replaces_existing_data(tmp_path):
    """--reset は監査ログ以外の全データを削除してから投入する。"""
    path = _write(tmp_path, MINIMAL_DATA)
    _run(path)
    audit_count = AuditLog.objects.count()

    code, _, _ = _run(path, "--reset")

    assert code == 0
    assert User.objects.count() == 1
    assert AuditLog.objects.count() == audit_count + 1


# trace: FR-060, NFR-OM-04
def test_command_reset_with_violation_keeps_existing_data(tmp_path):
    """--reset 指定でも違反がある場合は既存データを削除しない（AC-UC-013-007、手順8・9）。

    違反を検出した時点で手順9の全削除に進まないため、登録済みの利用者・仕入先・商品・在庫単位・
    カート・注文は処理前のまま残り、監査ログへ失敗が1件追加され、終了コードは0以外となる。
    """
    _run(_write(tmp_path, MINIMAL_DATA))
    buyer = User.objects.get(email="buyer@example.com")
    stock_unit = StockUnit.objects.get(sku="SKU-001")
    carts.add_line(buyer, stock_unit.stock_unit_id, 2)
    before = {
        "users": User.objects.count(),
        "suppliers": Supplier.objects.count(),
        "collections": Collection.objects.count(),
        "items": Item.objects.count(),
        "stock_units": StockUnit.objects.count(),
        "carts": Cart.objects.count(),
        "cart_lines": CartLine.objects.count(),
        "audit_logs": AuditLog.objects.count(),
    }
    assert before["carts"] == 1 and before["cart_lines"] == 1

    invalid = json.loads(json.dumps(MINIMAL_DATA))
    invalid["stock_units"][0]["price"] = -1

    code, _, err = _run(_write(tmp_path, invalid), "--reset")

    assert code != 0
    assert "在庫単位 行1 項目=price" in err
    assert User.objects.count() == before["users"]
    assert Supplier.objects.count() == before["suppliers"]
    assert Collection.objects.count() == before["collections"]
    assert Item.objects.count() == before["items"]
    assert StockUnit.objects.count() == before["stock_units"]
    assert Cart.objects.count() == before["carts"]
    assert CartLine.objects.count() == before["cart_lines"]
    assert StockUnit.objects.get(sku="SKU-001").quantity == stock_unit.quantity
    assert AuditLog.objects.count() == before["audit_logs"] + 1
    assert AuditLog.objects.filter(event_type=AuditEventType.INITIAL_DATA_LOAD, result="failure").count() == 1


# trace: FR-060
def test_command_without_reset_rejects_duplicates(tmp_path):
    """--reset が無い場合は登録済みデータと重複する行を違反とする。"""
    path = _write(tmp_path, MINIMAL_DATA)
    _run(path)

    code, _, err = _run(path)

    assert code != 0
    assert "登録済みのデータと重複しています。" in err
    assert User.objects.count() == 1


# trace: FR-060
def test_command_loads_repository_seed_file():
    """同梱の初期データ定義ファイルを投入できる（架空データのみ）。"""
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "seed" / "initial_data.json"

    code, out, _ = _run(str(path), "--reset")

    assert code == 0
    assert "商品: " in out
    assert User.objects.exists()
    assert all(user.email.endswith("@example.com") for user in User.objects.all())
