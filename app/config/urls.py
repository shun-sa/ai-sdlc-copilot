# trace: ADDR-004, ADDR-007
"""ルーティングの最上位定義。Web API は /api、画面はルート配下に配置する。"""
from django.urls import include, path

from shop.web import views_error

urlpatterns = [
    path("api/", include("shop.api.urls")),
    path("", include("shop.web.urls")),
]

handler400 = views_error.bad_request
handler403 = views_error.permission_denied
handler404 = views_error.page_not_found
handler500 = views_error.server_error
