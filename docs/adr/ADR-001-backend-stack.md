# ADR-001 バックエンド技術スタック

## Status

Accepted

## Related Requirements

- CON-001
- NFR-SEC-005

## Context

要件セクション14の技術スタックは未確定で設計工程での決定が求められている。
本システムは研究用サンプル（CON-001）であり外部連携を持たない。
過去実装痕跡（FastAPI + SQLAlchemy + SQLite / CPython 3.12）とも整合が必要。

## Decision

バックエンドを Python 3.12 + FastAPI、ORM に SQLAlchemy、DB に SQLite を採用する。
サーバーサイドでHTMLを描画し、DBアクセスはORM経由のパラメータ化クエリに統一する。

## Alternatives

- Flask + 生SQL
  - 不採用: パラメータ化・スキーマ検証が手作業になりSEC-005リスクが上がる
- Django
  - 不採用: 研究用サンプル規模に対し過剰で学習・変更コストが高い
- FastAPI + SQLAlchemy + SQLite
  - 採用: 軽量でPydantic検証・ORMによりSEC-005対策が容易、痕跡とも整合

## Consequences

- メリット: 軽量で入力検証とSQLi対策を標準機能で統一できる
- デメリット: SQLiteは高並行書き込みに弱く本番同等の負荷特性ではない
- 後続工程: 実装・テストは本スタック前提。DB差し替え方針はADR-003に従う

## AI Guardrails

- 生SQL文字列連結でクエリを構築してはならない（必ずORM/パラメータ化）
- 本スタック以外のフレームワーク・ORMを独自判断で導入してはならない
