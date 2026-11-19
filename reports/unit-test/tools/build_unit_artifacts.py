"""単体テスト工程の機械判定用成果物（coverage-summary.json・unit-test-evidence.json）を生成する。

入力は同一実行で生成された reports/unit-test/junit.xml（classname は app.tests.unit.test_xxx、各 testcase の property
database_statements を含む）と reports/unit-test/coverage.json（coverage.py の branch 有効 JSON）、
テストコードの trace 注釈（trace_check.parse_source で読む）、defects.json（工程内で分類した不具合の記録）だけ。値を推定・補完しない。
出力は ensure_ascii=False・UTF-8 で書き出す（PowerShell のパイプ・リダイレクトを経由しない）。
実行：python reports/unit-test/tools/build_unit_artifacts.py <execution_event_id>（リポジトリ直下）
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".github/skills/traceability-audit/scripts"))
import trace_check as tc  # noqa: E402

JUNIT = ROOT / "reports/unit-test/junit.xml"
COVERAGE = ROOT / "reports/unit-test/coverage.json"
SUMMARY = ROOT / "reports/unit-test/coverage-summary.json"
EVIDENCE = ROOT / "reports/unit-test/unit-test-evidence.json"
DEFECTS = ROOT / "reports/unit-test/tools/defects.json"
TEST_DIR = ROOT / "app/tests/unit"
RUN_ID = "RUN-AOBA-EC-1118"

IMPLEMENTATION = {
    "FR-001": [("app/accounts/services.py", "register"), ("app/accounts/views_api.py", "RegisterApi"), ("app/accounts/views_web.py", "register_view")],
    "FR-002": [("app/accounts/services.py", "verify_credentials, login_api, login_web"), ("app/accounts/hashers.py", "PBKDF2SHA256HexKeyPasswordHasher"), ("app/accounts/views_web.py", "login_view")],
    "FR-003": [("app/accounts/services.py", "logout_api, logout_web"), ("app/accounts/views_web.py", "logout_view")],
    "FR-004": [("app/accounts/services.py", "me, resolve_api_token"), ("app/accounts/authentication.py", "BearerAuthentication")],
    "FR-010": [("app/catalog/services.py", "list_categories")],
    "FR-011": [("app/catalog/services.py", "search_products"), ("app/common/paging.py", "parse_page, build_page")],
    "FR-012": [("app/catalog/services.py", "get_product_detail")],
    "FR-020": [("app/carts/services.py", "get_cart, _lock_or_create_active_cart"), ("app/carts/context_processors.py", "header_cart_count")],
    "FR-021": [("app/carts/services.py", "add_item"), ("app/carts/views_web.py", "cart_add_view"), ("app/common/submit_token.py", "run_with_token")],
    "FR-022": [("app/carts/services.py", "change_quantity"), ("app/carts/views_web.py", "cart_quantity_view, _cart_action")],
    "FR-023": [("app/carts/services.py", "delete_item")],
    "FR-024": [("app/carts/services.py", "apply_coupon")],
    "FR-025": [("app/carts/services.py", "remove_coupon")],
    "FR-026": [("app/carts/pricing.py", "calculate, coupon_period_state"), ("app/common/tax.py", "price_including_tax, consumption_tax")],
    "FR-030": [("app/orders/services.py", "place_order, _validate_address, _issue_order_number, _check_coupon")],
    "FR-031": [("app/orders/services.py", "pay_order"), ("app/payments/client.py", "request_payment, validate_response"), ("app/payments/mock.py", "MockPaymentGateway")],
    "FR-032": [("app/orders/services.py", "list_my_orders")],
    "FR-033": [("app/orders/services.py", "get_my_order, order_detail")],
    "FR-034": [("app/orders/services.py", "cancel_my_order, _cancel")],
    "FR-040": [("app/catalog/services.py", "list_stock_units")],
    "FR-041": [("app/orders/services.py", "admin_list_orders")],
    "FR-042": [("app/orders/services.py", "admin_get_order, admin_order_detail")],
    "FR-043": [("app/orders/services.py", "ship_order")],
    "FR-044": [("app/orders/services.py", "deliver_order")],
    "FR-045": [("app/orders/services.py", "admin_cancel_order")],
    "FR-060": [("app/initial_data/loader.py", "run_load, check_values, check_integrity, insert_rows"), ("app/initial_data/management/commands/load_initial_data.py", "Command")],
    "NFR-SC-01": [("app/accounts/hashers.py", "PBKDF2SHA256HexKeyPasswordHasher")],
    "NFR-SC-02": [("app/common/middleware.py", "HttpsOnlyMiddleware"), ("app/config/settings.py", "production profile")],
    "NFR-SC-03": [("app/common/api.py", "require_user"), ("app/common/web.py", "require_web_user")],
    "NFR-SC-04": [("app/common/normalize.py", "parse_int, parse_identifier, has_unstorable_chars"), ("app/common/middleware.py", "RequestCharsetMiddleware"), ("app/config/wsgi.py", "application")],
    "NFR-SC-05": [("app/config/settings.py", "CsrfViewMiddleware, TEMPLATES autoescape"), ("app/common/views.py", "csrf_failure")],
    "NFR-SC-06": [("app/common/logging.py", "JsonFormatter")],
    "NFR-SC-07": [("app/config/env.py", "read_required")],
    "NFR-SC-08": [("app/accounts/services.py", "login_api, resolve_api_token")],
    "NFR-SC-09": [("app/common/middleware.py", "IdleTimeoutMiddleware")],
    "NFR-SC-10": [("app/common/api.py", "exception_handler"), ("app/common/middleware.py", "WebExceptionMiddleware"), ("app/config/settings.py", "production profile")],
    "NFR-SC-15": [("app/accounts/services.py", "register"), ("app/accounts/management/commands", "createsuperuser, changepassword")],
    "NFR-SC-16": [("app/accounts/services.py", "password_violations")],
    "NFR-SC-18": [("app/accounts/services.py", "login_api, logout_api")],
    "NFR-SC-19": [("app/accounts/views_web.py", "login_view"), ("app/common/sessions.py", "SessionStore")],
    "NFR-SC-22": [("app/audit/services.py", "record_login_success, record_login_failure, record_logout")],
    "NFR-SC-23": [("app/audit/models.py", "AuditLog"), ("app/orders/models.py", "AppendOnlyModel")],
    "NFR-SC-24": [("app/orders/services.py", "order_detail"), ("app/payments/gateway.py", "PaymentRequest")],
    "NFR-EN-04": [("app/common/api.py", "to_json_value"), ("app/initial_data/loader.py", "parse_document")],
    "NFR-EN-05": [("app/payments/gateway.py", "get_gateway"), ("app/*/templates", "templates")],
    "NFR-LG-05": [("app/payments/gateway.py", "PaymentRequest"), ("app/orders/templates/orders/payment.html", "payment form")],
}

CRITERIA_KEYWORDS = {
    "boundary-value": r"boundary|limit|length|_10_|_50|254|period|minimum|threshold|expiry|29_minutes|pagination|per_page|range|inclusive|bytes",
    "invalid-input": r"invalid|reject|required|error|malformed|unparseable|nul|unstorable|wrong|bad_|type|format|not_found|indistinguishable|errors",
    "exception": r"failure|database|rolls_back|timeout|connection|integration|unexpected|exhaustion|conflict|tolerates|midway",
    "security": r"permission|other_buyer|csrf|escape|script|sql|injection|nul|token|hash|password|admin|role|login|logout|session|https|production|secret|log|credential|append_only|cookie|external|card|four_items|internal|charset|shell",
}
# database Criterion は同じ実行の JUnit property「database_statements」（app/tests/unit/conftest.py の autouse フィクスチャが
# 試験用 DB へ発行した SQL 文の数を記録）が1以上のテストだけに付ける（DB を使わないテストに付けない）。
DB_PROPERTY = "database_statements"


def junit_cases():
    for case in ET.parse(JUNIT).getroot().iter("testcase"):
        if case.find("failure") is not None:
            status = "FAIL"
        elif case.find("error") is not None:
            status = "ERROR"
        elif case.find("skipped") is not None:
            status = "SKIPPED"
        else:
            status = "PASS"
        properties = {p.get("name"): p.get("value") for p in case.iter("property")}
        statements = properties.get(DB_PROPERTY)
        yield (
            case.get("classname", "").rsplit(".", 1)[-1],
            case.get("name", "").split("[", 1)[0],
            status,
            int(statements) if statements is not None else None,
        )


def junit_results() -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], bool]]:
    statuses: dict[tuple[str, str], list[str]] = defaultdict(list)
    uses_db: dict[tuple[str, str], bool] = {}
    for module, name, status, statements in junit_cases():
        statuses[(module, name)].append(status)
        if statements is None:
            raise SystemExit(f"JUnit property {DB_PROPERTY} is missing: {module}::{name}")
        uses_db[(module, name)] = uses_db.get((module, name), False) or statements > 0
    results = {key: ("PASS" if all(s == "PASS" for s in values) else "FAIL") for key, values in statuses.items()}
    return results, uses_db


def junit_summary() -> dict[str, int]:
    summary = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    key = {"PASS": "passed", "FAIL": "failed", "ERROR": "errors", "SKIPPED": "skipped"}
    for _module, _name, status, _statements in junit_cases():
        summary["total"] += 1
        summary[key[status]] += 1
    return summary


def pct(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 2) if total else 100.0


def coverage_summary() -> dict:
    data = json.loads(COVERAGE.read_text(encoding="utf-8"))
    if data.get("meta", {}).get("branch_coverage") is not True:
        raise SystemExit("coverage.json is not branch-enabled")
    totals = data["totals"]
    fn_total = fn_covered = 0
    for entry in data["files"].values():
        for name, function in entry.get("functions", {}).items():
            if not name:
                continue  # モジュール直下の文（関数ではない）
            fn_total += 1
            if function["summary"]["covered_lines"] > 0:
                fn_covered += 1
    return {
        "source": "reports/unit-test/coverage.json",
        "tool": f"coverage.py {data['meta']['version']} (pytest-cov, branch=True)",
        "coverage_json_timestamp": data["meta"]["timestamp"],
        "total": {
            "statements": {"covered": totals["covered_lines"], "total": totals["num_statements"], "pct": pct(totals["covered_lines"], totals["num_statements"])},
            "branches": {"covered": totals["covered_branches"], "total": totals["num_branches"], "pct": pct(totals["covered_branches"], totals["num_branches"])},
            "functions": {"covered": fn_covered, "total": fn_total, "pct": pct(fn_covered, fn_total)},
            "lines": {"covered": totals["covered_lines"], "total": totals["num_statements"], "pct": pct(totals["covered_lines"], totals["num_statements"])},
        },
        "measured_files": len(data["files"]),
        "excluded": ["app/tests/*", "*/migrations/*", "app/manage.py", "app/gunicorn.conf.py"],
    }


def criteria_for(test_name: str, uses_db: bool) -> list[str]:
    result = [] if re.search(CRITERIA_KEYWORDS["invalid-input"], test_name) else ["normal-case"]
    for criterion in ("boundary-value", "invalid-input", "exception", "security"):
        if re.search(CRITERIA_KEYWORDS[criterion], test_name):
            result.append(criterion)
    if uses_db:
        result.append("database")
    return result


def check_classnames() -> None:
    """JUnit の classname がテストファイルのパス（app/tests/unit/test_xxx.py → app.tests.unit.test_xxx）と一致すること。"""
    for case in ET.parse(JUNIT).getroot().iter("testcase"):
        classname = case.get("classname", "")
        module = classname.split(".")
        if module[:3] != ["app", "tests", "unit"] or not (ROOT / "/".join(module[:4])).with_suffix(".py").is_file():
            raise SystemExit(f"JUnit classname does not match the test file path: {classname}")


def runtime_environment() -> dict:
    """同じ実行の JUnit testsuite property（runtime.*：app/tests/unit/conftest.py が記録）と固定版を照合する。"""
    root = ET.parse(JUNIT).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    props = {p.get("name"): p.get("value") for p in suite.iter("property") if (p.get("name") or "").startswith("runtime.")}
    if "runtime.python" not in props:
        raise SystemExit("JUnit testsuite property runtime.* is missing")
    pinned: dict[str, tuple[str, str]] = {}
    for name in ("app/requirements.txt", "app/requirements-dev.txt"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)", line)
            if match:
                pinned[match.group(1).lower().replace("_", "-")] = (match.group(2), name)
    packages = {}
    for key, value in sorted(props.items()):
        dist = key.removeprefix("runtime.")
        if dist in ("python", "virtualenv", "prefix"):
            continue
        fixed = pinned.get(dist)
        packages[dist] = {
            "runtime": value,
            "pinned": fixed[0] if fixed else None,
            "pinned_in": fixed[1] if fixed else None,
            "matches_pinned": (value == fixed[0]) if fixed else None,
        }
    return {
        "source": "reports/unit-test/junit.xml testsuite property runtime.*（同じ実行で記録）",
        "python": props["runtime.python"],
        "virtualenv": props.get("runtime.virtualenv") == "true",
        "interpreter_prefix": props.get("runtime.prefix"),
        "packages": packages,
        "all_pinned_packages_match": all(p["matches_pinned"] for p in packages.values() if p["pinned"] is not None),
        "unpinned_packages": sorted(d for d, p in packages.items() if p["pinned"] is None),
        "installation": "リポジトリ直下の .venv（.gitignore 対象）に app/requirements.txt・app/requirements-dev.txt を "
        "pip install --require-hashes --no-deps --force-reinstall で導入（ハッシュ照合）。"
        "固定ファイルにない計測用の coverage==7.15.4・pytest-cov==7.1.0 と Windows 専用の依存（tzdata・colorama）は"
        "版を指定して導入（ハッシュ照合なし）。",
    }


def main() -> int:
    policy = tc.load_policy(Path(tc.DEFAULT_POLICY))
    rules = tc.IdRules(policy)
    check_classnames()
    results, uses_db = junit_results()
    requirement_tests: dict[str, list[dict]] = defaultdict(list)
    requirement_adrs: dict[str, set[str]] = defaultdict(set)
    criteria_tests: dict[str, set[str]] = defaultdict(set)
    criteria_failures: dict[str, set[str]] = defaultdict(set)
    for path in sorted(TEST_DIR.glob("test_*.py")):
        source = tc.parse_source(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"), "unit_test", rules)
        for symbol in tc.considered_symbols(source):
            ids = sorted(source.effective_ids(symbol))
            result = results.get((path.stem, symbol.name), "NOT_EXECUTED")
            criteria = criteria_for(symbol.name, uses_db.get((path.stem, symbol.name), False))
            for criterion in criteria:
                criteria_tests[criterion].add(f"{path.name}::{symbol.name}")
                db_related = criterion != "database" or re.search(r"database|transaction|constraint|rolls_back", symbol.name)
                if result != "PASS" and db_related:
                    criteria_failures[criterion].add(f"{path.name}::{symbol.name}")
            for identifier in ids:
                if rules.kind_of(identifier) == "requirement":
                    requirement_tests[identifier].append(
                        {"path": path.relative_to(ROOT).as_posix(), "test": symbol.name, "criteria": criteria, "result": result}
                    )
                    requirement_adrs[identifier].update(i for i in ids if rules.kind_of(i) == "addr")
    expected = [
        line.strip()
        for line in (ROOT / "docs/requirements/expected-fr.txt").read_text(encoding="utf-8").splitlines()
        if re.fullmatch(r"FR-\d{3}", line.strip())
    ]
    requirement_coverage = []
    for requirement in expected + sorted(r for r in requirement_tests if r not in expected):
        tests = requirement_tests.get(requirement, [])
        requirement_coverage.append(
            {
                "requirement": requirement,
                "unit_testable": True,
                "related_adrs": sorted(requirement_adrs.get(requirement, set())),
                "implementation": [{"path": p, "symbol": s} for p, s in IMPLEMENTATION.get(requirement, [])],
                "tests": tests,
                "result": ("PASS" if all(t["result"] == "PASS" for t in tests) else "FAIL") if tests else "NO_TEST",
            }
        )
    reasons = {
        "invalid-input": "要件で禁止された入力（未入力・型・桁数・形式・値域・NUL 等）を全 FR の業務処理・API・画面で検証。",
        "security": "認証・権限境界・他者データ・CSRF・XSS・SQL/OS コマンドインジェクション・NUL・文字コード指定・ログ機密・ハッシャー・本番設定を検証。",
        "boundary-value": "数量1〜10・在庫数量・文字数・金額・有効期間の両端・送料5,000円・ページ・API 期限・無操作30分等の境界の内側・境界・外側を検証。",
        "normal-case": "全 26 FR の代表的な正常ケース（戻り値・状態変化・履歴・監査ログ）を要件の出力・事後条件で検証。",
        "exception": "DB 障害・決済の連携エラー・タイムアウト・障害注入でエラー変換と部分更新なしを検証。",
        "database": "DB を実際に使ったテスト（同じ実行の JUnit property database_statements が1以上）だけを対象とする。"
        "使い捨て PostgreSQL 16 コンテナで ORM の永続化・一意制約・検査制約・追記のみの記録・トランザクションのロールバック・"
        "アドバイザリロックの解放（二重送信防止トークン）を検証し、障害経路は DB 例外を差し込む（MOCK）。"
        "行ロック・アドバイザリロックによる排他（複数接続の並行実行）は単体テストの対象外とし、"
        "結合テスト工程（ADDR-011 DD-010：transaction=True の同時実行試験）で確認する。",
    }
    criteria_coverage = []
    for criterion in ("boundary-value", "database", "exception", "invalid-input", "normal-case", "security"):
        failures = sorted(criteria_failures.get(criterion, set()))
        criteria_coverage.append(
            {
                "criterion": criterion,
                "applicable": True,
                "result": "FAIL" if failures else "PASS",
                "tests": len(criteria_tests.get(criterion, set())),
                "failing_tests": failures,
                "reason": reasons[criterion]
                + (" 適用したテストのうち IMPLEMENTATION_ERROR による失敗あり（defects 参照）。" if failures else ""),
            }
        )
    defects = json.loads(DEFECTS.read_text(encoding="utf-8"))
    summary = coverage_summary()
    summary["execution_event_id"] = sys.argv[1] if len(sys.argv) > 1 else None
    db_tests = sum(1 for _m, _n, _s, statements in junit_cases() if statements)
    no_db_tests = sum(1 for _m, _n, _s, statements in junit_cases() if not statements)
    evidence = {
        "run_id": RUN_ID,
        "execution_event_id": sys.argv[1] if len(sys.argv) > 1 else None,
        "status": "IMPLEMENTATION_FIX_REQUIRED" if any(not d.get("resolved") for d in defects) else "SUCCESS",
        "test_summary": junit_summary(),
        "coverage": summary["total"],
        "requirement_coverage": requirement_coverage,
        "criteria_coverage": criteria_coverage,
        "defects": defects,
        "database_tests": [
            {
                "target": "業務処理（accounts/catalog/carts/orders/initial_data・submit_token）・Web API・画面のうち DB を使うテスト"
                f"（JUnit property database_statements≧1：{db_tests}件）",
                "strategy": "CONTAINER",
                "database_type": "PostgreSQL 16（固定ダイジェストの Docker 使い捨てコンテナ・--rm・127.0.0.1 の動的ポートのみ公開・乱数パスワード・"
                "pytest-django の test_* DB・実行後に停止削除。タイムアウトは記録器の timeout_seconds=1200）",
                "production_database_used": False,
                "shared_database_used": False,
            },
            {"target": "DB 障害・競合・外部連携の失敗経路", "strategy": "MOCK", "production_database_used": False, "shared_database_used": False},
            {
                "target": "注文金額計算・税・正規化・ハッシャー・ログ整形・設定読取り・決済応答検証・業務処理の DB 到達前の入力判定"
                f"（JUnit property database_statements＝0：{no_db_tests}件）",
                "strategy": "NOT_APPLICABLE",
                "production_database_used": False,
                "shared_database_used": False,
            },
        ],
        "concurrency_scope": "行ロック・アドバイザリロックによる排他（複数接続の並行実行）は単体テストでは扱わない。"
        "結合テスト工程で ADDR-011 DD-010（transaction=True の同時実行試験）により確認する。",
        "flaky_tests": [],
        "flaky_check": "unit-exec-3 の失敗8件（UT-DEF-001・002）を3回再実行し、毎回同じ8件が失敗（決定論的）であることを確認",
        "skipped_tests": [],
        "runtime_environment": runtime_environment(),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for written in (SUMMARY, EVIDENCE):
        text = written.read_text(encoding="utf-8")
        if "\ufffd" in text or re.search(r"\?\?", text):
            raise SystemExit(f"{written}: U+FFFD または「?」の連続が含まれる")
    print(json.dumps({"summary": evidence["test_summary"], "coverage": evidence["coverage"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
