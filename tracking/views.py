# views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Trip, Stop, GPSLog, ELDLog
from .serializers import TripSerializer, StopSerializer, GPSLogSerializer, ELDLogSerializer
from routing.services import create_route_for_trip 
from django.shortcuts import get_object_or_404
from datetime import datetime, time, timedelta 

class TripCreateView(generics.CreateAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
       
        trip = serializer.save(driver=request.user)
        
        route = create_route_for_trip(trip)
        
        response_data = serializer.data
        
        if route:
            from routing.serializers import RouteSerializer
            route_data = RouteSerializer(route).data
            response_data['route'] = route_data
        
        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

class TripListView(generics.ListAPIView):
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get('status', None)
        queryset = Trip.objects.filter(driver=self.request.user).select_related('route')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset

class TripDetailView(generics.RetrieveAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated]

class TripUpdateView(generics.UpdateAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        trip = serializer.instance
        status = serializer.validated_data.get('status', trip.status)
        
       
        if status == 'completed' and trip.status != 'completed':
            serializer.save(actual_end_date=timezone.now())
        else:
            serializer.save()

class StartTripView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, driver=request.user)
            
            if trip.status != 'planned':
                return Response({"error": "Only planned trips can be started"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            
            trip.status = 'in_progress'
            trip.startDate = timezone.now()
            trip.save()
            
            
            ELDLog.objects.create(
                trip=trip,
                event_type='on_duty',
                location=trip.pickup_location,
                coordinates=trip.pickup_coordinates,
                duration=1.0,  # 1 hour for pickup
                start_time=timezone.now()
            )
            
            return Response(TripSerializer(trip).data)
            
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

class LogELDEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, driver=request.user)
            
            if trip.status != 'in_progress':
                return Response({"error": "Trip must be in progress to log ELD events"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ELDLogSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(trip=trip)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

class LogGPSView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, driver=request.user)
            
            if trip.status != 'in_progress':
                return Response({"error": "Trip must be in progress to log GPS data"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            serializer = GPSLogSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(trip=trip)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

class CompleteStopView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk, stop_id):
        try:
            trip = Trip.objects.get(pk=pk, driver=request.user)
            stop = Stop.objects.get(pk=stop_id, trip=trip)
            
            stop.completed = True
            stop.actual_arrival_time = timezone.now()
            stop.save()
            
            return Response(StopSerializer(stop).data)
            
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)
        except Stop.DoesNotExist:
            return Response({"error": "Stop not found"}, status=status.HTTP_404_NOT_FOUND)


class DailyELDLogView(APIView):
    """
    Retrieve ELD Log entries for a specific trip on a specific date.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ELDLogSerializer # Specify the serializer

    def get(self, request, trip_id, date_str):
        """
        Handles GET requests to fetch ELD logs for the given trip and date.

        Args:
            request: The request object.
            trip_id: The ID of the trip.
            date_str: The date string in 'YYYY-MM-DD' format.

        Returns:
            A Response object containing the serialized ELD log data or an error.
        """
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        trip = get_object_or_404(Trip, pk=trip_id, driver=request.user)

        start_datetime = timezone.make_aware(datetime.combine(target_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(target_date, time.max))
      
        logs = ELDLog.objects.filter(
            trip=trip,
            start_time__lt=end_datetime, 
            end_time__gt=start_datetime 
        ).order_by('start_time') 

        serializer = self.serializer_class(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangeELDStatusView(APIView):
    """
    Allows the driver to change their current ELD duty status.
    Ends the previous log entry and starts a new one.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, trip_id):
        """
        Handles POST requests to change the current ELD status.

        Expected request data:
        {
            "new_status": "on_duty" | "off_duty" | "sleeper_berth" | "driving",
            "location": "Optional: Current location description",
            "coordinates": "Optional: Current coordinates (e.g., 'lat,lon')",
            "remarks": "Optional: Any remarks"
        }
        """
        trip = get_object_or_404(Trip, pk=trip_id, driver=request.user)
        if trip.status != 'in_progress':
             return Response({"error": "Trip must be in progress to change ELD status."},
                             status=status.HTTP_400_BAD_REQUEST)

        new_status = request.data.get('new_status')
        location = request.data.get('location', trip.current_location) 
        coordinates = request.data.get('coordinates', trip.current_coordinates)
        remarks = request.data.get('remarks', '') 

        valid_statuses = [choice[0] for choice in ELDLog.EVENT_TYPE_CHOICES]
        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status. Choose from: {', '.join(valid_statuses)}"},
                            status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        new_log_entry = None

        try:
            latest_log = ELDLog.objects.filter(trip=trip).latest('start_time')

            if latest_log.event_type == new_status:
                 return Response({"message": f"Status is already '{new_status}'."}, status=status.HTTP_200_OK)

            if latest_log.end_time is None:
                latest_log.end_time = now
                duration_delta = now - latest_log.start_time
                latest_log.duration = duration_delta.total_seconds() / 3600 
                latest_log.save()
            else:
                print(f"Warning: Latest log for Trip {trip.id} already had an end_time.")

            new_log_entry = ELDLog.objects.create(
                trip=trip,
                event_type=new_status,
                start_time=now,
                end_time=None, # Active log has no end time yet
                duration=0.0, # Duration is 0 until ended
                location=location,
                coordinates=coordinates,
            )

            trip.current_location = location
            trip.current_coordinates = coordinates
            trip.save()

            serializer = ELDLogSerializer(new_log_entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ELDLog.DoesNotExist:
            new_log_entry = ELDLog.objects.create(
                trip=trip,
                event_type=new_status,
                start_time=now, 
                end_time=None,
                duration=0.0,
                location=location,
                coordinates=coordinates,
                # remarks=remarks
            )
            trip.current_location = location
            trip.current_coordinates = coordinates
            trip.save()
            serializer = ELDLogSerializer(new_log_entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Error changing ELD status for Trip {trip_id}: {e}")
            return Response({"error": "An unexpected error occurred."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)