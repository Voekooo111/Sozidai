import calendar
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone


def normalize_nick(value):
    return (value or "").strip().lstrip("@").lower()


def plural(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 11 <= n % 100 <= 14:
        return few
    return many


def safe_date(year, month, day):
    if month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, month, day)


def _check_size(f, limit_mb):
    if f.size > limit_mb * 1024 * 1024:
        raise ValidationError(f"Файл слишком большой: максимум {limit_mb} МБ.")


def validate_avatar_size(f):
    _check_size(f, settings.MAX_AVATAR_MB)


def validate_task_image_size(f):
    _check_size(f, settings.MAX_TASK_IMAGE_MB)


def validate_news_image_size(f):
    _check_size(f, settings.MAX_NEWS_IMAGE_MB)


class Department(models.Model):
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Адрес (латиницей)", unique=True)
    description = models.CharField("Описание", max_length=255, blank=True)
    emoji = models.CharField("Иконка (эмодзи)", max_length=8, default="📁")
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name, verbose_name_plural = "отдел", "отделы"

    def __str__(self):
        return self.name


class Subdepartment(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="subdepartments", verbose_name="Отдел")
    name = models.CharField("Название", max_length=100)
    slug = models.SlugField("Адрес (латиницей)")
    description = models.CharField("Описание", max_length=255, blank=True)
    emoji = models.CharField("Иконка (эмодзи)", max_length=8, default="💬")
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    is_birthdays = models.BooleanField("Подотдел «Дни рождения»", default=False,
                                       help_text="Включает список дней рождения и поздравления ответственным")
    responsible = models.ManyToManyField("Profile", blank=True, related_name="responsible_for",
                                         verbose_name="Ответственные за подотдел")

    class Meta:
        ordering = ["order", "name"]
        unique_together = [("department", "slug")]
        verbose_name, verbose_name_plural = "подотдел", "подотделы"

    def __str__(self):
        return f"{self.department.name} / {self.name}"

    def clean(self):
        if self.name.strip().casefold() == "дни рождения" and Subdepartment.objects.filter(name__iexact="Дни рождения").exclude(pk=self.pk).exists():
            raise ValidationError({"name": "В организации может быть только один подотдел «Дни рождения»."})

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        birthday_room = self.name.strip().casefold() == "дни рождения"
        if birthday_room and Subdepartment.objects.filter(name__iexact="Дни рождения").exclude(pk=self.pk).exists():
            raise ValidationError("В организации может быть только один подотдел «Дни рождения».")
        self.is_birthdays = birthday_room
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("sub_start", args=[self.pk])

    def participants(self):
        """Все пользователи общей комнаты или участники доступного подотдела."""
        users = User.objects.filter(is_active=True)
        if self.department.slug == "common":
            return users
        participant_filter = Q(profile__subdepartments=self)
        if self.name == "Общий":
            participant_filter |= Q(profile__departments=self.department)
        return users.filter(
            participant_filter | Q(profile__role__in=[Profile.ROLE_HEAD, Profile.ROLE_CHAIR, Profile.ROLE_CENTER_HEAD]) | Q(is_superuser=True)
        ).distinct()


class Profile(models.Model):
    ROLE_FRESH, ROLE_HEAD, ROLE_CHAIR, ROLE_CENTER_HEAD = "fresh", "head", "chair", "center_head"
    ROLES = [(ROLE_FRESH, "Активист"), (ROLE_HEAD, "Руководитель"), (ROLE_CHAIR, "Председатель"), (ROLE_CENTER_HEAD, "Руководитель Центра")]

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="profile",
                                verbose_name="Аккаунт", help_text="Заполняется при регистрации человека")
    tg_nick = models.CharField("Telegram-ник", max_length=64, unique=True, null=True, blank=True,
                               help_text="Без @. По нему регистрация находит эту строку")
    display_name = models.CharField("Отображаемое имя", max_length=30, blank=True)
    full_name = models.CharField("ФИО", max_length=150, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    avatar = models.ImageField("Аватар", upload_to="avatars/", blank=True, validators=[validate_avatar_size])
    role = models.CharField("Роль", max_length=16, choices=ROLES, default=ROLE_FRESH)
    personal_data_consent_at = models.DateTimeField("Согласие на обработку ПД", null=True, blank=True)
    terms_accepted_at = models.DateTimeField("Принятие пользовательского соглашения", null=True, blank=True)
    departments = models.ManyToManyField(Department, blank=True, related_name="members", verbose_name="Отделы")
    subdepartments = models.ManyToManyField(Subdepartment, blank=True, related_name="members", verbose_name="Подотделы")

    class Meta:
        ordering = ["full_name", "tg_nick"]
        verbose_name, verbose_name_plural = "человек", "люди"

    def save(self, *args, **kwargs):
        self.tg_nick = normalize_nick(self.tg_nick) or None
        super().save(*args, **kwargs)

    def __str__(self):
        return " ".join(x for x in [self.handle, self.full_name] if x)

    @property
    def name(self):
        return self.display_name or (self.user.username if self.user_id else "") or self.full_name or self.tg_nick or "—"

    @property
    def handle(self):
        return f"@{self.tg_nick}" if self.tg_nick else self.name

    @property
    def avatar_url(self):
        return self.avatar.url if self.avatar else static("core/img/default-avatar.svg")

    # --- права ---
    @property
    def is_admin(self):
        return bool(self.user_id and self.user.is_superuser)

    @property
    def is_chair(self):
        return self.is_admin or self.role in [self.ROLE_CHAIR, self.ROLE_CENTER_HEAD]

    @property
    def sees_all(self):
        return self.is_chair or self.role == self.ROLE_HEAD

    @property
    def can_manage(self):  # создавать задачи и дедлайны
        return self.sees_all

    def accessible_departments(self):
        if self.sees_all:
            return Department.objects.all()
        return Department.objects.filter(Q(slug="common") | Q(members=self) | Q(subdepartments__members=self)).distinct()

    def accessible_subdepartments(self, department=None):
        qs = Subdepartment.objects.all() if self.sees_all else Subdepartment.objects.filter(
            Q(members=self) | Q(department__slug="common") | Q(name="Общий", department__members=self)
        ).distinct()
        return qs.filter(department=department) if department else qs

    # --- дни рождения ---
    def next_birthday(self, today=None):
        today = today or timezone.localdate()
        b = self.birth_date
        d = safe_date(today.year, b.month, b.day)
        return d if d >= today else safe_date(today.year + 1, b.month, b.day)

    def turns(self, on):
        return on.year - self.birth_date.year


class Notification(models.Model):
    KINDS = [("mention", "Отметка"), ("deadline", "Дедлайн"), ("birthday", "День рождения"), ("task", "Задача"), ("info", "Сообщение")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=KINDS, default="info")
    title = models.CharField(max_length=200)
    text = models.CharField(max_length=300, blank=True)
    url = models.CharField(max_length=300, blank=True)
    key = models.CharField(max_length=120, null=True, blank=True, help_text="Защита от повторных напоминаний")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="uniq_user_notification_key")]
        verbose_name, verbose_name_plural = "уведомление", "уведомления"

    def __str__(self):
        return f"{self.user}: {self.title}"


