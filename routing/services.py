import openrouteservice
from django.conf import settings
from django.utils import timezone
from datetime import timedelta 
from tracking.models import Trip, ELDLog 
from .models import Route

client = openrouteservice.Client(key=settings.ORS_API_KEY)

def get_stops_along_route(distance, duration, current_cycle_used, coordinates):
    """
    Determines required stops along the route based on HOS regulations.

    Args:
        distance (float): Total trip distance in miles
        duration (float): Estimated driving time in hours (only driving time)
        current_cycle_used (float): Hours already used in current cycle (0-70)
        coordinates: List of coordinates for the route

    Returns:
        list: Properly placed stops with locations, reasons, and timestamps
    """
    stops = []
    avg_speed = distance / duration if duration > 0 else 65  # mph

    # HOS regulations for property-carrying drivers
    MAX_DRIVING_HOURS_PER_SHIFT = 11  # Maximum 11 hours driving time within a 14-hour window
    MAX_DUTY_WINDOW = 14        # 14-hour driving window limit
    MANDATORY_BREAK_DURATION = 0.5  # 30-minute break required after 8 hours driving
    DRIVING_HOURS_BEFORE_BREAK = 8  # Drive hours before mandatory break
    REQUIRED_REST_DURATION = 10     # 10 consecutive hours off-duty required
    WEEKLY_LIMIT = 70           # 70-hour/8-day limit (as per assumption)
    FUEL_STOP_INTERVAL = 1000   # Miles before needing fuel (as per assumption)
    FUEL_STOP_DURATION = 0.5    # Duration for fueling stop (example)
    PICKUP_DURATION = 1.0       # Duration for pickup (as per assumption)
    DROPOFF_DURATION = 1.0      # Duration for dropoff (as per assumption)

    # Trip state variables
    remaining_distance = distance
    elapsed_trip_time = 0.0         # Total time including rests/breaks
    driving_time_in_shift = 0.0     # Tracks driving towards 11-hour limit
    driving_since_last_break = 0.0  # Tracks driving towards 8-hour break limit
    duty_window_elapsed = 0.0       # *** NEW: Tracks time against 14-hour window ***
    on_duty_hours_in_cycle = current_cycle_used # Tracks hours against 70-hour limit
    current_position_index = 0      # Index into route coordinates

    # --- Initial Pickup Stop ---
    stops.append({
        "location": "Pickup Point",
        "reason": "Pickup",
        "duration": PICKUP_DURATION,
        "coordinates": coordinates[0],
        "elapsed_time": elapsed_trip_time # Starts at 0
    })
    elapsed_trip_time += PICKUP_DURATION
    duty_window_elapsed += PICKUP_DURATION # Pickup counts towards 14-hr window
    on_duty_hours_in_cycle += PICKUP_DURATION # Counts towards 70-hr cycle

    while remaining_distance > 0:

        # Calculate maximum drivable distance/time before hitting ANY limit
        # Consider: 11-hr driving, 14-hr window, 8-hr break rule, 70-hr cycle, fuel, remaining distance

        # Time until 11-hour driving limit reached
        time_to_11h_limit = MAX_DRIVING_HOURS_PER_SHIFT - driving_time_in_shift
        # Time until 14-hour duty window limit reached
        time_to_14h_limit = MAX_DUTY_WINDOW - duty_window_elapsed
        # Time until 8-hour mandatory break needed
        time_to_mandatory_break = DRIVING_HOURS_BEFORE_BREAK - driving_since_last_break
        # Time until 70-hour cycle limit reached (assuming continuous work)
        time_to_70h_limit = WEEKLY_LIMIT - on_duty_hours_in_cycle

        # Calculate distance possible for each time limit
        dist_to_11h_limit = time_to_11h_limit * avg_speed
        dist_to_14h_limit = time_to_14h_limit * avg_speed # Approx, as window includes non-driving duty
        dist_to_mandatory_break = time_to_mandatory_break * avg_speed
        dist_to_70h_limit = time_to_70h_limit * avg_speed # Approx, as cycle includes non-driving duty

        # Determine the next driving segment distance (minimum of all constraints)
        max_drive_dist_this_segment = min(
            remaining_distance,
            dist_to_11h_limit,
            dist_to_14h_limit, # Check this constraint carefully
            dist_to_mandatory_break,
            dist_to_70h_limit, # Check this constraint carefully
            FUEL_STOP_INTERVAL # Distance until potential fuel stop
        )

        # Ensure we don't drive negative distance if a limit is already hit
        if max_drive_dist_this_segment <= 0:
             # If no distance can be driven, check which limit was hit and force appropriate stop
             if driving_time_in_shift >= MAX_DRIVING_HOURS_PER_SHIFT or duty_window_elapsed >= MAX_DUTY_WINDOW or on_duty_hours_in_cycle >= WEEKLY_LIMIT:
                 # Need 10-hour rest
                 stop_reason = "10-Hour Rest Period"
                 stop_duration = REQUIRED_REST_DURATION
                 reset_shift = True # Flag to reset shift counters after stop
             elif driving_since_last_break >= DRIVING_HOURS_BEFORE_BREAK:
                 # Need 30-min break
                 stop_reason = "30-Minute Break"
                 stop_duration = MANDATORY_BREAK_DURATION
                 reset_shift = False
             else:
                 # Should ideally not happen with positive remaining_distance, maybe handle error
                 print("Warning: Cannot drive but no specific limit hit.")
                 # Force a short break as a fallback? Or handle error appropriately.
                 stop_reason = "Forced Check/Break"
                 stop_duration = 0.1 # Minimal duration
                 reset_shift = False
                 # Or break the loop / raise an error if it's an unexpected state

             # Calculate stop position (approximate)
             # Use current_position_index as the stop location if no driving occurred
             stop_position_index = current_position_index
             stop_position_index = min(stop_position_index, len(coordinates) - 1)

             stops.append({
                "location": f"Stop Location ({stop_reason})", # Replace with better location finding later
                "reason": stop_reason,
                "duration": stop_duration,
                "coordinates": coordinates[stop_position_index],
                "elapsed_time": elapsed_trip_time
             })

             elapsed_trip_time += stop_duration
             # Update cycle hours ONLY if the stop counts as on-duty (e.g., some breaks might)
             # on_duty_hours_in_cycle += stop_duration # Example if break is on-duty
             # *** Reset driving/duty counters based on stop type ***
             driving_since_last_break = 0 # Reset after any break/rest
             if reset_shift: # Only reset for 10-hour rest
                 driving_time_in_shift = 0
                 duty_window_elapsed = 0 # *** Reset 14-hour window ***
             continue # Re-evaluate conditions in the next loop iteration


        # --- Simulate Driving the Segment ---
        driving_segment_time = max_drive_dist_this_segment / avg_speed
        driving_time_in_shift += driving_segment_time
        driving_since_last_break += driving_segment_time
        duty_window_elapsed += driving_segment_time # Driving counts towards 14hr window
        on_duty_hours_in_cycle += driving_segment_time # Driving counts towards 70hr cycle
        elapsed_trip_time += driving_segment_time
        remaining_distance -= max_drive_dist_this_segment

        # Update current position (approximate)
        segment_coord_count = int((max_drive_dist_this_segment / distance) * len(coordinates)) if distance > 0 else 0
        current_position_index += segment_coord_count
        current_position_index = min(current_position_index, len(coordinates) - 1) # Ensure bounds


        # --- Check if a Stop is Needed AFTER driving the segment ---

        stop_needed = False
        stop_reason = ""
        stop_duration = 0.0
        reset_shift = False # Flag to reset shift counters after stop

        # Priority: 10-hour rest (due to 11h driving, 14h window, or 70h cycle limits)
        if driving_time_in_shift >= MAX_DRIVING_HOURS_PER_SHIFT or duty_window_elapsed >= MAX_DUTY_WINDOW or on_duty_hours_in_cycle >= WEEKLY_LIMIT:
            stop_needed = True
            stop_reason = "10-Hour Rest Period"
            stop_duration = REQUIRED_REST_DURATION
            reset_shift = True

        # Next Priority: 30-min break (due to 8h driving)
        elif driving_since_last_break >= DRIVING_HOURS_BEFORE_BREAK:
            stop_needed = True
            stop_reason = "30-Minute Break"
            stop_duration = MANDATORY_BREAK_DURATION
            # Don't reset shift counters for 30-min break, only driving_since_last_break

        # Next Priority: Fuel stop (if interval reached and destination not closer)
        # (Simplified check: add fuel stop if we drove the full interval)
        elif max_drive_dist_this_segment >= FUEL_STOP_INTERVAL and remaining_distance > 0:
             stop_needed = True
             stop_reason = "Fueling"
             stop_duration = FUEL_STOP_DURATION
             # Fueling is on-duty, counts towards 14h window and 70h cycle

        # --- Add Stop if Needed ---
        if stop_needed:
            stop_position_index = current_position_index # Stop occurs at end of driving segment
            stop_position_index = min(stop_position_index, len(coordinates) - 1)

            stops.append({
                "location": f"Stop Location ({stop_reason})", # Replace with better location finding later
                "reason": stop_reason,
                "duration": stop_duration,
                "coordinates": coordinates[stop_position_index],
                "elapsed_time": elapsed_trip_time # Stop starts after driving segment ends
            })

            elapsed_trip_time += stop_duration
            # Update duty/cycle hours based on stop type
            if stop_reason == "Fueling":
                 duty_window_elapsed += stop_duration # Fueling counts for 14h window
                 on_duty_hours_in_cycle += stop_duration # Fueling counts for 70h cycle
            # Add similar checks if 30-min break is taken on-duty

            # *** Reset driving/duty counters based on stop type ***
            driving_since_last_break = 0 # Reset after any break/rest
            if reset_shift: # Only reset for 10-hour rest
                driving_time_in_shift = 0
                duty_window_elapsed = 0 # *** Reset 14-hour window ***


    # --- Final Dropoff Stop ---
    stops.append({
        "location": "Dropoff Point",
        "reason": "Delivery",
        "duration": DROPOFF_DURATION,
        "coordinates": coordinates[-1],
        "elapsed_time": elapsed_trip_time # Starts after last driving segment/stop
    })
    # Dropoff counts towards duty window and cycle if applicable (though trip ends here)
    # duty_window_elapsed += DROPOFF_DURATION
    # on_duty_hours_in_cycle += DROPOFF_DURATION
    # elapsed_trip_time += DROPOFF_DURATION # Add if needed for total trip time calculation

    return stops

