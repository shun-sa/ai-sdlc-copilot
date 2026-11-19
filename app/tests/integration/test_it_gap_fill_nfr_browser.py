# trace: NFR-US-01, NFR-US-02, NFR-US-06, NFR-PF-03
# trace: ADDR-012, ADDR-014
"""結合試験：AI GAP_FILL（実ブラウザでの画面の表示・操作と表示完了時間。Revision 5）。

GF-059・GF-060（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL は変更しない。
FULL Traceability C10（UNRESOLVED-e1d9dfe900863622）修正 cycle=2/3 で、NFR-US-01/02/06・NFR-PF-03 の測定条件
（2種のブラウザで全画面を表示・全操作、表示領域 1280×720・表示倍率
100%、Windows 11 の PC、各画面30回以上表示）を読み直し、
開発環境の PC（Windows 11）にインストール済みの Microsoft Edge・Google Chrome をヘッドレスで操作して行う。
-
  ヘッドレス表示での確認であり、通常のウィンドウ表示・目視による表示崩れ（重なり）の確認、全操作の網羅、最新版であることの
  確認は互換性・操作性テストで行う（nfr-verification-scope.json で PARTIAL_IT。合格扱いにしない）。
- NFR-PF-03 は単一利用者・小データ量で、ピーク負荷・3年後データ量・ENV-01
  の判定ではない参考計測（必要条件として目標値以内を確認）。
- 計測値は reports/integration-test/browser-reference.json に記録する。
"""

import json
import re
import threading
import time
from pathlib import Path

import pytest

from tests.integration._browser import Browser, executable, file_version, windows_info
from tests.integration._helpers import ADDRESS, PASSWORD, order_of, pay
from tests.integration._load import p95

pytestmark = pytest.mark.django_db(transaction=True)

REPO_DIR = Path(__file__).resolve().parents[3]
REFERENCE = REPO_DIR / "reports" / "integration-test" / "browser-reference.json"
LATEST = REPO_DIR / "reports" / "integration-test" / "dependency-vulnerability-osv.json"
_WRITE_LOCK = threading.Lock()
BROWSERS = ("edge", "chrome")
LOADS = 30


# trace: NFR-US-01, NFR-PF-03, ADDR-012
def _record(key, data):
    with _WRITE_LOCK:
        current = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else {}
        current[key] = data
        REFERENCE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# trace: NFR-US-01, NFR-PF-03, ADDR-012
def _screen_data(make_user, catalog, bearer, api_client, make_coupon):
    """全画面を表示するための架空のデータ（購入者・管理者・商品・注文受付と支払済の注文・カートの明細）。"""
    buyer = make_user("browser.buyer@example.test", name="画面 購入者")
    other = make_user("browser.other@example.test", name="画面 別購入者")
    admin = make_user("browser.admin@example.test", name="画面 管理者", user_type="admin")
    category = catalog.category("画面確認分類")
    product = catalog.product("画面確認商品", description="ブラウザでの表示確認用の商品です。", categories=(category,))
    units = [catalog.stock_unit(product, price=1200 + i * 100, stock=500) for i in range(2)]
    extra = catalog.stock_unit(catalog.product("画面確認商品2", categories=(category,)), price=3000, stock=500)
    for name in BROWSERS:
        make_coupon(f"BRW-{name.upper()}", discount_type="percentage", discount_value=10)
    data = {
        "buyer": buyer,
        "other": other,
        "admin": admin,
        "product": product,
        "units": units,
        "extra": extra,
        "tokens": {"buyer": bearer(buyer), "other": bearer(other)},
    }
    data.update(_fresh_orders(api_client, data))
    added = api_client.post(
        "/api/cart/items/",
        data=json.dumps({"stock_unit_id": units[1].pk, "quantity": 1}),
        content_type="application/json",
        HTTP_AUTHORIZATION=data["tokens"]["buyer"],
    )
    assert added.status_code == 200, added.content
    return data


# trace: NFR-US-01, NFR-PF-03, ADDR-012
def _fresh_orders(api_client, data):
    """購入者の注文受付の注文1件と、別の購入者の支払済の注文1件を作る。"""
    accepted = order_of(api_client, data["tokens"]["buyer"], [(data["units"][0], 1)])["order_id"]
    paid = order_of(api_client, data["tokens"]["other"], [(data["extra"], 2)])["order_id"]
    assert pay(api_client, data["tokens"]["other"], paid, "approved").status_code == 200
    return {"accepted": accepted, "paid": paid}


