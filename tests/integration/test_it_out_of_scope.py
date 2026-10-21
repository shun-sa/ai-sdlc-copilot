# trace: FR-OUT-09, FR-OUT-13, NFR-SC-17, NFR-SC-28
# trace: FR-004, FR-012, FR-021
# trace: ADDR-002, ADDR-008, ADDR-010, ADDR-011
"""対象外機能の非提供確認の結合試験（IT-AI-GAP-029〜030）。

本リリースで「提供しない」と決めた機能のうち、利用者が誤って到達し得る経路（会員情報の変更・
パスワードの変更／再設定・退会：FR-OUT-09、ファイルの送信・商品画像等：FR-OUT-13）について、
URL定義・API・画面・データ保存のいずれにも該当する経路が無いことを、実行中のシステムの振る舞い
として確かめる。

期待結果は 機能要件定義書 2.3（FR-OUT-09／FR-OUT-13）、非機能要件定義書 NFR-SC-17
（パスワードの変更・再設定が無いためパスワード方針は該当なし）・NFR-SC-28（ファイルを
アップロードする機能が無いため不正ファイル対策は該当なし）、提供済みAPI契約 6.1（提供するAPIの
一覧）、ADDR-002・ADDR-008・ADDR-010・ADDR-011 から導出する。

本ファイルのケースは origin=AI_GENERATED / generation_stage=GAP_FILL として記録する。
AI INITIAL Case および初期 Coverage 指標は変更していない。
"""

from __future__ import annotations

import pytest
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.urls import get_resolver

from carts.models import CART_OPEN, Cart, CartLine

pytestmark = pytest.mark.django_db

# 会員情報の変更・パスワードの変更／再設定・退会に相当する、利用者が試し得る API 経路。
ACCOUNT_CHANGE_API_PATHS = (
    "/api/auth/password",
    "/api/auth/password/change",
    "/api/auth/password-reset",
    "/api/auth/reset-password",
    "/api/auth/withdraw",
    "/api/auth/me/password",
    "/api/users/me",
    "/api/accounts/me",
)
# 同じく、利用者が試し得る画面の経路。
ACCOUNT_CHANGE_SCREEN_PATHS = (
    "/password-reset/",
    "/password/change/",
    "/account/",
    "/mypage/",
    "/withdraw/",
    "/profile/",
)
# URL定義に現れてはならない語（会員情報変更・パスワード再設定・退会）。
ACCOUNT_CHANGE_URL_TOKENS = ("password", "withdraw", "profile", "mypage", "unsubscribe")
# URL定義に現れてはならない語（ファイル送信・商品画像・レビュー・お気に入り・おすすめ）。
UPLOAD_URL_TOKENS = (
    "upload",
    "image",
    "photo",
    "attachment",
    "review",
    "favorite",
    "wishlist",
    "recommend",
)


# trace: FR-004, FR-012
def url_patterns() -> list[str]:
    """URL定義に登録されている経路（入れ子の include を展開した文字列）を返す。"""
    collected: list[str] = []

    def walk(patterns, prefix: str = "") -> None:
        for entry in patterns:
            path = prefix + str(entry.pattern)
            nested = getattr(entry, "url_patterns", None)
            if nested is None:
                collected.append(path)
            else:
                walk(nested, path)

    walk(get_resolver().url_patterns)
    return collected


# trace: FR-OUT-13, NFR-SC-28
def file_fields() -> list[str]:
    """永続化モデルが持つファイル保存項目（FileField/ImageField）の一覧を返す。"""
    return [
        f"{model._meta.label}.{field.name}"
        for model in apps.get_models()
        for field in model._meta.get_fields()
        if isinstance(field, models.FileField)
    ]


# trace: FR-OUT-09, NFR-SC-17, FR-004, ADDR-002, ADDR-010
def test_it_ai_gap_029_account_change_and_password_reset_are_not_provided(
    api_as, screen, screen_as, buyer, err
):
    """IT-AI-GAP-029 / COV-026：会員情報の変更・パスワードの変更／再設定・退会の経路を提供しない。

    FR-OUT-09（会員情報の変更、パスワード再設定、退会は対象外）と、それを前提に「該当なし」と
    している NFR-SC-17（パスワードの有効期限・再利用禁止世代・初期パスワードの変更強制を設けない）
    を、API・画面・URL定義・保存済みの資格情報の変化で確認する。
    """
    before = (buyer.email, buyer.full_name, buyer.password_hash)
    client = api_as(buyer)

    # 1) 会員情報の変更・パスワード変更／再設定・退会に相当する API 経路は存在しない。
    for path in ACCOUNT_CHANGE_API_PATHS:
        for send in (client.get, client.post, client.put, client.patch, client.delete):
            response = send(path)
            assert response.status_code == 404, f"{path}: {response.status_code}"

    # 2) ログイン利用者情報照会は参照（GET）だけを提供し、更新・削除の操作は受け付けない。
    assert client.get("/api/auth/me").status_code == 200
    for send in (client.post, client.put, client.patch, client.delete):
        response = send("/api/auth/me", {"full_name": "変更 太郎", "password": "Changed9A"}, format="json")
        assert response.status_code == 404
        assert err.code(response) == "NOT_FOUND"

    # 3) 画面にも会員情報の変更・パスワード再設定・退会の経路は存在しない（未ログイン・ログイン後とも）。
    logged_in = screen_as(buyer)
    for path in ACCOUNT_CHANGE_SCREEN_PATHS:
        assert screen.get(path).status_code == 404, path
        assert logged_in.get(path).status_code == 404, path

    # 4) URL定義そのものに該当する経路が無い。
    joined = " ".join(url_patterns())
    for token in ACCOUNT_CHANGE_URL_TOKENS:
        assert token not in joined, token

    # 5) ログイン画面から再設定へ誘導しない（未ログイン利用者が到達できる入口が無い）。
    login_body = screen.get("/login/").content.decode()
    for phrase in ("お忘れ", "再設定", "パスワード変更", "退会"):
        assert phrase not in login_body, phrase

    # 6) ログイン後の画面にも会員情報の変更・退会の導線が無い。
    home_body = logged_in.get("/").content.decode()
    for phrase in ("会員情報", "パスワード変更", "退会"):
        assert phrase not in home_body, phrase

    # 7) 一連の要求を通じて、保存済みのメールアドレス・氏名・パスワードハッシュは変化しない。
    buyer.refresh_from_db()
    assert (buyer.email, buyer.full_name, buyer.password_hash) == before


