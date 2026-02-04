from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
import uuid
from django.conf import settings  

from apps.recruiters.models import HRProfile

User = get_user_model()

def validate_icon_file(value):
    """Allow both image files and SVG files for icons"""
    if not value:
        return
    
    # Check file extension
    if value.name.lower().endswith('.svg'):
        return  # SVG is allowed
    
    # For non-SVG files, use default image validation
    from PIL import Image
    try:
        image = Image.open(value)
        image.verify()
    except Exception:
        raise ValidationError("Upload a valid image or SVG file.")

class FilterCategory(models.Model):
    """Main filter categories like Department, Religion, Location etc."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.FileField(upload_to='filter_icons/', blank=True, null=True, validators=[validate_icon_file])
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    bento_grid = models.PositiveIntegerField(default=0)
    dashboard_display = models.PositiveIntegerField(default=0)
    inner_filter = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name

class FilterOption(models.Model):
    """Individual options within each category"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(FilterCategory, on_delete=models.CASCADE, related_name='options')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    icon = models.FileField(upload_to='filter_option_icons/', blank=True, null=True, validators=[validate_icon_file])
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(
        default=True,
        help_text="Admin approval for custom 'Other' options"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='submitted_filter_options',
        help_text="User who submitted this custom option"
    )
    submitted_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="When this option was submitted"
    )
    approved_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="When this option was approved"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_filter_options',
        help_text="Admin who approved this option"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['category', 'slug']

    def __str__(self):
     approval_status = "✅" if self.is_approved else "⏳"
     return self.name.title()
    

class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidate_profile')
    profile_step = models.PositiveIntegerField(default=1)
    is_profile_completed = models.BooleanField(default=False)
    has_agreed_to_declaration = models.BooleanField(default=False, help_text="Candidate agreed to declaration")
    declaration_agreed_at = models.DateTimeField(null=True, blank=True, help_text="When candidate agreed to declaration")
    work_experience_details = models.ManyToManyField('WorkExperience', blank=True, related_name='candidates')

    # Step completion tracking
    step1_completed = models.BooleanField(default=False, help_text="Basic information filled")
    step1_completed_at = models.DateTimeField(null=True, blank=True)

    step2_completed = models.BooleanField(default=False, help_text="Work experience added")
    step2_completed_at = models.DateTimeField(null=True, blank=True)

    step3_completed = models.BooleanField(default=False, help_text="Education information added")
    step3_completed_at = models.DateTimeField(null=True, blank=True)

    step4_completed = models.BooleanField(default=False, help_text="Profile fully completed")
    step4_completed_at = models.DateTimeField(null=True, blank=True)

    # Basic Information
    # full_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    masked_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    age = models.PositiveIntegerField()
    
    role = models.ForeignKey(FilterOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='role_candidates')
    experience_years = models.PositiveIntegerField()
    # current_ctc = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    # expected_ctc = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    
    # Personal Information - Using FilterOption
    religion = models.ForeignKey(FilterOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='religion_candidates')
    
    # Location - Using FilterOption with hierarchy
    country = models.ForeignKey(FilterOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='country_candidates')
    state = models.ForeignKey(FilterOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='state_candidates')
    city = models.ForeignKey(FilterOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='city_candidates')
    
    skills = models.TextField()  

    
    # Resume & Documents
    resume = models.FileField(upload_to='resumes/', blank=True)
    video_intro = models.FileField(upload_to='video_intros/', blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    languages = models.TextField()  
    street_address = models.CharField(max_length=500)
    willing_to_relocate = models.BooleanField(default=False)
    joining_availability = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('NOTICE_PERIOD', 'Notice Period'),
        ],
        default='IMMEDIATE'
    )
    notice_period_details = models.CharField(max_length=255, blank=True, null=True)
    
    # Career Objective
    career_objective = models.TextField()


    # Meta Information
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, help_text="Admin approval for candidate profile")
    is_available_for_hiring = models.BooleanField(default=True, help_text="Is candidate currently available for hiring opportunities")
    last_availability_update = models.DateTimeField(null=True, blank=True, help_text="Last time candidate updated their availability status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return self.masked_name
        
    def get_skills_list(self):
        return [skill.strip() for skill in self.skills.split(',') if skill.strip()]

class UnlockHistory(models.Model):
    hr_user = models.ForeignKey(HRProfile, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    credits_used = models.PositiveIntegerField(default=10)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['hr_user', 'candidate']
        ordering = ['-unlocked_at']
        
    def __str__(self):
        return f"{self.hr_user.user.email} unlocked {self.candidate}"

class CandidateNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hr_user = models.ForeignKey(HRProfile, on_delete=models.CASCADE, related_name='candidate_notes')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='notes')
    note_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Note by {self.hr_user.user.email} for {self.candidate.masked_name}"

class CandidateFollowup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hr_user = models.ForeignKey(HRProfile, on_delete=models.CASCADE, related_name='candidate_followups')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='followups')
    followup_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['followup_date']
        
    def __str__(self):
        return f"{self.hr_user.user.email} for {self.candidate.masked_name} on {self.followup_date}"

