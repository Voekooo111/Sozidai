from django.conf import settings
from django.db.models import Max

from .models import Notification


def bell_hue(n):
    """0 уведомлений — зелёный (140), 10 и больше — красный (0), между ними плавный градиент."""
    return round(140 * (1 - min(n, 10) / 10))


def site(request):
    ctx = {"SITE_NAME": settings.SITE_NAME, "MAX_AVATAR_MB": settings.MAX_AVATAR_MB,
           "MAX_TASK_IMAGE_MB": settings.MAX_TASK_IMAGE_MB}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        qs = Notification.objects.filter(user=user)
        n = qs.filter(is_read=False).count()
        ctx.update(
            me=getattr(request, "profile", None),
            unread_count=n,
            bell_hue=bell_hue(n),
            notif_max_id=qs.aggregate(m=Max("id"))["m"] or 0,
        )
    return ctx
