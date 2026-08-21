# ADR-001 バックエンドプラットフォームにPython + FastAPIを採用する

## Status

Accepted

## Related Requirements

- FR-008
- NFR-SEC-004
- NFR-SEC-005

## Context

技術スタックは要件未確定であり設計工程で決定する（§14）。
サーバー側入力検証（NFR-SEC-004）、注文・在庫更新のサーバー処理（FR-008）、
インジェクション対策（NFR-SEC-005）を型安全かつ標準機構で実現する必要がある。

## Decision

バックエンドプラットフォームとしてPython 3.12 + FastAPIを採用する。
入力検証はPydanticスキーマをサーバー側の必須境界として用いる。

## Alternatives

- Python + FastAPI（採用）
  - Pydanticでサーバー側検証を標準化でき要件適合とテスト容易性が高い
- Node.js + Express（不採用）
  - 検証・型の標準化が弱く実装ばらつきが出やすい
- Java + Spring Boot（不採用）
  - 要件規模に対し構成が重く初期コストが高い

## Consequences

- メリット: サーバー側検証とAPI仕様を標準機構で強制できる
- デメリット: Python実行環境への依存が生じる
- 後続工程: 実装・テストはこのスタックを前提に構築する

## AI Guardrails

- クライアント側検証のみで入力検証を完結させてはならない（NFR-SEC-004）
- 要件・ADRの根拠なく別言語/フレームワークへ変更してはならない
