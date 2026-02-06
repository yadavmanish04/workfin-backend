from django.db import models
from django.core.validators import MinValueValidator


class PointsCreditMapping(models.Model):
    """Admin can define points to credits mapping"""

    points_threshold = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(0)],
        help_text="Minimum points required for this credit tier"
    )
    credits_required = models.IntegerField(
        validators=[MinValueValidator(10)],
        help_text="Credits required to unlock candidate at this points level"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Points-Credits Mapping"
        verbose_name_plural = "Points-Credits Mappings"
        ordering = ['points_threshold']

    def __str__(self):
        return f"{self.points_threshold}+ points = {self.credits_required} credits"


class RankingConfig(models.Model):
    """Admin can configure point values for each factor"""

    # Experience Points
    experience_points_per_year = models.IntegerField(
        default=2,
        validators=[MinValueValidator(0)],
        help_text="Points awarded per year of experience"
    )
    max_experience_points = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0)],
        help_text="Maximum points from experience"
    )

    # Education Points
    points_10th = models.IntegerField(default=2, validators=[MinValueValidator(0)])
    points_12th = models.IntegerField(default=4, validators=[MinValueValidator(0)])
    points_diploma = models.IntegerField(default=6, validators=[MinValueValidator(0)])
    points_bachelors = models.IntegerField(default=10, validators=[MinValueValidator(0)])
    points_masters = models.IntegerField(default=15, validators=[MinValueValidator(0)])
    points_phd = models.IntegerField(default=20, validators=[MinValueValidator(0)])

    # Certification Points
    points_per_certification = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Points per certification"
    )
    max_certification_points = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0)],
        help_text="Maximum points from certifications"
    )

    # Skills Points
    points_per_skill = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Points per skill"
    )
    max_skills_points = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Maximum points from skills"
    )

    # Profile Completeness Points
    points_resume_uploaded = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    points_video_uploaded = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    points_profile_image_uploaded = models.IntegerField(default=3, validators=[MinValueValidator(0)])
    points_career_objective_filled = models.IntegerField(default=3, validators=[MinValueValidator(0)])
    points_all_steps_completed = models.IntegerField(default=4, validators=[MinValueValidator(0)])

    # Availability Bonus
    points_immediate_joining = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=3.0,
        validators=[MinValueValidator(0)],
        help_text="Bonus for immediate joining availability"
    )
    points_willing_to_relocate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=3.0,
        validators=[MinValueValidator(0)],
        help_text="Bonus for willing to relocate"
    )

    # Verification Bonus
    points_verified_profile = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Bonus for admin-verified profile"
    )

    # Meta
    is_active = models.BooleanField(
        default=True,
        help_text="Only one configuration can be active at a time"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ranking Configuration"
        verbose_name_plural = "Ranking Configurations"
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        if self.is_active:
            return "Ranking Config (Active)"
        else:
            date_str = self.updated_at.strftime("%Y-%m-%d")
            return f"Ranking Config (Inactive - {date_str})"

    def save(self, *args, **kwargs):
        # Ensure only one configuration is active
        if self.is_active:
            RankingConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class CandidateRank(models.Model):
    """Stores calculated rank for each candidate"""

    candidate = models.OneToOneField(
        'candidates.Candidate',
        on_delete=models.CASCADE,
        related_name='rank',
        primary_key=True
    )

    # Total Score
    total_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Sum of all score components"
    )

    # Score Breakdown (for transparency)
    experience_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    education_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    certification_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    skills_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    profile_completeness_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    availability_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    verification_score = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    # Credits Required (based on points via PointsCreditMapping)
    credits_required = models.IntegerField(
        default=10,
        validators=[MinValueValidator(10)],
        help_text="Credits needed to unlock this candidate"
    )

    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_score']
        verbose_name = "Candidate Rank"
        verbose_name_plural = "Candidate Rankings"
        indexes = [
            models.Index(fields=['-total_score']),
        ]

    def __str__(self):
        return f"{self.candidate.masked_name} - {self.total_score} pts ({self.credits_required} credits)"


class RankingHistory(models.Model):
    """Historical record of score changes"""

    candidate = models.ForeignKey(
        'candidates.Candidate',
        on_delete=models.CASCADE,
        related_name='rank_history'
    )
    total_score = models.IntegerField(validators=[MinValueValidator(0)])
    credits_required = models.IntegerField(validators=[MinValueValidator(10)])
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-calculated_at']
        verbose_name = "Ranking History"
        verbose_name_plural = "Ranking History"
        indexes = [
            models.Index(fields=['candidate', '-calculated_at']),
        ]

    def __str__(self):
        return f"{self.candidate.masked_name} - {self.total_score} pts on {self.calculated_at.strftime('%Y-%m-%d')}"
