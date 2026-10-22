# MiniCommerce API Contract（提供済み仕様の移設）

この文書は受領済みSteering 5.2/6.1〜6.3のAPI仕様を移設したもの。新たな設計判断ではない。未提供の設計判断はArchitecture / ADDRへ委譲する。

## 応答項目の命名

- API の JSON 項目名は snake_case とし、データ要件定義書（`docs/requirements/data_requirements.md`）の項目英名（3章の項目、および各データの備考で定める算出項目 `min_price`, `min_price_incl_tax`, `price_incl_tax`, `in_stock`, `is_low_stock`, `unit_price`, `line_amount`, `stock_quantity`, `total_quantity`, `is_applicable`, `not_applicable_reason`, `can_pay`, `can_cancel`, `can_ship`, `can_deliver` を含む）、または機能要件定義書（`docs/requirements/functional_requirements.md`）の各 FR の出力で定める導出項目名に一致させる（例 `purchase_order_id`, `order_number`, `stock_unit_id`）。データ要件に無い応答専用の項目のうち、機能要件で英名を定めていないものは次表の名前を用いる。

| 項目名 | 用いる機能 | 意味（元になるデータ要件の項目） |
| --- | --- | --- |
| `token`, `expires_at`, `user` | FR-002 | 認証トークン、有効期限日時（発行時刻＋24時間）、ログイン利用者（`user_id`, `email`, `full_name`, `role`） |
| `collections` | FR-011, FR-012 | 所属分類の配列（`collection_id`, `name`） |
| `stock_units` | FR-012 | 在庫単位の配列（`stock_unit_id`, `sku`, `variant_name`, `price`, `price_incl_tax`, `quantity`, `in_stock`。SKU昇順） |
| `lines` | FR-020〜FR-025, FR-033, FR-042 | カート明細または注文明細の配列 |
| `coupon` | FR-020〜FR-025, FR-033, FR-042 | カート：`code`, `name`, `discount_type`, `discount_value`, `min_spend`, `valid_from`, `valid_until`, `is_applicable`, `not_applicable_reason`。注文：`code`, `discount_type`, `discount_value`（D-10 の `coupon_code`, `coupon_discount_type`, `coupon_discount_value` の値）。未適用は `null` |
| `amounts` | FR-020〜FR-025, FR-033, FR-042 | `subtotal`, `discount_amount`, `discounted_subtotal`, `shipping_fee`, `tax_amount`, `total` |
| `shipping_address` | FR-030, FR-033, FR-042 | 配送先（D-12 の項目） |
| `status_history` | FR-033, FR-042 | 注文状態履歴の配列（`from_status`, `to_status`, `changed_at`, `actor_role`。FR-042 は `actor_user_id` も含む） |
| `payment_records` | FR-042 | 決済記録の配列（`result`, `amount`, `transaction_ref`, `processed_at`） |
| `buyer` | FR-042 | 注文した購入者（`user_id`, `email`, `full_name`） |
| `item_name` | FR-020〜FR-025, FR-040 | 商品名（D-04 の `name`）。注文明細では D-11 の `item_name` |
| `item_is_public` | FR-040 | 商品の公開状態（D-04 の `is_public`） |
| `supplier_name` | FR-040 | 仕入先名（D-02 の `name`） |
| `buyer_email`, `buyer_name` | FR-041 | 購入者のメールアドレス・氏名（D-01 の `email`, `full_name`） |

- URL パスは小文字・ハイフン区切りとする（例 `/api/purchase-orders`, `/api/admin/stock-units`）。
- 用語は Glossary（`docs/requirements/glossary.md`）の定義語を使う（例「在庫単位」「注文」「カート」「クーポン」）。

## 6.1 API エンドポイント一覧

