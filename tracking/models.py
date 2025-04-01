from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Trip(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    driver = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100, default="Trip")
    description = models.TextField(blank=True, null=True)
    current_location = models.CharField(max_length=255)
    current_coordinates = models.CharField(max_length=255, default="0.0,0.0")
    pickup_location = models.CharField(max_length=255)
    pickup_coordinates = models.CharField(max_length=255, default="0.0,0.0")
    dropoff_location = models.CharField(max_length=255)
    dropoff_coordinates = models.CharField(max_length=255, default="0.0,0.0")
    current_cycle_used = models.FloatField(help_text="Hours used from 70hr/8day cycle")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    startDate = models.DateTimeField(default=timezone.now)
    estimatedEndDate = models.DateTimeField(null=True, blank=True)
    actual_end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.driver.username} - {self.pickup_location} to {self.dropoff_location}"
    @property
    def has_route(self):
        """Check if this trip has a generated route."""
        return hasattr(self, 'route')
    class Meta:
        ordering = ['-created_at']


class Stop(models.Model):
    STOP_TYPE_CHOICES = [
        ('rest', '10-Hour Rest'),
        ('break', '30-Minute Break'),
        ('fuel', 'Fueling'),
        ('pickup', 'Pickup'),
        ('dropoff', 'Dropoff'),
    ]
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    location = models.CharField(max_length=255)
    coordinates = models.CharField(max_length=255)
    reason = models.CharField(max_length=50, choices=STOP_TYPE_CHOICES)
    duration = models.FloatField(help_text="Duration in hours")
    elapsed_trip_time = models.FloatField(help_text="Hours elapsed since trip start")
    planned_arrival_time = models.DateTimeField()
    actual_arrival_time = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.trip.title} - {self.reason} at {self.location}"


class GPSLog(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="gps_logs")
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed = models.FloatField(null=True, blank=True)  # In mph
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']


class ELDLog(models.Model):
    EVENT_TYPE_CHOICES = [
        ('driving', 'Driving'),
        ('on_duty', 'On Duty Not Driving'),
        ('sleeper_berth', 'Sleeper Berth'),
        ('off_duty', 'Off Duty'),
    ]
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="eld_logs")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    location = models.CharField(max_length=255, null=True, blank=True)
    coordinates = models.CharField(max_length=255, null=True, blank=True)
    duration = models.FloatField(help_text="Duration in hours")
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.trip.title} - {self.event_type} - {self.start_time}"

    class Meta:
        ordering = ['start_time']