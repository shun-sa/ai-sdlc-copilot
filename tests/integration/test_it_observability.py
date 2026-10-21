# trace: NFR-OM-01, NFR-OM-18
# trace: ADDR-007
"""相関ID（request_id）の一貫性に関する結合試験（IT-AI-GAP-022〜023）。

検証対象の連携は 共通ミドルウェア → フレームワーク（応答確定後のログ出力） → ログ出力共通処理。
4xx・5xx の応答に対してフレームワークが出力するログ行（`django.request`）は、要求ごとの
実行文脈を抜けた後に記録されるため、相関IDが欠落しないことを独立して確認する。

期待結果は NFR-OM-18（1件のリクエストに関する全ログ行に同じ request_id を出力し、
X-Request-ID を引き継ぐ）、NFR-OM-01（JSON Lines と必須項目）、ADDR-007 INV-003
（1件の要求に関する全ログ行へ同一の request_id を出力する）、INV-004（要求本文・
クエリ文字列・個人情報をログへ渡さない）から導出する。

本ファイルのケースは origin=AI_GENERATED / generation_stage=GAP_FILL として記録する。
"""

from __future__ import annotations

import pytest

from carts import services as cart_services

pytestmark = pytest.mark.django_db

REQUIRED_REQUEST_FIELDS = {
    "timestamp",
    "level",
    "request_id",
    "method",
    "path",
    "status",
    "duration_ms",
}


# trace: ADDR-007
def framework_lines(capture) -> list[dict]:
    """フレームワークが応答確定後に出力したログ行（django.request）。"""
    return [row for row in capture.records if str(row.get("logger", "")).startswith("django.request")]


# trace: NFR-OM-01, ADDR-007
def request_lines(capture) -> list[dict]:
    """共通ミドルウェアが出力した1要求1行のアクセスログ。"""
    return [row for row in capture.records if row.get("logger") == "minicommerce.request"]


# trace: NFR-OM-01, NFR-OM-18, ADDR-007
def test_it_ai_gap_022_request_id_is_shared_by_framework_logs_on_4xx(
    api, api_as, buyer, configured_log_capture
):
    """IT-AI-GAP-022 / COV-145：4xx の要求では、フレームワークが出力する django.request の行にも
    同じ request_id を出力する（ADDR-007 INV-003、NFR-OM-18）。"""
    client = api_as(buyer)
    capture = configured_log_capture("minicommerce", "django")

    not_found = client.get("/api/purchase-orders/999999", HTTP_X_REQUEST_ID="trace-4xx-0001")

    assert not_found.status_code == 404
    assert not_found["X-Request-ID"] == "trace-4xx-0001"
    framework = framework_lines(capture)
    assert framework, "4xx の応答に対する django.request のログ行が出力されていない。"
    assert {row.get("request_id") for row in framework} == {"trace-4xx-0001"}
    assert all(row["level"] == "WARNING" for row in framework)
    access = request_lines(capture)
    assert access and all(row["request_id"] == "trace-4xx-0001" for row in access)
    assert all(set(row) >= REQUIRED_REQUEST_FIELDS for row in access)
    # 1件の要求に関する全ログ行が同一の相関IDを持つ。
    assert {row.get("request_id") for row in capture.records} == {"trace-4xx-0001"}
    # 要求オブジェクトそのものはログ行へ出力しない（INV-004）。
    assert all("request" not in row for row in capture.records)

    capture.lines.clear()
    invalid = api.post(
        "/api/auth/register",
        {"email": "bad-format-user"},
        format="json",
        HTTP_X_REQUEST_ID="trace-4xx-0002",
    )

    assert invalid.status_code == 400
    assert invalid["X-Request-ID"] == "trace-4xx-0002"
    assert {row.get("request_id") for row in capture.records} == {"trace-4xx-0002"}
    assert framework_lines(capture)
    assert "bad-format-user" not in capture.text  # 要求本文は出力しない（INV-004）


# trace: NFR-OM-01, NFR-OM-18, ADDR-007
def test_it_ai_gap_023_request_id_is_shared_by_framework_logs_on_5xx(
    api_as, buyer, monkeypatch, configured_log_capture
):
    """IT-AI-GAP-023 / COV-145：5xx の要求でも、フレームワークが出力する django.request の行に
    同じ request_id を出力し、未付与の要求では生成した値を全ログ行と応答ヘッダーへ用いる。"""
    client = api_as(buyer)

    def boom(*args, **kwargs):
        raise RuntimeError("storage failure")

    monkeypatch.setattr(cart_services, "show_cart", boom)
    capture = configured_log_capture("minicommerce", "django")

    failed = client.get("/api/cart", HTTP_X_REQUEST_ID="trace-5xx-0001")

    assert failed.status_code == 500
    assert failed["X-Request-ID"] == "trace-5xx-0001"
    framework = framework_lines(capture)
    assert framework, "5xx の応答に対する django.request のログ行が出力されていない。"
    assert {row.get("request_id") for row in framework} == {"trace-5xx-0001"}
    assert all(row["level"] == "ERROR" for row in framework)
    assert {row.get("request_id") for row in capture.records} == {"trace-5xx-0001"}
    assert "storage failure" not in capture.text  # 例外メッセージ本文は出力しない（LOG-02）

    capture.lines.clear()
    generated = client.get("/api/cart")

    assert generated.status_code == 500
    request_id = generated["X-Request-ID"]
    assert request_id and request_id != "trace-5xx-0001"
    assert {row.get("request_id") for row in capture.records} == {request_id}
    assert framework_lines(capture)
