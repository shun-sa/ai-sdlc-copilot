"""結合試験の共通設定（フィクスチャ・ケース実行結果の記録）。

DB は pytest-django が作成・破棄する使い捨てテストDB（test_<DB_NAME>）だけを使う。
本番DB・本番データ・本番資格情報は使用しない（Integration Test Policy database 節）。
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = REPO_ROOT / "reports" / "integration-test" / "case-run-results.json"

_RESULTS: dict[str, dict] = {}


def pytest_configure(config):
    """結合試験ケースIDを対応づけるマーカーを登録する。"""
    config.addinivalue_line("markers", "case(case_id): 結合試験ケースIDとテストを対応づける")


def pytest_runtest_makereport(item, call):
    """ケースIDつきテストの実行結果（結果・所要時間・エラー内容）を収集する。"""
    marker = item.get_closest_marker("case")
    if marker is None:
        return
    case_id = str(marker.args[0])
    entry = _RESULTS.setdefault(
        case_id,
        {
            "case_id": case_id,
            "node_id": item.nodeid,
            "result": "PASS",
            "duration_sec": 0.0,
            "error_message": None,
        },
    )
    entry["duration_sec"] = round(entry["duration_sec"] + float(call.duration or 0.0), 3)
    if call.excinfo is None:
        return
    if call.excinfo.errisinstance(KeyboardInterrupt):
        return
    message = str(call.excinfo.value).strip().split("\n")[0][:500]
    if call.when == "call":
        entry["result"] = "FAIL"
    else:
        entry["result"] = "ERROR"
    entry["error_message"] = f"{call.when}: {call.excinfo.typename}: {message}"


def pytest_sessionfinish(session, exitstatus):
    """収集したケース実行結果を JSON へ書き出す。"""
    if not _RESULTS:
        return
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "exit_status": int(exitstatus),
        "cases": [_RESULTS[key] for key in sorted(_RESULTS)],
    }
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def api(client):
    """Django のテストクライアントを用いた API 呼び出し用クライアントを返す。"""
    from tests.integration import _helpers

    return _helpers.ApiClient(client)
