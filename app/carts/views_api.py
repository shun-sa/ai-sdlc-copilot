# trace: ADDR-001, ADDR-012
"""カートの Web API（FR-020〜FR-025。金額内訳は FR-026 の結果を含める）。"""

from rest_framework.request import Request
from rest_framework.response import Response

from carts import services
from common.api import BaseApiView, request_body, require_buyer, run


# trace: ADDR-001, ADDR-012
class CartApi(BaseApiView):
    """FR-020 GET /api/cart/。"""

    def get(self, request: Request) -> Response:
        return run(request, "FR-020 cart", lambda: services.get_cart(require_buyer(request, "E-020")))


# trace: ADDR-001, ADDR-012
class CartItemsApi(BaseApiView):
    """FR-021 POST /api/cart/items/（stock_unit_id・quantity）。"""

    def post(self, request: Request) -> Response:
        def action() -> dict:
            user = require_buyer(request, "E-021")
            body = request_body(request)
            return services.add_item(user, body.get("stock_unit_id"), body.get("quantity"))

        return run(request, "FR-021 cart-add", action)


# trace: ADDR-001, ADDR-012
class CartItemApi(BaseApiView):
    """FR-022 PATCH・FR-023 DELETE /api/cart/items/カート明細ID/。"""

    def patch(self, request: Request, cart_item_id: str) -> Response:
        def action() -> dict:
            user = require_buyer(request, "E-022")
            body = request_body(request)
            return services.change_quantity(user, cart_item_id, body.get("quantity"))

        return run(request, "FR-022 cart-quantity", action)

    def delete(self, request: Request, cart_item_id: str) -> Response:
        return run(
            request,
            "FR-023 cart-delete",
            lambda: services.delete_item(require_buyer(request, "E-023"), cart_item_id),
        )


# trace: ADDR-001, ADDR-012
class CartCouponApi(BaseApiView):
    """FR-024 POST・FR-025 DELETE /api/cart/coupon/。"""

    def post(self, request: Request) -> Response:
        def action() -> dict:
            user = require_buyer(request, "E-024")
            body = request_body(request)
            return services.apply_coupon(user, body.get("coupon_code"))

        return run(request, "FR-024 coupon-apply", action)

    def delete(self, request: Request) -> Response:
        return run(request, "FR-025 coupon-remove", lambda: services.remove_coupon(require_buyer(request, "E-025")))
