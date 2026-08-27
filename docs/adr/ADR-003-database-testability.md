# ADR-003 データベース接続とテスト用使い捨てDB

## Status

Accepted

## Related Requirements

- CON-001
- NFR-AVL-001
- NFR-AVL-002

## Context

Production DB/Production Dataへの固定依存はテスト再現性と安全性を損なう。
注文・在庫、チケット・残席の整合性（NFR-AVL-001/002）は独立環境で検証が必要。
研究用サンプル（CON-001）であり本番DB資産を前提にできない。

## Decision

DB接続はSession Factoryを依存性注入（DI）で供給する。
開発はSQLiteファイル、テストは使い捨てのin-memory SQLite等へ切替可能とし、
テストでProduction DB/Credential/Dataを使用しない。

## Alternatives

- 接続をグローバル固定
  - 不採用: テストで差し替え不可で本番依存を招く
- テストも本番同種DBを常時起動
  - 不採用: サンプル規模に対し重く外部前提を暗黙導入する
- DIによる接続注入＋使い捨てDB
  - 採用: 本番非依存で整合性テストを再現可能に実行できる

## Consequences

- メリット: 本番資産に依存せず整合性テストを安全に再現できる
- デメリット: SQLiteとファイルDBで並行制御の挙動差に注意が必要
- 後続工程: テストは使い捨てDBを用い本番接続をハードコードしない

## AI Guardrails

- テストでProduction DB/Credential/Dataを使用してはならない
- DB接続先をコードへ固定ハードコードしてはならない
