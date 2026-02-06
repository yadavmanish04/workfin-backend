import logging
from typing import Dict, List, Optional
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.template import Template, Context
from datetime import timedelta

# Import your existing FCM utilities
from server.fcm_utils import SimpleFCM

logger = logging.getLogger(__name__)
User = get_user_model()


class WorkfinaFCMService:
    """Workfina-specific FCM notification service"""

    @staticmethod
    def get_user_display_name(user) -> str:
        """Get user's full name from profile or fallback to email"""
        # For candidates, check their profile first
        if user.role == 'candidate':
            try:
                # ForeignKey relationship, get first candidate profile
                candidate = user.candidate_profile.first()
                if candidate:
                    if candidate.first_name and candidate.last_name:
                        return f"{candidate.first_name} {candidate.last_name}".strip()
                    elif candidate.first_name:
                        return candidate.first_name
                    elif candidate.last_name:
                        return candidate.last_name
            except Exception:
                pass

        # Fallback to User model names
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}".strip()
        elif user.first_name:
            return user.first_name
        elif user.last_name:
            return user.last_name
        else:
            # Last resort: extract username from email
            return user.email.split('@')[0]

    @staticmethod
    def send_notification(notification) -> Dict:
        """Send individual notification via FCM"""
        try:
            from .models import NotificationLog
            
            # Check if user has FCM token
            if not notification.user.fcm_token:
                notification.status = 'FAILED'
                notification.error_message = 'User has no FCM token'
                notification.save()
                
                NotificationLog.objects.create(
                    log_type='FCM_ERROR',
                    user=notification.user,
                    notification=notification,
                    message=f'No FCM token for user {notification.user.email}'
                )
                return {'success': False, 'error': 'No FCM token'}
            
            # Prepare FCM data
            data_payload = {
                'notification_id': str(notification.id),
                'type': notification.template.notification_type if notification.template else 'CUSTOM',
                'timestamp': str(timezone.now().isoformat()),
                **notification.data_payload
            }
            
            # Send via SimpleFCM with sound enabled
            logger.info(f"Sending notification with sound enabled to {notification.user.email}")
            result = SimpleFCM.send_to_token(
                token=notification.user.fcm_token,
                title=notification.title,
                body=notification.body,
                data=data_payload,
                play_sound=True
            )
            logger.info(f"FCM result: {result}")
            
            if result.get('success_count', 0) > 0:
                notification.status = 'SENT'
                notification.sent_at = timezone.now()
                notification.fcm_message_id = result.get('message_id', '')
                notification.error_message = None
                
                NotificationLog.objects.create(
                    log_type='FCM_SENT',
                    user=notification.user,
                    notification=notification,
                    message=f'Notification sent successfully to {notification.user.email}',
                    metadata=result
                )
                
                logger.info(f'Notification sent to {notification.user.email}: {notification.title}')
                return {'success': True, 'message_id': result.get('message_id')}
            else:
                notification.status = 'FAILED'
                notification.error_message = result.get('error', 'Unknown FCM error')
                
                NotificationLog.objects.create(
                    log_type='FCM_ERROR',
                    user=notification.user,
                    notification=notification,
                    message=f'FCM send failed: {result.get("error", "Unknown error")}',
                    metadata=result
                )
                
                logger.error(f'Failed to send notification to {notification.user.email}: {result.get("error")}')
                return {'success': False, 'error': result.get('error')}
        
        except Exception as e:
            notification.status = 'FAILED'
            notification.error_message = str(e)
            notification.save()
            
            logger.error(f'Exception sending notification: {str(e)}', exc_info=True)
            return {'success': False, 'error': str(e)}
        finally:
            notification.save()
    
    @staticmethod
    def send_to_user(user, title: str, body: str, notification_type: str = 'GENERAL', data: Dict = None) -> Dict:
        """Send custom notification to specific user"""
        try:
            from .models import UserNotification, NotificationTemplate
            
            # Try to get template if exists
            template = None
            try:
                template = NotificationTemplate.objects.get(
                    notification_type=notification_type,
                    is_active=True
                )
                # Use template content if provided
                if not title:
                    title = template.title
                if not body:
                    body = template.body
            except NotificationTemplate.DoesNotExist:
                pass
            
            # Create notification record
            notification = UserNotification.objects.create(
                user=user,
                template=template,
                title=title,
                body=body,
                data_payload=data or {},
                scheduled_for=timezone.now()
            )
            
            # Send immediately
            return WorkfinaFCMService.send_notification(notification)
            
        except Exception as e:
            logger.error(f'Error in send_to_user: {str(e)}', exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_welcome_message(user) -> Dict:
        """Send welcome message to new users"""
        try:
            from .models import NotificationTemplate
            
            template = NotificationTemplate.objects.filter(
                notification_type='WELCOME',
                recipient_type__in=['ALL', user.role.upper()],
                is_active=True
            ).first()
            
            if not template:
                # Fallback welcome message
                title = "Welcome to Workfina! 🎉"
                body = f"Hi {WorkfinaFCMService.get_user_display_name(user)}, welcome to Workfina! Complete your profile to get started."
            else:
                # Use template with user context
                context = Context({'user_name': WorkfinaFCMService.get_user_display_name(user), 'user_email': user.email})
                title = Template(template.title).render(context)
                body = Template(template.body).render(context)
            
            return WorkfinaFCMService.send_to_user(
                user=user,
                title=title,
                body=body,
                notification_type='WELCOME',
                data={'welcome': True, 'user_role': user.role}
            )
            
        except Exception as e:
            logger.error(f'Error sending welcome message to {user.email}: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_profile_step_reminder(user, current_step: int, reminder_type: str = 'general') -> Dict:
        """Send profile completion reminder"""
        try:
            from .models import NotificationTemplate, ProfileStepReminder
            
            # Get or create profile reminder tracker
            reminder_obj, created = ProfileStepReminder.objects.get_or_create(
                user=user,
                defaults={'current_step': current_step}
            )
            
            if not created:
                reminder_obj.update_step(current_step)
            
            # Get appropriate template
            template = NotificationTemplate.objects.filter(
                notification_type='PROFILE_STEP_REMINDER',
                recipient_type__in=['ALL', 'CANDIDATE'],
                is_active=True
            ).first()
            
            if template:
                context = Context({
                    'user_name': WorkfinaFCMService.get_user_display_name(user),
                    'current_step': current_step,
                    'next_step': current_step + 1,
                    'reminder_type': reminder_type
                })
                title = Template(template.title).render(context)
                body = Template(template.body).render(context)
            else:
                # Fallback messages based on reminder type
                if reminder_type == 'first':
                    title = "Complete Your Profile 📋"
                    body = f"Hi {WorkfinaFCMService.get_user_display_name(user)}, you're on step {current_step}. Complete your profile to find better opportunities!"
                elif reminder_type == 'second':
                    title = "Don't Miss Out! Complete Profile 🚀"
                    body = f"Your profile is {(current_step-1)*25}% complete. Finish it now to get noticed by top recruiters!"
                else:
                    title = "Last Chance - Complete Profile ⚡"
                    body = f"Complete your profile to unlock all features and connect with hiring managers!"
            
            # Update reminder status
            if reminder_type == 'first':
                reminder_obj.first_reminder_sent = True
                reminder_obj.first_reminder_at = timezone.now()
            elif reminder_type == 'second':
                reminder_obj.second_reminder_sent = True
                reminder_obj.second_reminder_at = timezone.now()
            elif reminder_type == 'final':
                reminder_obj.final_reminder_sent = True
                reminder_obj.final_reminder_at = timezone.now()
            
            reminder_obj.save()
            
            return WorkfinaFCMService.send_to_user(
                user=user,
                title=title,
                body=body,
                notification_type='PROFILE_STEP_REMINDER',
                data={
                    'current_step': current_step,
                    'reminder_type': reminder_type,
                    'profile_completion': (current_step - 1) * 25
                }
            )
            
        except Exception as e:
            logger.error(f'Error sending profile reminder to {user.email}: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def notify_hrs_about_hired_candidate(candidate) -> Dict:
        """Notify HR users who unlocked this candidate about hiring"""
        try:
            from apps.candidates.models import UnlockHistory
            from .models import NotificationTemplate
            
            # Get HRs who unlocked this candidate
            unlocked_histories = UnlockHistory.objects.filter(candidate=candidate)
            
            if not unlocked_histories.exists():
                return {'success': True, 'message': 'No HRs to notify'}
            
            # Get template
            template = NotificationTemplate.objects.filter(
                notification_type='CANDIDATE_HIRED',
                recipient_type__in=['ALL', 'HR'],
                is_active=True
            ).first()
            
            success_count = 0
            failure_count = 0
            
            for history in unlocked_histories:
                hr_user = history.hr_user.user
                
                if template:
                    context = Context({
                        'candidate_name': candidate.masked_name,
                        'hr_name': hr_user.first_name or hr_user.email,
                        'company': getattr(candidate.hiring_status, 'company_name', 'Unknown Company') if hasattr(candidate, 'hiring_status') else 'Unknown Company'
                    })
                    title = Template(template.title).render(context)
                    body = Template(template.body).render(context)
                else:
                    title = f"Candidate Update: {candidate.masked_name} Hired! 🎉"
                    body = f"Good news! {candidate.masked_name} (whom you unlocked) has been hired. Update your search for similar profiles."
                
                result = WorkfinaFCMService.send_to_user(
                    user=hr_user,
                    title=title,
                    body=body,
                    notification_type='CANDIDATE_HIRED',
                    data={
                        'candidate_id': str(candidate.id),
                        'candidate_name': candidate.masked_name,
                        'action': 'hired'
                    }
                )
                
                if result.get('success'):
                    success_count += 1
                else:
                    failure_count += 1
            
            logger.info(f'Notified HRs about hired candidate {candidate.masked_name}: {success_count} success, {failure_count} failed')
            return {'success_count': success_count, 'failure_count': failure_count}
            
        except Exception as e:
            logger.error(f'Error notifying HRs about hired candidate: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_credit_update_notification(user, credits_added: int, current_balance: int) -> Dict:
        """Notify user about credit updates"""
        try:
            from .models import NotificationTemplate
            
            template = NotificationTemplate.objects.filter(
                notification_type='CREDIT_UPDATE',
                recipient_type__in=['ALL', 'HR'],
                is_active=True
            ).first()
            
            if template:
                context = Context({
                    'user_name': WorkfinaFCMService.get_user_display_name(user),
                    'credits_added': credits_added,
                    'current_balance': current_balance
                })
                title = Template(template.title).render(context)
                body = Template(template.body).render(context)
            else:
                title = f"Credits Added! 💰"
                body = f"Hi {WorkfinaFCMService.get_user_display_name(user)}, {credits_added} credits have been added to your account. Current balance: {current_balance}"
            
            return WorkfinaFCMService.send_to_user(
                user=user,
                title=title,
                body=body,
                notification_type='CREDIT_UPDATE',
                data={
                    'credits_added': credits_added,
                    'current_balance': current_balance,
                    'transaction_type': 'credit_added'
                }
            )
            
        except Exception as e:
            logger.error(f'Error sending credit update to {user.email}: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_bulk_notification(title: str, body: str, recipient_type: str = 'ALL', play_sound: bool = True) -> Dict:
        """Send bulk notification to multiple users"""
        try:
            from .models import UserNotification
            
            # Filter users based on recipient type
            if recipient_type == 'CANDIDATE':
                users = User.objects.filter(role='candidate', is_active=True, fcm_token__isnull=False).exclude(fcm_token='')
            elif recipient_type == 'HR':
                users = User.objects.filter(role='hr', is_active=True, fcm_token__isnull=False).exclude(fcm_token='')
            else:  # ALL
                users = User.objects.filter(is_active=True, fcm_token__isnull=False).exclude(fcm_token='')
            
            success_count = 0
            failure_count = 0
            
            # Create and send notifications
            for user in users:
                try:
                    notification = UserNotification.objects.create(
                        user=user,
                        title=title,
                        body=body,
                        data_payload={'bulk': True, 'recipient_type': recipient_type},
                        scheduled_for=timezone.now()
                    )
                    
                    result = WorkfinaFCMService.send_notification(notification)
                    if result.get('success'):
                        success_count += 1
                    else:
                        failure_count += 1
                        
                except Exception as e:
                    logger.error(f'Error sending bulk notification to {user.email}: {str(e)}')
                    failure_count += 1
            
            logger.info(f'Bulk notification sent: {success_count} success, {failure_count} failed')
            return {'success_count': success_count, 'failure_count': failure_count}
            
        except Exception as e:
            logger.error(f'Error in bulk notification: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def check_and_send_profile_reminders():
        """Check all users who need profile completion reminders (for cron/celery)"""
        try:
            from .models import ProfileStepReminder, NotificationLog

            # Get all users who need reminders
            reminders = ProfileStepReminder.objects.filter(is_profile_completed=False)

            sent_count = 0

            for reminder in reminders:
                needs_reminder, reminder_type = reminder.needs_reminder()

                if needs_reminder:
                    result = WorkfinaFCMService.send_profile_step_reminder(
                        user=reminder.user,
                        current_step=reminder.current_step,
                        reminder_type=reminder_type
                    )

                    if result.get('success'):
                        sent_count += 1

                    # Log the reminder activity
                    NotificationLog.objects.create(
                        log_type='REMINDER_SCHEDULED',
                        user=reminder.user,
                        message=f'Profile step reminder ({reminder_type}) sent to step {reminder.current_step}',
                        metadata={'reminder_type': reminder_type, 'step': reminder.current_step}
                    )

            logger.info(f'Profile reminder check completed: {sent_count} reminders sent')
            return {'sent_count': sent_count}

        except Exception as e:
            logger.error(f'Error checking profile reminders: {str(e)}')
            return {'error': str(e)}

    @staticmethod
    def send_daily_availability_reminder():
        """Send daily 8 AM availability reminder to all candidates (for cron/celery)"""
        try:
            from apps.candidates.models import Candidate
            from .models import NotificationTemplate, NotificationLog

            # Get all active candidates with completed profiles
            candidates = Candidate.objects.filter(
                is_active=True,
                is_profile_completed=True
            ).select_related('user')

            # Get template if exists
            template = NotificationTemplate.objects.filter(
                notification_type='AVAILABILITY_REMINDER',
                recipient_type__in=['ALL', 'CANDIDATE'],
                is_active=True
            ).first()

            success_count = 0
            failure_count = 0

            for candidate in candidates:
                user = candidate.user

                # Skip if no FCM token
                if not user.fcm_token:
                    continue

                if template:
                    # Use Django template rendering instead of .format()
                    context = Context({
                        'user_name': WorkfinaFCMService.get_user_display_name(user),
                        'current_status': 'Available' if candidate.is_available_for_hiring else 'Not Available'
                    })
                    title = Template(template.title).render(context)
                    body = Template(template.body).render(context)
                else:
                    title = "Are you still available for hiring?"
                    body = f"Hi {WorkfinaFCMService.get_user_display_name(user)}! Please confirm if you're still open to new job opportunities. Update your availability status."

                result = WorkfinaFCMService.send_to_user(
                    user=user,
                    title=title,
                    body=body,
                    notification_type='AVAILABILITY_REMINDER',
                    data={
                        'action': 'availability_check',
                        'current_status': candidate.is_available_for_hiring,
                        'candidate_id': str(candidate.id)
                    }
                )

                if result.get('success'):
                    success_count += 1
                else:
                    failure_count += 1

                # Log the notification
                NotificationLog.objects.create(
                    log_type='AVAILABILITY_REMINDER',
                    user=user,
                    message=f'Daily availability reminder sent to {user.email}',
                    metadata={
                        'success': result.get('success', False),
                        'candidate_id': str(candidate.id)
                    }
                )

            logger.info(f'Daily availability reminders sent: {success_count} success, {failure_count} failed')
            return {'success_count': success_count, 'failure_count': failure_count}

        except Exception as e:
            logger.error(f'Error sending daily availability reminders: {str(e)}')
            return {'success': False, 'error': str(e)}


# Signal handlers for automatic notifications
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def send_welcome_notification(sender, instance, created, **kwargs):
    """Send welcome notification to new users"""
    if created and instance.is_email_verified:
        try:
            # Delay the welcome message by 30 seconds to ensure user is set up
            from django.utils import timezone
            from .models import UserNotification, NotificationTemplate
            
            template = NotificationTemplate.objects.filter(
                notification_type='WELCOME',
                is_active=True,
                auto_trigger=True
            ).first()
            
            if template:
                # Render template with user context
                context = Context({'user_name': WorkfinaFCMService.get_user_display_name(instance), 'user_email': instance.email})
                title = Template(template.title).render(context)
                body = Template(template.body).render(context)

                UserNotification.objects.create(
                    user=instance,
                    template=template,
                    title=title,
                    body=body,
                    scheduled_for=timezone.now() + timedelta(seconds=30),
                    data_payload={'welcome': True, 'user_role': instance.role}
                )
        except Exception as e:
            logger.error(f'Error scheduling welcome notification: {str(e)}')


# You can add this to your candidates app models.py or signals.py
@receiver(post_save, sender='candidates.Candidate')
def track_profile_steps(sender, instance, created, **kwargs):
    """Track candidate profile completion steps"""
    if created:
        try:
            from .models import ProfileStepReminder
            
            ProfileStepReminder.objects.get_or_create(
                user=instance.user,
                defaults={
                    'current_step': instance.profile_step or 1,
                    'is_profile_completed': instance.is_profile_completed or False
                }
            )
        except Exception as e:
            logger.error(f'Error tracking profile steps: {str(e)}')
    else:
        # Update existing reminder
        try:
            from .models import ProfileStepReminder
            
            reminder, created = ProfileStepReminder.objects.get_or_create(
                user=instance.user,
                defaults={'current_step': instance.profile_step or 1}
            )
            
            if not created:
                reminder.update_step(instance.profile_step or 1)
                if instance.is_profile_completed:
                    reminder.is_profile_completed = True
                    reminder.save()
        except Exception as e:
            logger.error(f'Error updating profile steps: {str(e)}')