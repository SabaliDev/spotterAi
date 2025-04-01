from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id','username', 'email', 'is_driver', 'first_name', 'last_name')
    search_fields = ('username', 'email')
    list_filter = ('is_driver',)
    ordering = ('username',)
