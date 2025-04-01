from django.urls import path
from .views import GenerateRouteView, RouteDetailView

urlpatterns = [
    path('<int:trip_id>/generate/', GenerateRouteView.as_view(), name='generate_route'),
    path('<int:pk>/', RouteDetailView.as_view(), name='route_detail'),
]
