# ADR-005 認証・セッション方式

## Status

Accepted

## Related Requirements

- FR-002
- NFR-SEC-002
- C-AUTH-003

## Context

ログイン（FR-002）後の状態保持が必要で、要認証機能への未認証アクセスは
拒否しログイン画面へ遷移する必要がある（NFR-SEC-002, C-AUTH-003）。

## Decision

サーバー署名付きのセッションCookieで認証状態を保持する。
Cookieは HttpOnly を付与し改ざん検知可能な署名を用いる。
未認証で要認証機能へアクセスした場合はログイン画面へ遷移させる。

## Alternatives

- URLパラメータ/隠しフィールドでユーザーID保持
  - 不採用: 改ざん容易でなりすまし可能、SEC違反
- 自前JWTをlocalStorage保持
  - 不採用: サーバー描画前提に対し過剰でXSS露出面が増える
- 署名付きセッションCookie
  - 採用: 改ざん検知可能でHttpOnlyによりXSS露出を抑制

## Consequences

- メリット: 改ざん検知とHttpOnlyでなりすまし・盗用リスクを低減
- デメリット: 署名鍵の管理が必要
- 後続工程: 認可判定はセッションのユーザーIDを基準に行う

## AI Guardrails

- クライアント改ざん可能な値を認証状態の根拠にしてはならない
- 未認証の要認証アクセスを素通りさせてはならない
