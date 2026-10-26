from django.urls import path

from .views import health, not_found

handler404 = not_found
urlpatterns = [path("health/", health, name="health")]
