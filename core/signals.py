from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "Unknown")


@receiver(user_logged_in)
def send_login_alert_email(sender, request, user, **kwargs):
    if not getattr(settings, "SEND_LOGIN_EMAILS", True):
        return

    email = getattr(user, "email", None)
    if not email:
        return

    # Resolve display name: full name > username > email
    full_name = ""
    if hasattr(user, "get_full_name"):
        full_name = user.get_full_name().strip()
    display_name = full_name or getattr(user, "username", "") or email

    login_time = timezone.localtime().strftime("%d %b %Y, %I:%M %p %Z")
    ip_address = _get_client_ip(request)

    subject = "Login Alert"
    message = (
        f"Hello {display_name},\n\n"
        "You have successfully logged in to FindMyParking.\n\n"
        f"  Login time : {login_time}\n"
        f"  IP address : {ip_address}\n\n"
        "If this was not you, please secure your account immediately by "
        "changing your password.\n\n"
        "— The FindMyParking Team"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,  # never block login if SMTP fails
    )
