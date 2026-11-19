# trace: ADDR-003
"""パスワード（照合用）の保持方式（ADDR-003 r2 DD-001）。

Django 標準の PBKDF2PasswordHasher はパスワードの UTF-8 バイト列をそのまま HMAC-SHA256 の鍵とするため、
鍵が64バイト以下では HMAC の0埋めにより末尾の NUL の有無を区別できない。本ハッシャーは受け取った
パスワードを変換せずに UTF-8 で符号化して SHA-256 を計算し、その小文字16進64文字（常に64バイト）を
PBKDF2-HMAC-SHA256 の鍵とすることで、文字列として異なるパスワードを一致と判定しない（INV-004）。

- 鍵の変換は encode でだけ行う。verify・harden_runtime は継承元のまま encode を経由する（DD-001）。
- ソルト・反復回数・保持値の形式（方式＄反復回数＄ソルト＄ハッシュ）は継承元（Django 5.2 既定）のまま。
  反復回数を既定値より小さくしない（DD-003）。
- 平文・鍵として用いる中間値（SHA-256 の16進値）・保持値を保持・ログ出力しない（DD-005）。
"""

import hashlib

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.utils.encoding import force_bytes


# trace: ADDR-003
class PBKDF2SHA256HexKeyPasswordHasher(PBKDF2PasswordHasher):
    """方式名 pbkdf2_sha256_sha256hex。PASSWORD_HASHERS に置く唯一のハッシャー（DD-006）。"""

    algorithm = "pbkdf2_sha256_sha256hex"

    def encode(self, password: str, salt: str, iterations: int | None = None) -> str:
        self._check_encode_args(password, salt)
        # 文字の除去・置換・正規化を行わない（DD-007、INV-005）。文字列は UTF-8（strict）で符号化し、
        # 符号化できない値は例外のまま呼出し元へ返す（継承元の pbkdf2 と同じ force_bytes の扱い）
        key = hashlib.sha256(force_bytes(password)).hexdigest()
        return super().encode(key, salt, iterations)