class Message(models.Model):
    subdepartment = models.ForeignKey(Subdepartment, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name, verbose_name_plural = "сообщение", "сообщения"

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


class ChatState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_states")
    subdepartment = models.ForeignKey(Subdepartment, on_delete=models.CASCADE, related_name="chat_states")
    muted_until = models.DateTimeField(null=True, blank=True)
    muted_forever = models.BooleanField(default=False)
    last_read_id = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("user", "subdepartment")]

    @classmethod
    def for_user(cls, user, sub):
        return cls.objects.get_or_create(user=user, subdepartment=sub)[0]

    @property
    def muted(self):
        return self.muted_forever or bool(self.muted_until and self.muted_until > timezone.now())

    @property
    def mute_label(self):
        if self.muted_forever:
            return "Без звука навсегда"
        if self.muted_until and self.muted_until > timezone.now():
            return "Без звука до " + timezone.localtime(self.muted_until).strftime("%d.%m %H:%M")
        return ""


class Task(models.Model):
    subdepartment = models.ForeignKey(Subdepartment, on_delete=models.CASCADE, related_name="tasks", verbose_name="Подотдел")
    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField("Фото", upload_to="tasks/", blank=True, validators=[validate_task_image_size])
    deadline = models.DateField("Дедлайн", null=True, blank=True)
    assignees = models.ManyToManyField(User, blank=True, related_name="tasks", verbose_name="Ответственные")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    done = models.BooleanField("Выполнена", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = "задача", "задачи"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("sub_tasks", args=[self.subdepartment_id]) + f"#task-{self.pk}"

    @property
    def sub_total(self):
        return len(self.subtasks.all())

    @property
    def sub_done(self):
        return sum(1 for s in self.subtasks.all() if s.done)

    @property
    def percent(self):
        return round(100 * self.sub_done / self.sub_total) if self.sub_total else 0

    @property
    def deadline_info(self):
        if not self.deadline:
            return None
        if self.done:
            return (f"Дедлайн {self.deadline:%d.%m}", "")
        d = (self.deadline - timezone.localdate()).days
        if d < 0:
            return (f"Просрочено на {-d} дн.", "late")
        if d == 0:
            return ("Дедлайн сегодня", "soon")
        if d == 1:
            return ("Дедлайн завтра", "soon")
        return (f"До {self.deadline:%d.%m} ({d} дн.)", "")


class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    text = models.CharField("Подзадача", max_length=200)
    done = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name, verbose_name_plural = "подзадача", "подзадачи"

    def __str__(self):
        return self.text


class News(models.Model):
    PRIORITY_LOW = 1
    PRIORITY_NORMAL = 2
    PRIORITY_HIGH = 3
    PRIORITIES = [(PRIORITY_LOW, "Низкий"), (PRIORITY_NORMAL, "Обычный"), (PRIORITY_HIGH, "Высокий")]

    title = models.CharField("Заголовок", max_length=200)
    content = models.TextField("Текст новости")
    image = models.ImageField("Картинка", upload_to="news/", blank=True, validators=[validate_news_image_size])
    priority = models.PositiveSmallIntegerField("Приоритет", choices=PRIORITIES, default=PRIORITY_NORMAL)
    delete_on = models.DateField("Дата удаления", null=True, blank=True,
                                 help_text="Новость будет удалена в начале указанной даты.")
    is_published = models.BooleanField("Опубликована", default=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at", "-pk"]
        verbose_name = "новость"
        verbose_name_plural = "новости"

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        image_name = self.image.name if self.image else None
        result = super().delete(*args, **kwargs)
        if image_name:
            self.image.storage.delete(image_name)
        return result


class NewsImage(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Фото", upload_to="news/", validators=[validate_news_image_size])
    order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "фотография новости"
        verbose_name_plural = "фотографии новости"