class WorkExperience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='work_experiences')
    company_name = models.CharField(max_length=255)
    role_title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    current_ctc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.candidate.masked_name} - {self.role_title} at {self.company_name}"

class CareerGap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='career_gaps')
    start_date = models.DateField()
    end_date = models.DateField()
    gap_reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.candidate.masked_name} - Gap from {self.start_date} to {self.end_date}"

class Education(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='educations')
    institution_name = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255, blank=True)
    start_year = models.PositiveIntegerField()
    end_year = models.PositiveIntegerField(null=True, blank=True)  # Null for ongoing
    is_ongoing = models.BooleanField(default=False)
    grade_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_year']
    
    def __str__(self):
        return f"{self.candidate.masked_name} - {self.degree} from {self.institution_name}"

class Certification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='certifications')
    certification_name = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)  # Null for lifetime certs
    is_lifetime = models.BooleanField(default=False)
    certificate_number = models.CharField(max_length=255, blank=True)
    certificate_url = models.URLField(max_length=500, blank=True, null=True)
    document = models.FileField(upload_to='certifications/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.candidate.masked_name} - {self.certification_name} from {self.issuing_organization}"


# Signal to auto-generate masked_name
@receiver(pre_save, sender=Candidate)
def generate_masked_name(sender, instance, **kwargs):
    if instance.first_name and instance.last_name and not instance.masked_name:
        full_name = f"{instance.first_name} {instance.last_name}"
        names = full_name.split()
        masked = []
        for name in names:
            if len(name) > 1:
                masked.append(name[0] + '*' * (len(name) - 1))
            else:
                masked.append('*')
        instance.masked_name = ' '.join(masked)


class HiringAvailabilityUI(models.Model):
    """Dynamic UI Configuration for Hiring Availability Screen"""

    # Meta Information
    name = models.CharField(max_length=100, unique=True, help_text="Configuration name for admin reference")
    is_active = models.BooleanField(default=True, help_text="Only one configuration can be active at a time")

    # Content Fields
    title = models.CharField(max_length=200, default="Are you still available for hiring?")
    message = models.TextField(default="Please confirm if you're still open to new job opportunities.")

    # Layout Configuration
    LAYOUT_CHOICES = [
        ('column', 'Column (Vertical Stack)'),
        ('row', 'Row (Horizontal)'),
    ]
    button_layout = models.CharField(max_length=10, choices=LAYOUT_CHOICES, default='column')

    VERTICAL_ALIGNMENT_CHOICES = [
        ('top', 'Top - Content starts from top'),
        ('center', 'Center - Content centered vertically'),
        ('bottom', 'Bottom - Content aligned to bottom'),
    ]
    content_vertical_alignment = models.CharField(
        max_length=10,
        choices=VERTICAL_ALIGNMENT_CHOICES,
        default='center',
        help_text="Vertical position of all content in the screen"
    )

    # Background Configuration
    BACKGROUND_TYPE_CHOICES = [
        ('color', 'Solid Color'),
        ('image', 'Image'),
        ('gradient', 'Gradient'),
    ]
    background_type = models.CharField(max_length=10, choices=BACKGROUND_TYPE_CHOICES, default='color')
    background_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Hex color code (e.g., #FFFFFF)")
    background_image = models.ImageField(upload_to='hiring_availability_bg/', null=True, blank=True)
    gradient_start_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Gradient start color")
    gradient_end_color = models.CharField(max_length=7, default='#F5F5F5', help_text="Gradient end color")

    # Icon Configuration
    ICON_SOURCE_CHOICES = [
        ('material', 'Material Icon (Built-in)'),
        ('upload', 'Upload Custom Icon/Image'),
    ]
    icon_source = models.CharField(max_length=10, choices=ICON_SOURCE_CHOICES, default='material', help_text="Choose icon source")
    icon_type = models.CharField(max_length=50, default='work_outline_rounded', help_text="Material Icon name (only for material source)")
    icon_image = models.FileField(upload_to='hiring_availability_icons/', null=True, blank=True, validators=[validate_icon_file], help_text="Upload custom icon/image - supports PNG, JPG, JPEG, SVG (only for upload source)")
    icon_size = models.FloatField(default=60.0, help_text="Icon size in pixels")
    icon_color = models.CharField(max_length=7, default='#4CAF50', help_text="Icon color hex code (only for material icons)")
    icon_background_color = models.CharField(max_length=9, default='#4CAF5019', help_text="Icon background with opacity")
    show_icon = models.BooleanField(default=True)

    # Title Styling
    title_font_size = models.FloatField(default=24.0)
    title_font_weight = models.CharField(max_length=20, default='bold',
                                         choices=[('normal', 'Normal'), ('bold', 'Bold'), ('w600', 'Semi Bold'), ('w700', 'Bold'), ('w800', 'Extra Bold')])
    title_color = models.CharField(max_length=7, default='#000000')
    title_alignment = models.CharField(max_length=10, default='center',
                                       choices=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')])

    # Message Styling
    message_font_size = models.FloatField(default=16.0)
    message_font_weight = models.CharField(max_length=20, default='normal',
                                          choices=[('normal', 'Normal'), ('bold', 'Bold'), ('w500', 'Medium'), ('w600', 'Semi Bold')])
    message_color = models.CharField(max_length=7, default='#757575')
    message_alignment = models.CharField(max_length=10, default='center',
                                        choices=[('left', 'Left'), ('center', 'Center'), ('right', 'Right')])

    # Primary Button (Yes/Available)
    primary_button_text = models.CharField(max_length=100, default="Yes, I'm Available")
    primary_button_bg_color = models.CharField(max_length=7, default='#4CAF50')
    primary_button_text_color = models.CharField(max_length=7, default='#FFFFFF')
    primary_button_font_size = models.FloatField(default=18.0)
    primary_button_font_weight = models.CharField(max_length=20, default='w600',
                                                  choices=[('normal', 'Normal'), ('bold', 'Bold'), ('w500', 'Medium'), ('w600', 'Semi Bold'), ('w700', 'Bold')])
    primary_button_height = models.FloatField(default=56.0)
    primary_button_border_radius = models.FloatField(default=12.0)

    # Secondary Button (No/Not Available)
    secondary_button_text = models.CharField(max_length=100, default="No, Not Available")
    secondary_button_bg_color = models.CharField(max_length=7, default='#FFFFFF')
    secondary_button_text_color = models.CharField(max_length=7, default='#616161')
    secondary_button_border_color = models.CharField(max_length=7, default='#BDBDBD')
    secondary_button_font_size = models.FloatField(default=18.0)
    secondary_button_font_weight = models.CharField(max_length=20, default='w600',
                                                    choices=[('normal', 'Normal'), ('bold', 'Bold'), ('w500', 'Medium'), ('w600', 'Semi Bold'), ('w700', 'Bold')])
    secondary_button_height = models.FloatField(default=56.0)
    secondary_button_border_radius = models.FloatField(default=12.0)

    # Spacing Configuration
    spacing_between_buttons = models.FloatField(default=16.0, help_text="Space between buttons in pixels")
    content_padding_horizontal = models.FloatField(default=24.0)
    content_padding_vertical = models.FloatField(default=32.0)

    # Extra Content Sections (JSON field for dynamic content)
    extra_content = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional content sections in JSON format. Example: [{'type': 'text', 'content': 'Extra info', 'position': 'top'}]"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hiring Availability UI Configuration"
        verbose_name_plural = "Hiring Availability UI Configurations"
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return f"{self.name} {'(Active)' if self.is_active else ''}"

    def save(self, *args, **kwargs):
        # Ensure only one configuration is active
        if self.is_active:
            HiringAvailabilityUI.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)




class ProfileTip(models.Model):
    """Dynamic Profile Tips for Candidate Dashboard"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="Tip title")
    subtitle = models.CharField(max_length=300, help_text="Short description")
    icon_type = models.CharField(
        max_length=50, 
        default='photo_camera_outlined',
        help_text="Material Icon name"
    )
    
    # Instructions as JSON array
    instructions = models.JSONField(
        help_text="Array of instruction steps. Example: ['Step 1', 'Step 2']"
    )
    
    display_order = models.PositiveIntegerField(default=0, help_text="Order to display tips")
    is_active = models.BooleanField(default=True, help_text="Show/hide this tip")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'created_at']
        verbose_name = "Profile Tip"
        verbose_name_plural = "Profile Tips"
    
    def __str__(self):
        return f"{self.title} (Order: {self.display_order})"