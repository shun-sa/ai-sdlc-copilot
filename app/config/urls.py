# trace: ADDR-001, ADDR-012
"""ルートの URL 構成。/api/ 配下は Web API、それ以外は画面。存在しない要求先は 404（内部情報なし）。"""

from django.urls import include, path

urlpatterns = [
    path("api/", include("config.api_urls")),
    path("", include("config.web_urls")),
]

handler400 = "common.views.bad_request"
handler403 = "common.views.permission_denied_view"
handler404 = "common.views.not_found"
handler500 = "common.views.server_error"
