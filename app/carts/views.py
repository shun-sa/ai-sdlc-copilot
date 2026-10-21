# trace: ADDR-003
"""カート・クーポンの API ビュー（FR-020〜FR-025）。購入者のみ利用できる。"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from carts import serializers, services
from common.permissions import IsBuyer


# trace: ADDR-003
class CartView(APIView):
    """FR-020 カート照会。"""

    permission_classes = [IsBuyer]

    def get(self, request: Request) -> Response:
        view = services.show_cart(request.user)
        return Response(serializers.cart_payload(view), status=200)


# trace: ADDR-003
class CartLineCreateView(APIView):
    """FR-021 カート明細追加。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        view = services.add_line(request.user, data)
        return Response(serializers.cart_payload(view), status=200)


# trace: ADDR-003
class CartLineDetailView(APIView):
    """FR-022 カート明細数量変更／FR-023 カート明細削除。"""

    permission_classes = [IsBuyer]

    def patch(self, request: Request, cart_line_id: str) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        view = services.change_line_quantity(request.user, cart_line_id, data)
        return Response(serializers.cart_payload(view), status=200)

    def delete(self, request: Request, cart_line_id: str) -> Response:
        view = services.delete_line(request.user, cart_line_id)
        return Response(serializers.cart_payload(view), status=200)


# trace: ADDR-003
class ApplyCouponView(APIView):
    """FR-024 クーポン適用。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        view = services.apply_coupon(request.user, data)
        return Response(serializers.cart_payload(view), status=200)


# trace: ADDR-003
class RemoveCouponView(APIView):
    """FR-025 クーポン解除。"""

    permission_classes = [IsBuyer]

    def post(self, request: Request) -> Response:
        view = services.remove_coupon(request.user)
        return Response(serializers.cart_payload(view), status=200)