def get_route_details(pickup_coords, dropoff_coords, current_cycle_used):
    pickup = [float(pickup_coords.split(',')[1]), float(pickup_coords.split(',')[0])]
    dropoff = [float(dropoff_coords.split(',')[1]), float(dropoff_coords.split(',')[0])]
    
    coords = [pickup, dropoff]
    route = client.directions(coords, profile='driving-car', format='geojson')
    
    if not route:
        return None
    
    # Extract route information
    distance = route['features'][0]['properties']['segments'][0]['distance'] / 1609.34  # Convert to miles
    duration = route['features'][0]['properties']['segments'][0]['duration'] / 3600     # Convert to hours
    coordinates = route['features'][0]['geometry']['coordinates']
    
    # Get stops based on HOS regulations
    stops = get_stops_along_route(distance, duration, current_cycle_used, coordinates)
    
    return {
        "distance": distance,
        "duration": duration,
        "route_polyline": coordinates,
        "stops": stops,
        
    }

def create_route_for_trip(trip: Trip):
    """
    Create a route for the given trip using the trip's coordinates and cycle information,
    and generate initial ELD log entries based on the calculated route and stops.

    Args:
        trip: A Trip model instance

    Returns:
        The created Route instance or None if route generation failed
    """
    # --- 1. Get Route Details (including stops) ---
    route_data = get_route_details(
        trip.pickup_coordinates,
        trip.dropoff_coordinates,
        trip.current_cycle_used
    )

    if not route_data or not route_data.get("stops"):
        print(f"Could not generate route or stops for Trip {trip.id}")
        return None # Cannot proceed without route data and stops

    # --- 2. Create and Save the Route Object ---
    try:
        route = Route.objects.create(
            trip=trip,
            distance=route_data["distance"],
            duration=route_data["duration"],
            # Ensure route_polyline is stored correctly (e.g., as JSON string or text)
            route_polyline=str(route_data["route_polyline"]),
            # Ensure stops are stored correctly (e.g., as JSON)
            stops=route_data["stops"]
        )
    except Exception as e:
        print(f"Error saving Route for Trip {trip.id}: {e}")
        return None


    # --- 3. Generate Initial ELD Logs from Stops ---
    # Use trip.startDate as the absolute reference point
    # Note: Assumes trip.startDate is set correctly when the trip is created/started.
    # If routing is done before the trip starts, adjust timing logic accordingly.
    current_log_time = trip.startDate
    last_elapsed_time = 0.0

    # Clear any potentially existing auto-generated logs for this trip first?
    # ELDLog.objects.filter(trip=trip, auto_generated=True).delete() # Optional: Add an 'auto_generated' flag

    stops = route_data["stops"]

    for i, stop in enumerate(stops):
        stop_start_elapsed = stop['elapsed_time']
        stop_duration = stop['duration']
        stop_reason = stop['reason']
        stop_location = stop.get('location', 'Unknown Location') # Get location if available
        stop_coords = stop.get('coordinates', '0.0,0.0') # Get coordinates if available

        # --- a) Log the Driving Segment BEFORE this stop ---
        driving_duration = stop_start_elapsed - last_elapsed_time
        if driving_duration > 0.001: # Avoid tiny/zero driving logs
            drive_start_time = current_log_time
            drive_end_time = drive_start_time + timedelta(hours=driving_duration)
            ELDLog.objects.create(
                trip=trip,
                event_type='driving',
                start_time=drive_start_time,
                end_time=drive_end_time,
                duration=driving_duration,
                location="En Route", # Generic location for driving
                # coordinates=... # Could try interpolating coordinates
                # auto_generated=True # Optional flag
            )
            current_log_time = drive_end_time # Update current time

        # --- b) Log the Stop Event itself ---
        log_start_time = current_log_time
        log_end_time = log_start_time + timedelta(hours=stop_duration)

        # Map stop reason to ELD event type
        event_type = 'off_duty' # Default
        if stop_reason == "Pickup":
            event_type = 'on_duty'
        elif stop_reason == "Delivery":
            event_type = 'on_duty'
        elif stop_reason == "Fueling":
            event_type = 'on_duty'
        elif stop_reason == "30-Minute Break":
            # Could be 'off_duty', 'sleeper_berth', or 'on_duty' depending on driver action/policy
            # Defaulting to 'off_duty' here, might need adjustment or driver input later
            event_type = 'off_duty'
        elif stop_reason == "10-Hour Rest Period":
            # Could be 'off_duty' or 'sleeper_berth'
            # Defaulting to 'off_duty' here
            event_type = 'off_duty'
            # Consider adding logic for 'sleeper_berth' if the vehicle has one

        ELDLog.objects.create(
            trip=trip,
            event_type=event_type,
            start_time=log_start_time,
            end_time=log_end_time,
            duration=stop_duration,
            location=stop_location,
            coordinates=str(stop_coords), # Store coordinates as string or parse appropriately
            # auto_generated=True # Optional flag
        )

        current_log_time = log_end_time # Update current time
        last_elapsed_time = stop_start_elapsed + stop_duration # Update elapsed time marker


    print(f"Successfully created Route and initial ELD logs for Trip {trip.id}")
    return route
