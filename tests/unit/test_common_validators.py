# trace: FR-001, FR-011, FR-021, FR-024, FR-030, FR-040, FR-041, FR-043, NFR-SC-04, NFR-SC-16, ADDR-011
"""共通の入力検証（CMN-15 空白除去、CMN-16 全項目通知、CMN-35 ページ番号）の単体テスト。

期待結果は機能要件 6.1.3（会員登録の入力条件）、6.6.3（商品一覧検索の入力）、
共通機能要件 CMN-15／CMN-16／CMN-35、およびデータ要件 D-01-02（メールアドレス正規化）、
D-07-02（クーポンコード正規化）から導出する。
"""

from __future__ import annotations

import pytest
from common.exceptions import ValidationFailed
from common.validators import (
    COUPON_CODE_PATTERN,
    ORDER_NUMBER_PATTERN,
    PHONE_PATTERN,
    POSTAL_CODE_PATTERN,
    TRACKING_NUMBER_PATTERN,
    ValidationCollector,
    is_email_format,
    normalize_coupon_code,
    normalize_email,
    normalize_text,
    parse_bool,
    parse_int,
    password_violations,
    validate_page,
)


# trace: FR-001
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  値  ", "値"),
        ("\u3000全角空白\u3000", "全角空白"),
        ("\t\r\nタブ改行\n", "タブ改行"),
        ("", ""),
        (None, ""),
        (123, "123"),
    ],
)
def test_normalize_text_removes_surrounding_whitespace(value, expected):
    """CMN-15：前後の半角・全角スペース、タブ、改行を除去する。"""
    assert normalize_text(value) == expected


# trace: FR-001
def test_normalize_email_lowercases_and_trims():
    """D-01-02：メールアドレスは前後空白除去と英小文字化で正規化する。"""
    assert normalize_email("  User.Name@Example.TEST ") == "user.name@example.test"


# trace: FR-024
def test_normalize_coupon_code_uppercases_and_trims():
    """D-07-02：クーポンコードは前後空白除去と英大文字化で正規化する。"""
    assert normalize_coupon_code(" save-1000 ") == "SAVE-1000"


# trace: FR-001
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("user@example.test", True),
        ("user.name+tag@example.co.jp", True),
        ("userexample.test", False),
        ("user@@example.test", False),
        ("user name@example.test", False),
        ("@example.test", False),
        ("user@", False),
        ("", False),
    ],
)
def test_is_email_format_requires_local_and_domain_without_space(value, expected):
    """メールアドレスの形式はローカル部＠ドメイン部で空白を含まない。"""
    assert is_email_format(value) is expected


# trace: NFR-SC-16
@pytest.mark.parametrize(
    ("password", "email", "expected_reasons"),
    [
        ("abcd123", "", ["パスワードは8文字以上64文字以下で入力してください。"]),
        ("abcd1234", "", []),
        ("a" * 63 + "1", "", []),
        ("a" * 63 + "12", "", ["パスワードは8文字以上64文字以下で入力してください。"]),
        ("12345678", "", ["パスワードには英字を1文字以上含めてください。"]),
        ("abcdefgh", "", ["パスワードには数字を1文字以上含めてください。"]),
        (
            "USER1@example.test",
            "user1@example.test",
            ["パスワードにメールアドレスと同じ文字列は使用できません。"],
        ),
    ],
)
def test_password_violations_follow_fr001_rules(password, email, expected_reasons):
    """FR-001 6.1.3：8〜64文字、英字1文字以上、数字1文字以上、メールアドレスと不一致。"""
    assert password_violations(password, email) == expected_reasons


# trace: FR-001
def test_password_violations_reports_every_broken_rule():
    """CMN-16：条件を満たさない理由をすべて列挙する。"""
    reasons = password_violations("短い", "")

    assert len(reasons) == 3


# trace: FR-021
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, 5),
        ("5", 5),
        (" 7 ", 7),
        ("-3", -3),
        ("0", 0),
        ("abc", None),
        ("1.5", None),
        ("", None),
        (None, None),
        (True, None),
        (False, None),
    ],
)
def test_parse_int_accepts_only_integers(value, expected):
    """整数として解釈できない値は None とする（真偽値は整数として扱わない）。"""
    assert parse_int(value) == expected


