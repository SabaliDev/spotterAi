from django.urls import path
from .views import (
    TripCreateView, TripListView, TripDetailView, TripUpdateView,
    StartTripView, LogELDEventView, LogGPSView, CompleteStopView,DailyELDLogView,ChangeELDStatusView
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
    path('trip/<int:trip_id>/logs/<str:date_str>/', DailyELDLogView.as_view(), name='daily_eld_logs'),
    path('trip/<int:trip_id>/change-status/', ChangeELDStatusView.as_view(), name='change_eld_status'),
]


# This code defines the URL patterns for the tracking app in a Django project.
# Each URL pattern is associated with a specific view that handles the request.
# The patterns include creating, listing, updating trips, logging ELD and GPS events,
# starting trips, completing stops, and changing ELD status.
# The URL patterns use path converters to capture dynamic segments of the URL,
# such as trip IDs and dates.
# The views are expected to be defined in the views.py file of the tracking app.
# The urlpatterns list is included in the main URL configuration of the Django project,
# allowing the app to handle requests at the specified endpoints.
# The code is structured to follow RESTful principles, making it easy to understand
# and maintain. Each view corresponds to a specific action that can be performed
# on the trips and logs in the tracking system.