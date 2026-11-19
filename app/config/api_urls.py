# trace: ADDR-001
"""Web API のパス（ADDR-001 4.3 の1・4：/api/・/api/admin/、小文字・ハイフン区切り、末尾スラッシュあり）。

パス中の識別子は文字列で受け取り、業務処理層で解釈する（解釈できない値は対象なし：CMN-18。
判定順序 CMN-14 を保つため、識別子の解釈は業務処理の手順の位置で行う）。
"""

from django.urls import path

from accounts import views_api as accounts_api
from carts import views_api as carts_api
from catalog import views_api as catalog_api
from orders import views_api as orders_api

urlpatterns = [
    path("auth/register/", accounts_api.RegisterApi.as_view()),
    path("auth/login/", accounts_api.LoginApi.as_view()),
    path("auth/logout/", accounts_api.LogoutApi.as_view()),
    path("auth/me/", accounts_api.MeApi.as_view()),
    path("categories/", catalog_api.CategoryListApi.as_view()),
    path("products/", catalog_api.ProductListApi.as_view()),
    path("products/<str:product_id>/", catalog_api.ProductDetailApi.as_view()),
    path("cart/", carts_api.CartApi.as_view()),
    path("cart/items/", carts_api.CartItemsApi.as_view()),
    path("cart/items/<str:cart_item_id>/", carts_api.CartItemApi.as_view()),
    path("cart/coupon/", carts_api.CartCouponApi.as_view()),
    path("orders/", orders_api.OrdersApi.as_view()),
    path("orders/<str:order_id>/", orders_api.OrderDetailApi.as_view()),
    path("orders/<str:order_id>/payment/", orders_api.OrderPaymentApi.as_view()),
    path("orders/<str:order_id>/cancel/", orders_api.OrderCancelApi.as_view()),
    path("admin/stock-units/", catalog_api.StockUnitListApi.as_view()),
    path("admin/orders/", orders_api.AdminOrdersApi.as_view()),
    path("admin/orders/<str:order_id>/", orders_api.AdminOrderDetailApi.as_view()),
    path("admin/orders/<str:order_id>/ship/", orders_api.AdminOrderShipApi.as_view()),
    path("admin/orders/<str:order_id>/deliver/", orders_api.AdminOrderDeliverApi.as_view()),
    path("admin/orders/<str:order_id>/cancel/", orders_api.AdminOrderCancelApi.as_view()),
]
