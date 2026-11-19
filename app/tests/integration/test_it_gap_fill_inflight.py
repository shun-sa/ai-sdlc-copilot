# trace: NFR-US-10, FR-002, FR-021, FR-030, FR-031
# trace: ADDR-004, ADDR-008, ADDR-011
"""結合試験：AI GAP_FILL（処理中の同一送信トークンの繰り返し操作。TEST_ERROR 修正 cycle=2/3、QR-IT-1118-R1-001）。

GF-039〜GF-043（origin=AI_GENERATED、generation_stage=GAP_FILL）。AI INITIAL（IT-050 を含む）は変更しない。
GF-002・GF-003・GF-034・IT-050 は先着の応答を受け取った後の逐次の再送（使用済みトークンの判定）であり、
NFR-US-10 の「処理が完了するまでの間」の繰り返し操作を再現していない。本ファイルは、先着が送信トークンの
アドバイザリロック（ADDR-004 4.3 の11 ①）を保持して業務処理中の時点で、同じ Cookie・フォーム値（同じ送信トークン）の
後着を別スレッド・別の DB 接続から送る（ADDR-004 4.4 検証方法・テスト行、ADDR-011 DD-010 の transaction=True）。
- 先着を業務処理中に留める手段（Production Code は変更しない）：支払は模擬決済の応答遅延（試験用状態
  payment_delay_seconds、ADDR-011）、注文確定・カートに入れるは利用中カートの行、ログインは監査ログの表を
  別接続でロックして待たせる。
- 後着が送信トークンのアドバイザリロック待ち（pg_locks の未取得の advisory、送信トークン専用の名前空間）に入り、
  その時点で先着・後着とも未完了であることを確認してから先着を進める。
- 期待結果は NFR-US-10、CMN-22、UC-006（AC-UC-006-021・AC-UC-006-026・BR-UC-006-012）、UC-007（BR-UC-007-014）、
  ADDR-004 DD-002・DD-010・DD-013・DD-015・DD-016、FR-002・FR-021・FR-030・FR-031 から導出する。
  試験データは架空の値だけを使う。
"""

import copy
import hashlib
import json
import threading
import time
from contextlib import contextmanager

import pytest

from tests.integration._helpers import (
    ADDRESS,
    add_item,
    form_fields,
    install_recording_gateway,
    order_of,
    text,
)

pytestmark = pytest.mark.django_db(transaction=True)

PAYMENT_DELAY_SECONDS = 3.0  # 模擬決済の応答遅延（10秒の応答待ち上限未満。先着の処理中に後着を送るため）
MSG_SYSTEM_ERROR = "時間をおいて再度操作してください。解消しない場合は当社までお問い合わせください。"
MSG_DECLINED = "決済が承認されませんでした。お支払いは完了していません。再度お支払いください。"
MSG_AUTH_FAILED = "メールアドレスまたはパスワードが正しくありません。"


# trace: NFR-US-10, ADDR-004
def _token_locks(granted: bool) -> int:
    """送信トークン専用の名前空間のアドバイザリロック（2引数形式）の取得済み／待機中の数（試験用 DB）。"""
    from django.db import connection

    from common.submit_token import SUBMIT_TOKEN_LOCK_NAMESPACE

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objsubid = 2 AND classid::bigint = %s "
            "AND granted = %s AND database = (SELECT oid FROM pg_database WHERE datname = current_database())",
            [SUBMIT_TOKEN_LOCK_NAMESPACE, granted],
        )
        return int(cursor.fetchone()[0])


# trace: NFR-US-10, ADDR-004
def _data_lock_waiters() -> int:
    """アドバイザリロック以外（行・表）のロック待ちの接続数。"""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock' AND wait_event <> 'advisory'"
        )
        return int(cursor.fetchone()[0])


