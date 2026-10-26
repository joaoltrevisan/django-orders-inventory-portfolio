from django.urls import path

from .views import (
    OrderCancelView,
    OrderDeliverView,
    OrderDetailView,
    OrderListView,
    OrderPaymentView,
    OrderShipView,
)

urlpatterns = [
    path("", OrderListView.as_view()),
    path("<int:order_id>/", OrderDetailView.as_view()),
    path("<int:order_id>/cancel/", OrderCancelView.as_view()),
    path("<int:order_id>/simulated-payment/", OrderPaymentView.as_view()),
    path("<int:order_id>/ship/", OrderShipView.as_view()),
    path("<int:order_id>/deliver/", OrderDeliverView.as_view()),
]
