# trace: ADDR-001, ADDR-009
"""購入者の注文機能の Web API（FR-030〜FR-034）。"""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.api.authentication import current_user
from shop.api.permissions import IsBuyer
from shop.services import orders


# trace: ADDR-001
class CheckoutView(APIView):
    """注文確定（FR-030）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        """配送先を受け付けて注文を1件作成する。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(orders.checkout(current_user(request), data), status=201)


# trace: ADDR-001
class PurchaseOrderListView(APIView):
    """注文履歴一覧照会（FR-032）。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request) -> Response:
        """本人の注文を注文日時の降順で返す。"""
        return Response(orders.list_orders(current_user(request), request.query_params.get("page")))


# trace: ADDR-001
class PurchaseOrderDetailView(APIView):
    """注文詳細照会（FR-033）。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request, purchase_order_id: str) -> Response:
        """本人の注文の詳細を返す。"""
        return Response(orders.get_order_detail(current_user(request), purchase_order_id))


# trace: ADDR-009
class PayView(APIView):
    """支払（模擬決済）（FR-031）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        """決済サービス（模擬）へ決済を要求し、承認時に支払済へ変更する。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(orders.pay_order(current_user(request), purchase_order_id, data.get("mock_result")))


# trace: ADDR-001
class CancelView(APIView):
    """注文キャンセル（購入者）（FR-034）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        """注文をキャンセルし、在庫を戻す。"""
        return Response(orders.cancel_order(current_user(request), purchase_order_id))
