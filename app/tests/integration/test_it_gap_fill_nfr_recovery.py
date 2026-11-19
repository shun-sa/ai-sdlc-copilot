# trace: NFR-AV-04, NFR-AV-07, NFR-AV-08, NFR-AV-12, NFR-PF-13, NFR-OM-15
# trace: ADDR-001, ADDR-004, ADDR-010, ADDR-011, ADDR-012, ADDR-014
"""結合試験：AI GAP_FILL（バックアップ・リストア・復旧後の業務再開・更新と切戻しの参考確認。Revision 5）。

GF-072・GF-073（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
FULL Traceability C10（UNRESOLVED-e1d9dfe900863622）修正 cycle=2/3 で、NFR-AV-04/07/08/12・NFR-PF-13・NFR-OM-15 の
測定条件・検証方法（3年後相当のデータ量、サービスを停止しない取得、リストアと復元された時点、復旧後の全機能の確認、
更新と切戻しの所要時間）を読み直し、使い捨ての PostgreSQL 16 で実施できる部分を確認する。
- 本番のバックアップ方式・取得時刻（毎日 3:00）・7世代保持・保管場所は未決（NOQ-01、DIF-03）で確認しない。
  ここでは PostgreSQL 標準の論理バックアップ（pg_dump／pg_restore、コンテナ内で実行）を代わりに用いる参考確認で、
  合格扱いにしない（nfr-verification-scope.json で PARTIAL_IT）。
- 更新・切戻し（NFR-OM-15）は、リポジトリの最新のデータ構造の変更（catalog 0002）を適用する更新と、更新直前の
  バックアップからの切戻しを行う。プログラム（イメージ）の入替え・ENV-01（compose）での起動は確認しない。
- 計測値は reports/integration-test/recovery-reference.json に記録する。
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest
from django.core.management import call_command

from tests.integration._bulk import OFFSET, generate
from tests.integration._helpers import ADDRESS, PASSWORD, add_item, api, body, form_fields, order_of, pay

pytestmark = pytest.mark.django_db(transaction=True)

REPO_DIR = Path(__file__).resolve().parents[3]
REFERENCE = REPO_DIR / "reports" / "integration-test" / "recovery-reference.json"
# 取得中の要求で件数が減らない（追記・登録だけの）データ。復元後の件数が取得の前後の件数の間にあることを確かめる
_MONOTONIC = (
    "accounts_user",
    "audit_auditlog",
    "catalog_category",
    "catalog_product",
    "catalog_stockunit",
    "catalog_supplier",
    "orders_order",
    "orders_orderitem",
    "orders_orderstatushistory",
    "orders_paymentrecord",
    "orders_shippingaddress",
    "promotions_coupon",
)


# trace: NFR-AV-04, NFR-AV-12, NFR-OM-15, ADDR-011
def _record(key, data):
    current = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else {}
    current[key] = data
    REFERENCE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# trace: NFR-AV-04, NFR-AV-12, NFR-OM-15, ADDR-011
class _Database:
    """使い捨て DB のコンテナ内で pg_dump・pg_restore・psql を実行する（ローカル接続。認証情報を渡さない）。"""

    def __init__(self):
        from django.db import connection

        self.container = os.environ.get("IT_DB_CONTAINER")
        assert self.container, "IT_DB_CONTAINER（run_integration.py が設定する使い捨て DB のコンテナ名）が必要"
        self.name = connection.settings_dict["NAME"]
        self.user = connection.settings_dict["USER"]
        assert self.name.startswith("test_"), self.name

    def _exec(self, *args, timeout=1200):
        completed = subprocess.run(
            ["docker", "exec", self.container, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr[-2000:]
        return completed.stdout

    def dump(self, path):
        start = time.monotonic()
        self._exec("pg_dump", "-U", self.user, "-d", self.name, "-Fc", "-f", path)
        elapsed = time.monotonic() - start
        size = int(self._exec("stat", "-c", "%s", path).strip())
        return elapsed, size

    def destroy_and_restore(self, path):
        """障害（データベースの全データの喪失）を模してスキーマを削除し、バックアップから全データを復元する。"""
        from django.db import connections

        connections.close_all()
        self._exec(
            "psql",
            "-U",
            self.user,
            "-d",
            self.name,
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
            "-c",
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;",
        )
        start = time.monotonic()
        self._exec("pg_restore", "-U", self.user, "-d", self.name, "--no-owner", "--exit-on-error", path)
        return time.monotonic() - start

    def tables(self):
        out = self._exec(
            "psql",
            "-U",
            self.user,
            "-d",
            self.name,
            "-At",
            "-c",
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1",
        )
        return [line for line in out.splitlines() if line]


# trace: NFR-AV-04, NFR-AV-07, NFR-AV-12, ADDR-011
def _counts():
    from django.apps import apps

    return {m._meta.db_table: m.objects.count() for m in apps.get_models() if m._meta.managed}


# trace: NFR-PF-13, ADDR-001
class _Traffic(threading.Thread):
    """バックアップの取得中に画面・API の要求を送り続ける（購入者1名。照会と更新）。"""

    def __init__(self, token, unit_ids, results, stop, seed):
        super().__init__(daemon=True)
        self.token, self.unit_ids, self.results, self.stop, self.seed = token, unit_ids, results, stop, seed

    def run(self):
        from django.db import connection
        from django.test import Client
        from rest_framework.test import APIClient

        client, page = APIClient(), Client()
        n = self.seed
        try:
            while not self.stop.is_set():
                n += 1
                calls = [
                    ("GET /api/products/", api, (client, "get", "/api/products/?page=2"), (200,)),
                    ("GET /", page.get, ("/",), (200,)),
                    ("GET /api/orders/", api, (client, "get", "/api/orders/", self.token), (200,)),
                    ("POST /api/cart/items/", add_item, (client, self.token, self.unit_ids[n % 50], 1), (200,)),
                ]
                if n % 4 == 0:
                    calls.append(
                        (
                            "POST /api/orders/",
                            api,
                            (client, "post", "/api/orders/", self.token, {"shipping_address": dict(ADDRESS)}),
                            (201,),
                        )
                    )
                for label, call, args, ok in calls:
                    start = time.monotonic()
                    status = call(*args).status_code
                    self.results.append((label, start, time.monotonic(), status, status in ok))
        finally:
            connection.close()


# trace: NFR-AV-08, ADDR-001, ADDR-010, ADDR-012
def _all_functions(api_client, web, admin, catalog_unit, tmp_path):
    """復旧後に、障害前に提供していた全業務（NFR-AV-08 の目標値の業務範囲）を画面・API・初期データ一括投入で行う。"""
    results = {}

    def check(name, response, *ok):
        results[name] = response.status_code
        assert response.status_code in ok, (name, response.status_code, response.content[:300])
        return response

    product_id = catalog_unit.product_id
    check("来訪者：商品分類一覧（API）", api(api_client, "get", "/api/categories/"), 200)
    check("来訪者：商品一覧検索（API）", api(api_client, "get", "/api/products/?keyword=架空商品"), 200)
    check("来訪者：商品詳細（API）", api(api_client, "get", f"/api/products/{product_id}/"), 200)
    check("来訪者：商品一覧（画面）", web().get("/"), 200)
    check("来訪者：商品詳細（画面）", web().get(f"/products/{product_id}/"), 200)
    email = "restored.member@example.test"
    check(
        "来訪者：会員登録",
        api(
            api_client,
            "post",
            "/api/auth/register/",
            data={"email": email, "password": PASSWORD, "password_confirmation": PASSWORD, "name": "復旧 会員"},
        ),
        201,
    )
    login = check(
        "購入者：ログイン",
        api(api_client, "post", "/api/auth/login/", data={"email": email, "password": PASSWORD}),
        200,
    )
    token = f"Bearer {body(login)['token']}"
    check("購入者：カート明細追加", add_item(api_client, token, catalog_unit.pk, 2), 200)
    check("購入者：クーポン適用", api(api_client, "post", "/api/cart/coupon/", token, {"coupon_code": "V-CPN000"}), 200)
    placed = check(
        "購入者：注文確定", api(api_client, "post", "/api/orders/", token, {"shipping_address": dict(ADDRESS)}), 201
    )
    order_id = body(placed)["order_id"]
    check("購入者：支払", pay(api_client, token, order_id, "approved"), 200)
    check("購入者：注文履歴", api(api_client, "get", "/api/orders/", token), 200)
    check("購入者：注文詳細", api(api_client, "get", f"/api/orders/{order_id}/", token), 200)
    second = order_of(api_client, token, [(catalog_unit, 1)])["order_id"]
    check("購入者：注文キャンセル", api(api_client, "post", f"/api/orders/{second}/cancel/", token), 200)
    check("購入者：ログアウト", api(api_client, "post", "/api/auth/logout/", token), 204)
    page = web()
    fields = form_fields(page.get("/login/").content.decode("utf-8"), "/login/")
    fields.update({"email": email, "password": PASSWORD})
    check("購入者：画面のログイン", page.post("/login/", fields), 302)
    check("購入者：注文詳細（画面）", page.get(f"/orders/{order_id}/"), 200)
    admin_login = api(api_client, "post", "/api/auth/login/", data={"email": admin, "password": PASSWORD})
    admin_token = f"Bearer {body(check('管理者：ログイン', admin_login, 200))['token']}"
    check("管理者：在庫単位一覧", api(api_client, "get", "/api/admin/stock-units/", admin_token), 200)
    check("管理者：注文一覧検索", api(api_client, "get", "/api/admin/orders/?status=paid", admin_token), 200)
    check("管理者：注文詳細", api(api_client, "get", f"/api/admin/orders/{order_id}/", admin_token), 200)
    check(
        "管理者：出荷登録",
        api(api_client, "post", f"/api/admin/orders/{order_id}/ship/", admin_token, {"tracking_number": "RESTORE-1"}),
        200,
    )
    check("管理者：配達完了登録", api(api_client, "post", f"/api/admin/orders/{order_id}/deliver/", admin_token), 200)
    relogin = api(api_client, "post", "/api/auth/login/", data={"email": email, "password": PASSWORD})
    third = order_of(api_client, f"Bearer {body(relogin)['token']}", [(catalog_unit, 1)])["order_id"]
    check("管理者：注文キャンセル", api(api_client, "post", f"/api/admin/orders/{third}/cancel/", admin_token), 200)
    definition = tmp_path / "restored-load.json"
    definition.write_text(
        json.dumps({"suppliers": [{"supplier_code": "RESTORE-SUP", "name": "復旧後の架空仕入先"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    call_command("load_initial_data", str(definition))
    from catalog.models import Supplier

    results["運用者：初期データ一括投入"] = (
        "success" if Supplier.objects.filter(supplier_code="RESTORE-SUP").exists() else "failure"
    )
    assert results["運用者：初期データ一括投入"] == "success"
    return results


# trace: NFR-AV-04, NFR-AV-07, NFR-AV-08, NFR-AV-12, NFR-PF-13, ADDR-001, ADDR-011
def test_gf_072_backup_restore_and_resume(api_client, web, bearer, make_user, tmp_path):
    """GF-072 3年後相当のデータで、サービスを止めずに全データを取得し、
    全データの喪失後に取得時点へ復元して全業務を再開する。
    """
    from audit.models import AuditLog
    from catalog.models import StockUnit
    from orders.models import Order

    database = _Database()
    generated = generate(1.0)
    buyer = make_user("backup.buyer@example.test", name="バックアップ 購入者")
    token = bearer(buyer)
    unit = StockUnit.objects.get(pk=OFFSET)
    api(api_client, "post", "/api/auth/login/", data={"email": buyer.email, "password": "Wrong0Pass9"})
    pre_marker = order_of(api_client, token, [(unit, 1)])["order_id"]
    counts_pre = _counts()
    audit_pre = AuditLog.objects.count()

    results, stop = [], threading.Event()
    unit_ids = list(StockUnit.objects.filter(pk__gte=OFFSET).order_by("pk").values_list("pk", flat=True)[:50])
    traffic = [
        _Traffic(bearer(make_user(name=f"取得中 利用者{i}")), unit_ids, results, stop, i * 100) for i in range(3)
    ]
    for thread in traffic:
        thread.start()
    time.sleep(1.0)
    dump_started = time.monotonic()
    dump_seconds, dump_size = database.dump("/tmp/mc-it-backup.dump")
    dump_finished = time.monotonic()
    time.sleep(0.5)
    stop.set()
    for thread in traffic:
        thread.join(timeout=120)
    assert all(not t.is_alive() for t in traffic)
    during = [r for r in results if r[1] < dump_finished and r[2] > dump_started]
    failed = [r for r in results if not r[4]]

    post_marker = order_of(api_client, token, [(unit, 1)])["order_id"]
    counts_post = _counts()
    restore_seconds = database.destroy_and_restore("/tmp/mc-it-backup.dump")
    counts_restored = _counts()
    markers = {
        "before_backup_present": Order.objects.filter(pk=pre_marker).exists(),
        "after_backup_present": Order.objects.filter(pk=post_marker).exists(),
    }
    out_of_range = {
        table: (counts_pre[table], counts_restored.get(table), counts_post[table])
        for table in _MONOTONIC
        if not counts_pre[table] <= counts_restored.get(table, -1) <= counts_post[table]
    }
    admin_email = "vdc01.admin0@example.com"
    functions = _all_functions(api_client, web, admin_email, unit, tmp_path)
    _record(
        "GF-072_backup_restore",
        {
            "condition": "3年後相当のデータ（VDC-01〜VDC-03 の件数）を COPY で生成した使い捨て PostgreSQL 16 で、"
            "PostgreSQL 標準の"
            "論理バックアップ（pg_dump -Fc）を利用者の要求の処理中に取得し、"
            "スキーマ削除（全データの喪失）後に pg_restore で復元。"
            "本番のバックアップ方式・3:00 の取得・7世代保持・保管場所・ENV-02 は対象外の参考確認",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "generated_counts": generated,
            "backup": {"seconds": round(dump_seconds, 2), "bytes": dump_size},
            "requests_during_backup": {
                "count": len(during),
                "failed": [list(r) for r in failed][:20],
                "labels": sorted({r[0] for r in during}),
            },
            "restore_seconds": round(restore_seconds, 2),
            "restore_target_seconds": 4 * 3600,
            "counts_before_backup": counts_pre,
            "counts_restored": counts_restored,
            "counts_after_backup": counts_post,
            "markers": {"before_backup": pre_marker, "after_backup": post_marker, **markers},
            "functions_after_restore": functions,
        },
    )
    assert len(during) >= 10, len(during)
    assert not failed, failed[:10]
    assert set(database.tables()) >= set(counts_pre), sorted(set(counts_pre) - set(database.tables()))
    assert not out_of_range, out_of_range
    assert markers == {"before_backup_present": True, "after_backup_present": False}, markers
    assert counts_restored["audit_auditlog"] >= audit_pre and audit_pre >= 1
    assert counts_restored["orders_order"] >= generated["Order"]
    assert restore_seconds <= 4 * 3600


# trace: NFR-OM-15, ADDR-014
def test_gf_073_update_and_rollback(api_client, web):
    """GF-073 3年後相当のデータで、データ構造の変更を含む更新と、更新直前の状態への切戻しを行い所要時間を計測する。"""
    from django.db import connection

    database = _Database()
    generated = generate(1.0)

    def constraint_exists():
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_constraint WHERE conname = 'category_parent_name_uniq'")
            return cursor.fetchone()[0] == 1

    def applied():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM django_migrations WHERE app = 'catalog' AND name = %s",
                ["0002_category_parent_name_uniq"],
            )
            return cursor.fetchone()[0] == 1

    timings = {}
    try:
        call_command("migrate", "catalog", "0001", verbosity=0)
        assert not constraint_exists() and not applied()
        counts_before = _counts()
        timings["backup_seconds"], size = database.dump("/tmp/mc-it-pre-update.dump")
        start = time.monotonic()
        call_command("migrate", verbosity=0)
        timings["update_seconds"] = time.monotonic() - start
        start = time.monotonic()
        started = [web().get("/").status_code, api(api_client, "get", "/api/products/").status_code]
        timings["start_check_seconds"] = time.monotonic() - start
        updated = constraint_exists() and applied()
        timings["rollback_seconds"] = database.destroy_and_restore("/tmp/mc-it-pre-update.dump")
        rolled_back = (not constraint_exists(), not applied())
        counts_after = _counts()
        after_rollback = [web().get("/").status_code, api(api_client, "get", "/api/products/").status_code]
    finally:
        call_command("migrate", verbosity=0)
    total = sum(v for k, v in timings.items())
    _record(
        "GF-073_update_rollback",
        {
            "condition": "3年後相当のデータで、"
            "データ構造の変更（catalog 0002：商品分類の一意制約の追加）の適用を更新とし、更新直前に"
            "取得した pg_dump から切戻す。プログラム（イメージ）の入替え・ENV-01（compose）での起動は含まない参考計測",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "generated_counts": generated,
            "backup_bytes": size,
            "timings_seconds": {k: round(v, 2) for k, v in timings.items()},
            "total_seconds": round(total, 2),
            "target_seconds": 120 * 60,
            "started_after_update": started,
            "after_rollback": after_rollback,
        },
    )
    assert updated
    assert started == [200, 200]
    assert rolled_back == (True, True)
    assert counts_after == counts_before
    assert after_rollback == [200, 200]
    assert constraint_exists() and applied()
    assert total <= 120 * 60
