# ADR-002 レイヤードアーキテクチャ構成

## Status

Accepted

## Related Requirements

- FR-008
- FR-009

## Context

商品注文（FR-008）やチケット購入（FR-009）は入力検証・在庫/残席整合・
スナップショット保持など複数の関心が絡み、責務混在は誤実装リスクを高める。
過去のapp/構造（routers/services/repositories/schemas/models）とも整合させる。

## Decision

Presentation=routers、Application=services、Domain=models(entities)、
Infrastructure=repositories、境界DTO=schemas の構成を採用する。
業務ルールとトランザクション境界はservices層に集約する。

## Alternatives

- routersに業務ロジックを直書き
  - 不採用: テスト困難で整合性制御が分散し不整合を招く
- 汎用リポジトリのみでservice層なし
  - 不採用: トランザクション境界が曖昧になり整合性を保てない
- routers/services/repositories/schemasの層分離
  - 採用: 責務分離が明確で過去構造とも整合しテスト容易

## Consequences

- メリット: 業務ルールとDBアクセスを分離しテスト・変更が容易
- デメリット: 小規模処理でも層をまたぐ記述が必要
- 後続工程: DBアクセスはrepositories経由に限定、業務判断はservicesに置く

## AI Guardrails

- routersやrepositoriesに業務ルール・トランザクション制御を書いてはならない
- schemas(DTO)をそのままDBエンティティとして永続化してはならない
