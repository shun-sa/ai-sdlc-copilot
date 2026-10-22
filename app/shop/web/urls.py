# trace: ADDR-004
"""画面のルーティング（URL は小文字・ハイフン区切り）。"""
from django.urls import path

from shop.web import views_admin, views_cart, views_catalog, views_orders

urlpatterns = [
    path("", views_catalog.item_list),
    path("items/<str:item_id>", views_catalog.item_detail),
    path("register", views_catalog.register),
    path("login", views_catalog.login),
    path("logout", views_catalog.logout),
    path("cart", views_cart.cart),
    path("cart/lines", views_cart.add_line),
    path("cart/lines/<str:cart_line_id>/update", views_cart.update_line),
    path("cart/lines/<str:cart_line_id>/delete", views_cart.remove_line),
    path("cart/apply-coupon", views_cart.apply_coupon),
    path("cart/remove-coupon", views_cart.remove_coupon),
    path("checkout", views_orders.checkout_form),
    path("checkout/confirm", views_orders.checkout),
    path("purchase-orders", views_orders.order_list),
    path("purchase-orders/<str:purchase_order_id>", views_orders.order_detail),
    path("purchase-orders/<str:purchase_order_id>/complete", views_orders.order_complete),
    path("purchase-orders/<str:purchase_order_id>/pay", views_orders.pay),
    path("purchase-orders/<str:purchase_order_id>/cancel", views_orders.cancel),
    path("admin/stock-units", views_admin.stock_unit_list),
    path("admin/purchase-orders", views_admin.order_list),
    path("admin/purchase-orders/<str:purchase_order_id>", views_admin.order_detail),
    path("admin/purchase-orders/<str:purchase_order_id>/ship", views_admin.ship),
    path("admin/purchase-orders/<str:purchase_order_id>/deliver", views_admin.deliver),
    path("admin/purchase-orders/<str:purchase_order_id>/cancel", views_admin.cancel),
]
