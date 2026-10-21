# trace: ADDR-002
"""会員・認証 API の URL（docs/specifications/api-contract.md 6.1）。"""

from django.urls import path

from accounts import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="api-auth-register"),
    path("auth/login", views.LoginView.as_view(), name="api-auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="api-auth-logout"),
    path("auth/me", views.MeView.as_view(), name="api-auth-me"),
]
