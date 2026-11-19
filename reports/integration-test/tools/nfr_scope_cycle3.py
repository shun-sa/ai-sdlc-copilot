"""UNRESOLVED-e1d9dfe900863622 修正 cycle=3/3（最終）の確認結果を nfr-verification-scope.json／.md に追記する（RUN-AOBA-EC-1118）。

python reports/integration-test/tools/nfr_scope_cycle3.py

- nfr_scope.py が生成した一覧（items・counts・summary・区分）は変更しない。区分・テスト・計画・ケースは変えず、
  FULL 監査（cycle=2/3 後）の C10 に残った NFR 13件について、要件本文・代替確認方法の最終確認と
  リポジトリ・開発環境の入力探索の結果だけを追記する（items[].reevaluation_cycle3 と final_confirmation_cycle3）。
- nfr_scope.py を再実行した場合は、本スクリプトを続けて実行する（冪等。md の cycle=3/3 節は置き換える）。
- 推測で合格扱いにしない。追記は区分を変えず、counts_as_quality_pass も変えない。
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = HERE.parents[2]
ISSUE = "UNRESOLVED-e1d9dfe900863622"
MD_HEADER = "## 修正 cycle=3/3（最終）の確認"

# 探索した成果物（リポジトリ・開発環境。過去 Run のブランチ・reports は参照しない）
EXPLORED = [
    {"path": "docs/requirements/non_functional_requirements.md",
     "finding": "13件の条文・測定条件・確認方法・根拠、6.2 監視対象（MON-01〜MON-10、ENV-02 のみ・ENV-01 は対象外）、"
                "12.x DIF-02〜DIF-05・DIF-07（ENV-01 は監視・バックアップ・運用体制を設けない）、NCN-03・NCN-09、"
                "NOQ-01〜NOQ-03（未着手）、NFR-OM-19（本番運用手順書は本番基盤の選定後に作成）"},
    {"path": "README.md",
     "finding": "ENV-01 向けの手順書のみ（冒頭に「本番運用手順書は本番基盤の選定後に作成します」と明記）。"
                "計画停止・周知・復旧・パッチ適用・有人運用時間・問い合わせ連絡経路の記載なし"},
    {"path": "compose.yaml",
     "finding": "ENV-01 の app・db の2サービス。db の healthcheck（pg_isready）は起動順序の制御（GF-050 で確認済み）で監視・通知ではない。"
                "db-data は名前付きボリュームでバックアップ・保管先・所在地の定義なし"},
    {"path": "app/Dockerfile, app/gunicorn.conf.py, app/config/settings.py, app/config/env.py, .env.example, .dockerignore",
     "finding": "監視・通知・死活確認用の要求先・バックアップ・保管先・所在地（リージョン）に関する設定なし"},
    {"path": "app/（tests 以外の Production Code・管理コマンド）",
     "finding": "死活確認専用の要求先、定期処理・バックアップ・通知の処理なし（定期処理なしは GF-044 で NFR-AV-01・PF-12 として確認済み）"},
    {"path": "docs/operations/dependency-inventory.md",
     "finding": "照合日・固定版・脆弱性照合（NFR-SC-11、GF-064）・サポート期限（NFR-EN-10、GF-052）の記録。"
                "パッチの確認頻度（月1回）・適用手順・公開日と適用日の記録は無い"},
    {"path": "docs/addr/ADDR-010.md, ADDR-013.md, ADDR-014.md",
     "finding": "監視・通知（NOQ-02）、本番基盤（NOQ-01）、稼働後のパッチ適用（NFR-OM-14）は対象外。"
                "本番運用手順書への記載は本番基盤の決定時（ADDR-014 の運用、ADDR-010 ASM-001）"},
    {"path": "docs/architecture/implementation-task-list.md",
     "finding": "13件とも実装 Task の割当なし（None／N/A：本番基盤・運用事項・要件で該当なし）。"
                "本番運用手順書（NFR-OM-19 後段）は本番基盤の選定後に作成"},
    {"path": ".github/（skills 以外）",
     "finding": "CI のワークフロー・依存更新の定期確認設定（dependabot 等）なし"},
]

# 各 NFR：要件本文の要旨・代替確認方法・探索結果・結論
C3 = {
    "NFR-AV-02": ("稼働率 99.0%以上（月単位、MON-01 の死活監視の記録で停止時間を判定。ENV-02）",
                  "構成・設定レビュー（NFR-AV-04・NFR-AV-05 の復旧手順が整備されていること）",
                  "MON-01 の監視設定・記録、復旧手順書はいずれもリポジトリに無い（NFR-OM-19 により本番運用手順書は本番基盤の選定後に作成）"),
    "NFR-AV-03": ("計画停止は毎月第2水曜 2:00〜4:00、月1回以内・2時間以内、7日前までに周知（周知は本システム外の静的ページ。ENV-02）",
                  "構成・設定レビュー（運用手順書に停止時間帯・周知手順が記載されていること）",
                  "運用手順書・計画停止の実績記録・周知ページはリポジトリに無い。計画停止以外に停止を要する定期処理が無いことは NFR-AV-01 の代替確認（GF-044）で、本要件の確認対象ではない"),
    "NFR-AV-05": ("RTO 6時間以内（検知から全画面・全 API の再開まで。ENV-02）",
                  "構成・設定レビュー（復旧手順書の手順と所要時間見積りが6時間以内であること）",
                  "復旧手順書・所要時間見積り・障害対応記録はリポジトリに無い。GF-072 のリストア時間は NFR-AV-12 の参考値で、検知・切り分け・基盤の復旧を含まず RTO の根拠にならない"),
    "NFR-AV-09": ("拠点・地域単位の障害時の業務再開（要否：否）。測定条件・確認方法とも「該当なし」",
                  "該当なし",
                  "根拠（災害時は電話・FAX 受注で代替：NCN-03）は業務上の前提で、システムの機能・設定として確かめられる対象が無い"),
    "NFR-AV-11": ("NFR-AV-04 のバックアップを本番 DB と同時に失われない場所に保管（保管期間7日）",
                  "構成・設定レビュー（バックアップの保管先の設定を確認）",
                  "保管先は本番基盤（NOQ-01 未着手）の設定。ENV-01 はバックアップの仕組みを設けない（DIF-03）。compose.yaml にバックアップ・保管先の定義なし"),
    "NFR-EN-06": ("本番のサーバー・DB・バックアップ・ログの保管先を日本国内に置く",
                  "構成・設定レビュー（本番基盤の選定・構築時に所在地を確認）",
                  "本番基盤（NOQ-01 未着手）が未選定で、所在地（リージョン等）の設定はリポジトリに無い。TZ=Asia/Tokyo（NFR-EN-04）は時刻の設定で所在地の根拠にならない"),
    "NFR-EN-13": ("機器・消費エネルギー（該当なし）",
                  "該当なし",
                  "根拠（本番基盤が未選定で当社設置機器の制約が無い：NOQ-01）は調達上の前提で、システムの機能・設定として確かめられる対象が無い"),
    "NFR-MG-06": ("移行期間の停止許容時間（該当なし）",
                  "該当なし",
                  "根拠（新規システムで停止する稼働中のサービスが無い、電話・FAX 受注は影響を受けない）は業務上の事実で、システムの機能・設定として確かめられる対象が無い"),
    "NFR-OM-08": ("有人運用時間 平日 9:00〜18:00（情報システム課 2名。時間帯外は未決 NOQ-03）",
                  "構成・設定レビュー（運用手順書に対応時間帯と連絡先が記載されていること）",
                  "運用手順書・連絡先・対応記録はリポジトリに無い（ENV-01 は運用体制を設けない：DIF-05）"),
    "NFR-OM-09": ("6.2 の監視対象・閾値（MON-01〜MON-10 の全項目）で本番環境を監視。ENV-01 は対象外",
                  "構成・設定レビュー（監視設定の一覧が 6.2 と一致すること）",
                  "監視ツール・監視設定は NOQ-02（未着手）でリポジトリに無い。アプリケーションに死活確認専用の要求先・監視設定は無い。監視の入力となるログ（LOG-02・LOG-03）は NFR-OM-11・OM-02 の範囲で、監視項目の実装率は確かめられない"),
    "NFR-OM-10": ("閾値超過の検知から通知が届くまで5分以内（ENV-02）",
                  "構成・設定レビュー（通知設定を確認）",
                  "通知手段・通知設定は NOQ-02（未着手）でリポジトリに無い"),
    "NFR-OM-14": ("セキュリティパッチを計画停止の時間帯に適用、CVSS 7.0以上は公開から30日以内に本番適用",
                  "構成・設定レビュー（運用手順書にパッチの確認頻度（月1回）と適用手順が記載されていること）",
                  "運用手順書・公開日と適用日の記録・定期確認の設定（CI・dependabot 等）はリポジトリに無い。dependency-inventory.md は照合日時点の版・脆弱性照合（NFR-SC-11、GF-064）とサポート期限（NFR-EN-10、GF-052）の記録で、確認頻度・適用手順・適用期間は確かめられない"),
    "NFR-OM-16": ("システム障害が疑われる問い合わせへの一次回答を受付から4時間以内（受付時間内の経過時間。ENV-02）",
                  "構成・設定レビュー（運用手順書に連絡経路・受付時間・回答期限が記載されていること）",
                  "運用手順書・連絡経路・対応記録はリポジトリに無い（問い合わせの受付は本システム外、DIF-05）"),
}

CONCLUSION = ("13件とも、リポジトリ・開発環境（ENV-01）で実施できる部分検証（設定・手順書・構成定義・計測）は残っていない。"
              "代替確認の対象（本番運用手順書・本番基盤の設定・監視/通知設定・運用記録）はリポジトリに存在せず、"
              "NFR-OM-19 により本番運用手順書は本番基盤の選定（NOQ-01〜NOQ-03 未着手）後に作成される。"
              "該当なし3件（NFR-AV-09・EN-13・MG-06）の根拠は業務・調達上の前提で、システムで確かめられる前提が無い。"
              "GAP_FILL の追加・テスト・計画の変更は行わず、区分（NOT_VERIFIED 10・NOT_APPLICABLE 3）を維持する。"
              "C10 の未到達 13件は修正ループ上限（3/3）到達後も解消しない未解決として親へ返す")


def main() -> None:
    path = OUT / "nfr-verification-scope.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    trace_path = ROOT / "reports/traceability/traceability-report.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    c10 = sorted(
        re.match(r"(\S+) を", item["message"]).group(1)
        for item in trace.get("issues", [])
        if item.get("check") == "C10" and item.get("message", "").startswith("NFR-")
    )
    if c10 != sorted(C3):
        raise SystemExit(f"cycle=3/3 の対象と FULL 監査の C10 の NFR が一致しない: {c10}")
    by_id = {i["requirement_id"]: i for i in data["items"]}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    per_item = []
    for nfr, (req, alt, found) in C3.items():
        item = by_id[nfr]
        if item["test_traceability_reached"] or item["status"] not in ("NOT_VERIFIED", "NOT_APPLICABLE"):
            raise SystemExit(f"{nfr}: 区分・到達状態が想定と異なる")
        item["reevaluation_cycle3"] = f"cycle=3/3（最終）：{found}。実施可能な部分検証なし"
        per_item.append({
            "requirement_id": nfr,
            "status_kept": item["status"],
            "requirement_text_summary": req,
            "alternative_check_method": alt,
            "exploration_result": found,
            "executable_partial_verification": False,
            "verify_in": item["verify_in"],
            "counts_as_quality_pass": item["counts_as_quality_pass"],
        })
    data["final_confirmation_cycle3"] = {
        "issue": ISSUE,
        "cycle": "3/3",
        "run_id": data["run_id"],
        "confirmed_at": now,
        "trigger_source": "reports/traceability/traceability-report.json（更新日時 "
        f"{datetime.fromtimestamp(trace_path.stat().st_mtime, UTC).isoformat(timespec='seconds')}）の C10 の NFR {len(c10)} 件",
        "target_ids": c10,
        "explored_artifacts": EXPLORED,
        "items": per_item,
        "gap_fill_added": False,
        "tests_or_plan_changed": False,
        "re_execution": "なし（テスト・計画を変更していないため。最終の正式実行・JUnit・実行版の記録は直前の it-exec のまま）",
        "conclusion": CONCLUSION,
        "unresolved_after_cycle3": c10,
        "note": "counts・summary・items の区分は nfr_scope.py の生成値のまま（counts.c10_nfr_count_at_trigger は cycle=2/3 の差し戻し時点の値）",
    }
    data["updated_at"] = now
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_path = OUT / "nfr-verification-scope.md"
    md = md_path.read_text(encoding="utf-8")
    md = md.split("\n" + MD_HEADER)[0].rstrip("\n") + "\n"
    lines = [
        "",
        MD_HEADER,
        "",
        f"- 対象: {ISSUE} の FULL 監査（cycle=2/3 後）の C10 の NFR {len(c10)} 件（{trace_path.relative_to(ROOT).as_posix()}）",
        f"- 確認日時: {now}",
        f"- 結論: {CONCLUSION}",
        "- GAP_FILL の追加: なし／テスト・計画の変更: なし／再実行: なし",
        "",
        "### 探索した成果物",
        "",
        "| 成果物 | 確認結果 |",
        "|---|---|",
    ]
    lines += [f"| {e['path']} | {e['finding']} |" for e in EXPLORED]
    lines += [
        "",
        "### 要件ごとの最終確認",
        "",
        "| NFR | 区分（維持） | 要件本文（要旨） | 代替確認方法 | 探索結果 | 部分検証 | 検証すべき工程 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {p['requirement_id']} | {p['status_kept']} | {p['requirement_text_summary']} | {p['alternative_check_method']} | "
        f"{p['exploration_result']} | 実施可能なものなし | {p['verify_in']} |"
        for p in per_item
    ]
    md_path.write_text(md + "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"targets": len(c10), "gap_fill_added": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
