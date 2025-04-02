from django.urls import path
from .views import HOSStatusView

urlpatterns = [
    path('status/', HOSStatusView.as_view(), name='hos_status'),
]
