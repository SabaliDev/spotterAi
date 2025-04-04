# serializers.py
from rest_framework import serializers
from .models import Trip, Stop, GPSLog, ELDLog
from routing.serializers import RouteSerializer

try:
   
    from routing.serializers import RouteSerializer
except ImportError:
    RouteSerializer = None 

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
    
    stops = serializers.SerializerMethodField(read_only=True)
    eld_logs = serializers.SerializerMethodField(read_only=True)
    has_route = serializers.ReadOnlyField() 

    
    if RouteSerializer:
        route = RouteSerializer(read_only=True, required=False)
    else:
    
        route = serializers.PrimaryKeyRelatedField(read_only=True)


    class Meta:
        model = Trip
        fields = [
            'id', 'stops', 'eld_logs', 'has_route', 'route', 'title', 'description',
            'current_location', 'current_coordinates', 'pickup_location',
            'pickup_coordinates', 'dropoff_location', 'dropoff_coordinates',
            'current_cycle_used', 'status', 'startDate', 'estimatedEndDate',
            'actual_end_date', 'created_at', 'updated_at', 'driver'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'actual_end_date', 'driver', 
            'stops', 'eld_logs', 'has_route', 'route' 
        ]

       
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'current_location': {'required': False},
            'current_coordinates': {'required': False},
            'pickup_location': {'required': False},
            'pickup_coordinates': {'required': False},
            'dropoff_location': {'required': False},
            'dropoff_coordinates': {'required': False},
            'current_cycle_used': {'required': False},
            'startDate': {'required': False},
            'estimatedEndDate': {'required': False},
             'status': {'required': False},
        }
        
    def get_stops(self, obj):
       
        return []
        
    def get_eld_logs(self, obj):
    
        return []