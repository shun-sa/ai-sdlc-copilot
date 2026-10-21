# trace: ADDR-003
"""注文・管理者向け API の URL。"""

from django.urls import path

from orders import views

urlpatterns = [
    path("checkout", views.CheckoutView.as_view(), name="api-checkout"),
    path("purchase-orders", views.PurchaseOrderListView.as_view(), name="api-purchase-orders"),
    path(
        "purchase-orders/<str:purchase_order_id>",
        views.PurchaseOrderDetailView.as_view(),
        name="api-purchase-order-detail",
    ),
    path(
        "purchase-orders/<str:purchase_order_id>/pay",
        views.PurchaseOrderPayView.as_view(),
        name="api-purchase-order-pay",
    ),
    path(
        "purchase-orders/<str:purchase_order_id>/cancel",
        views.PurchaseOrderCancelView.as_view(),
        name="api-purchase-order-cancel",
    ),
    path("admin/stock-units", views.AdminStockUnitListView.as_view(), name="api-admin-stock-units"),
    path(
        "admin/purchase-orders",
        views.AdminPurchaseOrderListView.as_view(),
        name="api-admin-purchase-orders",
    ),
    path(
        "admin/purchase-orders/<str:purchase_order_id>",
        views.AdminPurchaseOrderDetailView.as_view(),
        name="api-admin-purchase-order-detail",
    ),
    path(
        "admin/purchase-orders/<str:purchase_order_id>/ship",
        views.AdminPurchaseOrderShipView.as_view(),
        name="api-admin-purchase-order-ship",
    ),
    path(
        "admin/purchase-orders/<str:purchase_order_id>/deliver",
        views.AdminPurchaseOrderDeliverView.as_view(),
        name="api-admin-purchase-order-deliver",
    ),
    path(
        "admin/purchase-orders/<str:purchase_order_id>/cancel",
        views.AdminPurchaseOrderCancelView.as_view(),
        name="api-admin-purchase-order-cancel",
    ),
]
