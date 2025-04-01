from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Route
from .serializers import RouteSerializer
from tracking.models import Trip
from .services import get_route_details

class GenerateRouteView(APIView):
    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id)
        
        # Extract coordinates from trip
        pickup_coords = trip.pickup_coordinates
        dropoff_coords = trip.dropoff_coordinates
        current_cycle_used = float(trip.current_cycle_used)
        
        # Get optimized route details
        route_data = get_route_details(pickup_coords, dropoff_coords, current_cycle_used)
        if not route_data:
            return Response({"error": "Could not generate route"}, status=400)
        
        # Save to database
        route = Route.objects.create(trip=trip, **route_data)
        
        return Response(RouteSerializer(route).data, status=201)

class RouteDetailView(generics.RetrieveAPIView):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
