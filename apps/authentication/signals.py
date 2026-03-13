from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.notifications.models import ProfileStepReminder, UserNotification, NotificationTemplate, NotificationLog

User = get_user_model()

# Store the previous role value to detect changes
_user_role_cache = {}


@receiver(pre_save, sender=User)
def cache_user_role(sender, instance, **kwargs):
    """Cache the user's previous role before saving"""
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            _user_role_cache[instance.pk] = old_user.role
        except User.DoesNotExist:
            _user_role_cache[instance.pk] = ''
    else:
        _user_role_cache[instance.pk] = ''


@receiver(post_save, sender=User)
def create_profile_step_reminder_on_role_update(sender, instance, created, **kwargs):
    """
    Auto-create ProfileStepReminder and send notifications when user selects 'candidate' role
    This runs when role is updated from '' to 'candidate'
    """
    old_role = _user_role_cache.get(instance.pk, '')

    # Check if role was just changed to 'hr' (recruiter)
    if instance.role == 'hr' and old_role != 'hr':
        # Create placeholder HRProfile if doesn't exist
        from apps.recruiters.models import HRProfile
        if not hasattr(instance, 'hr_profile'):
            HRProfile.objects.create(
                user=instance,
                full_name=f"{instance.first_name or ''} {instance.last_name or ''}".strip() or 'N/A',
                designation='',
                phone='',
                company=None  # Company will be set when user completes registration
            )

        # Log recruiter registration
        recruiter_name = f"{instance.first_name or instance.email}"
        NotificationLog.objects.create(
            log_type='USER_ACTION',
            user=instance,
            message=f"HR {recruiter_name} registered.",
            metadata={
                'user_id': str(instance.id),
                'role': 'hr'
            }
        )

    # Check if role was just changed to 'candidate'
    if instance.role == 'candidate' and old_role != 'candidate':
        # Create ProfileStepReminder if it doesn't exist
        if not hasattr(instance, 'step_reminder'):
            ProfileStepReminder.objects.create(
                user=instance,
                current_step=1,
                last_step_completed_at=timezone.now()
            )

        # Create placeholder Candidate profile if doesn't exist
        from apps.candidates.models import Candidate
        if not hasattr(instance, 'candidate_profile'):
            Candidate.objects.create(
                user=instance,
                first_name=instance.first_name or 'N/A',
                last_name=instance.last_name or 'N/A',
                masked_name='***',
                phone='',
                age=0,
                experience_years=0,
                skills='',
                languages='',
                street_address='',
                career_objective='',
                profile_step=1,
                is_profile_completed=False
            )

        # Send notification to all HR users about new candidate registration
        candidate_name = f"{instance.first_name or instance.email}"
        # registration_time = timezone.now().strftime("%-d %B %Y at %-I:%M %p")
        now = timezone.now()
        registration_time = f"{now.day} {now.strftime('%B %Y at %I:%M %p')}"

        notification_title = "New Candidate Registered"
        notification_body = f"{candidate_name} registered as a candidate on {registration_time}"

        # Try to get template if exists
        try:
            template = NotificationTemplate.objects.filter(
                notification_type='CANDIDATE_REGISTERED',
                is_active=True
            ).first()

            if template:
                notification_title = template.title.format(
                    candidate_name=candidate_name,
                    registration_time=registration_time
                )
                notification_body = template.body.format(
                    candidate_name=candidate_name,
                    registration_time=registration_time
                )
        except Exception:
            pass  # Use default title and body

        # Get all HR users to notify them
        hr_users = User.objects.filter(role='hr', is_active=True)

        for hr_user in hr_users:
            UserNotification.objects.create(
                user=hr_user,
                template=template if 'template' in locals() else None,
                title=notification_title,
                body=notification_body,
                data_payload={
                    'type': 'CANDIDATE_REGISTERED',
                    'user_id': str(instance.id),
                    'candidate_name': candidate_name,
                    'registration_time': registration_time
                }
            )

        # Create notification log
        NotificationLog.objects.create(
            log_type='USER_ACTION',
            user=instance,
            message=f"Candidate {candidate_name} registered. Notifications sent to {hr_users.count()} HR users.",
            metadata={
                'user_id': str(instance.id),
                'hr_notified_count': hr_users.count()
            }
        )

    # Clean up cache
    if instance.pk in _user_role_cache:
        del _user_role_cache[instance.pk]