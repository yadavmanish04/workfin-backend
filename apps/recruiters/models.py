from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
import uuid
import os


User = get_user_model()


def company_logo_path(instance, filename):
    """Generate upload path for company logos"""
    ext = filename.split('.')[-1]
    filename = f"{instance.name}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('company_logos', filename)


class Company(models.Model):
    """Company model to store centralized company information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(
        upload_to=company_logo_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg'])],
        help_text="Company logo (PNG, JPG, JPEG only)"
    )
    company_location = models.ManyToManyField('CompanyLocation', related_name='company_locations', blank=True)
    website = models.URLField(blank=True)
    size = models.CharField(max_length=50, choices=[
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-1000', '201-1000 employees'),
        ('1000+', '1000+ employees')
    ])
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class CompanyLocation(models.Model):
    """Separate model for company locations to support infinite locations via inline admin"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='locations')
    city = models.ForeignKey('candidates.FilterOption', on_delete=models.SET_NULL, null=True, blank=True, related_name='company_city_locations')
    state = models.ForeignKey('candidates.FilterOption', on_delete=models.SET_NULL, null=True, blank=True, related_name='company_state_locations')
    country = models.ForeignKey('candidates.FilterOption', on_delete=models.SET_NULL, null=True, blank=True, related_name='company_country_locations')
    address = models.TextField(blank=True)
    is_headquarters = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Company Location"
        verbose_name_plural = "Company Locations"
        ordering = ['-is_headquarters', 'city']

    def __str__(self):
        city_name = self.city.name if self.city else "Unknown City"
        country_name = self.country.name if self.country else "Unknown Country"
        return f"{city_name}, {country_name} {'(HQ)' if self.is_headquarters else ''}"


class HRProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='hr_profile')
    full_name = models.CharField(max_length=255, blank=True, default='')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='recruiters', null=True, blank=True)
    designation = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    is_verified = models.BooleanField(
        default=False,
        help_text="HR profile verification status (separate from company verification)"
    )
    profile_step = models.IntegerField(
        default=0,
        help_text="Profile setup step: 0=not started, 1=basic info filled, 2=complete"
    )
    is_profile_completed = models.BooleanField(
        default=False,
        help_text="Indicates if recruiter has completed profile setup"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "HR Profile"
        verbose_name_plural = "HR Profiles"

    def __str__(self):
        company_name = self.company.name if self.company else "No Company"
        return f"{company_name} - {self.user.email}"

    def update_profile_step(self):
        """
        Updates profile_step and is_profile_completed based on filled fields
        Step 0: Registration complete (email, password set)
        Step 1: Basic info filled (name, phone, designation)
        Step 2: Company details filled (company selected/created) → Complete
        """
        # Check if basic info is filled
        if self.full_name and self.phone and self.designation:
            self.profile_step = 1
        else:
            self.profile_step = 0

        # Check if company is linked and profile step is at least 1
        if self.company and self.profile_step >= 1:
            self.profile_step = 2
            self.is_profile_completed = True
        else:
            self.is_profile_completed = False

        self.save()