# trace: FR-OUT-13, NFR-SC-28, FR-012, FR-021, ADDR-008, ADDR-010, ADDR-011
def test_it_ai_gap_030_file_upload_and_item_images_are_not_provided(
    api, api_as, screen, screen_as, buyer, f, err
):
    """IT-AI-GAP-030 / COV-042：ファイルを送信する経路と商品画像・レビュー・お気に入り・
    おすすめ表示を提供しない。

    FR-OUT-13（商品画像・商品レビュー・お気に入り・おすすめ表示は対象外）と、それを前提に
    「該当なし」としている NFR-SC-28（画面・API にファイルをアップロードする機能が無い）を、
    URL定義・API の受け付ける形式・画面・保存先（モデル定義と MEDIA 設定）で確認する。
    """
    unit = f.sellable(price=1000, quantity=5, name="非提供確認商品")

    # 1) URL定義に、ファイル送信・画像・レビュー・お気に入り・おすすめの経路が無い。
    joined = " ".join(url_patterns())
    for token in UPLOAD_URL_TOKENS:
        assert token not in joined, token

    # 2) API は JSON だけを受け付け、ファイルを含む multipart/form-data は解釈せずに拒否する。
    upload = SimpleUploadedFile("item.png", b"\x89PNG\r\n\x1a\nfake-binary", content_type="image/png")
    client = api_as(buyer)
    rejected = client.post(
        "/api/cart/lines",
        {"stock_unit_id": str(unit.pk), "quantity": "1", "image": upload},
        format="multipart",
    )

    assert rejected.status_code == 400
    assert err.code(rejected) == "VALIDATION_ERROR"
    assert not CartLine.objects.filter(cart__user=buyer).exists()

    # 3) 画面の更新操作に添付ファイルを加えても、入力項目だけで処理し、ファイルは扱わない。
    screen_client = screen_as(buyer)
    added = screen_client.post(
        "/cart/lines/add/",
        {
            "item_id": str(unit.item_id),
            "stock_unit_id": str(unit.pk),
            "quantity": "1",
            "image": SimpleUploadedFile("item.png", b"fake-binary", content_type="image/png"),
        },
    )

    assert added.status_code == 302
    lines = list(CartLine.objects.filter(cart__user=buyer, cart__status=CART_OPEN))
    assert len(lines) == 1
    assert (lines[0].stock_unit_id, lines[0].quantity) == (unit.pk, 1)
    assert Cart.objects.filter(user=buyer, status=CART_OPEN).count() == 1

    # 4) 送信されたファイルを保存する先が存在しない（モデルのファイル項目・MEDIA 設定とも無い）。
    assert file_fields() == []
    assert not getattr(settings, "MEDIA_ROOT", "")

    # 5) 商品の応答に画像・レビュー・お気に入り・おすすめの項目が無い。
    detail = api.get(f"/api/items/{unit.item_id}")
    listed = api.get("/api/items")

    assert detail.status_code == 200 and listed.status_code == 200
    assert set(detail.json()) == {
        "item_id",
        "item_code",
        "name",
        "description",
        "collections",
        "stock_units",
    }
    assert set(detail.json()["stock_units"][0]) == {
        "stock_unit_id",
        "sku",
        "variant_name",
        "price",
        "price_incl_tax",
        "quantity",
        "in_stock",
    }
    assert set(listed.json()["results"][0]) == {
        "item_id",
        "item_code",
        "name",
        "min_price",
        "min_price_incl_tax",
        "in_stock",
        "collections",
    }

    # 6) 画面にも画像・ファイル選択欄・レビュー・お気に入り・おすすめの表示が無い。
    for path in ("/", f"/items/{unit.item_id}/"):
        body = screen.get(path).content.decode()
        for token in ("<img", 'type="file"', "multipart/form-data", "レビュー", "お気に入り", "おすすめ", "商品画像"):
            assert token not in body, f"{path}: {token}"
