# 設計資料とADDRの独立工程

現行仕様は [ArchitectureとADDRの独立工程](independent-architecture-addr.md) を参照してください。

通常順序はRequirements→Architecture→ADDR→Implementationです。
Architectureはファイル定義・成果物間整合性分析・実装タスク等の資料作成、
ADDRは重要判断・採否理由・判断から生じる差分/実装拘束だけを担当します。
ArchitectureがADDRを子として呼ぶ構成と、毎回のFINALIZE再呼出しは廃止しました。
本文修正が必要な場合だけ、OrchestratorがArchitectureへ実際に差し戻します。
参照追加だけならADDR側の明示参照と派生handoffで引き渡します。

新規Runの設計manifestはversion=2です。旧version=1のDRAFT/FINALIZEは読取り・検証互換だけ残します。
設計GateとADDR後の実装引渡しGateを分け、実験計測もADDRを独立工程として記録します。
詳細な契約・出力パス・検証・3回ループ・移行制約は現行仕様を参照してください。
