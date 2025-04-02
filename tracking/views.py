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
        
        # Save trip with the currently authenticated driver
        trip = serializer.save(driver=request.user)
        
        # Generate route for the trip
        route = create_route_for_trip(trip)
        
        # Include route in response if it was created
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
        # Filter trips by status if provided in query params
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
        
        # If trip is marked as completed, set actual end date
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
            
            # Update trip status to in_progress
            trip.status = 'in_progress'
            trip.startDate = timezone.now()
            trip.save()
            
            # Create first ELD log entry - On Duty for pickup
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
        # Validate date format
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Get the trip object, ensuring it belongs to the requesting user
        trip = get_object_or_404(Trip, pk=trip_id, driver=request.user)

        # Define the time range for the target date (from midnight to midnight)
        # Assumes settings.TIME_ZONE is set correctly (e.g., 'UTC')
        start_datetime = timezone.make_aware(datetime.combine(target_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(target_date, time.max))
        # Alternative for end: start_datetime + timedelta(days=1) if range is exclusive of end

        # Filter ELD logs for the trip that overlap with the target date range
        # This finds logs that start OR end within the 24-hour period.
        # Adjust filtering logic if specific behavior for logs crossing midnight is needed.
        logs = ELDLog.objects.filter(
            trip=trip,
            start_time__lt=end_datetime, # Log starts before the end of the day
            end_time__gt=start_datetime   # Log ends after the start of the day
        ).order_by('start_time') # Order logs chronologically

        # Serialize the data
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
        # Get the trip object, ensuring it belongs to the requesting user and is in progress
        trip = get_object_or_404(Trip, pk=trip_id, driver=request.user)
        if trip.status != 'in_progress':
             return Response({"error": "Trip must be in progress to change ELD status."},
                             status=status.HTTP_400_BAD_REQUEST)

        # --- Validate Input Data ---
        new_status = request.data.get('new_status')
        location = request.data.get('location', trip.current_location) # Default to trip's current if not provided
        coordinates = request.data.get('coordinates', trip.current_coordinates) # Default
        remarks = request.data.get('remarks', '') # Optional remarks field in ELDLog model needed

        # Check if new_status is valid
        valid_statuses = [choice[0] for choice in ELDLog.EVENT_TYPE_CHOICES]
        if new_status not in valid_statuses:
            return Response({"error": f"Invalid status. Choose from: {', '.join(valid_statuses)}"},
                            status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        new_log_entry = None

        try:
            # --- Find and End the Current Log Entry ---
            latest_log = ELDLog.objects.filter(trip=trip).latest('start_time')

            # Avoid creating duplicate entries if status hasn't changed
            if latest_log.event_type == new_status:
                 return Response({"message": f"Status is already '{new_status}'."}, status=status.HTTP_200_OK)

            if latest_log.end_time is None: # Ensure it's the truly active log
                latest_log.end_time = now
                # Calculate duration
                duration_delta = now - latest_log.start_time
                latest_log.duration = duration_delta.total_seconds() / 3600 # Duration in hours
                latest_log.save()
            else:
                # This case might indicate an issue (e.g., previous log wasn't closed properly)
                # Decide how to handle: log a warning, potentially still create new log?
                print(f"Warning: Latest log for Trip {trip.id} already had an end_time.")
                # Proceeding to create new log anyway for this example

            # --- Create the New Log Entry ---
            new_log_entry = ELDLog.objects.create(
                trip=trip,
                event_type=new_status,
                start_time=now,
                end_time=None, # Active log has no end time yet
                duration=0.0, # Duration is 0 until ended
                location=location,
                coordinates=coordinates,
                # remarks=remarks # Add remarks field to model if needed
            )

            # Optionally update trip's current location/coordinates
            trip.current_location = location
            trip.current_coordinates = coordinates
            trip.save()

            # Serialize the newly created log entry for the response
            serializer = ELDLogSerializer(new_log_entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ELDLog.DoesNotExist:
            # Handle case where there are no logs yet (shouldn't happen after StartTripView)
             # Create the first entry directly
            new_log_entry = ELDLog.objects.create(
                trip=trip,
                event_type=new_status,
                start_time=now, # Or should it be trip.startDate? Check logic.
                end_time=None,
                duration=0.0,
                location=location,
                coordinates=coordinates,
                # remarks=remarks
            )
             # Optionally update trip's current location/coordinates
            trip.current_location = location
            trip.current_coordinates = coordinates
            trip.save()
            serializer = ELDLogSerializer(new_log_entry)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Log the exception for debugging
            print(f"Error changing ELD status for Trip {trip_id}: {e}")
            return Response({"error": "An unexpected error occurred."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)