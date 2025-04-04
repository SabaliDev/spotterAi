# Create this file: togemi/compliance/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404
from authentication.models import User
from .services import get_hos_status 

class HOSStatusView(APIView):
    """
    API endpoint to get the current HOS status for the authenticated driver.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Calculates and returns the driver's current HOS status.
        """
        driver = request.user
        if not driver.is_driver: 
             return Response({"error": "User is not a driver."}, status=status.HTTP_403_FORBIDDEN)

        try:
            hos_status = get_hos_status(driver=driver) # Use the service function
            return Response(hos_status, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error calculating HOS status for driver {driver.id}: {e}")
            return Response({"error": "Failed to calculate HOS status."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

