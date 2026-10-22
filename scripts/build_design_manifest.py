import json
import sys
from pathlib import Path

sys.path.insert(0, ".github/skills/addr/scripts")
from design_common import baseline_paths, digest  # noqa: E402

ROOT = Path(".").resolve()
REVISION = "2e9703ddd0c7bb5e71d270783a5efd5e016d2f4d+WORKTREE"

ROLES = {
    "docs/requirements/requirements.md": "要件索引（派生）",
    "docs/requirements/business_requirements.md": "業務要件（BR）",
    "docs/requirements/functional_requirements.md": "機能要件（FR・CMN・ERR）",
    "docs/requirements/non_functional_requirements.md": "非機能要件（NFR）",
    "docs/requirements/data_requirements.md": "データ要件（D・DQ・INI・DCN）",
    "docs/requirements/external_interface_requirements.md": "外部インターフェース要件（IF-01）",
    "docs/requirements/ui_report_requirements.md": "画面要件（SCR）",
    "docs/requirements/glossary.md": "用語定義（TERM）",
    "docs/requirements/requirements_quality_checklist.md": "要件品質チェックリスト",
    "docs/requirements/use-case-user-story-index.md": "US/UC一覧",
    ".github/project-context/project-ai-steering.md": "Project AI Steering（PJ固有情報の正本）",
    "docs/specifications/api-contract.md": "提供済みAPI契約（受領仕様）",
}

FR_IDS = [
    "FR-001", "FR-002", "FR-003", "FR-004", "FR-010", "FR-011", "FR-012",
    "FR-020", "FR-021", "FR-022", "FR-023", "FR-024", "FR-025", "FR-026",
    "FR-030", "FR-031", "FR-032", "FR-033", "FR-034",
    "FR-040", "FR-041", "FR-042", "FR-043", "FR-044", "FR-045", "FR-060",
]
PLAN_NFR = [
    "NFR-EN-01", "NFR-EN-02", "NFR-EN-03", "NFR-EN-04", "NFR-EN-05",
    "NFR-EN-07", "NFR-EN-08", "NFR-EN-09", "NFR-EN-10", "NFR-EN-11", "NFR-EN-12",
    "NFR-OM-01", "NFR-OM-02", "NFR-OM-03", "NFR-OM-04", "NFR-OM-05", "NFR-OM-06", "NFR-OM-07",
    "NFR-OM-11", "NFR-OM-14", "NFR-OM-15", "NFR-OM-17", "NFR-OM-18", "NFR-OM-19",
    "NFR-PF-01", "NFR-PF-02", "NFR-PF-03", "NFR-PF-06", "NFR-PF-07", "NFR-PF-08", "NFR-PF-09", "NFR-PF-10",
    "NFR-SC-01", "NFR-SC-03", "NFR-SC-04", "NFR-SC-05", "NFR-SC-06", "NFR-SC-07",
    "NFR-SC-08", "NFR-SC-09", "NFR-SC-10", "NFR-SC-11", "NFR-SC-12", "NFR-SC-16",
    "NFR-SC-18", "NFR-SC-19", "NFR-SC-21", "NFR-SC-22", "NFR-SC-23", "NFR-SC-24",
    "NFR-US-01", "NFR-US-02", "NFR-US-03", "NFR-US-04", "NFR-US-07", "NFR-US-09", "NFR-US-10",
    "NFR-LG-02", "NFR-LG-03", "NFR-LG-05", "NFR-MG-02",
]
FILE_REQS = ["FR-060", "NFR-OM-04", "NFR-MG-02", "NFR-SC-01", "NFR-SC-06", "NFR-SC-07"]


def snapshot(path: str, role: str) -> dict:
    return {"path": path, "sha256": digest(ROOT / path), "role": role}


sources = [
    snapshot(path, ROLES.get(path, "要件リンク先"))
    for path in sorted(baseline_paths(ROOT))
]

targets = [
    {
        "target_id": "TGT-001",
        "title": "初期データ定義ファイル（FILE-001）",
        "scope": "FR-060 の入力となる定義ファイルの形式・項目・編集変換・異常処理・検証観点",
        "criticality": "MANDATORY",
        "criticality_reason": "稼働開始時のマスタ登録と検証環境初期化の唯一の入力であり、件数一致（NFR-MG-02）と機密情報の扱い（NFR-SC-01）を満たせないと受け入れ不能になるため",
        "basis_ids": ["FR-060", "NFR-OM-04", "NFR-MG-02", "NFR-SC-01"],
    },
    {
        "target_id": "TGT-002",
        "title": "MiniCommerce アプリケーション実装計画と成果物整合性",
        "scope": "FR-001〜FR-045・FR-060 と主要NFRを実装作業（TASK-001〜TASK-016）へ分解した計画、および現在の入力に対する整合性分析",
        "criticality": "MANDATORY",
        "criticality_reason": "初期リリースの全機能要件・主要非機能要件の実装範囲と順序を定める対象であり、欠落するとImplementationが要件網羅を確認できないため",
        "basis_ids": FR_IDS + PLAN_NFR,
    },
]

