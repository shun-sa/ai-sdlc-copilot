# trace: ADDR-006
"""商品カタログ参照の Web API（FR-010〜FR-012）。認証不要。"""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.services import catalog


# trace: ADDR-006
class CollectionListView(APIView):
    """商品分類一覧照会（FR-010）。ページングを用いず全件を配列で返す。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        """全商品分類を木構造の深さ優先順で返す。"""
        return Response(catalog.list_collections())


# trace: ADDR-006
class ItemListView(APIView):
    """商品一覧検索（FR-011）。20件/ページ。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        """検索条件・並び順・ページ番号に従って商品一覧を返す。"""
        return Response(
            catalog.search_items(
                raw_collection_id=request.query_params.get("collection_id"),
                raw_keyword=request.query_params.get("keyword"),
                raw_sort=request.query_params.get("sort"),
                raw_page=request.query_params.get("page"),
            )
        )


# trace: ADDR-006
class ItemDetailView(APIView):
    """商品詳細照会（FR-012）。"""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request, item_id: str) -> Response:
        """商品の情報と在庫単位の一覧（SKU昇順）を返す。"""
        return Response(catalog.get_item_detail(item_id))
