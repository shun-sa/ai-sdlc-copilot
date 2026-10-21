# trace: ADDR-010
"""カート（SCR-005）の表示と更新操作（FR-020〜FR-025）。"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from carts import serializers as cart_serializers
from carts import services as cart_services
from catalog import services as catalog_services
from common.exceptions import BusinessError, CartEmpty, CouponAlreadyApplied, ValidationFailed
from web.support import remember_path, require_buyer, screen, set_flash
from web.views.catalog_views import item_detail_context
from web.views.messages import (
    COUPON_CART_EMPTY_MESSAGE,
    business_message,
    coupon_already_applied_message,
    field_errors,
)

NOT_APPLICABLE_REASONS = {
    "COUPON_NOT_YET_VALID": "有効期間の開始前です",
    "COUPON_EXPIRED": "有効期間が終了しています",
    "COUPON_MIN_SPEND_NOT_MET": "小計が最低購入金額に達していません",
    "CART_EMPTY": "カートに商品がありません",
}


def enrich_cart(payload: dict[str, Any]) -> dict[str, Any]:
    """表示用に税込単価と適用不可理由の文言を補う（金額計算はサービスで行う）。"""
    for line in payload["lines"]:
        line["unit_price_incl_tax"] = catalog_services.price_incl_tax(line["unit_price"])
        line["shortage"] = line["quantity"] > line["stock_quantity"]
    coupon = payload.get("coupon")
    if coupon and coupon.get("not_applicable_reason"):
        coupon["not_applicable_text"] = NOT_APPLICABLE_REASONS.get(
            coupon["not_applicable_reason"], coupon["not_applicable_reason"]
        )
    return payload


def render_cart(request: HttpRequest, payload: dict[str, Any], context: dict[str, Any] | None = None) -> HttpResponse:
    """SCR-005 を表示する。"""
    data: dict[str, Any] = {"cart": enrich_cart(payload)}
    data["form"] = cart_form(payload)
    if context:
        data.update(context)
    return render(request, "buyer/cart.html", data)


def target_line_id(payload: dict[str, Any], cart_line_id: Any) -> Any:
    """操作対象のカート明細IDを、カート内容と同じ型で取り出す（入力値・理由の対応付けに用いる）。"""
    if cart_line_id is None:
        return None
    wanted = str(cart_line_id).strip()
    for line in payload["lines"]:
        if str(line["cart_line_id"]) == wanted:
            return line["cart_line_id"]
    return None


def cart_form(
    payload: dict[str, Any],
    *,
    cart_line_id: Any = None,
    quantity: Any = None,
    code: Any = None,
) -> dict[str, Any]:
    """SCR-005 の再表示で画面へ戻す入力値を組み立てる（CMN-17、UI-19）。

    数量は明細ごとに保持し、エラーとなった明細だけ入力値へ差し替える（理由の表示も同じ明細の
    近傍に限る。SCR-005-OP01）。クーポンコードは入力した値をそのまま戻す（SCR-005-OP03）。
    """
    quantities = {line["cart_line_id"]: str(line["quantity"]) for line in payload["lines"]}
    target = target_line_id(payload, cart_line_id)
    if target is not None and quantity is not None:
        quantities[target] = str(quantity)
    return {
        "quantities": quantities,
        "error_line_id": target,
        "code": "" if code is None else str(code),
    }


def render_item_detail(
    request: HttpRequest,
    item_id: Any,
    form: dict[str, Any],
    context: dict[str, Any],
    status: int,
) -> HttpResponse:
    """SCR-002 を入力値付きで再表示する（カートは変更しない。SCR-002-OP01、CMN-17）。"""
    data = item_detail_context(request, item_id, form)
    data.update(context)
    return render(request, "buyer/item_detail.html", data, status=status)


def added_message(payload: dict[str, Any], stock_unit_id: Any, quantity: Any) -> str:
    """カート追加の成功メッセージを「カートに追加しました（規格名、n個）。」で組み立てる（SCR-002-OP01）。"""
    added = next(
        (line for line in payload["lines"] if str(line["stock_unit_id"]) == str(stock_unit_id).strip()),
        None,
    )
    if added is None:
        return "カートに追加しました。"
    return f"カートに追加しました（{added['variant_name']}、{str(quantity).strip()}個）。"


@screen
@require_http_methods(["GET"])
def cart(request: HttpRequest) -> HttpResponse:
    """SCR-005 カート。FR-020 を実行する。"""
    user = require_buyer(request)
    view = cart_services.show_cart(user)
    return render_cart(request, cart_serializers.cart_payload(view))


@screen
@require_http_methods(["POST"])
def add_line(request: HttpRequest) -> HttpResponse:
    """FR-021 カート明細追加（SCR-002 の「カートに入れる」）。"""
    item_id = request.POST.get("item_id")
    if item_id:
        # 来訪者が操作した場合はログイン後に商品詳細（SCR-002）へ戻す（UI-17）。
        remember_path(request, reverse("web-item-detail", kwargs={"item_id": item_id}))
    user = require_buyer(request)
    form = {
        "stock_unit_id": request.POST.get("stock_unit_id"),
        "quantity": request.POST.get("quantity"),
    }
    try:
        view = cart_services.add_line(user, form)
    except ValidationFailed as error:
        # 数量の理由は数量欄の近傍へ表示し、入力値を保持して本画面に留まる（SCR-002-OP01、CMN-16、CMN-17）。
        return render_item_detail(request, item_id, form, {"field_errors": field_errors(error)}, 400)
    except BusinessError as error:
        # 数量上限超過・在庫不足はメッセージ領域へ表示し、入力値を保持して本画面に留まる（SCR-002-OP01）。
        return render_item_detail(request, item_id, form, {"error_message": business_message(error)}, 409)
    set_flash(request, added_message(cart_serializers.cart_payload(view), form["stock_unit_id"], form["quantity"]))
    return redirect("web-item-detail", item_id=item_id)


@screen
@require_http_methods(["POST"])
def update_line(request: HttpRequest, cart_line_id: str) -> HttpResponse:
    """FR-022 カート明細数量変更。"""
    user = require_buyer(request)
    quantity = request.POST.get("quantity")
    try:
        view = cart_services.change_line_quantity(user, cart_line_id, {"quantity": quantity})
    except ValidationFailed as error:
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        return render_cart(
            request,
            payload,
            {
                "field_errors": field_errors(error),
                "form": cart_form(payload, cart_line_id=cart_line_id, quantity=quantity),
            },
        )
    except BusinessError as error:
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        return render_cart(
            request,
            payload,
            {
                "error_message": business_message(error),
                "form": cart_form(payload, cart_line_id=cart_line_id, quantity=quantity),
            },
        )
    set_flash(request, "数量を変更しました。")
    return render_cart(request, cart_serializers.cart_payload(view))


@screen
@require_http_methods(["POST"])
def delete_line(request: HttpRequest, cart_line_id: str) -> HttpResponse:
    """FR-023 カート明細削除。"""
    user = require_buyer(request)
    cart_services.delete_line(user, cart_line_id)
    set_flash(request, "カートから削除しました。")
    return redirect("web-cart")


@screen
@require_http_methods(["POST"])
def apply_coupon(request: HttpRequest) -> HttpResponse:
    """FR-024 クーポン適用。"""
    user = require_buyer(request)
    code = request.POST.get("code")
    try:
        cart_services.apply_coupon(user, {"code": code})
    except ValidationFailed as error:
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        return render_cart(
            request,
            payload,
            {"field_errors": field_errors(error), "form": cart_form(payload, code=code)},
        )
    except CartEmpty:
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        return render_cart(
            request,
            payload,
            {"error_message": COUPON_CART_EMPTY_MESSAGE, "form": cart_form(payload, code=code)},
        )
    except CouponAlreadyApplied as error:
        # 適用中のクーポンコードは応答の context ではなくカートの内容から表示する（SCR-005-OP03）。
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        applied = payload.get("coupon") or {}
        return render_cart(
            request,
            payload,
            {
                "error_message": coupon_already_applied_message(error, applied.get("code")),
                "form": cart_form(payload, code=code),
            },
        )
    except BusinessError as error:
        payload = cart_serializers.cart_payload(cart_services.show_cart(user))
        return render_cart(
            request,
            payload,
            {"error_message": business_message(error), "form": cart_form(payload, code=code)},
        )
    set_flash(request, "クーポンを適用しました。")
    return redirect("web-cart")


@screen
@require_http_methods(["POST"])
def remove_coupon(request: HttpRequest) -> HttpResponse:
    """FR-025 クーポン解除。"""
    user = require_buyer(request)
    cart_services.remove_coupon(user)
    set_flash(request, "クーポンを解除しました。")
    return redirect("web-cart")