artifacts = [
    {
        "artifact_id": "FILE-DEF-001",
        "path": "docs/architecture/files/FILE-001.md",
        "template": "file-definition",
        "sha256": digest(ROOT / "docs/architecture/files/FILE-001.md"),
        "target_id": "TGT-001",
        "related_requirement_ids": FILE_REQS,
        "related_addr_ids": [],
        "element_ids": ["FILE-001"],
        "note": "文書内で定義する File Interface ID は FILE-001。artifact_id と区別する",
    },
    {
        "artifact_id": "PLAN-001",
        "path": "docs/architecture/implementation-task-list.md",
        "template": "implementation-task-list",
        "sha256": digest(ROOT / "docs/architecture/implementation-task-list.md"),
        "target_id": "TGT-002",
        "related_requirement_ids": FR_IDS + PLAN_NFR,
        "related_addr_ids": [],
        "element_ids": [f"TASK-{index:03d}" for index in range(1, 17)],
        "note": "文書内で定義する Task ID は TASK-001〜TASK-016。artifact_id と区別する",
    },
    {
        "artifact_id": "ANALYSIS-001",
        "path": "reports/architecture/cross-artifact-consistency.md",
        "template": "cross-artifact-consistency-analysis",
        "sha256": digest(ROOT / "reports/architecture/cross-artifact-consistency.md"),
        "target_id": "TGT-002",
        "related_requirement_ids": FR_IDS + ["NFR-EN-08", "NFR-OM-01", "NFR-PF-07", "NFR-SC-04", "NFR-SC-06", "NFR-SC-08", "NFR-SC-11", "NFR-MG-02"],
        "related_addr_ids": [],
        "element_ids": ["ARCH-CI-001", "ARCH-CI-002", "ARCH-CI-003"],
        "note": "Producerによる入力時点の分析。独立Assuranceの合格証拠ではない（Overall Result は BLOCKED）",
    },
]