# trace: NFR-US-01, NFR-US-02, NFR-PF-03, ADDR-012
def _problems(report, base_url, expected_status=200):
    """表示結果の問題（主文書の状態・資源の読込失敗・スクリプトの例外・外部への要求・横スクロール・表示領域外の要素）。"""
    problems = []
    document = report["document"] or {}
    if document.get("status") != expected_status:
        problems.append(f"document status {document.get('status')} != {expected_status}")
    for row in report["resources"]:
        if row["status"] >= 400 and not row["url"].endswith("/favicon.ico"):
            problems.append(f"resource {row['url']} {row['status']}")
    if report["failures"]:
        problems.append(f"loading failed {report['failures']}")
    for error in report["errors"]:
        url = error.get("url") or ""
        if error["kind"] == "log" and (
            url.endswith("/favicon.ico") or (expected_status >= 400 and url == document.get("url"))
        ):
            continue
        problems.append(f"error {error}")
    for url in report["requested"]:
        if not url.startswith(base_url + "/") and not url.startswith("data:"):
            problems.append(f"off-origin request {url}")
    layout = report["layout"]
    if layout["innerWidth"] != 1280 or layout["innerHeight"] != 720:
        problems.append(f"viewport {layout['innerWidth']}x{layout['innerHeight']}")
    if layout["scrollWidth"] > layout["clientWidth"] or layout["bodyScrollWidth"] > layout["clientWidth"]:
        problems.append(
            f"horizontal scroll {layout['scrollWidth']}/{layout['bodyScrollWidth']} > {layout['clientWidth']}"
        )
    if layout["overflowCount"]:
        problems.append(f"elements outside viewport {layout['overflowElements']}")
    if layout["lang"] != "ja" or layout["charset"].lower() != "utf-8":
        problems.append(f"lang/charset {layout['lang']} {layout['charset']}")
    return problems


# trace: NFR-US-01, NFR-US-02, ADDR-012
def _path(report):
    return re.sub(r"^https?://[^/]+", "", (report["document"] or {}).get("url", ""))


