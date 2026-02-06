"""
Django signals for automatic rank recalculation
Triggers rank updates when candidate data changes
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.candidates.models import Candidate, Education, Certification, WorkExperience
from apps.ranking.services import update_candidate_rank


@receiver(post_save, sender=Candidate)
def recalculate_on_candidate_update(sender, instance, created, **kwargs):
    """Recalculate rank when candidate profile is updated"""

    # Only recalculate if profile is active
    if instance.is_active:
        update_candidate_rank(instance, save_history=False)


@receiver([post_save, post_delete], sender=Education)
def recalculate_on_education_change(sender, instance, **kwargs):
    """Recalculate rank when education is added/updated/deleted"""

    if instance.candidate.is_active:
        update_candidate_rank(instance.candidate, save_history=False)


@receiver([post_save, post_delete], sender=Certification)
def recalculate_on_certification_change(sender, instance, **kwargs):
    """Recalculate rank when certification is added/updated/deleted"""

    if instance.candidate.is_active:
        update_candidate_rank(instance.candidate, save_history=False)


@receiver([post_save, post_delete], sender=WorkExperience)
def recalculate_on_experience_change(sender, instance, **kwargs):
    """Recalculate rank when work experience is added/updated/deleted"""

    if instance.candidate.is_active:
        update_candidate_rank(instance.candidate, save_history=False)
