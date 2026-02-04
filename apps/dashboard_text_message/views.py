from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import DashboardContent
from .serializers import DashboardContentSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_content(request):
    """
    Get dashboard content based on user role
    
    - Candidates get CANDIDATE_DASHBOARD content
    - HR users get HR_DASHBOARD content
    """
    
    # Determine which dashboard content to fetch based on user role
    if request.user.role == 'candidate':
        screen_type = 'CANDIDATE_DASHBOARD'
    elif request.user.role == 'hr':
        screen_type = 'HR_DASHBOARD'
    else:
        return Response({
            'error': 'Invalid user role'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        content = DashboardContent.objects.get(
            screen=screen_type,
            is_active=True
        )
        serializer = DashboardContentSerializer(content)
        
        return Response({
            'success': True,
            'content': serializer.data
        })
        
    except DashboardContent.DoesNotExist:
        return Response({
            'success': True,
            'content': None
        })