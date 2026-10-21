# trace: ADDR-001, ADDR-010, ADDR-011
"""URL ルーティング（API と画面）。"""

from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

from web.views import error_views

# trace: ADDR-001
urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("carts.urls")),
    path("api/", include("orders.urls")),
    path("", include("web.urls")),
]

# 静的ファイルの配信経路は、本アプリケーションが配信する設定のときだけ結線する（VUL-08）。
if settings.SERVE_STATIC_FILES:
    urlpatterns.append(
        re_path(
            r"^static/(?P<path>.*)$",
            serve,
            {"document_root": str(settings.BASE_DIR / "web" / "static")},
        )
    )

# 画面向けの共通エラー応答（ADDR-011 DD-005、SCR-901）。
# trace: ADDR-011
handler400 = error_views.bad_request
# trace: ADDR-011
handler403 = error_views.permission_denied
# trace: ADDR-011
handler404 = error_views.not_found
# trace: ADDR-011
handler500 = error_views.server_error