| 対応機能ID | 機能名 | Method | Path | 成功ステータス | 利用できるロール | 備考 |
| --- | --- | --- | --- | --- | --- | --- |
| FR-001 | 会員登録 | POST | `/api/auth/register` | 201 | 認証不要 | 自動ログインしない。ログイン中の buyer・admin からの要求も受け付ける（登録される利用者は buyer） |
| FR-002 | ログイン | POST | `/api/auth/login` | 200 | 認証不要 | `token`, `expires_at`, `user` を返す |
| FR-003 | ログアウト | POST | `/api/auth/logout` | 204 | buyer, admin | 要求に使われたトークンを無効化 |
| FR-004 | ログイン利用者情報照会 | GET | `/api/auth/me` | 200 | buyer, admin | |
| FR-010 | 商品分類一覧照会 | GET | `/api/collections` | 200 | 認証不要 | ページングなし（全件を配列で返す） |
| FR-011 | 商品一覧検索 | GET | `/api/items` | 200 | 認証不要 | ページング形式（20件/ページ） |
| FR-012 | 商品詳細照会 | GET | `/api/items/{item_id}` | 200 | 認証不要 | |
| FR-020 | カート照会 | GET | `/api/cart` | 200 | buyer | カート表現 |
| FR-021 | カート明細追加 | POST | `/api/cart/lines` | 200 | buyer | 更新後のカート表現 |
| FR-022 | カート明細数量変更 | PATCH | `/api/cart/lines/{cart_line_id}` | 200 | buyer | 更新後のカート表現 |
| FR-023 | カート明細削除 | DELETE | `/api/cart/lines/{cart_line_id}` | 200 | buyer | 更新後のカート表現 |
| FR-024 | クーポン適用 | POST | `/api/cart/apply-coupon` | 200 | buyer | 更新後のカート表現 |
| FR-025 | クーポン解除 | POST | `/api/cart/remove-coupon` | 200 | buyer | 更新後のカート表現 |
| FR-026 | 注文金額計算 | APIなし | APIなし | 該当なし | 該当なし | FR-020〜FR-025, FR-030 の実行時に内部で起動 |
| FR-030 | 注文確定 | POST | `/api/checkout` | 201 | buyer | 注文詳細表現（FR-033 と同じ形） |
| FR-031 | 支払（模擬決済） | POST | `/api/purchase-orders/{purchase_order_id}/pay` | 200 | buyer（自分の注文に限る） | 注文詳細表現。IF-01 を起動 |
| FR-032 | 注文履歴一覧照会 | GET | `/api/purchase-orders` | 200 | buyer | ページング形式（20件/ページ）。自分の注文のみ |
| FR-033 | 注文詳細照会（購入者） | GET | `/api/purchase-orders/{purchase_order_id}` | 200 | buyer（自分の注文に限る） | 注文詳細表現 |
| FR-034 | 注文キャンセル（購入者） | POST | `/api/purchase-orders/{purchase_order_id}/cancel` | 200 | buyer（自分の注文に限る） | 注文詳細表現 |
| FR-040 | 在庫単位一覧照会 | GET | `/api/admin/stock-units` | 200 | admin | ページング形式（50件/ページ） |
| FR-041 | 注文一覧検索（管理者） | GET | `/api/admin/purchase-orders` | 200 | admin | ページング形式（20件/ページ）。`status` の複数指定は同じクエリ名を繰り返す（例 `?status=created&status=paid`） |
| FR-042 | 注文詳細照会（管理者） | GET | `/api/admin/purchase-orders/{purchase_order_id}` | 200 | admin | 管理者向け注文詳細表現 |
| FR-043 | 出荷登録 | POST | `/api/admin/purchase-orders/{purchase_order_id}/ship` | 200 | admin | 管理者向け注文詳細表現 |
| FR-044 | 配達完了登録 | POST | `/api/admin/purchase-orders/{purchase_order_id}/deliver` | 200 | admin | 管理者向け注文詳細表現 |
| FR-045 | 注文キャンセル（管理者） | POST | `/api/admin/purchase-orders/{purchase_order_id}/cancel` | 200 | admin | 管理者向け注文詳細表現 |
| FR-060 | 初期データ一括投入 | APIなし | APIなし | 該当なし | 該当なし（運用者がコマンドで実行） | 9章 Seed のコマンド |

