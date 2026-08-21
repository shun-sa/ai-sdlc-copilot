# ADR-003 レイヤードアーキテクチャを採用する

## Status

Accepted

## Related Requirements

- FR-008
- NFR-SEC-002
- NFR-SEC-004

## Context

認証・認可の強制（NFR-SEC-002）、サーバー側検証（NFR-SEC-004）、
注文/購入の業務整合性（FR-008）を一貫して適用する場所を明確化する必要がある。
責務が混在すると横断要件の抜け漏れが発生しやすい。

## Decision

Presentation / Application(Service) / Domain / Infrastructure の
レイヤードアーキテクチャを採用する。トランザクション境界はApplication層に置く。

## Alternatives

- レイヤードアーキテクチャ（採用）
  - 認証・検証・トランザクション境界を層で強制でき要件規模に適合
- トランザクションスクリプト単層（不採用）
  - 横断要件が各所へ散在し保守・テスト性が低下
- マイクロサービス（不採用）
  - 要件規模に対し過剰で運用コストが高い

## Consequences

- メリット: 横断要件の適用点が明確になり実装・テストが安定する
- デメリット: 小機能でも層をまたぐ実装が必要
- 後続工程: 実装は層責務に従い、テストは層境界で検証する

## AI Guardrails

- 認証・認可・トランザクションをPresentation層に実装してはならない
- Domainロジックを直接DBアクセスへ結合させてはならない
