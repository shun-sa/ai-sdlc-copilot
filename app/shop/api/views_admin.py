# trace: ADDR-001, ADDR-006
"""管理者機能の Web API（FR-040〜FR-045）。"""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shop.api.authentication import current_user
from shop.api.permissions import IsAdmin
from shop.services import admin_orders


# trace: ADDR-006
class StockUnitListView(APIView):
    """在庫単位一覧照会（FR-040）。50件/ページ。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        """検索条件に従って在庫単位を SKU 昇順で返す。"""
        return Response(
            admin_orders.search_stock_units(
                raw_sku=request.query_params.get("sku"),
                raw_item_name=request.query_params.get("item_name"),
                raw_supplier_id=request.query_params.get("supplier_id"),
                raw_low_stock_only=request.query_params.get("low_stock_only"),
                raw_page=request.query_params.get("page"),
            )
        )


# trace: ADDR-006
class AdminPurchaseOrderListView(APIView):
    """注文一覧検索（管理者）（FR-041）。20件/ページ。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request) -> Response:
        """検索条件に従って全購入者の注文を返す。"""
        return Response(
            admin_orders.search_orders(
                raw_order_number=request.query_params.get("order_number"),
                raw_statuses=request.query_params.getlist("status"),
                raw_ordered_from=request.query_params.get("ordered_from"),
                raw_ordered_to=request.query_params.get("ordered_to"),
                raw_buyer_email=request.query_params.get("buyer_email"),
                raw_page=request.query_params.get("page"),
            )
        )


# trace: ADDR-001
class AdminPurchaseOrderDetailView(APIView):
    """注文詳細照会（管理者）（FR-042）。"""

    permission_classes = [IsAdmin]

    def get(self, request: Request, purchase_order_id: str) -> Response:
        """管理者向け注文詳細を返す。"""
        return Response(admin_orders.get_order_detail(purchase_order_id))


# trace: ADDR-001
class ShipView(APIView):
    """出荷登録（FR-043）。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        """支払済の注文を出荷済にする。"""
        data = request.data if isinstance(request.data, dict) else {}
        return Response(
            admin_orders.ship_order(current_user(request), purchase_order_id, data.get("tracking_number"))
        )


# trace: ADDR-001
class DeliverView(APIView):
    """配達完了登録（FR-044）。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        """出荷済の注文を配達完了にする。"""
        return Response(admin_orders.deliver_order(current_user(request), purchase_order_id))


# trace: ADDR-001
class AdminCancelView(APIView):
    """注文キャンセル（管理者）（FR-045）。"""

    permission_classes = [IsAdmin]

    def post(self, request: Request, purchase_order_id: str) -> Response:
        """出荷前の注文をキャンセルし、在庫を戻す。"""
        return Response(admin_orders.cancel_order(current_user(request), purchase_order_id))
