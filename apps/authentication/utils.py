from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_otp_email(email, otp):
    subject = 'WorkFina - Email Verification Code'
    
    # Log OTP for debugging
    print(f'[OTP DEBUG] Sending OTP {otp} to {email}')
    
    # HTML template render
    html_message = render_to_string('auth/otp_email.html', {
        'otp': otp,
        'email': email
    })
    
    # Plain text version
    plain_message = strip_tags(html_message)
    
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=False
    )
    
    print(f'[OTP DEBUG] OTP successfully sent to {email}')