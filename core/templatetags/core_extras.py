from django import template
from django.templatetags.static import static

register = template.Library()


@register.filter
def pname(user):
    p = getattr(user, "profile", None)
    return (p.name if p else "") or getattr(user, "username", "")


@register.filter
def pavatar(user):
    p = getattr(user, "profile", None)
    return p.avatar_url if p else static("core/img/default-avatar.svg")