# trace: NFR-US-10, ADDR-004
def _wait_until(predicate, what: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, f"timeout: {what}"
        time.sleep(0.02)


# trace: NFR-US-10, ADDR-004, ADDR-011
@contextmanager
def _holding(acquire):
    """別の接続（スレッド）で acquire() のロックを取得して保持する。with の値は解放の関数。"""
    from django.db import connection, transaction

    held, release = threading.Event(), threading.Event()
    errors: list = []

    def holder() -> None:
        try:
            with transaction.atomic():
                acquire()
                held.set()
                release.wait(timeout=60)
        except Exception as exc:  # noqa: BLE001 - スレッド内の例外をテストへ返す
            errors.append(exc)
        finally:
            connection.close()

    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert held.wait(timeout=30), errors
        yield release.set
    finally:
        release.set()
        thread.join(timeout=60)
    assert not errors, errors
    assert not thread.is_alive()


# trace: NFR-US-10, ADDR-004
def _in_flight(first, second, *, first_in_processing, release=None) -> tuple:
    """先着 first を開始し、送信トークンのロックを保持して業務処理中になってから同じトークンの後着 second を送る。

    後着が送信トークンのロック待ちに入り、その時点で先着・後着とも未完了であることを確認してから先着を進める
    （release。支払は応答遅延の経過で進む）。応答を (先着, 後着) で返す。
    """
    from django.db import connection

    results: list = [None, None]
    errors: list = []
    done = [threading.Event(), threading.Event()]

    def worker(index: int, call) -> None:
        try:
            results[index] = call()
        except Exception as exc:  # noqa: BLE001 - スレッド内の例外をテストへ返す
            errors.append(exc)
        finally:
            done[index].set()
            connection.close()

    threads = [threading.Thread(target=worker, args=(0, first)), threading.Thread(target=worker, args=(1, second))]
    observed = None
    try:
        threads[0].start()
        _wait_until(
            lambda: done[0].is_set() or (_token_locks(granted=True) == 1 and first_in_processing()),
            "先着が送信トークンのロックを保持して業務処理中になる",
        )
        assert not done[0].is_set(), ("先着が後着の送信前に完了した（処理中の繰り返しを再現できていない）", errors)
        threads[1].start()
        _wait_until(lambda: done[1].is_set() or _token_locks(granted=False) == 1, "後着がトークンのロック待ちに入る")
        observed = {
            "token_lock_held": _token_locks(granted=True),
            "token_lock_waiting": _token_locks(granted=False),
            "first_running": not done[0].is_set(),
            "second_running": not done[1].is_set(),
        }
    finally:
        if release is not None:
            release()
        for thread in threads:
            if thread.is_alive() or thread.ident is not None:
                thread.join(timeout=120)
    assert not errors, errors
    assert all(not t.is_alive() for t in threads)
    # 後着は先着の処理中に到着し、同じトークンのロック（①）で先着の終了（⑤）まで待った（DD-002 の⓪・DD-010）
    assert observed == {"token_lock_held": 1, "token_lock_waiting": 1, "first_running": True, "second_running": True}
    return results[0], results[1]


# trace: NFR-US-10, ADDR-004
def _flash(response) -> list[str]:
    """その要求で追加した画面の通知（メッセージ）。セッションを共有する2つのブラウザの通知を区別するため要求ごとに読む。"""
    return [str(m) for m in response.wsgi_request._messages._queued_messages]


# trace: NFR-US-10, ADDR-004
def _token_rows(operation: str, raw_token: str) -> list:
    """その送信トークン（操作種別＋照合値）の記録。"""
    from common.models import SubmitToken

    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return list(SubmitToken.objects.filter(operation=operation, token_hash=digest))


# trace: NFR-US-10, FR-031, ADDR-004, ADDR-011
def _with_insert_fault(model, call):
    """この要求のスレッドの接続だけで、model の表への INSERT を DB 障害にする（承認の反映途中の障害：E-031-08）。"""
    from django.db import DatabaseError, connection

    table = model._meta.db_table

    def wrapper(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith("INSERT") and f'"{table}"' in sql:
            raise DatabaseError(f"injected fault: INSERT {table}")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(wrapper):
        return call()


# trace: NFR-US-10, FR-031, ADDR-004
def _pay_form(browser, web, order_id, instruction):
    pay_path = f"/orders/{order_id}/payment/"
    fields = form_fields(text(browser.get(pay_path)), pay_path)
    fields["mock_instruction"] = instruction
    repeated = web()
    repeated.cookies = copy.deepcopy(browser.cookies)  # 同じブラウザの繰り返し操作（同じ Cookie・フォーム値）
    return pay_path, fields, repeated


# trace: NFR-US-10, FR-031, ADDR-004
def _history(order_id):
    from orders.models import OrderStatusHistory

    return [
        (h.from_status, h.to_status)
        for h in OrderStatusHistory.objects.filter(order_id=order_id).order_by("changed_at", "pk")
    ]


# trace: NFR-US-10, FR-031, ADDR-004, ADDR-008, ADDR-011
def test_gf_039_inflight_repeat_pay_approved_declined(api_client, web, buyer, bearer, catalog, set_state, monkeypatch):
    """GF-039 支払（承認・否認）の処理中（決済応答待ち）に同じ送信トークンの「支払う」を繰り返しても決済要求は1回。"""
    from orders.models import Order, PaymentRecord

    recorder = install_recording_gateway(monkeypatch)
    set_state(payment_delay_seconds=PAYMENT_DELAY_SECONDS)
    unit = catalog.stock_unit(price=1000, stock=10)
    token = bearer(buyer)
    browser = web()
    browser.force_login(buyer, backend="accounts.backends.SessionUserBackend")

    def pay_in_flight(instruction):
        order = order_of(api_client, token, [(unit, 1)])
        oid, number = order["order_id"], order["order_number"]
        pay_path, fields, repeated = _pay_form(browser, web, oid, instruction)

        def sent():
            return [r for r in recorder.requests if r.order_number == number]

        first, second = _in_flight(
            lambda: browser.post(pay_path, fields),
            lambda: repeated.post(pay_path, fields),
            first_in_processing=lambda: len(sent()) == 1,
        )
        assert len(sent()) == 1, instruction  # 決済要求は1回分だけ送信（NFR-US-10、BR-UC-007-014）
        (record,) = _token_rows("order_pay", fields["submit_token"])
        return order, first, second, record, Order.objects.get(pk=oid)

    order, first, second, record, row = pay_in_flight("approved")
    oid = order["order_id"]
    detail_path = f"/orders/{oid}/"
    assert first.status_code == 302 and first["Location"] == detail_path
    assert _flash(first) == ["支払が完了しました。"]
    # 後着：先着の反映後は注文受付でないため再判定どおり E-031-05（ADDR-004 DD-013）
    assert second.status_code == 302 and second["Location"] == detail_path
    assert _flash(second) == ["この注文は支払できません（現在の状態：支払済）。"]
    approved = [("approved", order["amounts"]["total_amount"])]
    assert list(PaymentRecord.objects.filter(order_id=oid).values_list("result", "amount")) == approved
    assert row.status == "paid" and row.paid_at is not None
    assert _history(oid) == [(None, "accepted"), ("accepted", "paid")]
    assert record.outcome == {"status": "success", "redirect": detail_path}

    order, first, second, record, row = pay_in_flight("declined")
    oid = order["order_id"]
    # 後着：注文受付のままなので決済要求を送らず先着の結果（E-031-06）を通知（ADDR-004 DD-013）
    assert first.status_code == 422 and second.status_code == 422
    assert MSG_DECLINED in text(first) and MSG_DECLINED in text(second)
    assert list(PaymentRecord.objects.filter(order_id=oid).values_list("result", flat=True)) == ["declined"]
    assert row.status == "accepted" and row.paid_at is None
    assert _history(oid) == [(None, "accepted")]
    assert record.outcome["code"] == "E-031-06" and record.outcome["status"] == "error"
    assert len(recorder.requests) == 2


# trace: NFR-US-10, FR-031, ADDR-004, ADDR-008, ADDR-011
def test_gf_040_inflight_repeat_pay_system_error_and_interrupted(
    api_client, web, buyer, bearer, catalog, set_state, monkeypatch
):
    """GF-040 先着が E-031-08（承認の反映の障害）・結果の記録前の中断で終わる間の「支払う」の繰り返しで決済要求1回。"""
    from common import submit_token
    from orders.models import Order, OrderStatusHistory, PaymentRecord

    recorder = install_recording_gateway(monkeypatch)
    set_state(payment_delay_seconds=PAYMENT_DELAY_SECONDS)
    unit = catalog.stock_unit(price=1000, stock=10)
    token = bearer(buyer)
    browser = web()
    browser.force_login(buyer, backend="accounts.backends.SessionUserBackend")

    def run_case(oid, number, pay_path, fields, repeated):
        def sent():
            return [r for r in recorder.requests if r.order_number == number]

        first, second = _in_flight(
            lambda: _with_insert_fault(OrderStatusHistory, lambda: browser.post(pay_path, fields)),
            lambda: repeated.post(pay_path, fields),
            first_in_processing=lambda: len(sent()) == 1,
        )
        assert len(sent()) == 1  # 後着は決済要求を再送信しない
        for response in (first, second):
            assert response.status_code == 500 and MSG_SYSTEM_ERROR in text(response)
        row = Order.objects.get(pk=oid)
        assert row.status == "accepted" and row.paid_at is None
        assert not PaymentRecord.objects.filter(order_id=oid).exists()  # 承認の反映は全体をロールバック
        assert _history(oid) == [(None, "accepted")]
        return _token_rows("order_pay", fields["submit_token"])

    # (a) 先着は承認の反映途中の障害で E-031-08。後着は送信せず先着の結果（E-031-08）を通知
    order = order_of(api_client, token, [(unit, 1)])
    oid_a, number_a = order["order_id"], order["order_number"]
    pay_path, fields, repeated = _pay_form(browser, web, oid_a, "approved")
    (record,) = run_case(oid_a, number_a, pay_path, fields, repeated)
    assert record.outcome["status"] == "error" and record.outcome["code"] == "E-031-08"
    # システムエラーの後に新たに表示した支払画面からの操作は新たな支払（ADDR-004 4.3 の11、NFR-US-10）
    set_state(payment_delay_seconds=0)
    retry = form_fields(text(browser.get(pay_path)), pay_path)
    assert retry["submit_token"] != fields["submit_token"]
    retry["mock_instruction"] = "approved"
    assert browser.post(pay_path, retry).status_code == 302
    assert [r.order_number for r in recorder.requests].count(number_a) == 2
    assert list(PaymentRecord.objects.filter(order_id=oid_a).values_list("result", flat=True)) == ["approved"]
    assert Order.objects.get(pk=oid_a).status == "paid"

    # (b) 先着が結果の記録（④）の前に中断。後着は先着の結果の記録がないためシステムエラー（E-031-08）とし再送信しない
    set_state(payment_delay_seconds=PAYMENT_DELAY_SECONDS)
    order = order_of(api_client, token, [(unit, 1)])
    oid_b, number_b = order["order_id"], order["order_number"]
    pay_path, fields, repeated = _pay_form(browser, web, oid_b, "approved")

    def interrupted(operation, token_hash, outcome):
        raise RuntimeError("injected interruption before recording the outcome")

    monkeypatch.setattr(submit_token, "_record_outcome", interrupted)
    (record,) = run_case(oid_b, number_b, pay_path, fields, repeated)
    assert record.outcome is None
    assert len(recorder.requests) == 3


# trace: NFR-US-10, FR-030, ADDR-004, ADDR-011
def test_gf_041_inflight_repeat_place_order(api_client, web, buyer, bearer, catalog):
    """GF-041 注文確定の処理中に同じ送信トークンの「注文を確定する」を繰り返しても注文は1件（後着はカートが空）。"""
    from carts.models import Cart, CartItem
    from catalog.models import StockUnit
    from orders.models import Order, OrderItem

    unit = catalog.stock_unit(price=1000, stock=10)
    assert add_item(api_client, bearer(buyer), unit.pk, 2).status_code == 200
    cart_pk = Cart.objects.get(buyer=buyer, status="active").pk
    browser = web()
    browser.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    fields = form_fields(text(browser.get("/checkout/")), "/checkout/")
    fields.update(ADDRESS)
    repeated = web()
    repeated.cookies = copy.deepcopy(browser.cookies)

    with _holding(lambda: Cart.objects.select_for_update().get(pk=cart_pk)) as release:
        first, second = _in_flight(
            lambda: browser.post("/checkout/", fields),
            lambda: repeated.post("/checkout/", fields),
            first_in_processing=lambda: _data_lock_waiters() >= 1,
            release=release,
        )

    assert Order.objects.filter(buyer=buyer).count() == 1
    order = Order.objects.get(buyer=buyer)
    assert first.status_code == 302 and first["Location"] == f"/orders/{order.pk}/complete/"
    # 後着（使用済みトークン）は受付時点のデータで再判定し E-030-04 カートが空（AC-UC-006-021、ADDR-004 DD-013）
    assert second.status_code == 302 and second["Location"] == "/cart/"
    assert _flash(second) == ["カートに商品がありません。"]
    assert StockUnit.objects.get(pk=unit.pk).stock_quantity == 8
    assert list(OrderItem.objects.filter(order=order).values_list("quantity", flat=True)) == [2]
    assert Cart.objects.get(pk=cart_pk).status == "ordered"
    assert list(CartItem.objects.filter(cart_id=cart_pk).values_list("quantity", flat=True)) == [2]
    (record,) = _token_rows("order_place", fields["submit_token"])
    assert record.outcome == {"status": "success", "redirect": f"/orders/{order.pk}/complete/"}


# trace: NFR-US-10, FR-021, ADDR-004, ADDR-011
def test_gf_042_inflight_repeat_cart_add(api_client, web, buyer, bearer, catalog):
    """GF-042「カートに入れる」の処理中に同じ送信トークンで繰り返しても数量は1回分だけ加算。"""
    from carts.models import Cart, CartItem

    product = catalog.product()
    unit = catalog.stock_unit(product, stock=20)
    other = catalog.stock_unit(stock=20)
    assert add_item(api_client, bearer(buyer), other.pk, 1).status_code == 200  # 利用中カート（ロックする行）を用意
    cart_pk = Cart.objects.get(buyer=buyer, status="active").pk
    browser = web()
    browser.force_login(buyer, backend="accounts.backends.SessionUserBackend")
    fields = form_fields(text(browser.get(f"/products/{product.pk}/")), "/cart/items/add/")
    fields.update({"stock_unit_id": str(unit.pk), "quantity": "3"})
    repeated = web()
    repeated.cookies = copy.deepcopy(browser.cookies)

    with _holding(lambda: Cart.objects.select_for_update().get(pk=cart_pk)) as release:
        first, second = _in_flight(
            lambda: browser.post("/cart/items/add/", fields),
            lambda: repeated.post("/cart/items/add/", fields),
            first_in_processing=lambda: _data_lock_waiters() >= 1,
            release=release,
        )

    detail_path = f"/products/{product.pk}/"
    expected_flash = [f"カートに追加しました（{unit.variant_name}、3個）。"]
    # 後着：再判定が成立しても加算せず先着の結果（成功）を通知（ADDR-004 DD-013）
    for response in (first, second):
        assert response.status_code == 302 and response["Location"] == detail_path
        assert _flash(response) == expected_flash
    assert list(CartItem.objects.filter(cart_id=cart_pk, stock_unit=unit).values_list("quantity", flat=True)) == [3]
    assert list(CartItem.objects.filter(cart_id=cart_pk, stock_unit=other).values_list("quantity", flat=True)) == [1]
    assert Cart.objects.filter(buyer=buyer).count() == 1
    (record,) = _token_rows("cart_add", fields["submit_token"])
    assert record.outcome == {"status": "success", "redirect": detail_path}


# trace: NFR-US-10, FR-002, ADDR-004, ADDR-011
def test_gf_043_inflight_repeat_login_failure(web, buyer):
    """GF-043 先着が E-002-02 で終わる間の「ログイン」の繰り返しでログイン失敗の監査ログは1件・ログイン状態なし。"""
    from django.db import connection

    from audit.models import AuditLog

    browser = web()
    fields = form_fields(text(browser.get("/login/")), "/login/")
    fields.update({"email": buyer.email, "password": "Wrong0Password"})
    repeated = web()
    repeated.cookies = copy.deepcopy(browser.cookies)
    table = AuditLog._meta.db_table

    def lock_audit_table():
        with connection.cursor() as cursor:
            cursor.execute(f'LOCK TABLE "{table}" IN SHARE MODE')

    with _holding(lock_audit_table) as release:
        first, second = _in_flight(
            lambda: browser.post("/login/", fields),
            lambda: repeated.post("/login/", fields),
            first_in_processing=lambda: _data_lock_waiters() >= 1,
            release=release,
        )

    # 後着は照合・監査ログの記録を行わず、先着の記録済みの結果（E-002-02）を通知（ADDR-004 DD-013・DD-016）
    for response in (first, second):
        assert response.status_code == 401 and MSG_AUTH_FAILED in text(response)
    assert AuditLog.objects.filter(event_type="login_failure").count() == 1
    assert AuditLog.objects.filter(event_type="login_failure", target_user_id=buyer.pk).count() == 1
    assert AuditLog.objects.filter(event_type="login_success").count() == 0
    for client in (browser, repeated):  # どちらのブラウザにもログイン状態は作られない
        protected = client.get("/cart/")
        assert protected.status_code == 302 and protected["Location"].startswith("/login/?required=1")
    (record,) = _token_rows("login", fields["submit_token"])
    assert record.outcome["status"] == "error" and record.outcome["code"] == "E-002-02"
    stored = json.dumps(record.outcome, ensure_ascii=False)
    assert buyer.email not in stored and "Wrong0Password" not in stored  # 入力値を記録しない（ADDR-004 4.3 の11 ④）
