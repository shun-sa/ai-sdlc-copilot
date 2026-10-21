# trace: ADDR-010
"""画面の URL（小文字・ハイフン区切り）。"""

from django.urls import path

from web.views import admin_views, auth_views, cart_views, catalog_views, order_views

urlpatterns = [
    path("", catalog_views.item_list, name="web-items"),
    path("items/<str:item_id>/", catalog_views.item_detail, name="web-item-detail"),
    path("register/", auth_views.register, name="web-register"),
    path("login/", auth_views.login, name="web-login"),
    path("logout/", auth_views.logout, name="web-logout"),
    path("cart/", cart_views.cart, name="web-cart"),
    path("cart/lines/add/", cart_views.add_line, name="web-cart-add-line"),
    path("cart/lines/<str:cart_line_id>/update/", cart_views.update_line, name="web-cart-update-line"),
    path("cart/lines/<str:cart_line_id>/delete/", cart_views.delete_line, name="web-cart-delete-line"),
    path("cart/coupon/apply/", cart_views.apply_coupon, name="web-cart-apply-coupon"),
    path("cart/coupon/remove/", cart_views.remove_coupon, name="web-cart-remove-coupon"),
    path("checkout/", order_views.checkout, name="web-checkout"),
    path("orders/", order_views.order_history, name="web-orders"),
    path(
        "orders/<str:purchase_order_id>/complete/",
        order_views.order_complete,
        name="web-order-complete",
    ),
    path("orders/<str:purchase_order_id>/", order_views.order_detail, name="web-order-detail"),
    path("orders/<str:purchase_order_id>/pay/", order_views.payment, name="web-order-pay"),
    path("orders/<str:purchase_order_id>/cancel/", order_views.cancel_order, name="web-order-cancel"),
    path("admin-console/stock-units/", admin_views.stock_unit_list, name="web-admin-stock-units"),
    path("admin-console/orders/", admin_views.order_list, name="web-admin-orders"),
    path(
        "admin-console/orders/<str:purchase_order_id>/",
        admin_views.order_detail,
        name="web-admin-order-detail",
    ),
    path(
        "admin-console/orders/<str:purchase_order_id>/ship/",
        admin_views.ship,
        name="web-admin-order-ship",
    ),
    path(
        "admin-console/orders/<str:purchase_order_id>/deliver/",
        admin_views.deliver,
        name="web-admin-order-deliver",
    ),
    path(
        "admin-console/orders/<str:purchase_order_id>/cancel/",
        admin_views.cancel,
        name="web-admin-order-cancel",
    ),
]
