# trace: ADDR-001, ADDR-007
"""カート機能の Web API（FR-020〜FR-025）。更新後は常にカート表現を返す。"""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.api.authentication import current_user
from shop.api.permissions import IsBuyer
from shop.services import carts


# trace: ADDR-001
class CartView(APIView):
    """カート照会（FR-020）。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request) -> Response:
        """利用中カートの内容を返す（無い場合は作成する）。"""
        return Response(carts.view_cart(current_user(request)))


# trace: ADDR-001
class CartLineListView(APIView):
    """カート明細追加（FR-021）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        """在庫単位と数量を指定して明細を追加する。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(
            carts.add_line(current_user(request), data.get("stock_unit_id"), data.get("quantity"))
        )


# trace: ADDR-001
class CartLineDetailView(APIView):
    """カート明細の数量変更・削除（FR-022、FR-023）。"""

    permission_classes = [IsBuyer]

    def patch(self, request: Request, cart_line_id: str) -> Response:
        """明細の数量を変更する。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(carts.update_line_quantity(current_user(request), cart_line_id, data.get("quantity")))

    def delete(self, request: Request, cart_line_id: str) -> Response:
        """明細を削除する。"""
        return Response(carts.remove_line(current_user(request), cart_line_id))


# trace: ADDR-001
class ApplyCouponView(APIView):
    """クーポン適用（FR-024）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        """クーポンコードを指定してカートへ適用する。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(carts.apply_coupon(current_user(request), data.get("code")))


# trace: ADDR-001
class RemoveCouponView(APIView):
    """クーポン解除（FR-025）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        """適用中のクーポンを解除する。"""
        return Response(carts.remove_coupon(current_user(request)))
