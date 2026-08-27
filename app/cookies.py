from itsdangerous import BadSignature, URLSafeSerializer

_SALT = "session-cookie"


class SessionCookieCodec:
    """署名付きセッションCookieのエンコード/デコード（ADR-005）。

    Cookie値はサーバー署名され、改ざんは検知される。クライアント改ざん値を
    認証状態の根拠にしない。
    """

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeSerializer(secret_key, salt=_SALT)

    def encode(self, session_token: str) -> str:
        return self._serializer.dumps({"t": session_token})

    def decode(self, cookie_value: str) -> str | None:
        try:
            data = self._serializer.loads(cookie_value)
        except BadSignature:
            return None
        if not isinstance(data, dict):
            return None
        token = data.get("t")
        return token if isinstance(token, str) else None
