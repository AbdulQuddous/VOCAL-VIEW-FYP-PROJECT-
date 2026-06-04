"""
Signals for sending emails
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Send welcome email when a new user registers
    """
    if created:
        try:
            subject = 'Welcome to Vocal View - AI Interview Coach'
            
            message = f"""
Hello {instance.username}!

Welcome to Vocal View - Your AI-Powered Interview Coach! 🎉

Thank you for joining us. We're excited to help you ace your next interview with our advanced AI technology.

What You Can Do:
✓ Practice unlimited mock interviews
✓ Get instant AI-powered feedback on your performance
✓ Track your progress over time
✓ Download detailed reports as PDF/JSON
✓ Analyze your speech, facial expressions, and content

Getting Started:
1. Log in to your dashboard: {settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'}/dashboard/
2. Click "Start New Interview"
3. Select your target job role
4. Answer the AI-generated questions
5. Receive comprehensive feedback instantly

Need Help?
If you have any questions or need assistance, feel free to reach out to our support team.

Best of luck with your interview preparation!

Best regards,
The Vocal View Team

---
This is an automated message. Please do not reply to this email.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=False,
            )
            
            logger.info(f"Welcome email sent to {instance.email}")
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {instance.email}: {str(e)}")