# trace: NFR-US-01, NFR-US-02, NFR-US-06, ADDR-012
def _walk(browser, base_url, data):
    """1つのブラウザで全画面を表示し、来訪者・購入者・管理者の代表的な操作をブラウザのフォーム送信で行う。"""
    steps = []

    def step(name, screen, report, expected_status=200, path=None):
        problems = _problems(report, base_url, expected_status)
        if path is not None and not re.fullmatch(path, _path(report)):
            problems.append(f"path {_path(report)} !~ {path}")
        steps.append(
            {
                "step": name,
                "screen": screen,
                "status": (report["document"] or {}).get("status"),
                "path": _path(report),
                "scroll_width": report["layout"]["scrollWidth"],
                "client_width": report["layout"]["clientWidth"],
                "title": report["layout"]["title"],
                "problems": problems,
            }
        )
        return report

    pid = data["product"].pk
    step("来訪者：商品一覧", "SCR-001", browser.open(f"{base_url}/"))
    step("来訪者：商品詳細", "SCR-002", browser.open(f"{base_url}/products/{pid}/"))
    step("来訪者：会員登録の表示", "SCR-003", browser.open(f"{base_url}/register/"))
    step(
        "来訪者：会員登録",
        "SCR-004",
        browser.submit(
            "main form[action='/register/']",
            {
                "email": f"browser.new.{browser.name}@example.test",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
                "name": "画面 新規会員",
            },
        ),
        path=r"/login/.*",
    )
    step(
        "来訪者：対象なし（エラー画面）",
        "SCR-901",
        browser.open(f"{base_url}/products/999999999/"),
        expected_status=404,
    )
    step("来訪者：ログイン画面", "SCR-004", browser.open(f"{base_url}/login/"))
    step(
        "購入者：ログイン",
        "SCR-001",
        browser.submit("main form[action='/login/']", {"email": data["buyer"].email, "password": PASSWORD}),
        path=r"/",
    )
    step("購入者：商品詳細", "SCR-002", browser.open(f"{base_url}/products/{pid}/"))
    step(
        "購入者：カートに入れる",
        "SCR-002",
        browser.submit(
            "main form[action='/cart/items/add/']", {"stock_unit_id": str(data["units"][0].pk), "quantity": "2"}
        ),
        path=rf"/products/{pid}/",
    )
    step("購入者：カート", "SCR-005", browser.open(f"{base_url}/cart/"))
    step(
        "購入者：クーポン適用",
        "SCR-005",
        browser.submit("main form[action='/cart/coupon/apply/']", {"coupon_code": f"BRW-{browser.name.upper()}"}),
        path=r"/cart/",
    )
    step("購入者：注文手続き", "SCR-006", browser.open(f"{base_url}/checkout/"))
    values = {k: v for k, v in ADDRESS.items()}
    completed = step(
        "購入者：注文確定",
        "SCR-007",
        browser.submit("main form[action='/checkout/']", values),
        path=r"/orders/\d+/complete/",
    )
    order_id = re.search(r"/orders/(\d+)/complete/", _path(completed)).group(1)
    step("購入者：支払画面", "SCR-008", browser.open(f"{base_url}/orders/{order_id}/payment/"))
    step(
        "購入者：支払（承認）",
        "SCR-010",
        browser.submit(f"main form[action='/orders/{order_id}/payment/']", {"mock_instruction": "approved"}),
        path=rf"/orders/{order_id}/",
    )
    step("購入者：注文履歴", "SCR-009", browser.open(f"{base_url}/orders/"))
    step("購入者：注文詳細", "SCR-010", browser.open(f"{base_url}/orders/{data['accepted']}/"))
    step(
        "購入者：注文キャンセル",
        "SCR-010",
        browser.submit(f"main form[action='/orders/{data['accepted']}/cancel/']"),
        path=rf"/orders/{data['accepted']}/",
    )
    step("購入者：ログアウト", "SCR-001", browser.submit("header form[action='/logout/']"))
    step("管理者：ログイン画面", "SCR-004", browser.open(f"{base_url}/login/"))
    step(
        "管理者：ログイン",
        "SCR-102",
        browser.submit("main form[action='/login/']", {"email": data["admin"].email, "password": PASSWORD}),
        path=r"/manage/orders/",
    )
    step("管理者：在庫単位一覧", "SCR-101", browser.open(f"{base_url}/manage/stock-units/"))
    step("管理者：注文詳細", "SCR-103", browser.open(f"{base_url}/manage/orders/{data['paid']}/"))
    step(
        "管理者：出荷登録",
        "SCR-103",
        browser.submit(f"main form[action='/manage/orders/{data['paid']}/ship/']", {"tracking_number": "BRW-0001"}),
        path=rf"/manage/orders/{data['paid']}/",
    )
    step(
        "管理者：配達完了登録",
        "SCR-103",
        browser.submit(f"main form[action='/manage/orders/{data['paid']}/deliver/']"),
        path=rf"/manage/orders/{data['paid']}/",
    )
    step("管理者：注文一覧", "SCR-102", browser.open(f"{base_url}/manage/orders/"))
    step("管理者：ログアウト", "SCR-001", browser.submit("header form[action='/logout/']"))
    return steps


# trace: NFR-US-01, NFR-US-02, NFR-US-06, ADDR-012, ADDR-014
def test_gf_059_browser_compatibility(live_server, make_user, catalog, bearer, api_client, make_coupon):
    """GF-059 Windows 11 の PC の Edge・Chrome
    で、1280×720 の表示領域に全画面を横スクロールなく表示し、代表操作を行える。
    """
    from orders.models import Order

    os_info = windows_info()
    base_url = live_server.url.replace("localhost", "127.0.0.1")
    data = _screen_data(make_user, catalog, bearer, api_client, make_coupon)
    results = {}
    for name in BROWSERS:
        if name != BROWSERS[0]:
            data.update(_fresh_orders(api_client, data))
        browser = Browser(name)
        try:
            steps = _walk(browser, base_url, data)
            results[name] = {
                "executable": browser.path,
                "file_version": file_version(browser.path),
                "devtools_version": browser.version.get("Browser"),
                "dialogs": browser.dialogs,
                "steps": steps,
            }
        finally:
            browser.close()
    latest = json.loads(LATEST.read_text(encoding="utf-8")).get("browsers_latest_stable") if LATEST.exists() else None
    screens = sorted({s["screen"] for r in results.values() for s in r["steps"]})
    _record(
        "GF-059_browser_compatibility",
        {
            "condition": "開発環境の PC の OS とインストール済みのブラウザをヘッドレスで起動し、表示領域 "
            "1280×720・表示倍率 100%、"
            "live_server（Django "
            "の試験用サーバー）。目視による表示崩れの確認・通常のウィンドウ表示・全操作の網羅は含まない",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "os": os_info,
            "browsers": results,
            "latest_stable_at_fetch": latest,
            "screens": screens,
        },
    )
    assert os_info.get("is_windows_11"), os_info
    assert screens == [
        "SCR-001",
        "SCR-002",
        "SCR-003",
        "SCR-004",
        "SCR-005",
        "SCR-006",
        "SCR-007",
        "SCR-008",
        "SCR-009",
        "SCR-010",
        "SCR-101",
        "SCR-102",
        "SCR-103",
        "SCR-901",
    ]
    for name, result in results.items():
        failed = [s for s in result["steps"] if s["problems"]]
        assert not failed, (name, failed)
        assert len(result["dialogs"]) == 4, (name, result["dialogs"])
    assert Order.objects.filter(status="delivered").count() == 2
    assert Order.objects.filter(status="paid").count() == 2


