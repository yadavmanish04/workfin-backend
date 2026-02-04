from django.urls import path
from .views import get_dashboard_content

urlpatterns = [
    path('dashboard/', get_dashboard_content, name='dashboard-content'),
]