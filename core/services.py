import re
from datetime import timedelta

from django.core.cache import cache
from django.contrib.auth.models import User
from django.db.models import Max, Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from .models import ChatState, Message, News, Notification, Profile, Subdepartment, Task, plural

MENTION_RE = re.compile(r"(?<!\w)@([\w\-]+)")
ALL_CHAT_RE = re.compile(r"(?<!\w)@все\s+в\s+чате(?!\w)", re.IGNORECASE)
ALL_DEPARTMENT_RE = re.compile(r"(?<!\w)@все\s+в\s+отделе(?!\w)", re.IGNORECASE)


def person_name(user):
    p = getattr(user, "profile", None)
    return (p.name if p else "") or user.username


def person_avatar(user):
    p = getattr(user, "profile", None)
    return p.avatar_url if p else static("core/img/default-avatar.svg")


def notify(user, kind, title, text="", url="", key=None):
    data = dict(kind=kind, title=title[:200], text=text[:300], url=url)
    if key:
        obj, created = Notification.objects.get_or_create(user=user, key=key, defaults=data)
        return obj if created else None
    return Notification.objects.create(user=user, **data)


def post_message(sub, author, text):
    """Сохраняет сообщение и рассылает уведомления об отметках."""
    msg = Message.objects.create(subdepartment=sub, author=author, text=text)
    all_chat = bool(ALL_CHAT_RE.search(text))
    all_department = bool(ALL_DEPARTMENT_RE.search(text))
    personal_text = ALL_CHAT_RE.sub("", text)
    personal_text = ALL_DEPARTMENT_RE.sub("", personal_text)
    words = {w.lower() for w in MENTION_RE.findall(personal_text)}
    if not words and not all_chat and not all_department:
        return msg
    if all_department:
        recipients = User.objects.filter(is_active=True).filter(
            Q(profile__departments=sub.department)
            | Q(profile__subdepartments__department=sub.department)
            | Q(profile__role__in=[Profile.ROLE_HEAD, Profile.ROLE_CHAIR, Profile.ROLE_CENTER_HEAD])
            | Q(is_superuser=True)
        ).values_list("pk", flat=True)
        recipient_ids = set(recipients)
        recipient_ids.update(sub.participants().values_list("pk", flat=True))
        users = User.objects.filter(pk__in=recipient_ids)
    else:
        users = sub.participants()
    states = {s.user_id: s for s in ChatState.objects.filter(subdepartment=sub)}
    who = person_name(author)
    for u in users.exclude(pk=author.pk).select_related("profile"):
        p = getattr(u, "profile", None)
        handles = {u.username.lower()}
        if p and p.tg_nick:
            handles.add(p.tg_nick)
        personal = bool(words & handles)
        muted = bool(states.get(u.pk) and states[u.pk].muted)
        mass_mention = all_department or all_chat
        # Личная отметка пробивает мут; массовые упоминания учитывают мут чата.
        if personal or (mass_mention and not muted):
            if personal:
                title = f"{who} отметил(а) вас: {sub.name}"
            elif all_department:
                title = f"{who} написал(а) всем в отделе: {sub.department.name}"
            else:
                title = f"{who} написал(а) всем в чате: {sub.name}"
            notify(u, "mention", title, text[:140], reverse("sub_chat", args=[sub.pk]))
    return msg


def mark_read(user, sub):
    last = sub.messages.aggregate(m=Max("id"))["m"] or 0
    ChatState.objects.update_or_create(user=user, subdepartment=sub, defaults={"last_read_id": last})


def run_reminders(today=None):
    """Дедлайны — за день; дни рождения — накануне и в сам день."""
    today = today or timezone.localdate()
    purge_expired_news(today)
    created = 0
    tomorrow = today + timedelta(days=1)

    for task in Task.objects.filter(deadline=tomorrow, done=False).select_related("subdepartment").prefetch_related("assignees"):
        for user in task.assignees.all():
            notice = notify(
                user, "deadline", f"Завтра дедлайн: {task.title}",
                f"Подотдел «{task.subdepartment.name}». Нужно выполнить задачу.",
                task.get_absolute_url(), key=f"deadline:{task.pk}:{task.deadline}:{user.pk}",
            )
            created += bool(notice)

    birthday_people = []
    for person in Profile.objects.exclude(birth_date=None).select_related("user"):
        birthday_on = person.next_birthday(today)
        if birthday_on in (today, tomorrow):
            birthday_people.append((person, birthday_on))

    birthday_subdepartments = Subdepartment.objects.filter(is_birthdays=True).select_related("department")
    for sub in birthday_subdepartments:
        recipients = Profile.objects.filter(user__isnull=False, user__is_active=True, user__is_superuser=False).exclude(
            role__in=[Profile.ROLE_CHAIR, Profile.ROLE_CENTER_HEAD]
        ).filter(
            Q(role=Profile.ROLE_FRESH, subdepartments=sub)
            | Q(role=Profile.ROLE_HEAD, departments=sub.department)
            | Q(role=Profile.ROLE_HEAD, pk__in=sub.responsible.values("pk"))
        ).select_related("user").distinct()

        for person, birthday_on in birthday_people:
            age = person.turns(birthday_on)
            is_tomorrow = birthday_on == tomorrow
            when = "Завтра" if is_tomorrow else "Сегодня"
            age_text = f"исполнится {age}" if is_tomorrow else f"исполняется {age}"
            for recipient in recipients:
                if recipient.user_id == person.user_id:
                    continue
                notice = notify(
                    recipient.user, "birthday", f"{when} день рождения у {person.handle}",
                    f"{age_text} {plural(age, 'год', 'года', 'лет')}. Не забудьте поздравить!",
                    reverse("sub_birthdays", args=[sub.pk]),
                    key=f"bday:{person.pk}:{birthday_on.isoformat()}:{sub.pk}:{recipient.pk}",
                )
                created += bool(notice)
    return created

def purge_expired_news(today=None):
    """Удаляет новости в дату удаления и связанные картинки."""
    today = today or timezone.localdate()
    expired = News.objects.filter(delete_on__lte=today).only("id", "image")
    deleted = 0
    for news in expired.iterator():
        news.delete()
        deleted += 1
    return deleted


def maybe_run_reminders():
    """Лёгкий «планировщик»: не чаще раза в 10 минут, когда кто-то открыт на сайте."""
    if cache.add("sozidai:reminders", 1, 600):
        run_reminders()
