# ADR-009 入力検証とインジェクション/XSS対策

## Status

Accepted

## Related Requirements

- NFR-SEC-004
- NFR-SEC-005

## Context

入力値はサーバー側で検証し（NFR-SEC-004）、SQLインジェクションとXSSを
防止する必要がある（NFR-SEC-005）。クライアント検証のみでは信頼できない。

## Decision

全入力はschemas(Pydantic)でサーバー側検証する。DBアクセスはORMの
パラメータ化クエリに限定し、HTML出力はテンプレートの自動エスケープを用いる。

## Alternatives

- クライアント側検証のみ
  - 不採用: 改ざん可能でNFR-SEC-004違反
- 生SQL＋手動サニタイズ
  - 不採用: 漏れが生じSQLi/XSSリスクが残る
- Pydantic検証＋ORM＋自動エスケープ
  - 採用: 境界で一貫検証しSQLi/XSSを標準的に防止

## Consequences

- メリット: 入力検証とエスケープを標準化し注入リスクを低減
- デメリット: スキーマ定義の記述コストが増える
- 後続工程: 検証はschemasに集約、生SQL/エスケープ無効化を行わない

## AI Guardrails

- ユーザー入力を文字列連結でSQL/HTMLに埋め込んではならない
- サーバー側検証を省略しクライアント検証のみに依存してはならない
