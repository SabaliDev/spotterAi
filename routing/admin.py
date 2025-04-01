from django.contrib import admin
from .models import Route
# Register your models here.

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip', 'distance', 'duration')
    search_fields = ('id', 'trip')
    list_filter = ('trip',)
    ordering = ('-id',)