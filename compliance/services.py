from django.utils import timezone
from datetime import timedelta, datetime, time
from tracking.models import ELDLog, Trip
from authentication.models import User

# HOS Constants (mirrors routing/services.py, consider defining in settings or a constants file)
MAX_DRIVING_HOURS_PER_SHIFT = 11
MAX_DUTY_WINDOW = 14
DRIVING_HOURS_BEFORE_BREAK = 8
REQUIRED_REST_DURATION = 10
MANDATORY_BREAK_DURATION = 0.5
WEEKLY_LIMIT = 70
CYCLE_DAYS = 8 # 8-day cycle for 70 hours

def get_hos_status(driver: User, check_time: datetime = None):
    """
    Calculates the driver's current HOS status and remaining hours.

    Args:
        driver: The User object for the driver.
        check_time: The datetime object to check status at (defaults to now).

    Returns:
        A dictionary containing HOS status details.
        Example:
        {
            "remaining_driving_hours": 8.5,
            "remaining_duty_window_hours": 5.0,
            "remaining_cycle_hours": 25.0,
            "time_until_break_required": 3.0, # Hours of driving left before break needed
            "on_duty_today": 6.0,
            "driving_today": 4.0,
            "cycle_total_hours": 45.0,
            "errors": [] # List of potential compliance issues detected
        }
    """
    if check_time is None:
        check_time = timezone.now()

    # --- 1. Calculate 70-Hour/8-Day Cycle ---
    cycle_start_time = check_time - timedelta(days=CYCLE_DAYS)
    # Get logs within the cycle lookback period that ended before check_time
    cycle_logs = ELDLog.objects.filter(
        trip__driver=driver,
        start_time__gte=cycle_start_time,
        start_time__lt=check_time # Only count logs fully or partially completed before check_time
    ).order_by('start_time')

    cycle_on_duty_seconds = 0
    for log in cycle_logs:
        if log.event_type in ['driving', 'on_duty']:
            # Determine the effective end time for calculation (either actual end or check_time)
            effective_end_time = log.end_time if log.end_time and log.end_time < check_time else check_time
            # Ensure we only count duration within the cycle window and before check_time
            effective_start_time = max(log.start_time, cycle_start_time)

            if effective_end_time > effective_start_time:
                 duration_in_window = (effective_end_time - effective_start_time).total_seconds()
                 cycle_on_duty_seconds += duration_in_window

    cycle_total_hours = cycle_on_duty_seconds / 3600
    remaining_cycle_hours = max(0, WEEKLY_LIMIT - cycle_total_hours)

    # --- 2. Calculate 11-Hour Driving and 14-Hour Window ---
    # Find the start of the current duty period by looking backwards from check_time
    # for the last period of >= REQUIRED_REST_DURATION hours off-duty/sleeper
    logs_for_shift_search = ELDLog.objects.filter(
        trip__driver=driver,
        start_time__lt=check_time
    ).order_by('-start_time') # Look backwards

    shift_start_time = None
    accumulated_off_duty_seconds = 0
    previous_log_start = check_time

    for log in logs_for_shift_search:
        is_off_duty_type = log.event_type in ['off_duty', 'sleeper_berth']
        log_end = log.end_time if log.end_time and log.end_time < previous_log_start else previous_log_start

        if is_off_duty_type:
            duration_seconds = (log_end - log.start_time).total_seconds()
            accumulated_off_duty_seconds += duration_seconds
            if accumulated_off_duty_seconds >= REQUIRED_REST_DURATION * 3600:
                # Found the start of the shift (end of the qualifying break)
                shift_start_time = log_end
                break
        else:
            # Reset accumulated off-duty time if an on-duty/driving period is encountered
             accumulated_off_duty_seconds = 0

        previous_log_start = log.start_time
        # If we reach the cycle start time without finding a break, the shift started before that
        if log.start_time <= cycle_start_time:
             # Heuristic: Assume shift started just after the cycle window began if no break found
             # This might need refinement based on how far back you store logs
             shift_start_time = cycle_start_time # Fallback, may not be accurate
             break

    # If no logs found or no shift start identified, assume default/zero values
    if shift_start_time is None:
        # This might happen if the driver hasn't worked recently or logs are missing
        # Set defaults assuming a full fresh shift is available
        shift_start_time = check_time # Or some other sensible default
        driving_in_shift_hours = 0
        duty_window_elapsed_hours = 0
    else:
        # Calculate driving and duty time since shift_start_time
        shift_logs = ELDLog.objects.filter(
            trip__driver=driver,
            start_time__gte=shift_start_time,
            start_time__lt=check_time
        ).order_by('start_time')

        driving_in_shift_seconds = 0
        duty_in_shift_seconds = 0 # Includes driving and on_duty

        for log in shift_logs:
            effective_end = log.end_time if log.end_time and log.end_time < check_time else check_time
            duration_in_shift_seconds = (effective_end - log.start_time).total_seconds()

            if duration_in_shift_seconds > 0:
                duty_in_shift_seconds += duration_in_shift_seconds # All time since shift start counts towards window
                if log.event_type == 'driving':
                    driving_in_shift_seconds += duration_in_shift_seconds

        driving_in_shift_hours = driving_in_shift_seconds / 3600
        # Duty window calculation needs refinement for split sleeper if implemented
        duty_window_elapsed_hours = (check_time - shift_start_time).total_seconds() / 3600

    remaining_driving_hours = max(0, MAX_DRIVING_HOURS_PER_SHIFT - driving_in_shift_hours)
    remaining_duty_window_hours = max(0, MAX_DUTY_WINDOW - duty_window_elapsed_hours)


    # --- 3. Calculate Time Since Last 30-Min Break ---
    # Look backwards from check_time for the end of the last break >= 30 mins
    driving_since_break_seconds = 0
    last_break_end_time = shift_start_time # Start search from shift start

    logs_for_break_search = ELDLog.objects.filter(
        trip__driver=driver,
        start_time__gte=shift_start_time, # Only consider logs within current shift
        start_time__lt=check_time
    ).order_by('-start_time')

    accumulated_break_seconds = 0
    break_found = False
    previous_log_start_for_break = check_time

    for log in logs_for_break_search:
         is_break_type = log.event_type in ['off_duty', 'sleeper_berth'] # Could include 'on_duty' if policy allows
         log_end_for_break = log.end_time if log.end_time and log.end_time < previous_log_start_for_break else previous_log_start_for_break

         if is_break_type:
             duration_seconds = (log_end_for_break - log.start_time).total_seconds()
             accumulated_break_seconds += duration_seconds
             if accumulated_break_seconds >= MANDATORY_BREAK_DURATION * 3600:
                 # Found the end of the last qualifying break
                 last_break_end_time = log_end_for_break
                 break_found = True
                 break # Stop searching
         else:
             # Reset accumulated break time if non-break period encountered
             accumulated_break_seconds = 0

         previous_log_start_for_break = log.start_time

    # Calculate driving time since last_break_end_time
    if break_found:
        driving_since_break_logs = ELDLog.objects.filter(
            trip__driver=driver,
            event_type='driving',
            start_time__gte=last_break_end_time,
            start_time__lt=check_time
        ).order_by('start_time')

        for log in driving_since_break_logs:
            effective_end = log.end_time if log.end_time and log.end_time < check_time else check_time
            driving_since_break_seconds += (effective_end - log.start_time).total_seconds()

    driving_since_break_hours = driving_since_break_seconds / 3600
    time_until_break_required = max(0, DRIVING_HOURS_BEFORE_BREAK - driving_since_break_hours)


    # --- 4. Calculate Today's Totals (Optional but useful) ---
    today_start = timezone.make_aware(datetime.combine(check_time.date(), time.min))
    today_logs = ELDLog.objects.filter(
        trip__driver=driver,
        start_time__lt=check_time,
        end_time__gt=today_start # Overlaps with today
    ).order_by('start_time')

    on_duty_today_seconds = 0
    driving_today_seconds = 0
    for log in today_logs:
         effective_start = max(log.start_time, today_start)
         effective_end = log.end_time if log.end_time and log.end_time < check_time else check_time
         duration_today_seconds = (effective_end - effective_start).total_seconds()

         if duration_today_seconds > 0:
             if log.event_type in ['driving', 'on_duty']:
                 on_duty_today_seconds += duration_today_seconds
                 if log.event_type == 'driving':
                     driving_today_seconds += duration_today_seconds

    on_duty_today_hours = on_duty_today_seconds / 3600
    driving_today_hours = driving_today_seconds / 3600

    # --- 5. Compile Results ---
    # Add basic error/warning checks
    errors = []
    if remaining_driving_hours <= 0: errors.append("Driving limit reached or exceeded.")
    if remaining_duty_window_hours <= 0: errors.append("Duty window limit reached or exceeded.")
    if remaining_cycle_hours <= 0: errors.append("Cycle limit reached or exceeded.")
    if time_until_break_required <= 0 and driving_since_break_hours > 0: # Check if break needed
         # Check if currently driving - if so, it's a violation
         current_status_log = ELDLog.objects.filter(trip__driver=driver).latest('start_time')
         if current_status_log.event_type == 'driving':
              errors.append("Mandatory break required, currently driving.")
         else:
              errors.append("Mandatory break required.")


    return {
        "remaining_driving_hours": round(remaining_driving_hours, 2),
        "remaining_duty_window_hours": round(remaining_duty_window_hours, 2),
        "remaining_cycle_hours": round(remaining_cycle_hours, 2),
        "time_until_break_required": round(time_until_break_required, 2),
        "on_duty_today": round(on_duty_today_hours, 2),
        "driving_today": round(driving_today_hours, 2),
        "cycle_total_hours": round(cycle_total_hours, 2),
        "shift_start_time": shift_start_time.isoformat() if shift_start_time else None,
        "driving_in_shift_hours": round(driving_in_shift_hours, 2),
        "duty_window_elapsed_hours": round(duty_window_elapsed_hours, 2),
        "driving_since_last_break_hours": round(driving_since_break_hours, 2),
        "check_time": check_time.isoformat(),
        "errors": errors
    }

