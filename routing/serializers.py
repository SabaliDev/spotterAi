# In routing/serializer.py
from rest_framework import serializers
from .models import Route


class RouteSerializer(serializers.ModelSerializer):
    trip_id = serializers.IntegerField(source='trip.id', read_only=True)
    trip_title = serializers.CharField(source='trip.title', read_only=True)
    
    class Meta:
        model = Route
        fields = ['id', 'trip_id', 'trip_title', 'distance', 'duration', 'route_polyline', 'stops']