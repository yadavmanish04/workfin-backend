from django.db import models
import uuid


class DashboardContent(models.Model):
    """Model to manage dynamic content for dashboard screens"""
    
    SCREEN_CHOICES = [
        ('CANDIDATE_DASHBOARD', 'Candidate Dashboard'),
        ('HR_DASHBOARD', 'HR Dashboard'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    screen = models.CharField(
        max_length=50, 
        choices=SCREEN_CHOICES,
        unique=True,
        help_text="Which dashboard screen this content is for"
    )
    
    # Main heading
    main_heading = models.CharField(
        max_length=200,
        default="Ready to take the\\nnext step?",
        help_text="Main heading text (use \\n for line breaks)"
    )
    
    # Optional subheading
    subheading = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        help_text="Optional subheading below main heading"
    )
    
    # Welcome message
    welcome_prefix = models.CharField(
        max_length=50,
        default="Hello 👋",
        help_text="Greeting text shown in header"
    )
    
    # Meta information
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['screen']
        verbose_name = 'Dashboard Text Message'
        verbose_name_plural = 'Dashboard Text Messages'
    
    def __str__(self):
        return f"{self.get_screen_display()} - {self.main_heading[:30]}"
    
    def get_main_heading_lines(self):
        """Return main heading as list of lines"""
        return self.main_heading.split('\\n')