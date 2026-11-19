# trace: FR-002, FR-021, FR-031, ADDR-004
"""画面の二重送信防止（common.submit_token：ADDR-004 DD-010・DD-013〜DD-017）の単体テスト。

期待値：ADDR-004 DD-010（128ビット以上の1回限りのトークン、（操作種別、SHA-256 照合値）の一意登録を業務処理より前の
独立トランザクションで確定、通知した結果の記録、ロックの解放）、DD-015（業務処理のロールバックで消費が取り消されない）、
CMN-22（FR-002・FR-021・FR-031 等の画面の更新操作は1回分だけ反映）。
DB Test Strategy：CONTAINER（一意制約・アドバイザリロック）。
"""

import hashlib

import pytest
from django.db import connection

from common import errors
from common.models import SubmitToken
from common.submit_token import NO_TOKEN, TokenContext, issue_token, run_with_token

pytestmark = pytest.mark.django_db


# trace: ADDR-004
def _advisory_locks_held() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()")
        return cursor.fetchone()[0]


# trace: FR-021, ADDR-004
def test_issue_token_is_random_and_long_enough():
    tokens = {issue_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 32 for t in tokens)  # 192ビット（128ビット以上）


# trace: FR-021, ADDR-004
@pytest.mark.parametrize(
    "raw",
    [None, "", "short", "x" * 129, "has space" + "a" * 20, 12345, "ああああああああああああああああああああああ"],
)
def test_missing_or_malformed_token_runs_normally_without_record(raw):
    seen = []
    assert run_with_token("op", raw, lambda ctx: seen.append(ctx) or "r", lambda r: {"status": "success"}) == "r"
    assert seen == [NO_TOKEN]
    assert not SubmitToken.objects.exists()


# trace: FR-021, ADDR-004
def test_first_use_registers_hash_and_records_outcome_then_second_use_sees_prior():
    token = issue_token()
    contexts = []

    def body(ctx: TokenContext):
        contexts.append(ctx)
        return {"value": len(contexts)}

    first = run_with_token("cart_add", token, body, lambda r: {"status": "success", "n": r["value"]})
    assert first == {"value": 1}
    row = SubmitToken.objects.get()
    assert row.operation == "cart_add"
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest() and token not in row.token_hash
    assert row.outcome == {"status": "success", "n": 1}
    second = run_with_token("cart_add", token, body, lambda r: {"status": "success", "n": r["value"]})
    assert contexts[0] == TokenContext(active=True, used=False, prior=None)
    assert contexts[1] == TokenContext(active=True, used=True, prior={"status": "success", "n": 1})
    assert second == {"value": 2}
    assert SubmitToken.objects.get().outcome == {"status": "success", "n": 1}  # 使用済みの要求は記録を上書きしない
    assert _advisory_locks_held() == 0


# trace: FR-002, ADDR-004
def test_same_token_for_different_operation_is_not_used():
    token = issue_token()
    run_with_token("login", token, lambda ctx: None, lambda r: {"status": "success"})
    seen = []
    run_with_token("logout", token, lambda ctx: seen.append(ctx), lambda r: {"status": "success"})
    assert seen[0].used is False
    assert SubmitToken.objects.count() == 2


# trace: FR-031, ADDR-004
def test_service_error_outcome_is_recorded_and_consumption_survives_failure():
    """DD-015：業務処理の失敗でトークンの消費が取り消されない。通知した結果（エラー）を記録する。"""
    token = issue_token()

    def failing(ctx):
        raise errors.IntegrationError("E-031-07", "連携エラー")

    with pytest.raises(errors.IntegrationError):
        run_with_token("order_pay", token, failing, lambda r: {"status": "success"})
    row = SubmitToken.objects.get()
    assert row.outcome["type"] == "integration_error" and row.outcome["code"] == "E-031-07"
    prior = []
    with pytest.raises(errors.IntegrationError):
        run_with_token(
            "order_pay",
            token,
            lambda ctx: prior.append(ctx) or (_ for _ in ()).throw(errors.from_record(ctx.prior)),
            lambda r: {},
        )
    assert prior[0].used and prior[0].prior["code"] == "E-031-07"
    assert _advisory_locks_held() == 0


# trace: FR-031, ADDR-004
def test_unexpected_exception_records_system_error_and_releases_lock():
    token = issue_token()
    with pytest.raises(RuntimeError):
        run_with_token("order_pay", token, lambda ctx: (_ for _ in ()).throw(RuntimeError("x")), lambda r: {})
    assert SubmitToken.objects.get().outcome == {"status": "error", "type": "system_error"}
    assert _advisory_locks_held() == 0


# trace: FR-021, ADDR-004
def test_used_token_body_error_does_not_overwrite_prior_outcome():
    token = issue_token()
    run_with_token("cart_add", token, lambda ctx: None, lambda r: {"status": "success"})
    with pytest.raises(errors.BusinessError):
        run_with_token(
            "cart_add", token, lambda ctx: (_ for _ in ()).throw(errors.BusinessError("E", "m")), lambda r: {}
        )
    with pytest.raises(ValueError):
        run_with_token("cart_add", token, lambda ctx: (_ for _ in ()).throw(ValueError()), lambda r: {})
    assert SubmitToken.objects.get().outcome == {"status": "success"}
