"""受け入れ試験の共通フィクスチャと結果収集フック。

人間が事前作成した HUMAN_ACCEPTANCE_TEST_SPEC
(movie-ec-acceptance-test-cases.json) を AGENT_DRIVEN で実行する。

各ケースは使い捨て in-memory SQLite 上でアプリ全体を構築し、
HTTP 境界から DB までを通した実挙動で expected_result を検証する（ADR-003）。
Production DB / Credential / Data は使用しない。

結果は PASS / FAIL / BLOCKED として reports/acceptance-test/ へ出力する。
FAIL / BLOCKED は測定結果であり、隠蔽・改変しない。
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.config import Settings
from app.main import create_app

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORT_DIR = _REPO_ROOT / "reports" / "acceptance-test"


def _test_settings() -> Settings:
    return Settings(
        secret_key="acceptance-test-secret-key-not-production",
        database_url="sqlite://",  # 使い捨て in-memory（StaticPoolで単一接続共有）
        session_cookie_name="session",
        cookie_secure=False,
        page_size=20,
    )


@pytest.fixture()
def app() -> Iterator[FastAPI]:
    application = create_app(_test_settings())
    try:
        yield application
    finally:
        application.state.engine.dispose()


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def raw_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def session_factory(app: FastAPI) -> sessionmaker[Session]:
    return app.state.session_factory


# --------------------------------------------------------------------------
# 結果収集（PASS / FAIL / BLOCKED）
# --------------------------------------------------------------------------

_results: dict[str, dict] = {}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "acceptance(case_id, requirement_id, requirement_type, title): "
        "受け入れ試験ケースのメタ情報を宣言する",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()
    marker = item.get_closest_marker("acceptance")
    if marker is None:
        return

    case_id = marker.kwargs["case_id"]
    entry = _results.setdefault(
        case_id,
        {
            "case_id": case_id,
            "requirement_id": marker.kwargs["requirement_id"],
            "requirement_type": marker.kwargs["requirement_type"],
            "title": marker.kwargs.get("title", ""),
            "result": "PASS",
            "duration_seconds": 0.0,
            "blocked_reason": "",
        },
    )

    # setup/teardown の失敗は実行不成立として BLOCKED（測定不能）。
    if report.when in ("setup", "teardown") and report.failed:
        entry["result"] = "BLOCKED"
        entry["blocked_reason"] = f"{report.when}_error"
        return

    if report.when == "call":
        entry["duration_seconds"] = round(report.duration, 4)
        if report.passed:
            # setup で既に BLOCKED になっていない限り PASS。
            if entry["result"] != "BLOCKED":
                entry["result"] = "PASS"
        elif report.failed:
            entry["result"] = "FAIL"
        elif report.skipped:
            entry["result"] = "BLOCKED"
            entry["blocked_reason"] = "skipped"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _results:
        return
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [_results[cid] for cid in sorted(_results)]

    csv_path = _REPORT_DIR / "acceptance-test-results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "case_id",
                "requirement_id",
                "requirement_type",
                "result",
                "duration_seconds",
                "blocked_reason",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r["case_id"],
                    r["requirement_id"],
                    r["requirement_type"],
                    r["result"],
                    r["duration_seconds"],
                    r["blocked_reason"],
                ]
            )

    total = len(rows)
    passed = sum(1 for r in rows if r["result"] == "PASS")
    failed = sum(1 for r in rows if r["result"] == "FAIL")
    blocked = sum(1 for r in rows if r["result"] == "BLOCKED")
    now = datetime.now(timezone.utc).astimezone().isoformat()

    md_path = _REPORT_DIR / "acceptance-summary.md"
    lines = [
        "# 受け入れ試験結果サマリ",
        "",
        f"- 実行日時: {now}",
        "- 入力仕様: movie-ec-acceptance-test-cases.json (HUMAN_ACCEPTANCE_TEST_SPEC)",
        "- 実行モード: AGENT_DRIVEN",
        "- 実行手段: FastAPI TestClient + in-memory SQLite（ADR-003）",
        "",
        "## 集計",
        "",
        f"- 総ケース数: {total}",
        f"- PASS: {passed}",
        f"- FAIL: {failed}",
        f"- BLOCKED: {blocked}",
        f"- PASS率(BLOCKED除外なし): {passed}/{total}",
        "",
        "## ケース別結果",
        "",
        "| case_id | requirement_id | type | result | duration(s) | title |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['case_id']} | {r['requirement_id']} | {r['requirement_type']} "
            f"| {r['result']} | {r['duration_seconds']} | {r['title']} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
