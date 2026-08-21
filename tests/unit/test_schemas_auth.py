"""認証スキーマ バリデーション単体テスト (FR-001 / FR-002)。

対象: app/schemas/auth.py
検証Requirement: FR-001 入力項目/バリデーション (氏名1-50, メール形式/255, パスワード
8-64英数, 確認一致), ERR-001 (入力不備/形式不正), NFR-SEC-004 (サーバー側検証)。
DB Strategy: NOT_APPLICABLE (純粋バリデーション)。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.auth import LoginInput, RegisterInput


def _register(**overrides: object) -> RegisterInput:
    data = {
        "name": "山田太郎",
        "email": "taro@example.com",
        "password": "abcd1234",
        "password_confirm": "abcd1234",
    }
    data.update(overrides)
    return RegisterInput(**data)  # type: ignore[arg-type]


class TestRegisterInputNormal:
    # 正常系: 妥当な入力で会員登録スキーマが生成できる (FR-001)
    def test_valid_input(self) -> None:
        model = _register()
        assert model.name == "山田太郎"
        assert str(model.email) == "taro@example.com"


class TestRegisterInputInvalid:
    # ERR-001: 氏名は必須 (空文字/空白のみは不可)
    @pytest.mark.parametrize("name", ["", "   "])
    def test_name_required(self, name: str) -> None:
        with pytest.raises(PydanticValidationError):
            _register(name=name)

    # FR-001 境界: 氏名は1-50文字。51文字は不可
    def test_name_max_length_boundary(self) -> None:
        _register(name="あ" * 50)  # 上限50はOK
        with pytest.raises(PydanticValidationError):
            _register(name="あ" * 51)

    # ERR-001: メール形式不正は不可
    @pytest.mark.parametrize("email", ["not-an-email", "a@", "@example.com", "a b@example.com"])
    def test_invalid_email_format(self, email: str) -> None:
        with pytest.raises(PydanticValidationError):
            _register(email=email)

    # FR-001 境界: パスワードは8-64文字。7文字は不可、8文字はOK
    def test_password_min_length_boundary(self) -> None:
        _register(password="abcd1234", password_confirm="abcd1234")  # 8文字OK
        with pytest.raises(PydanticValidationError):
            _register(password="abcd123", password_confirm="abcd123")  # 7文字NG

    # FR-001 境界: パスワード64文字はOK、65文字は不可
    def test_password_max_length_boundary(self) -> None:
        pw = "a" * 64
        _register(password=pw, password_confirm=pw)
        pw65 = "a" * 65
        with pytest.raises(PydanticValidationError):
            _register(password=pw65, password_confirm=pw65)

    # FR-001: パスワードは英数。記号は不可
    @pytest.mark.parametrize("password", ["abcd123!", "パスワード1", "abcd 123"])
    def test_password_must_be_alphanumeric(self, password: str) -> None:
        with pytest.raises(PydanticValidationError):
            _register(password=password, password_confirm=password)

    # ERR-001 / FR-001: 確認用パスワード不一致は不可
    def test_password_confirm_mismatch(self) -> None:
        with pytest.raises(PydanticValidationError):
            _register(password="abcd1234", password_confirm="abcd9999")


class TestLoginInput:
    # 正常系: メール+パスワードでログイン入力生成
    def test_valid_login(self) -> None:
        model = LoginInput(email="taro@example.com", password="abcd1234")
        assert str(model.email) == "taro@example.com"

    # ERR-001: メール形式不正は不可
    def test_invalid_email(self) -> None:
        with pytest.raises(PydanticValidationError):
            LoginInput(email="invalid", password="abcd1234")

    # ERR-001: パスワード必須 (空文字不可)
    def test_password_required(self) -> None:
        with pytest.raises(PydanticValidationError):
            LoginInput(email="taro@example.com", password="")
