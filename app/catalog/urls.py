# trace: ADDR-008
"""商品カタログ API の URL。"""

from django.urls import path

from catalog import views

urlpatterns = [
    path("collections", views.CollectionListView.as_view(), name="api-collections"),
    path("items", views.ItemListView.as_view(), name="api-items"),
    path("items/<str:item_id>", views.ItemDetailView.as_view(), name="api-item-detail"),
]
