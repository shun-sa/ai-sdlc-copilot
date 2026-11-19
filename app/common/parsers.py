# trace: ADDR-001
"""Web API の要求本文の解釈（ADDR-001 4.3 の7：JSON として解釈できない本文は 400 input_error）。

DRF の設定（DEFAULT_PARSER_CLASSES）から読み込まれるため、APIView を読み込むモジュール（common.api）と分ける。
"""

from typing import Any

from rest_framework import exceptions as drf_exceptions
from rest_framework.parsers import JSONParser

MSG_BODY_PARSE_ERROR = "要求の本文を JSON として解釈できません。"


class JsonBodyParser(JSONParser):
    """要求本文の JSON の解釈。解釈できない本文は全て ParseError（400 input_error）とする。

    深い入れ子（RecursionError）、文字コードの指定の誤り（文字列を返さない・圧縮等の符号化方式）による失敗、
    本文の読取りの失敗も外部入力の誤りとして扱い、システムエラー（ERR-08）・LOG-02 の対象にしない（NFR-SC-04）。
    """

    def parse(self, stream: Any, media_type: str | None = None, parser_context: dict[str, Any] | None = None) -> Any:
        try:
            return super().parse(stream, media_type, parser_context)
        except drf_exceptions.ParseError:
            raise
        except MemoryError:
            raise
        except Exception as exc:  # noqa: BLE001 - 本文の復号・解釈の失敗（符号化方式ごとに例外の種類が異なる）は入力の誤り
            raise drf_exceptions.ParseError(MSG_BODY_PARSE_ERROR) from exc
