from django.db import models
from tracking.models import Trip

class Route(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="route")
    distance = models.FloatField()  # Distance in miles
    duration = models.FloatField()  # Time in hours
    route_polyline = models.TextField()  # Encoded polyline for drawing the route on a map
    stops = models.JSONField(default=list)  # List of rest/fueling stops

    def __str__(self):
        return f"Route for Trip {self.trip.id}"
