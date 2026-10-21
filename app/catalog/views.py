# trace: ADDR-008
"""商品カタログの API ビュー（FR-010〜FR-012）。"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog import serializers, services
from common.pagination import page_payload


# trace: ADDR-008
class CollectionListView(APIView):
    """FR-010 商品分類一覧照会。認証不要・ページングなし。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        collections = services.list_collections()
        return Response([serializers.collection_payload(item) for item in collections], status=200)


# trace: ADDR-008
class ItemListView(APIView):
    """FR-011 商品一覧検索。認証不要・20件/ページ。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        items, meta, _conditions = services.search_items(request.query_params.dict())
        results = [serializers.item_summary_payload(item) for item in items]
        return Response(page_payload(results, meta), status=200)


# trace: ADDR-008
class ItemDetailView(APIView):
    """FR-012 商品詳細照会。認証不要。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request, item_id: str) -> Response:
        item = services.get_public_item(item_id)
        return Response(serializers.item_detail_payload(item), status=200)