# trace: FR-040
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        (" TRUE ", True),
        ("1", None),
        ("yes", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_bool_accepts_only_true_or_false(value, expected):
    """FR-040 6.20.3：低在庫のみは true／false のいずれかで指定する。"""
    assert parse_bool(value) == expected


# trace: FR-011
@pytest.mark.parametrize(("value", "expected"), [(None, 1), ("", 1), ("  ", 1), ("3", 3), (2, 2)])
def test_validate_page_defaults_to_one(value, expected):
    """CMN-35：ページ番号の省略時は1とする。"""
    collector = ValidationCollector()

    assert validate_page(value, collector) == expected
    assert collector.has_errors is False


# trace: NFR-SC-04
@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_validate_page_rejects_non_positive_integers(value):
    """CMN-35：整数でない値・1未満は入力エラーとする。"""
    collector = ValidationCollector()

    validate_page(value, collector)

    assert collector.details == [
        {"field": "page", "reason": "ページ番号は1以上の整数で指定してください。"}
    ]


# trace: FR-001
def test_validation_collector_raises_with_every_detail():
    """CMN-16：不備のある全項目を1回の例外で通知する。"""
    collector = ValidationCollector()
    collector.add("email", "メールアドレスを入力してください。")
    collector.add("password", "パスワードを入力してください。")

    with pytest.raises(ValidationFailed) as error:
        collector.raise_if_any()

    assert [detail["field"] for detail in error.value.details] == ["email", "password"]
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.status_code == 400


# trace: FR-001
def test_validation_collector_does_not_raise_without_errors():
    """不備がない場合は例外を送出しない。"""
    collector = ValidationCollector()

    assert collector.has_errors is False
    assert collector.raise_if_any() is None


# trace: FR-024
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("SAVE-1000", True),
        ("A", True),
        ("A" * 20, True),
        ("A" * 21, False),
        ("save", False),
        ("SAVE_1", False),
        ("", False),
    ],
)
def test_coupon_code_pattern_allows_upper_digits_hyphen_within_20(value, expected):
    """FR-024 6.12.3：クーポンコードは英大文字・数字・ハイフンの20文字以内。"""
    assert bool(COUPON_CODE_PATTERN.match(value)) is expected


# trace: FR-030
@pytest.mark.parametrize(
    ("value", "expected"),
    [("1234567", True), ("123-4567", True), ("12345678", False), ("123-456", False), ("abcdefg", False)],
)
def test_postal_code_pattern_accepts_seven_digits_with_optional_hyphen(value, expected):
    """FR-030 6.15.3：郵便番号は「1234567」または「123-4567」。"""
    assert bool(POSTAL_CODE_PATTERN.match(value)) is expected


# trace: FR-030
@pytest.mark.parametrize(("value", "expected"), [("09012345678", True), ("03-1234-5678", True), ("090-abc", False)])
def test_phone_pattern_allows_digits_and_hyphen(value, expected):
    """FR-030 6.15.3：電話番号は数字とハイフンだけで構成する。"""
    assert bool(PHONE_PATTERN.match(value)) is expected


# trace: FR-043
@pytest.mark.parametrize(
    ("value", "expected"),
    [("ABC-123", True), ("a" * 30, True), ("a" * 31, False), ("ABC_123", False)],
)
def test_tracking_number_pattern_allows_alnum_and_hyphen_within_30(value, expected):
    """FR-043 6.23.3：配送伝票番号は英数字とハイフンの30文字以内。"""
    assert bool(TRACKING_NUMBER_PATTERN.match(value)) is expected


# trace: FR-041
@pytest.mark.parametrize(
    ("value", "expected"),
    [("PO-00000001", True), ("PO-12345678", True), ("PO-1234567", False), ("po-12345678", False), ("12345678", False)],
)
def test_order_number_pattern_requires_prefix_and_eight_digits(value, expected):
    """FR-041 6.21.3：注文番号は「PO-」＋数字8桁。"""
    assert bool(ORDER_NUMBER_PATTERN.match(value)) is expected