# trace: NFR-PF-03, ADDR-012
def test_gf_060_screen_display_time_reference(live_server, make_user, catalog, bearer, api_client, make_coupon):
    """GF-060 全画面（14画面）の表示完了時間の95パーセンタイル（Edge・Chrome で各30回。単一利用者の参考計測）。"""
    data = _screen_data(make_user, catalog, bearer, api_client, make_coupon)
    base_url = live_server.url.replace("localhost", "127.0.0.1")
    pid, accepted, paid = data["product"].pk, data["accepted"], data["paid"]
    visitor = {"SCR-003": "/register/", "SCR-004": "/login/"}
    buyer_screens = {
        "SCR-001": "/",
        "SCR-002": f"/products/{pid}/",
        "SCR-005": "/cart/",
        "SCR-006": "/checkout/",
        "SCR-007": f"/orders/{accepted}/complete/",
        "SCR-008": f"/orders/{accepted}/payment/",
        "SCR-009": "/orders/",
        "SCR-010": f"/orders/{accepted}/",
        "SCR-901": "/products/999999999/",
    }
    admin_screens = {
        "SCR-101": "/manage/stock-units/",
        "SCR-102": "/manage/orders/",
        "SCR-103": f"/manage/orders/{paid}/",
    }
    results, problems = {}, []

    def measure(browser, screen, path):
        expected = 404 if screen == "SCR-901" else 200
        rows = []
        for _ in range(LOADS):
            report = browser.open(base_url + path)
            issue = _problems(report, base_url, expected)
            if issue:
                problems.append((browser.name, screen, issue))
            rows.append(browser.timing()["display_complete_ms"])
        results.setdefault(browser.name, {})[screen] = {
            "loads": len(rows),
            "p95_ms": round(p95(rows), 1),
            "max_ms": round(max(rows), 1),
            "min_ms": round(min(rows), 1),
            "limit_ms": 2000,
        }

    for name in BROWSERS:
        browser = Browser(name, disable_cache=True)
        try:
            for screen, path in visitor.items():
                measure(browser, screen, path)
            browser.open(f"{base_url}/login/")
            browser.submit("main form[action='/login/']", {"email": data["buyer"].email, "password": PASSWORD})
            for screen, path in buyer_screens.items():
                measure(browser, screen, path)
            browser.submit("header form[action='/logout/']")
            browser.open(f"{base_url}/login/")
            browser.submit("main form[action='/login/']", {"email": data["admin"].email, "password": PASSWORD})
            for screen, path in admin_screens.items():
                measure(browser, screen, path)
        finally:
            browser.close()
    _record(
        "GF-060_screen_display_time",
        {
            "condition": "各画面を各ブラウザ（ヘッドレス、キャッシュ無効）で30回表示し、Navigation "
            "Timing の画面要求の開始から"
            "load "
            "イベント終了（画面の構成に必要な資源の読込完了）までの時間を計測。単一利用者・小データ量・live_server。"
            "ピーク負荷（同時155利用者）・3年後データ量・ENV-01 の判定ではない参考計測",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "os": windows_info(),
            "browsers": {
                n: {"executable": executable(n), "file_version": file_version(executable(n))} for n in BROWSERS
            },
            "results": results,
        },
    )
    assert not problems, problems[:10]
    for name in BROWSERS:
        assert len(results[name]) == 14, (name, sorted(results[name]))
        for screen, row in results[name].items():
            assert row["loads"] >= LOADS
            assert row["p95_ms"] <= row["limit_ms"], (name, screen, row)
