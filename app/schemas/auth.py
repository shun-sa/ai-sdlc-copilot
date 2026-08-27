from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# FR-001 / FR-002: 会員登録・ログインの入力検証（NFR-SEC-004 / ADR-009）。


class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=64)
    password_confirm: str

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("氏名を入力してください。")
        return value

    @field_validator("password")
    @classmethod
    def _password_alnum(cls, value: str) -> str:
        if not value.isalnum() or not value.isascii():
            raise ValueError("パスワードは英数字で入力してください。")
        return value

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterInput":
        if self.password != self.password_confirm:
            raise ValueError("パスワードが一致しません。")
        return self


class LoginInput(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=64)
