from .models import Profile


class ProfileMiddleware:
    """Гарантирует, что у вошедшего пользователя есть Profile (например, у суперпользователя)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.profile = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            request.profile, _ = Profile.objects.get_or_create(user=user, defaults={"display_name": user.username[:30]})
        return self.get_response(request)
