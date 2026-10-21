# trace: ADDR-003, ADDR-008
"""注文・管理者向け照会／更新の API ビュー（FR-030〜FR-034、FR-040〜FR-045）。"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog import serializers as catalog_serializers
from catalog import services as catalog_services
from common.pagination import page_payload
from common.permissions import IsAdmin, IsBuyer
from orders import serializers, services


# trace: ADDR-003
class CheckoutView(APIView):
    """FR-030 注文確定。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        order = services.checkout(request.user, data)
        return Response(serializers.buyer_order_payload(order), status=201)


# trace: ADDR-003
class PurchaseOrderListView(APIView):
    """FR-032 注文履歴一覧照会。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request) -> Response:
        orders, meta = services.list_buyer_orders(request.user, request.query_params.dict())
        results = [serializers.order_summary_payload(order) for order in orders]
        return Response(page_payload(results, meta), status=200)


# trace: ADDR-003
class PurchaseOrderDetailView(APIView):
    """FR-033 注文詳細照会（購入者）。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request, purchase_order_id: str) -> Response:
        order = services.get_buyer_order(request.user, purchase_order_id)
        return Response(serializers.buyer_order_payload(order), status=200)


# trace: ADDR-003
class PurchaseOrderPayView(APIView):
    """FR-031 支払（模擬決済）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        order = services.pay(request.user, purchase_order_id, data)
        return Response(serializers.buyer_order_payload(order), status=200)


# trace: ADDR-003
class PurchaseOrderCancelView(APIView):
    """FR-034 注文キャンセル（購入者）。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        order = services.cancel_by_buyer(request.user, purchase_order_id)
        return Response(serializers.buyer_order_payload(order), status=200)


# trace: ADDR-008
class AdminStockUnitListView(APIView):
    """FR-040 在庫単位一覧照会（管理者）。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        stock_units, meta, _conditions = catalog_services.search_stock_units(request.query_params.dict())
        results = [catalog_serializers.admin_stock_unit_payload(unit) for unit in stock_units]
        return Response(page_payload(results, meta), status=200)


# trace: ADDR-008
class AdminPurchaseOrderListView(APIView):
    """FR-041 注文一覧検索（管理者）。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        params = request.query_params.dict()
        params["status"] = request.query_params.getlist("status")
        orders, meta, _conditions = services.admin_search_orders(params)
        results = [serializers.admin_order_summary_payload(order) for order in orders]
        return Response(page_payload(results, meta), status=200)


# trace: ADDR-008
class AdminPurchaseOrderDetailView(APIView):
    """FR-042 注文詳細照会（管理者）。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request, purchase_order_id: str) -> Response:
        order = services.get_admin_order(purchase_order_id)
        return Response(serializers.admin_order_payload(order), status=200)


# trace: ADDR-003
class AdminPurchaseOrderShipView(APIView):
    """FR-043 出荷登録。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        order = services.ship(request.user, purchase_order_id, data)
        return Response(serializers.admin_order_payload(order), status=200)


# trace: ADDR-003
class AdminPurchaseOrderDeliverView(APIView):
    """FR-044 配達完了登録。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        order = services.deliver(request.user, purchase_order_id)
        return Response(serializers.admin_order_payload(order), status=200)


# trace: ADDR-003
class AdminPurchaseOrderCancelView(APIView):
    """FR-045 注文キャンセル（管理者）。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        order = services.cancel_by_admin(request.user, purchase_order_id)
        return Response(serializers.admin_order_payload(order), status=200)
