# serializers.py
from rest_framework import serializers
from .models import Trip, Stop, GPSLog, ELDLog
from routing.serializers import RouteSerializer

class GPSLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GPSLog
        fields = '__all__'

class ELDLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ELDLog
        fields = '__all__'

class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = '__all__'

class TripSerializer(serializers.ModelSerializer):
    stops = serializers.SerializerMethodField()
    eld_logs = serializers.SerializerMethodField()
    has_route = serializers.ReadOnlyField()
    route = RouteSerializer(read_only=True, required=False)
    
    class Meta:
        model = Trip
        fields = ['id', 'stops', 'eld_logs', 'has_route', 'route', 'title', 'description', 
                  'current_location', 'current_coordinates', 'pickup_location', 
                  'pickup_coordinates', 'dropoff_location', 'dropoff_coordinates', 
                  'current_cycle_used', 'status', 'startDate', 'estimatedEndDate', 
                  'actual_end_date', 'created_at', 'updated_at', 'driver']
        
    def get_stops(self, obj):
        # Your existing implementation...
        return []
        
    def get_eld_logs(self, obj):
        # Your existing implementation...
        return []