- buyer が admin 専用 API を、admin が buyer 専用 API（カート・注文確定・支払・購入者の注文照会・キャンセル）を要求した場合は `PERMISSION_DENIED`（403）。
- buyer が他の購入者の注文を指定した場合は `NOT_FOUND`（404）とし、存在有無を明かさない（PRM-01）。

## 6.2 エラーコード一覧

| エラーコード | HTTP ステータス | エラー種別 | 主な発生機能 |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | 400 | ERR-01 入力エラー | 入力を持つ全 API（`details` に全項目分の項目名と理由） |
| `EMAIL_ALREADY_REGISTERED` | 409 | ERR-02 業務エラー | FR-001 |
| `QUANTITY_LIMIT_EXCEEDED` | 409 | ERR-02 業務エラー | FR-021, FR-022, FR-030 |
| `INSUFFICIENT_STOCK` | 409 | ERR-02 業務エラー | FR-021, FR-022, FR-030 |
| `ITEM_NOT_AVAILABLE` | 409 | ERR-02 業務エラー | FR-030 |
| `CART_EMPTY` | 409 | ERR-02 業務エラー | FR-024, FR-030 |
| `COUPON_ALREADY_APPLIED` | 409 | ERR-02 業務エラー | FR-024 |
| `COUPON_NOT_FOUND` | 409 | ERR-02 業務エラー | FR-024 |
| `COUPON_NOT_YET_VALID` | 409 | ERR-02 業務エラー | FR-024, FR-030 |
| `COUPON_EXPIRED` | 409 | ERR-02 業務エラー | FR-024, FR-030 |
| `COUPON_MIN_SPEND_NOT_MET` | 409 | ERR-02 業務エラー | FR-024, FR-030 |
| `INVALID_STATUS_TRANSITION` | 409 | ERR-02 業務エラー | FR-031, FR-034, FR-043, FR-044, FR-045 |
| `PAYMENT_DECLINED` | 409 | ERR-02 業務エラー | FR-031 |
| `PERMISSION_DENIED` | 403 | ERR-03 権限エラー | 認証要の全 API（ロールに権限がない場合） |
| `AUTHENTICATION_REQUIRED` | 401 | ERR-04 認証エラー | 認証要の全 API（未ログイン・ログアウト済・トークン期限切れ） |
| `INVALID_CREDENTIALS` | 401 | ERR-05 認証失敗 | FR-002（メールアドレスとパスワードのどちらが誤りかを区別しない。メールアドレスの形式不正もこのエラー。未入力のみ `VALIDATION_ERROR`） |
| `NOT_FOUND` | 404 | ERR-06 対象なしエラー | FR-012, FR-021, FR-022, FR-023, FR-031, FR-033, FR-034, FR-042, FR-043, FR-044, FR-045 |
| `PAYMENT_SERVICE_ERROR` | 502 | ERR-07 外部連携エラー | FR-031 |
| `INTERNAL_ERROR` | 500 | ERR-08 システムエラー | 全 API（内部詳細は返さない） |

- 同時実行の競合は専用の排他エラーコードを設けず、上表の業務エラー（`INSUFFICIENT_STOCK`, `INVALID_STATUS_TRANSITION`, `CART_EMPTY`, `EMAIL_ALREADY_REGISTERED`）で返す。

## 6.3 業務エラーの context

| エラーコード | `context` の内容 |
| --- | --- |
| `QUANTITY_LIMIT_EXCEEDED` | `stock_unit_id`、`limit`（10）、`current_quantity`（カート内の現在数量）、`requested_quantity`（要求後の数量） |
| `INSUFFICIENT_STOCK` | `shortages`：`[{stock_unit_id, sku, requested_quantity, available_quantity}]`（カート操作時は1件、注文確定時は不足する全件） |
| `COUPON_MIN_SPEND_NOT_MET` | `min_spend`、`subtotal` |
| `COUPON_NOT_YET_VALID`／`COUPON_EXPIRED` | `valid_from`、`valid_until` |
| `INVALID_STATUS_TRANSITION` | `current_status` |
| `ITEM_NOT_AVAILABLE` | `stock_unit_ids`（非公開の商品に属する在庫単位IDの配列） |
| 上記以外 | `{}` |
