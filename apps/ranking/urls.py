from django.urls import path
from .views import ranking_points_breakdown

urlpatterns = [
    path('how-it-works/', ranking_points_breakdown, name='ranking-how-it-works'),
]
