# trace: ADDR-001, ADDR-012, ADDR-006
"""入力値の正規化と型判定の共通部品（CMN-15、CMN-18、ADDR-001 INV-002、ADDR-012 DD-003）。

業務処理層が全ての外部入力（path・query・本文・定義ファイル）を型・桁数・値域・形式で検証するために使う。
データベースへ保存・照会する文字列にデータベースが受理しない文字（NUL 等）が含まれる場合は、
データベースの操作に至る前に各要件の規則（入力エラー、または該当なし）で扱う。
整数・識別子は桁数を判定してから数値へ変換する（64ビット整数の範囲外の値で変換の例外を起こさない）。
"""

import re
from typing import Any

# 前後の空白（半角スペース・全角スペース・タブ・改行）
_WHITESPACE = " \t\r\n\u3000"
# 文字列全体との一致で判定する（fullmatch。末尾の改行を許す $ を使わない：CMN-18）
_INT_PATTERN = re.compile(r"(-?)([0-9]+)")
_ID_PATTERN = re.compile(r"[0-9]+")
_MAX_BIGINT = 9223372036854775807
_MIN_BIGINT = -9223372036854775808
# 64ビット整数の最大桁数（先頭の0を除く）。これを超える数字列は数値へ変換せず範囲外とする
_BIGINT_DIGITS = 19
# 64ビット整数の範囲外の整数を表す値（値域の判定で必ず範囲外となる。識別子としては解釈しない）
INT_ABOVE_RANGE = _MAX_BIGINT + 1
INT_BELOW_RANGE = _MIN_BIGINT - 1
# データベース（PostgreSQL の文字列・JSON）が受理しない文字：NUL（0x00）と UTF-8 に符号化できないサロゲート
_UNSTORABLE = re.compile("[\x00\ud800-\udfff]")
# Unicode の文字でない値（対になっていないサロゲート）。UTF-8 に符号化できず、照合計算にも渡せない
_SURROGATE = re.compile("[\ud800-\udfff]")


# trace: ADDR-012
def has_unstorable_chars(value: Any) -> bool:
    """文字列にデータベースが受理しない文字（NUL 等）が含まれるか判定する（NFR-SC-04）。"""
    return isinstance(value, str) and _UNSTORABLE.search(value) is not None


# trace: ADDR-012
def has_surrogates(value: Any) -> bool:
    """文字列が Unicode の文字でない値（対になっていないサロゲート）を含むか判定する（文字列として扱えない値）。"""
    return isinstance(value, str) and _SURROGATE.search(value) is not None


# trace: ADDR-012
def unstorable_message(label: str) -> str:
    """使用できない文字を含む入力の通知文言（fields[].reason は invalid_format：ADDR-001 4.3 の12）。"""
    return f"{label}に使用できない文字（制御文字等）が含まれています。"


# trace: ADDR-012
def strip_text(value: Any) -> Any:
    """文字列なら前後の空白を除去する。文字列以外はそのまま返す（型判定は呼出し側）。"""
    if isinstance(value, str):
        return value.strip(_WHITESPACE)
    return value


# trace: ADDR-012
def is_blank(value: Any) -> bool:
    """未入力（値なし、または前後空白除去後に0文字）か判定する。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip(_WHITESPACE) == ""
    return False


# trace: ADDR-001
def _bounded(number: int) -> int:
    """64ビット整数の範囲外の整数を INT_ABOVE_RANGE／INT_BELOW_RANGE に置き換える。"""
    if number > _MAX_BIGINT:
        return INT_ABOVE_RANGE
    if number < _MIN_BIGINT:
        return INT_BELOW_RANGE
    return number


# trace: ADDR-001
def _digits_to_int(negative: bool, digits: str) -> int:
    """数字列を桁数の判定後に数値へ変換する（桁数の上限を超える数字列は変換しない）。"""
    significant = digits.lstrip("0")
    if len(significant) > _BIGINT_DIGITS:
        return INT_BELOW_RANGE if negative else INT_ABOVE_RANGE
    number = int(significant or "0")
    return _bounded(-number if negative else number)


# trace: ADDR-001
def parse_int(value: Any) -> int | None:
    """整数として解釈する。JSON の整数（真偽値を除く）または整数表記の文字列のみ受け付ける。

    整数でない値（小数・真偽値・数字以外を含む文字列等）は None。64ビット整数の範囲外の整数は
    INT_ABOVE_RANGE／INT_BELOW_RANGE を返し、呼出し側の値域の判定（1以上・10以下等）で範囲外として扱う。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return _bounded(value)
    if isinstance(value, str):
        matched = _INT_PATTERN.fullmatch(value.strip(_WHITESPACE))
        if matched:
            return _digits_to_int(matched.group(1) == "-", matched.group(2))
    return None


# trace: ADDR-001, ADDR-006
def parse_identifier(value: Any) -> int | None:
    """識別子として解釈する（1以上の64ビット整数）。解釈できない値は None（対象なし：CMN-18）。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and _ID_PATTERN.fullmatch(value):
        number = _digits_to_int(False, value)
    else:
        return None
    if number < 1 or number > _MAX_BIGINT:
        return None
    return number


# trace: ADDR-001, ADDR-006
def is_ascii_digits(value: Any) -> bool:
    """文字列全体が ASCII の数字（0〜9）だけか判定する（fullmatch。全角・他の文字体系の数字を含めない：CMN-18）。"""
    return isinstance(value, str) and _ID_PATTERN.fullmatch(value) is not None


# trace: ADDR-012
def text_length(value: str) -> int:
    """文字数（Unicode のコードポイント数）。"""
    return len(value)
