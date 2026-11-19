"""Step 13〜18：Coverage 比較・Initial Coverage Metrics の保存・Gap 分析・GAP_FILL・最終計画の作成。

python reports/integration-test/tools/build_plan.py

- AI INITIAL は固定済みの ai-initial-cases.json から読む（definitions を再評価しない）。
- External は external-test-cases.normalized.json（今回はユーザーの明示選択により未提供）。
- initial-coverage-metrics.json は GAP_FILL 追加前の値として初回だけ書き、以後は上書きしない（Step 15）。
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from definitions_gap_fill import build_cases as build_gap_fill  # noqa: E402
from required_coverage import (  # noqa: E402
    KEY_BY_ID,
    REQUIRED_COVERAGE,
    REVISION1_IDS,
    REVISION2_IDS,
    REVISION3_IDS,
    REVISION4_IDS,
    REVISION5_IDS,
)

OUT = HERE.parent
RUN_ID = "RUN-AOBA-EC-1118"


def read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pct(part: int, whole: int) -> float:
    return 100.0 if whole == 0 else round(part / whole * 100.0, 2)


def main() -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    previous_required = read("required-coverage.json")
    previous_revision2_at = next(
        (r["recorded_at"] for r in previous_required.get("revisions", []) if r.get("revision") == 2), now
    )
    # cycle=3/3 は Required Coverage を変更しない（Revision 3 の記録時刻・改訂時刻を維持する）
    previous_revision3_at = next(
        (r["recorded_at"] for r in previous_required.get("revisions", []) if r.get("revision") == 3), now
    )
    previous_revision4_at = next(
        (r["recorded_at"] for r in previous_required.get("revisions", []) if r.get("revision") == 4), now
    )
    previous_revision5_at = next(
        (r["recorded_at"] for r in previous_required.get("revisions", []) if r.get("revision") == 5), now
    )
    write(
        "required-coverage.json",
        {
            "run_id": RUN_ID,
            "generated_at": previous_required.get("generated_at"),
            "revised_at": previous_required.get("revised_at") or now,
            "source": "docs/requirements（FR・CMN・UC の AC・NFR）、docs/addr ADDR-001〜014（ACTIVE）、Steering",
            "derived_from_cases": False,
            "revisions": [
                {
                    "revision": 1,
                    "recorded_at": "2026-11-19T14:11:39+00:00",
                    "coverage_ids": f"{REVISION1_IDS[0]}〜{REVISION1_IDS[-1]}（{len(REVISION1_IDS)}件）",
                    "basis": "要件・ADDR から AI INITIAL 生成前に作成。Initial Coverage Metrics（initial-coverage-metrics.json）の基準",
                },
                {
                    "revision": 2,
                    "recorded_at": previous_revision2_at,
                    "coverage_ids": f"{REVISION2_IDS[0]}〜{REVISION2_IDS[-1]}（{len(REVISION2_IDS)}件）",
                    "basis": "INTEGRATION_TEST Scope Assurance（Quality QR-IT-1118-001〜004、Traceability C10 の NFR 92件）の指摘を受け、"
                    "UC の AC・NFR の測定条件・ADDR の検証方法から欠落していた観点を追加（ケースから逆算していない）。"
                    "結合試験で検証できない NFR は Required Coverage に含めず nfr-verification-scope.json に未検証として記録",
                    "trigger": "TEST_ERROR 修正 cycle=1/3（RUN-AOBA-EC-1118）",
                },
                {
                    "revision": 3,
                    "recorded_at": previous_revision3_at,
                    "coverage_ids": f"{REVISION3_IDS[0]}〜{REVISION3_IDS[-1]}（{len(REVISION3_IDS)}件）",
                    "basis": "Quality QR-IT-1118-R1-001 を受け、NFR-US-10「処理が完了するまでの間」の繰り返し操作と ADDR-004 4.4 の"
                    "検証方法（画面の処理中の繰り返し操作、先着が E-002-02・E-031-08 で終わる間、先着が結果の記録前に中断した場合）・"
                    "テスト行（複数の接続・スレッドから実際に同時要求）から、処理中の同一送信トークンの到着の観点を追加（ケースから逆算していない）",
                    "trigger": "TEST_ERROR 修正 cycle=2/3（RUN-AOBA-EC-1118）",
                },
                {
                    "revision": 4,
                    "recorded_at": previous_revision4_at,
                    "coverage_ids": f"{REVISION4_IDS[0]}〜{REVISION4_IDS[-1]}（{len(REVISION4_IDS)}件）",
                    "basis": "FULL Traceability C10（NFR 60件にテスト到達なし：NOT_VERIFIED 48・NOT_APPLICABLE 12）の差し戻しを受け、"
                    "60件の要件本文・測定条件・検証方法・根拠を読み直し、(a)「該当なし」の根拠の前提（機能・処理・接続が無いこと）を"
                    "コード・URL・設定の不存在として確かめられるもの、(b) 構成・設定レビュー／静的解析を検証方法とし、リポジトリ内の"
                    "起動定義・依存の固定・設定値・手順書・ソースコードから一部を確かめられるもの、(c) 対応方針の一部を API・DB で"
                    "確かめられるものを追加（ケースから逆算していない。本番環境・運用・負荷・ブラウザ・法令判断に依存する部分は含めない）",
                    "trigger": "FULL Traceability C10 の差し戻し UNRESOLVED-e1d9dfe900863622 修正 cycle=1/3（RUN-AOBA-EC-1118）",
                },
                {
                    "revision": 5,
                    "recorded_at": previous_revision5_at,
                    "coverage_ids": f"{REVISION5_IDS[0]}〜{REVISION5_IDS[-1]}（{len(REVISION5_IDS)}件）",
                    "basis": "cycle=1/3 の後も FULL Traceability C10 で要件→テスト未到達の NFR 38件の要件本文・測定条件・検証方法・"
                    "代替確認を読み直し、cycle=1/3 で検討しなかった観点として、(d) 開発環境の PC（Windows 11）とインストール済みの"
                    "ブラウザ・使い捨て PostgreSQL 16 で測定条件に沿って行える参考計測・操作確認、(e) 開発時の公開脆弱性情報との照合、"
                    "(f) Production Code・設定・起動定義から機械的に確かめられる前提を追加（ケースから逆算していない。本番環境・運用記録・"
                    "運用体制・法令判断・診断ツールによる診断は含めない）",
                    "trigger": "FULL Traceability C10 の差し戻し UNRESOLVED-e1d9dfe900863622 修正 cycle=2/3（RUN-AOBA-EC-1118）",
                },
            ],
            "required_coverage": REQUIRED_COVERAGE,
        },
    )
    required = REQUIRED_COVERAGE
    initial_doc = read("ai-initial-cases.json")
    initial = initial_doc["cases"]
    external_doc = read("external-test-cases.normalized.json")
    external = external_doc["cases"]
    keys = [item["coverage_key"] for item in required]
    key_set = set(keys)

    def covered(cases: list[dict]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for case in cases:
            for key in case.get("coverage_keys", []):
                result.setdefault(key, []).append(case["case_id"])
        return result

    ai_initial_map = covered(initial)
    external_map = covered(external)
    ai_initial = set(ai_initial_map) & key_set
    ext = set(external_map) & key_set
    common = ai_initial & ext
    ai_only = ai_initial - ext
    external_only = ext - ai_initial
    missing = key_set - (ai_initial | ext)

    initial_metrics = {
        "required": len(key_set),
        "common": len(common),
        "ai_only": len(ai_only),
        "external_only": len(external_only),
        "missing": len(missing),
        "ai_initial_coverage_rate": pct(len(ai_initial), len(key_set)),
        "external_coverage_rate": pct(len(ext), len(key_set)) if external else None,
        "combined_initial_coverage_rate": pct(len(ai_initial | ext), len(key_set)),
    }
    rev1_keys = {item["coverage_key"] for item in required if item["revision"] == 1}
    rev1_initial = ai_initial & rev1_keys
    rev1_metrics = {
        "required": len(rev1_keys),
        "common": len(rev1_initial & ext),
        "ai_only": len(rev1_initial - ext),
        "external_only": len((ext & rev1_keys) - ai_initial),
        "missing": len(rev1_keys - (ai_initial | ext)),
        "ai_initial_coverage_rate": pct(len(rev1_initial), len(rev1_keys)),
        "external_coverage_rate": pct(len(ext & rev1_keys), len(rev1_keys)) if external else None,
        "combined_initial_coverage_rate": pct(len(rev1_keys & (ai_initial | ext)), len(rev1_keys)),
    }
    metrics_file = OUT / "initial-coverage-metrics.json"
    if not metrics_file.exists():
        write(
            "initial-coverage-metrics.json",
            {
                "run_id": RUN_ID,
                "recorded_at": now,
                "recorded_before_gap_fill": True,
                "ai_initial_case_count": len(initial),
                "external_case_count": len(external),
                "external_input": {"provided": False, "user_confirmed_without_external_cases": True},
                "initial_metrics": initial_metrics,
                "missing_coverage_ids": [i["coverage_id"] for i in required if i["coverage_key"] in missing],
            },
        )
    saved = json.loads(metrics_file.read_text(encoding="utf-8"))["initial_metrics"]
    if saved != rev1_metrics:
        raise SystemExit("Revision 1 の Initial Coverage Metrics が保存値と一致しない（INITIAL・External の変更を検出）。")

    gap_fill = build_gap_fill(KEY_BY_ID)
    gap_map = covered(gap_fill)
    final_covered = ai_initial | ext | (set(gap_map) & key_set)
    final_missing = key_set - final_covered
    supplemental = []
    for case in gap_fill:
        declared = [
            (cid, key) for cid, key in zip(case["coverage_ids"], case["coverage_keys"], strict=True) if key not in missing
        ]
        if not declared:
            continue
        supplemental.append(
            {
                "case_id": case["case_id"],
                "coverage_ids": [cid for cid, _ in declared],
                "reason": case["notes"],
                "initially_declared_by": sorted({i for _, key in declared for i in ai_initial_map.get(key, [])}),
            }
        )

    by_key = {item["coverage_key"]: item for item in required}
    gaps = []
    for index, key in enumerate(k for k in keys if k in missing):
        item = by_key[key]
        gaps.append(
            {
                "gap_id": f"GAP-{index + 1:03d}",
                "required_coverage_revision": item["revision"],
                "coverage_id": item["coverage_id"],
                "coverage_key": key,
                "requirement_id": item["requirement_id"],
                "related_adr": item["related_adr"],
                "criterion": item["criterion"],
                "missing": item["expected_behavior"],
                "ai_initial": "NOT_COVERED",
                "external": "NOT_PROVIDED",
                "filled_by_gap_fill_cases": gap_map.get(key, []),
            }
        )

    comparison_items = []
    for key in keys:
        if key in common:
            label = "COMMON"
        elif key in ai_only:
            label = "AI_ONLY"
        elif key in external_only:
            label = "EXTERNAL_ONLY"
        else:
            label = "MISSING"
        comparison_items.append(
            {
                "coverage_id": by_key[key]["coverage_id"],
                "coverage_key": key,
                "requirement_id": by_key[key]["requirement_id"],
                "criterion": by_key[key]["criterion"],
                "classification": label,
                "ai_initial_cases": ai_initial_map.get(key, []),
                "external_cases": external_map.get(key, []),
                "gap_fill_cases": gap_map.get(key, []),
            }
        )
    write(
        "case-comparison.json",
        {
            "run_id": RUN_ID,
            "generated_at": now,
            "basis": "Required Coverage に対する AI INITIAL と External の比較（GAP_FILL は比較対象外で別欄）",
            "external_input": {"provided": False, "user_confirmed_without_external_cases": True},
            "summary": {
                "required": len(key_set),
                "common": len(common),
                "ai_only": len(ai_only),
                "external_only": len(external_only),
                "missing": len(missing),
            },
            "items": comparison_items,
        },
    )

    write(
        "coverage-gap-report.json",
        {
            "run_id": RUN_ID,
            "generated_at": now,
            "initial_metrics": initial_metrics,
            "initial_metrics_basis": f"Required Coverage Revision 5（{REVISION1_IDS[0]}〜{REVISION5_IDS[-1]}、{len(key_set)}件）に対する、"
            "固定済み AI INITIAL（61件）と External（未提供）の分類",
            "initial_metrics_revision1_frozen": {
                "source": "reports/integration-test/initial-coverage-metrics.json（Gap Fill 前に保存、変更しない）",
                "metrics": rev1_metrics,
                "note": "Revision 1 の AI INITIAL Coverage Rate 90.38% には、INITIAL の宣言が一部条件を検証していなかった "
                "RC-036・RC-038・RC-039（GF-010・GF-011 で補完）、RC-063・RC-084・RC-085（GF-019〜GF-021 で補完）、"
                "RC-091（GF-018 で補完）の過大宣言分が含まれる（値は変更しない）",
            },
            "final_metrics": {
                "covered": len(final_covered),
                "missing": len(final_missing),
                "final_coverage_rate": pct(len(final_covered), len(key_set)),
                "ai_gap_fill_case_count": len(gap_fill),
            },
            "gaps": gaps,
            "supplemental_gap_fill": supplemental,
            "required_coverage": required,
        },
    )

    plan_cases = list(initial) + list(external) + gap_fill
    write(
        "integration-test-plan.json",
        {
            "run_id": RUN_ID,
            "generated_at": now,
            "status": "FINAL",
            "external_input": {"provided": False, "user_confirmed_without_external_cases": True},
            "revision": {
                "plan_event": "it-plan-8",
                "reason": "FULL Traceability C10 の差し戻し（UNRESOLVED-e1d9dfe900863622、修正 cycle=2/3）：cycle=1/3 の後も未到達の"
                "NFR 38件を再評価し、Required Coverage Revision 5（RC-149〜RC-163）と AI GAP_FILL GF-059〜GF-073 を追加。開発環境の PC"
                "（Windows 11・Edge/Chrome）と使い捨て PostgreSQL 16 で測定条件に沿った参考計測・操作確認、開発時の公開脆弱性情報との照合、"
                "Production Code・設定・起動定義の機械確認を行い、いずれも PARTIAL_IT（合格扱いにしない）。検証したケースの要件 ID だけを"
                " trace に付与。AI INITIAL・既存ケースの判定・期待値は変更しない",
                "history": [
                    "it-plan-3（cycle=1/3：QR-IT-1118-001〜006、SR-IT-R1-001、Traceability C10。Revision 2、GF-012〜GF-038）",
                    "it-plan-4（cycle=2/3：QR-IT-1118-R1-001。Revision 3、GF-039〜GF-043、GF-034 の前提を逐次再送に修正）",
                    "it-plan-5（cycle=3/3：QR-IT-1118-R2-001。GF-034 の title・docstring と GF-002 の注記の修正）",
                    "it-plan-6（UNRESOLVED-e1d9dfe900863622 cycle=1/3：NFR 60件の再評価。Revision 4、GF-044〜GF-058）",
                    "it-plan-7（UNRESOLVED-e1d9dfe900863622 cycle=2/3：NFR 38件の再評価。Revision 5、GF-059〜GF-073。正式実行 it-exec-6 で"
                    "GF-062 の TEST_ERROR（仮想利用者のクーポン適用状態の同期漏れ）を検出）",
                    "it-plan-8（cycle=2/3：GF-062 の試験コードを修正した後の再実行 it-exec-7 の直前。計画のケース・期待値は it-plan-7 と同じ）",
                ],
                "nfr_verification_scope": "reports/integration-test/nfr-verification-scope.json",
            },
            "sources": {
                "ai_initial": "reports/integration-test/ai-initial-cases.json（固定、experiment snapshot it-initial-1）",
                "external": "reports/integration-test/external-test-cases.normalized.json（未提供・ユーザー明示選択）",
                "ai_gap_fill": "reports/integration-test/tools/definitions_gap_fill.py",
                "required_coverage": "reports/integration-test/required-coverage.json",
            },
            "environment": {
                "database": "使い捨て PostgreSQL 16（Docker、127.0.0.1 のみ公開、tmpfs、statement/lock/idle タイムアウト、終了時に停止・削除）。pytest-django が test_ で始まる試験用 DB を作成・破棄",
                "runner": ".venv の固定版依存（Django 5.2.19・DRF 3.18.3・psycopg 3.3.9・pytest 9.2.0・pytest-django 4.14.0）、python -m pytest -c app/pytest.ini --rootdir=. app/tests/integration",
                "concurrency": "複数接続の同時実行試験は ADDR-011 DD-010 に従い transaction=True。逐次順序の固定は注文行を別接続で"
                "ロックし、2要求が行ロック待ち（pg_stat_activity）に入ってから解放する。注文番号の確定順はコミット時刻"
                "（track_commit_timestamp=on）で判定",
                "wsgi": "charset＋クエリ等の WSGI 入口経路は config.wsgi.application を直接呼ぶ",
                "external_services": "模擬決済はプロセス内（外部通信なし）",
                "browser": "GF-059・GF-060・GF-062：開発環境の PC（Windows 11）にインストール済みの Microsoft Edge・Google Chrome を"
                "ヘッドレスで起動し CDP で操作（一時プロファイル、背景通信を停止、終了時にプロセス停止・プロファイル削除）。live_server"
                "（Django の試験用サーバー、127.0.0.1）",
                "load": "GF-062・GF-063：live_server へ HTTP で要求する仮想利用者のスレッド（同じ PC。DIF-09）。資源使用量は試験プロセスと"
                "DB コンテナ（docker stats）",
                "backup": "GF-072・GF-073：DB コンテナ内の pg_dump・pg_restore・psql（ローカル接続、試験用 DB だけ。認証情報を渡さない）",
                "vulnerability_data": "GF-064：実行前に tools/fetch_dependency_vulns.py が OSV・PyPI から取得した照合結果"
                "（dependency-vulnerability-osv.json）。pytest は外部へ接続しない",
            },
            "counts": {
                "ai_initial": len(initial),
                "ai_gap_fill": len(gap_fill),
                "external": len(external),
                "total": len(plan_cases),
            },
            "cases": plan_cases,
        },
    )
    print(json.dumps({"initial": initial_metrics, "final_missing": len(final_missing), "cases": len(plan_cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
