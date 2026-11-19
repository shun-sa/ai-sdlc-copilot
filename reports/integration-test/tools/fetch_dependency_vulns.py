"""依存ライブラリの既知の脆弱性情報と対応ブラウザの最新安定版を、開発時に公開情報源から取得して固定する（GF-064・GF-059 の入力）。

python reports/integration-test/tools/fetch_dependency_vulns.py

- Steering（Network / Access）：実行時は外部インターネットへ接続しない。依存パッケージ等の取得時のみ例外。本スクリプトは
  結合試験の実行前（開発時）に公開情報を取得するだけで、結合試験（pytest）とアプリケーションは外部へ接続しない。
- 送信するのはパッケージ名と版だけ（公開情報）。認証情報・リポジトリの内容・個人情報は送らない。
- 照合先：OSV（https://api.osv.dev。PyPI の公開脆弱性情報：GHSA・PYSEC 等）、PyPI JSON API（版の実在）、
  Google Chrome VersionHistory API・Microsoft Edge 更新情報 API（最新安定版。記録のみ）。
- ネットワークに接続できない場合は status=OFFLINE と理由を記録する（照合済みとして扱わない）。
- 出力：reports/integration-test/dependency-vulnerability-osv.json（UTF-8、ensure_ascii=False）。
"""

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "reports" / "integration-test" / "dependency-vulnerability-osv.json"
FILES = ("app/requirements.txt", "app/requirements-dev.txt")
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)")
TIMEOUT = 30


def _get(url: str) -> tuple[int, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "minicommerce-it/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, None


def _post(url: str, payload: dict) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "minicommerce-it/1.0"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _pins() -> tuple[list[dict], dict]:
    pins, hashes = [], {}
    for name in FILES:
        raw = (ROOT / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8").splitlines():
            matched = PIN.match(line)
            if matched:
                pins.append({"file": name, "name": matched.group(1).lower(), "version": matched.group(2)})
    return pins, hashes


def _latest_browsers() -> dict:
    result = {}
    try:
        status, data = _get(
            "https://versionhistory.googleapis.com/v1/chrome/platforms/win64/channels/stable/versions?pageSize=1"
        )
        result["chrome"] = data["versions"][0]["version"] if status == 200 and data else None
    except (OSError, KeyError, IndexError, ValueError) as exc:
        result["chrome"] = None
        result["chrome_error"] = type(exc).__name__
    try:
        status, data = _get("https://edgeupdates.microsoft.com/api/products?view=enterprise")
        stable = next(p for p in data if p.get("Product") == "Stable")
        versions = [
            r["ProductVersion"]
            for r in stable["Releases"]
            if r.get("Platform") == "Windows" and r.get("Architecture") == "x64"
        ]
        result["edge"] = max(versions, key=lambda v: tuple(int(x) for x in v.split("."))) if versions else None
    except (OSError, KeyError, StopIteration, ValueError, TypeError) as exc:
        result["edge"] = None
        result["edge_error"] = type(exc).__name__
    return result


def main() -> None:
    pins, hashes = _pins()
    now = datetime.now(UTC).isoformat(timespec="seconds")
    data = {
        "fetched_at": now,
        "purpose": "NFR-SC-11（依存ライブラリの既知の重大な脆弱性 CVSS 7.0以上 0件）の開発時の照合。リリース前の再照合（TASK-021）と"
        "コンテナイメージの OS パッケージの照合は対象外",
        "requirements_sha256": hashes,
        "sources": {
            "vulnerabilities": "https://api.osv.dev/v1/querybatch・/v1/vulns/{id}（OSV、PyPI エコシステム）",
            "package_exists": "https://pypi.org/pypi/{name}/{version}/json",
            "browsers": "Chrome VersionHistory API（win64 stable）・Microsoft Edge 更新情報 API（Stable・Windows x64）",
        },
        "packages": [],
    }
    try:
        batch = _post(
            "https://api.osv.dev/v1/querybatch",
            {"queries": [{"package": {"name": p["name"], "ecosystem": "PyPI"}, "version": p["version"]} for p in pins]},
        )
        details = {}
        for pin, result in zip(pins, batch["results"], strict=True):
            vulns = []
            for item in result.get("vulns", []):
                vid = item["id"]
                if vid not in details:
                    _, details[vid] = _get(f"https://api.osv.dev/v1/vulns/{vid}")
                detail = details[vid] or {}
                vulns.append(
                    {
                        "id": vid,
                        "aliases": detail.get("aliases", []),
                        "severity": detail.get("severity", []),
                        "database_specific_severity": (detail.get("database_specific") or {}).get("severity"),
                        "summary": detail.get("summary"),
                    }
                )
            status, _ = _get(f"https://pypi.org/pypi/{pin['name']}/{pin['version']}/json")
            data["packages"].append({**pin, "pypi_status": status, "vulns": vulns})
        data["browsers_latest_stable"] = _latest_browsers()
        data["status"] = "FETCHED"
    except (OSError, ValueError, KeyError) as exc:
        data["status"] = "OFFLINE"
        data["reason"] = f"{type(exc).__name__}: {exc}"
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": data["status"], "packages": len(data["packages"]),
                      "vulns": sum(len(p["vulns"]) for p in data["packages"]),
                      "browsers": data.get("browsers_latest_stable")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