decisions = [
    {
        "candidate_key": "concurrency-control-mechanism",
        "target_id": "TGT-002",
        "blocker_id": "BLK-001",
        "subject": "在庫引当・注文状態遷移・同一カート操作を逐次実行と同じ結果にするための同時実行制御の実現方式",
        "location": "docs/architecture/implementation-task-list.md TASK-008, TASK-010, TASK-011, TASK-012, TASK-013",
        "related_requirement_ids": ["FR-021", "FR-022", "FR-030", "FR-031", "FR-034", "FR-043", "FR-044", "FR-045", "NFR-PF-07"],
        "basis_references": [
            "docs/requirements/functional_requirements.md 7.4（CMN-19, CMN-20, CMN-23）",
            "docs/requirements/non_functional_requirements.md NFR-PF-07",
            "docs/requirements/external_interface_requirements.md IF-01-CON-01",
        ],
        "reason_unresolved": "要件は結果（在庫数量が0未満にならない、承認済み決済は最大1件、二重送信で作成する注文は1件）のみを定め、実現方式を定めていない。Architectureでは方式を比較・採否しない",
    },
    {
        "candidate_key": "authentication-state-mechanism",
        "target_id": "TGT-002",
        "blocker_id": "BLK-002",
        "subject": "API認証トークンと画面ログインセッションの保持・検証・無効化の実現方式",
        "location": "docs/architecture/implementation-task-list.md TASK-005, TASK-015",
        "related_requirement_ids": ["FR-002", "FR-003", "FR-004", "NFR-SC-08", "NFR-SC-09", "NFR-SC-18", "NFR-SC-19"],
        "basis_references": [
            "docs/requirements/non_functional_requirements.md NFR-SC-08, NFR-SC-09, NFR-SC-19",
            ".github/project-context/project-ai-steering.md 8.1",
            "docs/specifications/api-contract.md 6.1（Authentication Header）",
        ],
        "reason_unresolved": "128ビット以上相当の乱数・24時間・ログアウト無効化・多重ログイン・無操作30分という条件のみが与えられ、保持先と検証経路が未提供",
    },
    {
        "candidate_key": "order-number-numbering",
        "target_id": "TGT-002",
        "blocker_id": "BLK-003",
        "subject": "注文番号（PO-＋8桁ゼロ埋め、一意・確定順に増加・欠番許容）の採番方式",
        "location": "docs/architecture/implementation-task-list.md TASK-002, TASK-010",
        "related_requirement_ids": ["FR-030", "FR-032", "FR-041"],
        "basis_references": [
            "docs/requirements/functional_requirements.md 6.15 手順12",
            "docs/requirements/data_requirements.md DQ-11",
            "docs/requirements/glossary.md TERM-020",
        ],
        "reason_unresolved": "形式と性質のみが定義され、同時確定時に一意性と昇順性を保証する手段が未提供",
    },
    {
        "candidate_key": "application-module-structure",
        "target_id": "TGT-002",
        "blocker_id": "BLK-004",
        "subject": "app 内部のモジュール分割と、画面・APIが同一業務ロジックを共有する構成",
        "location": "docs/architecture/implementation-task-list.md TASK-001, TASK-015",
        "related_requirement_ids": ["FR-026", "NFR-EN-01", "NFR-OM-06", "NFR-OM-07", "NFR-OM-17", "NFR-OM-18"],
        "basis_references": [
            ".github/project-context/project-ai-steering.md 4.1, 4.2（app内部の分割は設計で決めると明記）",
            "docs/requirements/non_functional_requirements.md NFR-OM-06, NFR-OM-17, NFR-OM-18",
        ],
        "reason_unresolved": "SteeringがPJ固有情報として明示的に設計へ委譲しており、構成が未確定",
    },
    {
        "candidate_key": "structured-logging-and-request-correlation",
        "target_id": "TGT-002",
        "blocker_id": "BLK-005",
        "subject": "JSON Lines のアプリケーションログ出力と X-Request-ID 相関付け、禁止項目の非出力制御の実現方式",
        "location": "docs/architecture/implementation-task-list.md TASK-004",
        "related_requirement_ids": ["NFR-OM-01", "NFR-OM-02", "NFR-OM-18", "NFR-SC-06"],
        "basis_references": [
            "docs/requirements/non_functional_requirements.md NFR-OM-01, NFR-SC-06",
            ".github/project-context/project-ai-steering.md 7.2",
        ],
        "reason_unresolved": "出力形式と必須・禁止項目のみが定義され、出力経路と相関付けの手段が未提供",
    },
    {
        "candidate_key": "list-query-index-design",
        "target_id": "TGT-002",
        "blocker_id": "BLK-006",
        "subject": "一覧検索（商品一覧・注文一覧・在庫単位一覧）の索引・問い合わせ方式",
        "location": "docs/architecture/implementation-task-list.md TASK-002, TASK-006, TASK-013",
        "related_requirement_ids": ["FR-011", "FR-032", "FR-040", "FR-041", "NFR-PF-01", "NFR-PF-06", "NFR-PF-08", "NFR-SC-04"],
        "basis_references": [
            "docs/requirements/non_functional_requirements.md NFR-PF-01, NFR-PF-06, NFR-PF-08",
            "docs/requirements/non_functional_requirements.md NFR-SC-04（DB操作はプレースホルダで行い、SQL文を入力値の文字列連結で組み立てない）、8.2 VUL-04",
            "docs/requirements/data_requirements.md 9章（将来データ量）",
        ],
        "reason_unresolved": "目標応答時間と将来データ量のみが与えられ、索引・問い合わせの方式が未提供。選択する方式は NFR-SC-04 の制約（FR-011・FR-041 の外部入力がクエリへ到達する）を満たす必要がある",
    },
    {
        "candidate_key": "common-error-response-mechanism",
        "target_id": "TGT-002",
        "blocker_id": "BLK-007",
        "subject": "共通エラー応答（code・message・details・context）と判定順序の共通化方式",
        "location": "docs/architecture/implementation-task-list.md TASK-003",
        "related_requirement_ids": ["NFR-SC-04", "NFR-SC-10", "NFR-US-04"],
        "basis_references": [
            "docs/specifications/api-contract.md 6.2, 6.3",
            "docs/requirements/functional_requirements.md 7.3（CMN-14）, 10章",
        ],
        "reason_unresolved": "応答形式とエラーコードは受領済みだが、全APIへ一貫適用する仕組みが未提供",
    },
    {
        "candidate_key": "password-hash-method",
        "target_id": "TGT-002",
        "blocker_id": "BLK-008",
        "subject": "ソルト付き一方向ハッシュの具体方式（アルゴリズム・パラメータ）",
        "location": "docs/architecture/implementation-task-list.md TASK-005, TASK-014",
        "related_requirement_ids": ["FR-001", "FR-060", "NFR-SC-01", "NFR-SC-16", "NFR-PF-09"],
        "basis_references": [
            "docs/requirements/non_functional_requirements.md NFR-SC-01, NFR-PF-09",
            "docs/requirements/use-cases/UC-013.md BR-UC-013-007",
        ],
        "reason_unresolved": "保存形式の性質（利用者ごとに異なるソルト、平文・可逆暗号の禁止）のみが定義され、方式が未提供",
    },
    {
        "candidate_key": "payment-mock-boundary",
        "target_id": "TGT-002",
        "blocker_id": "BLK-009",
        "subject": "決済サービス（模擬）の配置・呼び出し境界・応答待ち10秒の制御方式",
        "location": "docs/architecture/implementation-task-list.md TASK-011",
        "related_requirement_ids": ["FR-031", "NFR-EN-05", "NFR-PF-02"],
        "basis_references": [
            "docs/requirements/external_interface_requirements.md IF-01（5.1.9 例外、5.1.10 整合性）",
            ".github/project-context/project-ai-steering.md 10章",
        ],
        "reason_unresolved": "模擬機能であることと例外時の振る舞いのみが定義され、実装上の境界・指示値の受け渡し経路が未提供",
    },
    {
        "candidate_key": "seed-file-container-structure",
        "target_id": "TGT-001",
        "blocker_id": "BLK-010",
        "subject": "初期データ定義ファイルのトップレベル構造・データ別キー名・参照項目名、および日時表記とBOMの受理範囲",
        "location": "docs/architecture/files/FILE-001.md 7章（FLD-001〜FLD-006, FLD-015, FLD-021, FLD-024, FLD-025）, 14章 OQ-FILE-001, OQ-FILE-002",
        "related_requirement_ids": ["FR-060", "NFR-OM-04", "NFR-MG-02"],
        "basis_references": [
            "docs/requirements/functional_requirements.md 6.26.3",
            "docs/requirements/data_requirements.md DCN-08",
            "docs/requirements/use-cases/UC-013.md AC-UC-013-003, AC-UC-013-006, AC-UC-013-009",
        ],
        "reason_unresolved": "要件は各データの項目英名を定めるが、JSONの入れ物構造・参照項目名・日時表記の受理範囲を定めていない。Architectureでは名称を推測して確定しない",
    },
    {
        "candidate_key": "web-application-server-selection",
        "target_id": "TGT-002",
        "blocker_id": "BLK-011",
        "subject": "app サービス内で動作する Web サーバー・AP サーバーの選定（本番環境で Django 付属の開発用サーバーを使用しないこと）",
        "location": "docs/architecture/implementation-task-list.md TASK-001, TASK-016",
        "related_requirement_ids": ["NFR-EN-08", "NFR-EN-03", "NFR-EN-10", "NFR-SC-11", "NFR-OM-05", "NFR-OM-19", "NFR-PF-01"],
        "basis_references": [
            "docs/requirements/non_functional_requirements.md NFR-EN-08（目標値「指定なし（app サービス内で動作する Web サーバー・AP サーバーは設計で選定する）。ただし本番環境では Django 付属の開発用サーバーを使用しないこと」、重要度 必須、検証方法 構成・設定レビュー、根拠 VUL-08）",
            "docs/requirements/non_functional_requirements.md NFR-EN-03（コンテナ構成・本番基盤に依存しないこと）、NFR-EN-10（サポート期限内の版）、NFR-SC-11（依存ライブラリの脆弱性確認）",
            ".github/project-context/project-ai-steering.md 3章・9章（技術スタックと起動コマンド。Web/APサーバーの指定はない）",
        ],
        "reason_unresolved": "要件が製品名・バージョンを指定せず、明示的に設計での選定へ委譲している（BLK-004 と同種の委譲）。Architectureでは候補の比較・採否を行わないため未確定のままADDRへ引き渡す",
    },
]

manifest = {
    "version": 2,
    "stage": "FINAL",
    "run_id": "RUN-20261022-MC",
    "source_revision": REVISION,
    "generated_at": "2026-10-22T07:30:00+09:00",
    "phase": "ARCHITECTURE",
    "note": "FINALはArchitecture成果物の確定版であり、重要判断の完了を意味しない。未確定判断は unresolved_design_decisions として独立ADDR工程へ委譲する。repair cycle 1（QR-ARCH-001〜003 / SR-ARCH-001〜003）の修正を反映した再発行",
    "sources": sources,
    "targets": targets,
    "artifacts": artifacts,
    "unresolved_design_decisions": decisions,
}

out = ROOT / "reports/architecture/design-manifest.json"
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"sources={len(sources)} artifacts={len(artifacts)} decisions={len(decisions)}")
