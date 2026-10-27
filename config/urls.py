from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.routers import DefaultRouter

from accounts.permissions import IsAdministrator
from accounts.views import CustomerDetailView, CustomerListView
from catalog.views import OfferViewSet, ProductViewSet, SellerViewSet
from olist import views as history
from olist.report_views import ReportView

from .views import health, not_found

handler404 = not_found
router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("sellers", SellerViewSet)
router.register("offers", OfferViewSet)
historical = DefaultRouter()
for prefix, view in [
    ("customers", history.CustomerViewSet),
    ("categories", history.CategoryViewSet),
    ("products", history.ProductViewSet),
    ("sellers", history.SellerViewSet),
    ("orders", history.OrderViewSet),
    ("items", history.ItemViewSet),
    ("payments", history.PaymentViewSet),
]:
    historical.register(prefix, view, basename="historical-" + prefix)
urlpatterns = [
    path("health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/customers/", CustomerListView.as_view()),
    path("api/customers/<int:pk>/", CustomerDetailView.as_view()),
    path("api/olist/", include(historical.urls)),
    path("api/olist/reports/<slug:report_name>/", ReportView.as_view()),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[IsAdministrator]),
        name="schema",
    ),
    path("api/", include(router.urls)),
]
