# ADR-002 永続化データストアにPostgreSQLを採用する

## Status

Accepted

## Related Requirements

- FR-008
- FR-009

## Context

注文登録と在庫減算（FR-008）、チケット購入登録と残席減算（FR-009）は
原子性と一意制約（order_number/purchase_number等）を要する。
更新失敗時に不整合を残さない（ERR-005/NFR-AVL）ためACIDトランザクションが必要。

## Decision

永続化データストアとしてリレーショナルDBのPostgreSQLを採用する。
在庫・残席の整合性はDBトランザクションと行ロック/制約で担保する。

## Alternatives

- PostgreSQL（採用）
  - ACIDトランザクション・一意制約・行ロックを標準提供し要件に適合
- MySQL/MariaDB（不採用）
  - 要件は満たすが本PJで優位差はなく候補として保持のみ
- NoSQL（MongoDB等）（不採用）
  - 多テーブル原子更新の担保が難しくNFR-AVLに不適

## Consequences

- メリット: 原子的な在庫/残席更新と参照整合性を実現できる
- デメリット: スキーマ設計・マイグレーション運用が必要
- 後続工程: 実装・テストは関係モデルとトランザクション前提で構築する

## AI Guardrails

- 在庫/残席更新をトランザクション外で行ってはならない（NFR-AVL）
- 一意制約が必要なキーをアプリ側チェックのみで代替してはならない
