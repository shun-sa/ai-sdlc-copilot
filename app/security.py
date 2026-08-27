import bcrypt


def hash_password(plain_password: str) -> str:
    """パスワードをbcryptで一方向ハッシュ化する（ADR-004 / NFR-SEC-001）。"""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """平文とbcryptハッシュを照合する。照合以外に平文を保持・出力しない。"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
