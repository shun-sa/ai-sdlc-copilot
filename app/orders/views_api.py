# trace: ADDR-001, ADDR-012
"""注文の Web API（FR-030〜FR-034、FR-041〜FR-045）。"""

from rest_framework.request import Request
from rest_framework.response import Response

from common.api import BaseApiView, request_body, require_admin, require_buyer, run
from orders import services


# trace: ADDR-001, ADDR-012
class OrdersApi(BaseApiView):
    """FR-032 GET・FR-030 POST /api/orders/。"""

    def get(self, request: Request) -> Response:
        return run(
            request,
            "FR-032 orders",
            lambda: services.list_my_orders(require_buyer(request, "E-032"), request.query_params.get("page")),
        )

    def post(self, request: Request) -> Response:
        def action() -> dict:
            user = require_buyer(request, "E-030")
            body = request_body(request)
            return services.place_order(user, body.get("shipping_address"))

        return run(request, "FR-030 order-place", action, status=201)


# trace: ADDR-001, ADDR-012
class OrderDetailApi(BaseApiView):
    """FR-033 GET /api/orders/注文ID/。"""

    def get(self, request: Request, order_id: str) -> Response:
        return run(request, "FR-033 order", lambda: services.get_my_order(require_buyer(request, "E-033"), order_id))


# trace: ADDR-001, ADDR-012
class OrderPaymentApi(BaseApiView):
    """FR-031 POST /api/orders/注文ID/payment/（mock_instruction：approved・declined、省略時 approved）。"""

    def post(self, request: Request, order_id: str) -> Response:
        def action() -> dict:
            user = require_buyer(request, "E-031")
            body = request_body(request)
            return services.pay_order(user, order_id, body.get("mock_instruction"))

        return run(request, "FR-031 order-pay", action)


# trace: ADDR-001, ADDR-012
class OrderCancelApi(BaseApiView):
    """FR-034 POST /api/orders/注文ID/cancel/。"""

    def post(self, request: Request, order_id: str) -> Response:
        return run(
            request,
            "FR-034 order-cancel",
            lambda: services.cancel_my_order(require_buyer(request, "E-034"), order_id),
        )


# trace: ADDR-001, ADDR-012
class AdminOrdersApi(BaseApiView):
    """FR-041 GET /api/admin/orders/（status はキーの繰返しで複数指定）。"""

    def get(self, request: Request) -> Response:
        query = request.query_params

        def action() -> dict:
            require_admin(request, "E-041")
            return services.admin_list_orders(
                query.get("order_number"),
                query.getlist("status"),
                query.get("order_date_from"),
                query.get("order_date_to"),
                query.get("buyer_email"),
                query.get("page"),
            )

        return run(request, "FR-041 admin-orders", action)


# trace: ADDR-001, ADDR-012
class AdminOrderDetailApi(BaseApiView):
    """FR-042 GET /api/admin/orders/注文ID/。"""

    def get(self, request: Request, order_id: str) -> Response:
        def action() -> dict:
            require_admin(request, "E-042")
            return services.admin_get_order(order_id)

        return run(request, "FR-042 admin-order", action)


# trace: ADDR-001, ADDR-012
class AdminOrderShipApi(BaseApiView):
    """FR-043 POST /api/admin/orders/注文ID/ship/（tracking_number 任意）。"""

    def post(self, request: Request, order_id: str) -> Response:
        def action() -> dict:
            admin = require_admin(request, "E-043")
            body = request_body(request)
            return services.ship_order(admin, order_id, body.get("tracking_number"))

        return run(request, "FR-043 admin-ship", action)


# trace: ADDR-001, ADDR-012
class AdminOrderDeliverApi(BaseApiView):
    """FR-044 POST /api/admin/orders/注文ID/deliver/。"""

    def post(self, request: Request, order_id: str) -> Response:
        return run(
            request,
            "FR-044 admin-deliver",
            lambda: services.deliver_order(require_admin(request, "E-044"), order_id),
        )


# trace: ADDR-001, ADDR-012
class AdminOrderCancelApi(BaseApiView):
    """FR-045 POST /api/admin/orders/注文ID/cancel/。"""

    def post(self, request: Request, order_id: str) -> Response:
        return run(
            request,
            "FR-045 admin-cancel",
            lambda: services.admin_cancel_order(require_admin(request, "E-045"), order_id),
        )
