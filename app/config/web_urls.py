# trace: ADDR-012
"""画面のパス（SCR-001〜SCR-010、SCR-101〜SCR-103）。管理者向けは /manage/ 配下。

Django 付属の管理サイト（admin/）は設けない（ADDR-012 DD-010）。
"""

from django.urls import path

from accounts import views_web as accounts_web
from carts import views_web as carts_web
from catalog import views_web as catalog_web
from orders import views_web as orders_web

urlpatterns = [
    path("", catalog_web.product_list_view),
    path("products/<str:product_id>/", catalog_web.product_detail_view),
    path("register/", accounts_web.register_view),
    path("login/", accounts_web.login_view),
    path("logout/", accounts_web.logout_view),
    path("cart/", carts_web.cart_view),
    path("cart/items/add/", carts_web.cart_add_view),
    path("cart/items/<str:cart_item_id>/quantity/", carts_web.cart_quantity_view),
    path("cart/items/<str:cart_item_id>/delete/", carts_web.cart_delete_view),
    path("cart/coupon/apply/", carts_web.coupon_apply_view),
    path("cart/coupon/remove/", carts_web.coupon_remove_view),
    path("checkout/", orders_web.checkout_view),
    path("orders/", orders_web.history_view),
    path("orders/<str:order_id>/", orders_web.detail_view),
    path("orders/<str:order_id>/complete/", orders_web.complete_view),
    path("orders/<str:order_id>/payment/", orders_web.payment_view),
    path("orders/<str:order_id>/cancel/", orders_web.cancel_view),
    path("manage/stock-units/", catalog_web.stock_unit_list_view),
    path("manage/orders/", orders_web.admin_list_view),
    path("manage/orders/<str:order_id>/", orders_web.admin_detail_view),
    path("manage/orders/<str:order_id>/ship/", orders_web.admin_ship_view),
    path("manage/orders/<str:order_id>/deliver/", orders_web.admin_deliver_view),
    path("manage/orders/<str:order_id>/cancel/", orders_web.admin_cancel_view),
]
