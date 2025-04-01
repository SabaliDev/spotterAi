import openrouteservice
from django.conf import settings

client = openrouteservice.Client(key=settings.ORS_API_KEY)

def get_stops_along_route(distance, duration, current_cycle_used, coordinates):
    """
    Determines required stops along the route based on HOS regulations.
    
    Args:
        distance (float): Total trip distance in miles
        duration (float): Estimated driving time in hours
        current_cycle_used (float): Hours already used in current cycle (0-70)
        coordinates: List of coordinates for the route
        
    Returns:
        list: Properly placed stops with locations, reasons, and timestamps
    """
    stops = []
    avg_speed = distance / duration if duration > 0 else 65  # mph
    
    # HOS regulations for property-carrying drivers
    MAX_DRIVING_HOURS = 11      # Maximum 11 hours driving time
    MAX_DUTY_WINDOW = 14        # 14-hour driving window
    MANDATORY_BREAK = 0.5       # 30-minute break required after 8 hours driving
    REQUIRED_REST = 10          # 10 consecutive hours off-duty required
    WEEKLY_LIMIT = 70           # 70-hour/8-day limit
    
    # Trip parameters
    remaining_hours_in_cycle = WEEKLY_LIMIT - current_cycle_used
    pickup_time = 1.0  # 1 hour for pickup
    dropoff_time = 1.0  # 1 hour for dropoff
    
    # Calculate remaining driving time available
    available_driving_time = min(MAX_DRIVING_HOURS, remaining_hours_in_cycle)
    
    # Calculate stops based on driving constraints
    trip_segments = []
    remaining_distance = distance
    elapsed_trip_time = 0
    current_position = 0  # index into route coordinates
    
    # Add pickup location as first stop
    stops.append({
        "location": "Pickup Point",
        "reason": "Pickup",
        "duration": pickup_time,
        "coordinates": coordinates[0],
        "elapsed_time": elapsed_trip_time
    })
    elapsed_trip_time += pickup_time
    
    # Track driving hours since last break
    driving_since_break = 0
    driving_in_window = 0
    
    while remaining_distance > 0:
        # Determine how far we can drive before needing a break
        if driving_since_break >= 8:  # Need 30-min break after 8 hours
            # Find appropriate coordinates for this stop
            stop_position = int(current_position + (8 / duration) * len(coordinates))
            stop_position = min(stop_position, len(coordinates) - 1)
            
            stops.append({
                "location": f"Rest Stop",
                "reason": "30-Minute Break",
                "duration": MANDATORY_BREAK,
                "coordinates": coordinates[stop_position],
                "elapsed_time": elapsed_trip_time
            })
            elapsed_trip_time += MANDATORY_BREAK
            driving_since_break = 0
            continue
            
        # Check if we've reached driving limit or duty window
        if driving_in_window >= MAX_DRIVING_HOURS or elapsed_trip_time >= MAX_DUTY_WINDOW:
            # Find appropriate coordinates for this stop
            stop_position = int(current_position + (driving_in_window / duration) * len(coordinates))
            stop_position = min(stop_position, len(coordinates) - 1)
            
            stops.append({
                "location": f"Rest Stop",
                "reason": "10-Hour Rest Period",
                "duration": REQUIRED_REST,
                "coordinates": coordinates[stop_position],
                "elapsed_time": elapsed_trip_time
            })
            elapsed_trip_time += REQUIRED_REST
            driving_in_window = 0
            driving_since_break = 0
            continue
            
        # Check if we need fuel (every 1000 miles)
        next_segment_distance = min(remaining_distance, 1000)
        if next_segment_distance >= 1000:
            # Calculate position in coordinate list for fuel stop
            stop_position = int(current_position + (1000 / distance) * len(coordinates))
            stop_position = min(stop_position, len(coordinates) - 1)
            
            stops.append({
                "location": f"Fuel Stop",
                "reason": "Fueling",
                "duration": 0.5,  # 30 minutes for fueling
                "coordinates": coordinates[stop_position],
                "elapsed_time": elapsed_trip_time
            })
            elapsed_trip_time += 0.5
            remaining_distance -= 1000
            driving_segment_time = 1000 / avg_speed
            driving_since_break += driving_segment_time
            driving_in_window += driving_segment_time
            current_position = stop_position
            continue
            
        # Drive the remaining segment
        driving_segment_time = remaining_distance / avg_speed
        driving_since_break += driving_segment_time
        driving_in_window += driving_segment_time
        elapsed_trip_time += driving_segment_time
        remaining_distance = 0
    
    # Add dropoff as final stop
    stops.append({
        "location": "Dropoff Point",
        "reason": "Delivery",
        "duration": dropoff_time,
        "coordinates": coordinates[-1],
        "elapsed_time": elapsed_trip_time
    })
    
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

def create_route_for_trip(trip):
    """
    Create a route for the given trip using the trip's coordinates and cycle information
    
    Args:
        trip: A Trip model instance
        
    Returns:
        The created Route instance or None if route generation failed
    """
    route_data = get_route_details(
        trip.pickup_coordinates,
        trip.dropoff_coordinates,
        trip.current_cycle_used
    )
    
    if route_data:
        from .models import Route
        route = Route.objects.create(
            trip=trip,
            distance=route_data["distance"],
            duration=route_data["duration"],
            route_polyline=route_data["route_polyline"],
            stops=route_data["stops"]
        )
        return route
    return None
