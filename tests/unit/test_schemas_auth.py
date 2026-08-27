"""app.schemas.auth の入力検証テスト（サーバー側検証）。

Requirement: FR-001 / FR-002 / NFR-SEC-004
ADR: ADR-009（Pydantic によるサーバー側検証）
Criteria: normal-case, invalid-input, boundary-value
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginInput, RegisterInput


def _valid_register(**overrides: object) -> dict:
    data = {
        "name": "会員太郎",
        "email": "member@example.com",
        "password": "password123",
        "password_confirm": "password123",
    }
    data.update(overrides)
    return data


class TestRegisterInputNormal:
    def test_valid_input(self) -> None:
        model = RegisterInput(**_valid_register())
        assert model.name == "会員太郎"
        assert str(model.email) == "member@example.com"


class TestRegisterInputBoundary:
    def test_name_min_length_1(self) -> None:
        # FR-001: 氏名 1-50。下限 1 は許可。
        assert RegisterInput(**_valid_register(name="A")).name == "A"

    def test_name_max_length_50(self) -> None:
        name = "あ" * 50
        assert RegisterInput(**_valid_register(name=name)).name == name

    def test_name_over_max_51_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(name="あ" * 51))

    def test_password_min_length_8(self) -> None:
        # FR-001: パスワード 8-64。下限 8 は許可。
        assert RegisterInput(**_valid_register(password="pass1234", password_confirm="pass1234"))

    def test_password_below_min_7_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(password="pass123", password_confirm="pass123"))

    def test_password_max_length_64(self) -> None:
        pw = "a" * 64
        assert RegisterInput(**_valid_register(password=pw, password_confirm=pw))

    def test_password_over_max_65_rejected(self) -> None:
        pw = "a" * 65
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(password=pw, password_confirm=pw))


class TestRegisterInputInvalid:
    def test_name_blank_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(name="   "))

    @pytest.mark.parametrize("bad_email", ["not-an-email", "a@b", "@example.com", "member@"])
    def test_invalid_email_format(self, bad_email: str) -> None:
        # NFR-SEC-004 / ERR-001: メール形式不正は拒否。
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(email=bad_email))

    def test_password_non_alnum_rejected(self) -> None:
        # FR-001: パスワードは英数字。記号は拒否。
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(password="pass!@#$", password_confirm="pass!@#$"))

    def test_password_mismatch_rejected(self) -> None:
        # FR-001: 確認用パスワード不一致は拒否。
        with pytest.raises(ValidationError):
            RegisterInput(**_valid_register(password_confirm="different1"))


class TestLoginInput:
    def test_valid(self) -> None:
        model = LoginInput(email="member@example.com", password="password123")
        assert str(model.email) == "member@example.com"

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginInput(email="bad", password="x")

    def test_empty_password_rejected(self) -> None:
        # FR-002: パスワード必須。
        with pytest.raises(ValidationError):
            LoginInput(email="member@example.com", password="")
