from django.urls import path
from .views import (
    TripCreateView, TripListView, TripDetailView, TripUpdateView,
    StartTripView, LogELDEventView, LogGPSView, CompleteStopView
)

urlpatterns = [
    path('create/', TripCreateView.as_view(), name='create_trip'),
    path('list/', TripListView.as_view(), name='list_trips'),
    path('<int:pk>/', TripDetailView.as_view(), name='trip_detail'),
    path('<int:pk>/update/', TripUpdateView.as_view(), name='update_trip'),
    path('<int:pk>/start/', StartTripView.as_view(), name='start_trip'),
    path('<int:pk>/log-eld/', LogELDEventView.as_view(), name='log_eld'),
    path('<int:pk>/log-gps/', LogGPSView.as_view(), name='log_gps'),
    path('<int:pk>/complete-stop/<int:stop_id>/', CompleteStopView.as_view(), name='complete_stop'),
]