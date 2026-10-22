# trace: FR-001, NFR-SC-01, NFR-SC-16, ADDR-008
"""会員登録（FR-001）の単体テスト。

期待値は FR-001 6.1 および NFR-SC-16（パスワード条件）、CMN-15（前後空白除去）から導出する。
"""
import pytest

from shop.common.errors import EmailAlreadyRegisteredError, ValidationError
from shop.models import Role, User
from shop.services import accounts
from shop.tests.unit import _helpers

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Passw0rd"


# trace: FR-001
def _register(**overrides):
    """既定の正常な入力に上書きを適用して会員登録を実行する。"""
    data = {
        "email": "hanako.sato@example.com",
        "password": VALID_PASSWORD,
        "password_confirmation": VALID_PASSWORD,
        "full_name": "佐藤 花子",
    }
    data.update(overrides)
    return accounts.register_user(**data)


# trace: FR-001
def test_register_user_creates_buyer():
    """正常な入力で購入者（role=buyer）が1件登録される。"""
    user = _register()

    assert user.user_id is not None
    assert user.email == "hanako.sato@example.com"
    assert user.full_name == "佐藤 花子"
    assert user.role == Role.BUYER
    assert user.registered_at is not None
    assert User.objects.count() == 1


# trace: FR-001, NFR-SC-01
def test_register_user_does_not_store_plain_password():
    """パスワードは平文で保存せず、ソルト付き一方向ハッシュで保存する。"""
    user = _register()

    assert user.password_hash != VALID_PASSWORD
    assert VALID_PASSWORD not in user.password_hash
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert accounts.verify_password(VALID_PASSWORD, user.password_hash) is True


# trace: FR-001
def test_register_user_normalizes_email():
    """メールアドレスは前後空白除去・英小文字化して登録する（D-01-02）。"""
    user = _register(email="  Hanako.Sato@Example.COM  ")

    assert user.email == "hanako.sato@example.com"


# trace: FR-001
def test_register_user_strips_full_name():
    """氏名の前後空白（全角空白を含む）を除去して登録する（CMN-15）。"""
    user = _register(full_name="　佐藤 花子　")

    assert user.full_name == "佐藤 花子"


# trace: FR-001
def test_register_user_rejects_duplicated_email_after_normalization():
    """正規化後に同一となるメールアドレスは登録済みとして拒否する。"""
    _register(email="hanako.sato@example.com")

    with pytest.raises(EmailAlreadyRegisteredError) as exc:
        _register(email=" HANAKO.SATO@EXAMPLE.COM ")

    assert exc.value.code == "EMAIL_ALREADY_REGISTERED"
    assert exc.value.http_status == 409
    assert User.objects.count() == 1


# trace: FR-001, NFR-SC-16
@pytest.mark.parametrize(
    ("password", "is_valid"),
    [
        ("Pasw0rd", False),  # 7文字（下限の外側）
        ("Passw0rd", True),  # 8文字（下限）
        ("Passw0rdx", True),  # 9文字（下限の内側）
        ("a1" + "b" * 62, True),  # 64文字（上限）
        ("a1" + "b" * 63, False),  # 65文字（上限の外側）
    ],
)
def test_register_user_password_length_boundary(password, is_valid):
    """パスワードは8文字以上64文字以下とする（境界値）。"""
    if is_valid:
        user = _register(password=password, password_confirmation=password)
        assert user.user_id is not None
    else:
        with pytest.raises(ValidationError) as exc:
            _register(password=password, password_confirmation=password)
        assert [detail["field"] for detail in exc.value.details] == ["password"]


# trace: FR-001, NFR-SC-16
@pytest.mark.parametrize("password", ["Passwordx", "12345678"])
def test_register_user_requires_letter_and_digit(password):
    """英字のみ・数字のみのパスワードを拒否する。"""
    with pytest.raises(ValidationError) as exc:
        _register(password=password, password_confirmation=password)

    assert any(detail["field"] == "password" for detail in exc.value.details)


# trace: FR-001, NFR-SC-16
def test_register_user_rejects_password_equal_to_email():
    """メールアドレスと同一のパスワードを拒否する。"""
    email = "user1@example.com"

    with pytest.raises(ValidationError) as exc:
        _register(email=email, password=email, password_confirmation=email)

    assert any("メールアドレス" in detail["reason"] for detail in exc.value.details)


# trace: FR-001
def test_register_user_keeps_password_whitespace():
    """パスワードの前後空白は除去しない（入力値をそのまま用いる）。"""
    password = " Passw0rd "

    user = _register(password=password, password_confirmation=password)

    assert accounts.verify_password(password, user.password_hash) is True
    assert accounts.verify_password(password.strip(), user.password_hash) is False


# trace: FR-001
def test_register_user_rejects_password_confirmation_mismatch():
    """パスワードとパスワード（確認）が一致しない場合は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        _register(password_confirmation="Passw0rd1")

    assert any(detail["field"] == "password_confirmation" for detail in exc.value.details)


# trace: FR-001
def test_register_user_rejects_empty_password_confirmation():
    """パスワード（確認）未入力は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        _register(password_confirmation="")

    assert any(detail["field"] == "password_confirmation" for detail in exc.value.details)


# trace: FR-001
@pytest.mark.parametrize(
    ("full_name", "is_valid"),
    [("", False), ("あ", True), ("あ" * 50, True), ("あ" * 51, False)],
)
def test_register_user_full_name_length_boundary(full_name, is_valid):
    """氏名は1文字以上50文字以下とする（境界値）。"""
    if is_valid:
        assert _register(full_name=full_name).full_name == full_name
    else:
        with pytest.raises(ValidationError) as exc:
            _register(full_name=full_name)
        assert any(detail["field"] == "full_name" for detail in exc.value.details)


# trace: FR-001
def test_register_user_email_max_length_boundary():
    """メールアドレスは254文字以下とする（境界値）。"""
    local_part = "a" * (254 - len("@example.com"))
    email_254 = f"{local_part}@example.com"
    email_255 = f"{local_part}a@example.com"

    assert _register(email=email_254).email == email_254

    with pytest.raises(ValidationError) as exc:
        _register(email=email_255)
    assert any(detail["field"] == "email" for detail in exc.value.details)


# trace: FR-001
@pytest.mark.parametrize("email", ["", "   ", "invalid", "no-at-mark.example.com", "a@b", "a b@example.com"])
def test_register_user_rejects_invalid_email(email):
    """メールアドレスの形式が正しくない場合は入力エラーとする。"""
    with pytest.raises(ValidationError) as exc:
        _register(email=email)

    assert any(detail["field"] == "email" for detail in exc.value.details)


# trace: FR-001
def test_register_user_reports_all_invalid_fields_at_once():
    """不備のある全項目を1回の入力エラーで列挙する（CMN-16）。"""
    with pytest.raises(ValidationError) as exc:
        accounts.register_user(email="", password="", password_confirmation="", full_name="")

    fields = {detail["field"] for detail in exc.value.details}
    assert fields == {"email", "password", "password_confirmation", "full_name"}
    assert exc.value.http_status == 400


# trace: FR-001
def test_register_user_validates_input_before_duplicate_check():
    """入力不備の判定は登録済み判定より優先する。"""
    _helpers.make_user(email="hanako.sato@example.com")

    with pytest.raises(ValidationError):
        _register(password="short")


# trace: FR-001
def test_register_user_does_not_issue_token_or_session():
    """会員登録では自動ログインしない（認証トークンを発行しない）。"""
    user = _register()

    assert user.auth_tokens.count() == 0
