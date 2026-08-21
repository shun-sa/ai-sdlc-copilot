"""認証系スキーマ (FR-001 / FR-002)。"""

from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

_PASSWORD_RE = re.compile(r"^[A-Za-z0-9]+$")


class RegisterInput(BaseModel):
    """会員登録入力 (FR-001)。"""

    name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=64)
    password_confirm: str = Field(min_length=8, max_length=64)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("氏名を入力してください。")
        return v

    @field_validator("password")
    @classmethod
    def _password_alnum(cls, v: str) -> str:
        # パスワードは英数 (FR-001)
        if not _PASSWORD_RE.match(v):
            raise ValueError("パスワードは英数字で入力してください。")
        return v

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterInput":
        if self.password != self.password_confirm:
            raise ValueError("確認用パスワードが一致しません。")
        return self


class LoginInput(BaseModel):
    """ログイン入力 (FR-002)。"""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=64)
