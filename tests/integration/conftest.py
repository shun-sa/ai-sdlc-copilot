"""結合試験（tests/integration）の共通フィクスチャとテストデータ生成。

結合試験は API（DRF View）・画面（Django View）から Service・ORM・PostgreSQL までを
通しで検証する。DB は pytest-django が作成する使い捨てのテストDB（Docker コンテナ上の
PostgreSQL 16）だけを使用し、Production DB・Production Credential・Production Data は
使用しない。テストデータは架空の値のみを用いる。

期待結果（仕様）は各テストモジュール側に置く。本モジュールは実行環境とデータ準備のみを担う。
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import logging
from typing import Any

import pytest
from django.test import Client
from rest_framework.test import APIClient

from accounts.models import ROLE_ADMIN, ROLE_BUYER, User
from accounts.services import hash_password, issue_token
from carts.models import CART_OPEN, DISCOUNT_FIXED, DISCOUNT_PERCENTAGE, Cart, CartLine, Coupon
from catalog.models import Collection, Item, ItemCollection, StockUnit, Supplier
from common import timeutils

_counter = itertools.count(1)

SHIPPING_INPUT = {
    "recipient_name": "結合 受取人",
    "postal_code": "1234567",
    "prefecture_code": "13",
    "address_line1": "千代田区1-1-1",
    "address_line2": "結合ビル101",
    "phone_number": "09012345678",
}


def unique_suffix() -> str:
    """テスト内で一意な連番（業務キーの重複を避けるために使う）。"""
    return f"{next(_counter):05d}"


def shipping_input(**overrides: Any) -> dict[str, Any]:
    """配送先入力（架空の住所・電話番号）。"""
    payload = dict(SHIPPING_INPUT)
    payload.update(overrides)
    return payload


class Factory:
    """結合試験で使う架空データの生成（Production Data は使用しない）。"""

    def user(
        self,
        *,
        email: str | None = None,
        password: str = "Passw0rdA",
        full_name: str = "結合 購入者",
        role: str = ROLE_BUYER,
    ) -> User:
        suffix = unique_suffix()
        user = User.objects.create(
            email=email or f"buyer{suffix}@example.test",
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            registered_at=timeutils.now(),
        )
        user.raw_password = password
        return user

    def admin(self, *, email: str | None = None, password: str = "Passw0rdA") -> User:
        suffix = unique_suffix()
        return self.user(
            email=email or f"admin{suffix}@example.test",
            password=password,
            full_name="結合 管理者",
            role=ROLE_ADMIN,
        )

    def supplier(self, *, supplier_code: str | None = None, name: str = "結合仕入先") -> Supplier:
        return Supplier.objects.create(
            supplier_code=supplier_code or f"SUP-{unique_suffix()}", name=name
        )

    def collection(
        self,
        *,
        collection_code: str | None = None,
        name: str | None = None,
        parent: Collection | None = None,
        sort_order: int = 0,
    ) -> Collection:
        suffix = unique_suffix()
        return Collection.objects.create(
            collection_code=collection_code or f"col-{suffix}",
            name=name or f"分類{suffix}",
            parent=parent,
            depth=1 if parent is None else parent.depth + 1,
            sort_order=sort_order,
        )

    def item(
        self,
        *,
        item_code: str | None = None,
        name: str | None = None,
        description: str = "",
        is_public: bool = True,
        created_at: dt.datetime | None = None,
        collections: list[Collection] | None = None,
    ) -> Item:
        suffix = unique_suffix()
        item = Item.objects.create(
            item_code=item_code or f"ITEM-{suffix}",
            name=name or f"商品{suffix}",
            description=description,
            is_public=is_public,
            created_at=created_at or timeutils.now(),
        )
        for collection in collections or []:
            ItemCollection.objects.create(item=item, collection=collection)
        return item

    def stock_unit(
        self,
        item: Item,
        *,
        supplier: Supplier | None = None,
        sku: str | None = None,
        variant_name: str = "標準",
        price: int = 1000,
        quantity: int = 10,
    ) -> StockUnit:
        return StockUnit.objects.create(
            item=item,
            supplier=supplier or self.supplier(),
            sku=sku or f"SKU-{unique_suffix()}",
            variant_name=variant_name,
            price=price,
            quantity=quantity,
            updated_at=timeutils.now(),
        )

    def sellable(self, *, price: int = 1000, quantity: int = 10, **item_kwargs: Any) -> StockUnit:
        """公開商品に属する在庫単位を1件作る。"""
        return self.stock_unit(self.item(**item_kwargs), price=price, quantity=quantity)

    def coupon(
        self,
        *,
        code: str | None = None,
        name: str = "結合クーポン",
        discount_type: str = DISCOUNT_FIXED,
        discount_value: int = 1000,
        min_spend: int = 0,
        valid_from: dt.datetime | None = None,
        valid_until: dt.datetime | None = None,
    ) -> Coupon:
        now = timeutils.now()
        return Coupon.objects.create(
            code=code or f"CPN-{unique_suffix()}",
            name=name,
            discount_type=discount_type,
            discount_value=discount_value,
            min_spend=min_spend,
            valid_from=valid_from or (now - dt.timedelta(days=1)),
            valid_until=valid_until or (now + dt.timedelta(days=1)),
        )

    def percentage_coupon(self, *, percent: int, **kwargs: Any) -> Coupon:
        return self.coupon(discount_type=DISCOUNT_PERCENTAGE, discount_value=percent, **kwargs)

    def open_cart(self, user: User, *, coupon: Coupon | None = None) -> Cart:
        now = timeutils.now()
        return Cart.objects.create(
            user=user, coupon=coupon, status=CART_OPEN, created_at=now, updated_at=now
        )

    def cart_line(self, cart: Cart, stock_unit: StockUnit, *, quantity: int = 1) -> CartLine:
        return CartLine.objects.create(
            cart=cart, stock_unit=stock_unit, quantity=quantity, added_at=timeutils.now()
        )

    def fill_cart(self, user: User, *lines: tuple[StockUnit, int], coupon: Coupon | None = None) -> Cart:
        """購入者の利用中カートへ明細を用意する（試験前提データの準備）。"""
        cart = Cart.objects.filter(user=user, status=CART_OPEN).first() or self.open_cart(user)
        for stock_unit, quantity in lines:
            self.cart_line(cart, stock_unit, quantity=quantity)
        if coupon is not None:
            cart.coupon = coupon
            cart.save(update_fields=["coupon"])
        return cart


@pytest.fixture
def f() -> Factory:
    """テストデータ生成ヘルパー。"""
    return Factory()


@pytest.fixture
def buyer(db, f: Factory) -> User:
    """購入者1名。"""
    return f.user()


@pytest.fixture
def other_buyer(db, f: Factory) -> User:
    """別の購入者1名（他人のデータを参照する試験で使う）。"""
    return f.user(full_name="結合 別購入者")


@pytest.fixture
def admin_user(db, f: Factory) -> User:
    """管理者1名。"""
    return f.admin()


@pytest.fixture
def api() -> APIClient:
    """API 要求用のクライアント（認証なし）。"""
    return APIClient()


@pytest.fixture
def token_for(db):
    """利用者の認証トークン（平文）を発行するファクトリ。"""

    def _issue(user: User) -> str:
        raw_token, _token = issue_token(user)
        return raw_token

    return _issue


@pytest.fixture
def api_as(token_for):
    """指定した利用者の認証トークンを設定した API クライアントを返すファクトリ。"""

    def _client(user: User) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_for(user)}")
        return client

    return _client


@pytest.fixture
def screen() -> Client:
    """画面要求用のクライアント（未ログイン）。"""
    return Client()


@pytest.fixture
def screen_as(db):
    """画面のログインセッションを開始したクライアントを返すファクトリ。"""

    def _client(user: User) -> Client:
        client = Client()
        session = client.session
        session["login_user_id"] = user.pk
        session.save()
        return client

    return _client


@pytest.fixture
def fixed_now(monkeypatch):
    """処理時刻を固定する（境界値・日時の判定を決定論的にする）。"""

    def _fix(value: dt.datetime) -> dt.datetime:
        fixed = value.replace(microsecond=0)
        monkeypatch.setattr(timeutils, "now", lambda: fixed)
        return fixed

    return _fix


class ErrorResponse:
    """エラー応答の読み取り補助。

    エラー応答の形（封筒 `error` と `details[].reason`）そのものは、提供済みAPI契約の
    共通エラー形式を検証するテストで直接確認する。個別機能のテストはエラーコード・
    HTTPステータス・context を対象とするため、本補助では封筒の有無を吸収して読み取る。
    """

    def body(self, response: Any) -> dict[str, Any]:
        data = response.json() if hasattr(response, "json") else response.data
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            return data["error"]
        return data if isinstance(data, dict) else {}

    def code(self, response: Any) -> str:
        return str(self.body(response).get("code", ""))

    def message(self, response: Any) -> str:
        return str(self.body(response).get("message", ""))

    def details(self, response: Any) -> list[dict[str, Any]]:
        details = self.body(response).get("details")
        return details if isinstance(details, list) else []

    def fields(self, response: Any) -> list[str]:
        return [str(item.get("field", "")) for item in self.details(response)]

    def reasons(self, response: Any) -> str:
        texts = []
        for item in self.details(response):
            for key in ("reason", "message"):
                if item.get(key):
                    texts.append(str(item[key]))
        return " / ".join(texts)

    def context(self, response: Any) -> dict[str, Any]:
        context = self.body(response).get("context")
        return context if isinstance(context, dict) else {}


@pytest.fixture
def err() -> ErrorResponse:
    """エラー応答の読み取り補助。"""
    return ErrorResponse()


@pytest.fixture
def run_parallel():
    """複数の処理を同時に開始して並行実行する（同時実行制御の検証用）。

    各スレッドは自分のDB接続を使い、終了時に必ず解放する。戻り値は実行結果（例外も含む）。
    """
    import threading

    from django.db import connection

    def _run(*funcs, timeout: float = 60.0):
        count = len(funcs)
        barrier = threading.Barrier(count, timeout=timeout)
        results: list[Any] = [None] * count

        def worker(index: int, func) -> None:
            try:
                barrier.wait()
                results[index] = func()
            except BaseException as exc:  # 競合時の例外も結果として評価する
                results[index] = exc
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(index, func)) for index, func in enumerate(funcs)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout)
        for thread in threads:
            assert not thread.is_alive(), "並行実行したスレッドが終了しませんでした。"
        return results

    return _run


class LogCapture(logging.Handler):
    """アプリケーションログを JSON Lines のまま収集する（ログ出力要件の検証用）。"""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))

    @property
    def records(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.lines]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def log_capture():
    """指定したロガーの出力を JSON Lines 形式で収集する。"""
    from common.logging import JsonLinesFormatter

    handlers: list[tuple[logging.Logger, LogCapture, int]] = []

    def _capture(*names: str) -> LogCapture:
        capture = LogCapture()
        capture.setFormatter(JsonLinesFormatter())
        for name in names or ("minicommerce", "django"):
            logger = logging.getLogger(name)
            previous = logger.level
            logger.addHandler(capture)
            logger.setLevel(logging.DEBUG)
            handlers.append((logger, capture, previous))
        return capture

    yield _capture

    for logger, capture, previous in handlers:
        logger.removeHandler(capture)
        logger.setLevel(previous)


@pytest.fixture
def configured_log_capture():
    """設定済み（LOGGING）のハンドラと同じ整形・フィルタでログ行を収集する。

    ログ行の整形と相関IDの補完はハンドラ側（Formatter・Filter）で行うため、収集用ハンドラにも
    設定済みハンドラの Formatter・Filter をそのまま適用し、実際に出力される1行と同じ内容を
    評価する。ロガーに設定済みハンドラがない場合は設定の誤りとして失敗させる。
    """
    attached: list[tuple[logging.Logger, LogCapture, int]] = []

    def _capture(*names: str) -> LogCapture:
        capture = LogCapture()
        for name in names or ("minicommerce", "django"):
            logger = logging.getLogger(name)
            configured = [handler for handler in logger.handlers if handler is not capture]
            assert configured, f"ロガー {name} に設定済みハンドラがありません。"
            source = configured[0]
            capture.setFormatter(source.formatter)
            for log_filter in source.filters:
                if log_filter not in capture.filters:
                    capture.addFilter(log_filter)
            previous = logger.level
            logger.addHandler(capture)
            logger.setLevel(logging.DEBUG)
            attached.append((logger, capture, previous))
        return capture

    yield _capture

    for logger, capture, previous in attached:
        logger.removeHandler(capture)
        logger.setLevel(previous)
