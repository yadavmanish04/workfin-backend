from django.contrib import admin
from .models import DashboardContent


@admin.register(DashboardContent)
class DashboardContentAdmin(admin.ModelAdmin):
    list_display = [
        'screen', 
        'main_heading_preview', 
        'is_active', 
        'updated_at'
    ]
    list_filter = ['screen', 'is_active', 'updated_at']
    search_fields = ['main_heading', 'subheading']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Screen Selection', {
            'fields': ('screen', 'is_active')
        }),
        ('Header Content', {
            'fields': ('welcome_prefix',),
            'description': 'Content shown in the app header'
        }),
        ('Main Content', {
            'fields': ('main_heading', 'subheading'),
            'description': 'Main dashboard heading. Use \\n for line breaks in main_heading'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def main_heading_preview(self, obj):
        """Show truncated main heading in list view"""
        return obj.main_heading[:50] + ('...' if len(obj.main_heading) > 50 else '')
    main_heading_preview.short_description = 'Main Heading'
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of dashboard content"""
        return False