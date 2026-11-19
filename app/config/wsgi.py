# trace: ADDR-014, ADDR-012
"""WSGI の起動点（Gunicorn から読み込む。ADDR-014 4.3 の3）。

要求の Content-Type の文字コード指定（charset）が文字列の符号化方式でない場合、Django は要求の生成時
（クエリ文字列の復号）に例外となり、アプリケーションの共通処理を経ずに失敗する。WSGI の入口でその指定を
取り除いて印を付け、common.middleware.RequestCharsetMiddleware が入力エラー（400）として応答する（NFR-SC-04）。
"""

import os
from collections.abc import Callable, Iterable
from typing import Any

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

_django_application = get_wsgi_application()


# trace: ADDR-012
def application(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
    from django.utils.http import parse_header_parameters

    from common.middleware import INVALID_CHARSET_ENVIRON_KEY, is_unusable_charset

    content_type = environ.get("CONTENT_TYPE") or ""
    if "charset" in content_type.lower():
        main_type, params = parse_header_parameters(content_type)
        if is_unusable_charset(params.get("charset")):
            environ = dict(environ)
            environ["CONTENT_TYPE"] = main_type
            environ[INVALID_CHARSET_ENVIRON_KEY] = True
    return _django_application(environ, start_response)
