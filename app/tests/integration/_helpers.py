# trace: ADDR-011
"""結合試験の共通部品（HTML のフォーム値の取出し・要求の送信・日時）。

テストケースの本体は各 test_it_*.py に置く。本ファイルは試験データの業務判定を持たない。
"""

import html
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
PASSWORD = "Passw0rdIt1"

ADDRESS = {
    "recipient_name": "受取 太郎",
    "postal_code": "1000001",
    "prefecture": "13",
    "address_line1": "千代田区千代田1-1",
    "address_line2": "",
    "phone_number": "0312345678",
}

_FORM = re.compile(r"<form\b[^>]*>.*?</form>", re.S | re.I)
_INPUT = re.compile(r"<input\b[^>]*>", re.I)
_ATTR = re.compile(r'([a-zA-Z_:-]+)="([^"]*)"')


def jst(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, micro: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, micro, tzinfo=JST)


def text(response: Any) -> str:
    return response.content.decode("utf-8")


def body(response: Any) -> Any:
    return json.loads(response.content.decode("utf-8")) if response.content else None


def form_fields(page: str, action: str) -> dict[str, str]:
    """action 属性が一致するフォームの hidden を含む input の name→value（最初のフォーム）。"""
    for form in _FORM.findall(page):
        head = form.split(">", 1)[0]
        attrs = dict(_ATTR.findall(head))
        if attrs.get("action") == action:
            values: dict[str, str] = {}
            for tag in _INPUT.findall(form):
                a = dict(_ATTR.findall(tag))
                if "name" in a and a.get("type") not in ("radio", "checkbox"):
                    values[a["name"]] = html.unescape(a.get("value", ""))
            return values
    raise AssertionError(f"form action={action} not found")


def input_value(page: str, name: str) -> str | None:
    for tag in _INPUT.findall(page):
        a = dict(_ATTR.findall(tag))
        if a.get("name") == name:
            return html.unescape(a.get("value", ""))
    return None


def api(client: Any, method: str, path: str, token: str | None = None, data: Any = None) -> Any:
    """Web API を呼ぶ（JSON 本文・Bearer）。"""
    headers = {"HTTP_AUTHORIZATION": token} if token else {}
    caller = getattr(client, method.lower())
    if data is None:
        return caller(path, **headers)
    return caller(path, data=json.dumps(data), content_type="application/json", **headers)


def error_of(response: Any) -> dict:
    payload = body(response)
    assert isinstance(payload, dict) and "error" in payload, payload
    error = payload["error"]
    for key in ("type", "reason", "message", "fields", "values"):
        assert key in error, (key, error)
    return error


def field_names(response: Any) -> set[str]:
    return {item["field"] for item in error_of(response)["fields"]}


def add_item(client: Any, token: str, unit_id: Any, quantity: Any) -> Any:
    return api(client, "post", "/api/cart/items/", token, {"stock_unit_id": unit_id, "quantity": quantity})


def place(client: Any, token: str, address: dict | None = None) -> Any:
    return api(client, "post", "/api/orders/", token, {"shipping_address": dict(address or ADDRESS)})


def order_of(client: Any, token: str, lines: list, address: dict | None = None) -> dict:
    """カートに明細を入れて注文を確定し、注文詳細内容を返す（201 を確認する）。"""
    for unit, quantity in lines:
        added = add_item(client, token, unit.pk, quantity)
        assert added.status_code == 200, added.content
    placed = place(client, token, address)
    assert placed.status_code == 201, placed.content
    return body(placed)


def pay(client: Any, token: str, order_id: Any, instruction: str | None = None) -> Any:
    data = {} if instruction is None else {"mock_instruction": instruction}
    return api(client, "post", f"/api/orders/{order_id}/payment/", token, data)


# --- 以下は AI GAP_FILL（GF-012 以降）で追加した共通部品。既存の部品の振る舞いは変更しない ---


class RecordingGateway:
    """決済ゲートウェイの境界（payments.gateway.PaymentGateway）を包み、実装（模擬機能）が受けた要求を記録する。

    実装そのものは差し替えず、受けた PaymentRequest と送信から応答受信までの時間だけを記録する（ADDR-008 DD-004）。
    """

    def __init__(self, inner: Any) -> None:
        import threading

        self.inner = inner
        self.requests: list[Any] = []
        self.durations: list[float] = []
        self._lock = threading.Lock()

    def prepare(self, request: Any) -> Any:
        import time

        with self._lock:
            self.requests.append(request)
        send = self.inner.prepare(request)

        def timed_send() -> Any:
            start = time.monotonic()
            try:
                return send()
            finally:
                with self._lock:
                    self.durations.append(time.monotonic() - start)

        return timed_send


def install_recording_gateway(monkeypatch: Any) -> RecordingGateway:
    """payments.client が使う get_gateway を、模擬機能を包んだ記録用の境界に置き換える（全スレッド共通）。"""
    from payments import client as payment_client
    from payments.mock import MockPaymentGateway

    recorder = RecordingGateway(MockPaymentGateway())
    monkeypatch.setattr(payment_client, "get_gateway", lambda: recorder)
    return recorder


def parallel(*calls: Any) -> list:
    """各呼出しを別スレッド（別の DB 接続）で同時に開始し、応答を呼出し順に返す（transaction=True で使う）。"""
    import threading

    from django.db import connection
    from rest_framework.test import APIClient

    barrier = threading.Barrier(len(calls))
    results: list = [None] * len(calls)
    errors: list = []

    def worker(index: int, call: Any) -> None:
        try:
            client = APIClient()
            barrier.wait(timeout=30)
            results[index] = call(client)
        except Exception as exc:  # noqa: BLE001 - スレッド内の例外をテストへ返す
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not errors, errors
    assert all(not t.is_alive() for t in threads)
    return results


def lock_waiters() -> int:
    """現在の試験用 DB で行ロック等の待機中の接続数（pg_stat_activity）。"""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'"
        )
        return int(cursor.fetchone()[0])


def in_lock_order(order_id: Any, first: Any, second: Any) -> tuple:
    """注文行を別接続でロックしたまま first→second の順に要求を送り、両方が同じ行のロック待ちに入ってから解放する。

    PostgreSQL の行ロック待ちは到着順に処理されるため、2要求を同時に実行しつつ first が先に確定する順序を再現できる
    （同時実行の逐次順序のそれぞれを確実に検証するため。transaction=True で使う）。
    """
    import threading
    import time

    from django.db import connection, transaction
    from rest_framework.test import APIClient

    from orders.models import Order

    held, release = threading.Event(), threading.Event()
    results: list = [None, None]
    errors: list = []

    def holder() -> None:
        try:
            with transaction.atomic():
                Order.objects.select_for_update().get(pk=order_id)
                held.set()
                release.wait(timeout=60)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    def worker(index: int, call: Any) -> None:
        try:
            results[index] = call(APIClient())
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    def wait_for(count: int) -> None:
        deadline = time.monotonic() + 30
        while lock_waiters() < count:
            assert time.monotonic() < deadline, f"lock waiters did not reach {count}"
            time.sleep(0.02)

    lock_thread = threading.Thread(target=holder)
    lock_thread.start()
    assert held.wait(timeout=30)
    threads = [threading.Thread(target=worker, args=(0, first)), threading.Thread(target=worker, args=(1, second))]
    try:
        threads[0].start()
        wait_for(1)
        threads[1].start()
        wait_for(2)
    finally:
        release.set()
    for thread in (lock_thread, *threads):
        thread.join(timeout=120)
    assert not errors, errors
    assert all(not t.is_alive() for t in (lock_thread, *threads))
    return results[0], results[1]
