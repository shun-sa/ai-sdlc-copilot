# trace: ADDR-004, ADDR-007
"""Web API のルーティング（api-contract 6.1）。URL は小文字・ハイフン区切りとする。"""
from django.urls import path

from shop.api import views_admin, views_auth, views_cart, views_catalog, views_orders

urlpatterns = [
    path("auth/register", views_auth.RegisterView.as_view()),
    path("auth/login", views_auth.LoginView.as_view()),
    path("auth/logout", views_auth.LogoutView.as_view()),
    path("auth/me", views_auth.MeView.as_view()),
    path("collections", views_catalog.CollectionListView.as_view()),
    path("items", views_catalog.ItemListView.as_view()),
    path("items/<str:item_id>", views_catalog.ItemDetailView.as_view()),
    path("cart", views_cart.CartView.as_view()),
    path("cart/lines", views_cart.CartLineListView.as_view()),
    path("cart/lines/<str:cart_line_id>", views_cart.CartLineDetailView.as_view()),
    path("cart/apply-coupon", views_cart.ApplyCouponView.as_view()),
    path("cart/remove-coupon", views_cart.RemoveCouponView.as_view()),
    path("checkout", views_orders.CheckoutView.as_view()),
    path("purchase-orders", views_orders.PurchaseOrderListView.as_view()),
    path("purchase-orders/<str:purchase_order_id>", views_orders.PurchaseOrderDetailView.as_view()),
    path("purchase-orders/<str:purchase_order_id>/pay", views_orders.PayView.as_view()),
    path("purchase-orders/<str:purchase_order_id>/cancel", views_orders.CancelView.as_view()),
    path("admin/stock-units", views_admin.StockUnitListView.as_view()),
    path("admin/purchase-orders", views_admin.AdminPurchaseOrderListView.as_view()),
    path("admin/purchase-orders/<str:purchase_order_id>", views_admin.AdminPurchaseOrderDetailView.as_view()),
    path("admin/purchase-orders/<str:purchase_order_id>/ship", views_admin.ShipView.as_view()),
    path("admin/purchase-orders/<str:purchase_order_id>/deliver", views_admin.DeliverView.as_view()),
    path("admin/purchase-orders/<str:purchase_order_id>/cancel", views_admin.AdminCancelView.as_view()),
]
