# trace: FR-001, FR-002, FR-004, FR-010, FR-011, FR-012, NFR-SC-03, ADDR-002
"""Web API の認証・権限判定（api-contract 6.1・6.3）の単体テスト。

期待値は CMN-01〜CMN-03（認証・権限）、ADDR-002（認証トークン方式）、
api-contract の認証不要エンドポイントの定義から導出する。
"""
import pytest
from rest_framework.test import APIRequestFactory

from shop.api import views_admin, views_auth, views_cart, views_catalog, views_orders
from shop.api.authentication import ApiTokenAuthentication, current_token, current_user
from shop.api.permissions import IsAdmin, IsAuthenticated, IsBuyer
from shop.common.errors import AuthenticationRequiredError, PermissionDeniedError
from shop.services import accounts

pytestmark = pytest.mark.django_db


# trace: ADDR-002
def _api_request(token: str | None = None):
    """Authorization ヘッダーの有無を指定した API 要求を組み立てる。"""
    factory = APIRequestFactory()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    from rest_framework.request import Request

    return Request(factory.get("/api/auth/me", **headers))


# trace: FR-004
def test_authentication_resolves_user_from_bearer_token(buyer):
    """Authorization ヘッダーの Bearer トークンから利用者を特定する。"""
    issued = accounts.login_with_token(buyer.email, "Passw0rd")

    user, token = ApiTokenAuthentication().authenticate(_api_request(issued.value))

    assert user.user_id == buyer.user_id
    assert token.revoked_at is None


# trace: FR-004
def test_authentication_returns_none_without_header(db):
    """Authorization ヘッダーが無い場合は認証しない（権限判定で拒否する）。"""
    assert ApiTokenAuthentication().authenticate(_api_request()) is None


# trace: NFR-SC-03
@pytest.mark.parametrize("header_token", ["", "   "])
def test_authentication_rejects_empty_bearer_value(db, header_token):
    """Bearer のトークン値が空の場合は認証エラーとする。"""
    with pytest.raises(AuthenticationRequiredError):
        ApiTokenAuthentication().authenticate(_api_request(header_token))


# trace: NFR-SC-03
def test_authentication_rejects_unknown_scheme(db):
    """Bearer 以外の認証方式は認証エラーとする。"""
    from rest_framework.request import Request

    factory = APIRequestFactory()
    request = Request(factory.get("/api/auth/me", HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz"))

    with pytest.raises(AuthenticationRequiredError):
        ApiTokenAuthentication().authenticate(request)


# trace: NFR-SC-03
def test_authentication_rejects_revoked_token(buyer):
    """無効化済みトークンでは認証エラーとする。"""
    issued = accounts.login_with_token(buyer.email, "Passw0rd")
    _, token = accounts.resolve_token(issued.value)
    accounts.logout_token(token)

    with pytest.raises(AuthenticationRequiredError):
        ApiTokenAuthentication().authenticate(_api_request(issued.value))


# trace: FR-002, ADDR-002
def test_authenticate_header_announces_bearer(db):
    """認証方式として Bearer を返す。"""
    assert ApiTokenAuthentication().authenticate_header(_api_request()) == "Bearer"


# trace: NFR-SC-03
def test_current_user_and_token_require_authentication(db):
    """認証済みでない要求から利用者・トークンを取り出せない。"""

    class _Request:
        user = None
        auth = None

    with pytest.raises(AuthenticationRequiredError):
        current_user(_Request())
    with pytest.raises(AuthenticationRequiredError):
        current_token(_Request())


# trace: NFR-SC-03
def test_permission_classes_allow_matching_roles(buyer, admin_user):
    """権限判定は購入者・管理者のロールに従って許可する。"""

    class _Request:
        def __init__(self, user):
            self.user = user

    assert IsAuthenticated().has_permission(_Request(buyer), None) is True
    assert IsBuyer().has_permission(_Request(buyer), None) is True
    assert IsAdmin().has_permission(_Request(admin_user), None) is True


# trace: NFR-SC-03
def test_permission_classes_reject_other_roles(buyer, admin_user):
    """購入者専用機能は管理者を、管理者専用機能は購入者を拒否する。"""

    class _Request:
        def __init__(self, user):
            self.user = user

    with pytest.raises(PermissionDeniedError):
        IsBuyer().has_permission(_Request(admin_user), None)
    with pytest.raises(PermissionDeniedError):
        IsAdmin().has_permission(_Request(buyer), None)


# trace: NFR-SC-03
def test_permission_classes_reject_anonymous(db):
    """未認証の要求はすべての権限判定で認証エラーとする。"""

    class _Request:
        user = None

    for permission in (IsAuthenticated(), IsBuyer(), IsAdmin()):
        with pytest.raises(AuthenticationRequiredError):
            permission.has_permission(_Request(), None)


# trace: NFR-SC-03
@pytest.mark.parametrize(
    "view_class",
    [
        views_auth.LogoutView,
        views_auth.MeView,
        views_cart.CartView,
        views_cart.CartLineListView,
        views_cart.CartLineDetailView,
        views_cart.ApplyCouponView,
        views_cart.RemoveCouponView,
        views_orders.CheckoutView,
        views_orders.PurchaseOrderListView,
        views_orders.PurchaseOrderDetailView,
        views_orders.PayView,
        views_orders.CancelView,
        views_admin.StockUnitListView,
        views_admin.AdminPurchaseOrderListView,
        views_admin.AdminPurchaseOrderDetailView,
        views_admin.ShipView,
        views_admin.DeliverView,
        views_admin.AdminCancelView,
    ],
)
def test_protected_endpoints_require_authentication(view_class):
    """認証が必要なエンドポイントは権限判定クラスを持つ（既定は拒否）。"""
    assert view_class.permission_classes
    assert view_class.permission_classes != []


# trace: NFR-SC-03
@pytest.mark.parametrize(
    "view_class",
    [
        views_admin.StockUnitListView,
        views_admin.AdminPurchaseOrderListView,
        views_admin.AdminPurchaseOrderDetailView,
        views_admin.ShipView,
        views_admin.DeliverView,
        views_admin.AdminCancelView,
    ],
)
def test_admin_endpoints_require_admin_role(view_class):
    """管理者専用エンドポイントは管理者の権限判定を用いる。"""
    assert view_class.permission_classes == [IsAdmin]


# trace: NFR-SC-03
@pytest.mark.parametrize(
    "view_class",
    [
        views_cart.CartView,
        views_cart.CartLineListView,
        views_cart.CartLineDetailView,
        views_cart.ApplyCouponView,
        views_cart.RemoveCouponView,
        views_orders.CheckoutView,
        views_orders.PurchaseOrderListView,
        views_orders.PurchaseOrderDetailView,
        views_orders.PayView,
        views_orders.CancelView,
    ],
)
def test_buyer_endpoints_require_buyer_role(view_class):
    """購入者専用エンドポイントは購入者の権限判定を用いる。"""
    assert view_class.permission_classes == [IsBuyer]


# trace: FR-001, FR-002, FR-010, FR-011, FR-012
@pytest.mark.parametrize(
    "view_class",
    [
        views_auth.RegisterView,
        views_auth.LoginView,
        views_catalog.CollectionListView,
        views_catalog.ItemListView,
        views_catalog.ItemDetailView,
    ],
)
def test_public_endpoints_do_not_require_authentication(view_class):
    """api-contract 6.1 の認証不要エンドポイントだけが認証を要求しない。"""
    assert view_class.authentication_classes == []
    assert view_class.permission_classes == []
