# trace: ADDR-003
"""カート API の URL。"""

from django.urls import path

from carts import views

urlpatterns = [
    path("cart", views.CartView.as_view(), name="api-cart"),
    path("cart/lines", views.CartLineCreateView.as_view(), name="api-cart-lines"),
    path("cart/lines/<str:cart_line_id>", views.CartLineDetailView.as_view(), name="api-cart-line-detail"),
    path("cart/apply-coupon", views.ApplyCouponView.as_view(), name="api-cart-apply-coupon"),
    path("cart/remove-coupon", views.RemoveCouponView.as_view(), name="api-cart-remove-coupon"),
]
