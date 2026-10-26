from django.urls import path

from .views import MovementListView, StockChangeView, StockDetailView, StockListView

urlpatterns = [
    path("", StockListView.as_view()),
    path("movements/", MovementListView.as_view()),
    path("<int:offer_id>/", StockDetailView.as_view()),
    path("<int:offer_id>/changes/", StockChangeView.as_view()),
]
