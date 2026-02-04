from rest_framework import serializers
from .models import DashboardContent


class DashboardContentSerializer(serializers.ModelSerializer):
    """Serializer for dashboard content"""
    
    main_heading_lines = serializers.SerializerMethodField()
    
    class Meta:
        model = DashboardContent
        fields = [
            'id',
            'screen',
            'main_heading',
            'main_heading_lines',
            'subheading',
            'welcome_prefix',
            'is_active'
        ]
    
    def get_main_heading_lines(self, obj):
        """Split main heading by \\n for multi-line display"""
        return obj.main_heading.split('\\n') if obj.main_heading else []