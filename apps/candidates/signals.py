from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Candidate, CandidateFollowup
from apps.notifications.models import UserNotification, NotificationTemplate, NotificationLog, ProfileStepReminder

# Cache previous step values to detect changes
_candidate_step_cache = {}


@receiver(pre_save, sender=Candidate)
def cache_candidate_steps(sender, instance, **kwargs):
    """Cache candidate's previous step completion status"""
    if instance.pk:
        try:
            old_candidate = Candidate.objects.get(pk=instance.pk)
            _candidate_step_cache[instance.pk] = {
                'step1': old_candidate.step1_completed,
                'step2': old_candidate.step2_completed,
                'step3': old_candidate.step3_completed,
                'step4': old_candidate.step4_completed,
            }
        except Candidate.DoesNotExist:
            _candidate_step_cache[instance.pk] = {}
    else:
        _candidate_step_cache[instance.pk] = {}


@receiver(post_save, sender=Candidate)
def sync_step_completion_to_profile_reminder(sender, instance, created, **kwargs):
    """
    Sync Candidate step completion to ProfileStepReminder
    and send notifications to CANDIDATE when steps are completed
    """
    # Get old step values
    old_steps = _candidate_step_cache.get(instance.pk, {})

    # Get or create ProfileStepReminder
    try:
        profile_reminder, created = ProfileStepReminder.objects.get_or_create(
            user=instance.user,
            defaults={'current_step': 1}
        )

        # Sync step completion status
        profile_reminder.step1_completed = instance.step1_completed
        profile_reminder.step1_completed_at = instance.step1_completed_at

        profile_reminder.step2_completed = instance.step2_completed
        profile_reminder.step2_completed_at = instance.step2_completed_at

        profile_reminder.step3_completed = instance.step3_completed
        profile_reminder.step3_completed_at = instance.step3_completed_at

        profile_reminder.step4_completed = instance.step4_completed
        profile_reminder.step4_completed_at = instance.step4_completed_at

        # Update current step based on completion
        if instance.step4_completed:
            profile_reminder.current_step = 5  # All done
            profile_reminder.is_profile_completed = True
        elif instance.step3_completed:
            profile_reminder.current_step = 4
        elif instance.step2_completed:
            profile_reminder.current_step = 3
        elif instance.step1_completed:
            profile_reminder.current_step = 2
        else:
            profile_reminder.current_step = 1

        profile_reminder.save()

        # Send congratulations notification to CANDIDATE when step is completed
        steps_to_check = [
            (1, instance.step1_completed, old_steps.get('step1', False), "Basic Information"),
            (2, instance.step2_completed, old_steps.get('step2', False), "Work Experience"),
            (3, instance.step3_completed, old_steps.get('step3', False), "Education"),
            (4, instance.step4_completed, old_steps.get('step4', False), "Complete Profile"),
        ]

        for step_num, is_completed, was_completed, step_name in steps_to_check:
            # Check if step was just completed (changed from False to True)
            if is_completed and not was_completed:
                # Send notification to CANDIDATE
                UserNotification.objects.create(
                    user=instance.user,
                    title=f"Step {step_num} Completed! 🎉",
                    body=f"Great job! You've completed {step_name}. Keep going to complete your profile.",
                    data_payload={
                        'type': 'STEP_COMPLETED',
                        'step_number': step_num,
                        'step_name': step_name
                    }
                )

                # Reset reminder sent flag for next step
                if step_num == 1:
                    profile_reminder.step1_reminder_sent = False
                elif step_num == 2:
                    profile_reminder.step2_reminder_sent = False
                elif step_num == 3:
                    profile_reminder.step3_reminder_sent = False
                elif step_num == 4:
                    profile_reminder.step4_reminder_sent = False

                profile_reminder.save()

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error syncing step completion for user {instance.user.email}: {str(e)}")

    # Clean up cache
    if instance.pk in _candidate_step_cache:
        del _candidate_step_cache[instance.pk]


@receiver(post_save, sender=Candidate)
def notify_hr_on_profile_creation(sender, instance, created, **kwargs):
    """
    Send notification when a candidate completes their profile
    Note: ProfileStepReminder and initial registration notifications are handled
    in authentication/signals.py when the user selects 'candidate' role
    """
    if created:
        # Get the candidate's full name
        candidate_name = f"{instance.first_name} {instance.last_name}"
        # registration_time = timezone.now().strftime("%d %B %Y at %I:%M %p")
        now = timezone.now()
        registration_time = f"{now.day} {now.strftime('%B %Y at %I:%M %p')}"
    
        # Create notification for admin/HR about new candidate profile completion
        notification_title = "Candidate Profile Created"
        notification_body = f"{candidate_name} completed their candidate profile on {registration_time}"

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
        from django.contrib.auth import get_user_model
        User = get_user_model()

        hr_users = User.objects.filter(role='hr', is_active=True)

        for hr_user in hr_users:
            UserNotification.objects.create(
                user=hr_user,
                template=template if 'template' in locals() else None,
                title=notification_title,
                body=notification_body,
                data_payload={
                    'type': 'CANDIDATE_PROFILE_COMPLETED',
                    'candidate_id': str(instance.id),
                    'candidate_name': candidate_name,
                    'registration_time': registration_time
                }
            )

        # Create notification log
        NotificationLog.objects.create(
            log_type='USER_ACTION',
            user=instance.user,
            message=f"Candidate {candidate_name} completed profile. Notifications sent to {hr_users.count()} HR users.",
            metadata={
                'candidate_id': str(instance.id),
                'hr_notified_count': hr_users.count()
            }
        )


@receiver(post_save, sender=CandidateFollowup)
def schedule_followup_reminder(sender, instance, created, **kwargs):
    """Schedule notification 5 minutes before followup time"""
    from server.scheduler import schedule_followup_notification

    if not instance.is_completed:
        schedule_followup_notification(instance)


@receiver(post_delete, sender=CandidateFollowup)
def cancel_followup_reminder(sender, instance, **kwargs):
    """Cancel scheduled notification when followup is deleted"""
    from server.scheduler import cancel_followup_notification
    cancel_followup_notification(instance.id)