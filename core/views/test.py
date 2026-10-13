# Agrega a core/views/test.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def test_middleware(request):
    from django.conf import settings
    return JsonResponse({
        'email_host': getattr(settings, 'EMAIL_HOST', None),
        'email_user': getattr(settings, 'EMAIL_HOST_USER', None),
        'session_age': getattr(settings, 'SESSION_COOKIE_AGE', None),
        'site_url': getattr(settings, 'SITE_URL', None),
    })