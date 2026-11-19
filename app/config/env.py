# trace: ADDR-014, ADDR-011
"""環境変数だけから設定値を読み取る（ADDR-014 4.3 の1・2、DD-001・DD-002・DD-011）。

真偽値は未設定のときだけ false とし、設定されている場合は小文字の true・false だけを受理する。
それ以外の表記（True・1・yes・空文字・前後空白付き等）は環境を問わず設定エラーとする。
"""

import os

from django.core.exceptions import ImproperlyConfigured

ENV_DEVELOPMENT = "development"
ENV_PRODUCTION = "production"
_VALID_ENVS = (ENV_DEVELOPMENT, ENV_PRODUCTION)


# trace: ADDR-014
def read_environment_name() -> str:
    """MINICOMMERCE_ENV を必須・既定なしで読む（fail-closed）。"""
    value = os.environ.get("MINICOMMERCE_ENV")
    if value is None or value not in _VALID_ENVS:
        raise ImproperlyConfigured("MINICOMMERCE_ENV must be set to 'development' or 'production'.")
    return value


# trace: ADDR-014, ADDR-011
def read_bool(name: str) -> bool:
    """真偽値の設定値を厳格に解釈する（未設定は false、設定時は小文字の true/false のみ）。"""
    value = os.environ.get(name)
    if value is None:
        return False
    if value == "true":
        return True
    if value == "false":
        return False
    raise ImproperlyConfigured(f"{name} must be 'true' or 'false' (lowercase) when set.")


# trace: ADDR-014
def read_required(name: str) -> str:
    """秘密情報など既定値を持たない必須の設定値を読む（未設定・空は設定エラー）。"""
    value = os.environ.get(name)
    if value is None or value == "":
        raise ImproperlyConfigured(f"{name} must be set.")
    return value


# trace: ADDR-014
def read_optional(name: str, default: str) -> str:
    """秘密情報でない設定値を読む（未設定・空なら既定値）。"""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


# trace: ADDR-014
def read_list(name: str, default: list[str]) -> list[str]:
    """カンマ区切りの設定値を読む。"""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


# trace: ADDR-014
def read_proxy_ssl_header(name: str) -> tuple[str, str] | None:
    """HTTPS を終端する前段のヘッダー指定（ヘッダー名=値）を Django の形式へ変換する。"""
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    if "=" not in value:
        raise ImproperlyConfigured(f"{name} must be in the form 'Header-Name=value'.")
    header, expected = value.split("=", 1)
    header = header.strip()
    expected = expected.strip()
    if not header or not expected:
        raise ImproperlyConfigured(f"{name} must be in the form 'Header-Name=value'.")
    meta_name = "HTTP_" + header.upper().replace("-", "_")
    return meta_name, expected
