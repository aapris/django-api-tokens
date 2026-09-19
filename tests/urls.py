"""URLs for the test suite: one echo endpoint and the admin."""

from django.contrib import admin
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class EchoView(APIView):
    """Return the authenticated username for any method."""

    def get(self, request: Request) -> Response:
        """Echo the user.

        Args:
            request: The request.

        Returns:
            ``{"user": <username>}``.
        """
        return Response({"user": request.user.get_username()})

    post = get
    delete = get


class OpenEchoView(EchoView):
    """Same, but with its own permission_classes — scope must still be enforced."""

    permission_classes = [AllowAny]


urlpatterns = [
    path("echo/", EchoView.as_view()),
    path("open-echo/", OpenEchoView.as_view()),
    path("admin/", admin.site.urls),
]
