import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from .models import Profile, SubTask, Task, Subdepartment, normalize_nick

NICK_RE = re.compile(r"^[a-z0-9_]{3,32}$")
DATE_WIDGET = lambda: forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def clean_nick(value):
    nick = normalize_nick(value)
    if not NICK_RE.match(nick):
        raise ValidationError("Ник: 3–32 символа, латинские буквы, цифры и подчёркивание.")
    return nick


class LoginForm(AuthenticationForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["username"].label = "Логин"


class RegisterForm(forms.Form):
    username = forms.CharField(
        label="Отображаемое имя (логин)", max_length=30,
        help_text="Это ваш логин для входа. Отображаемое имя потом можно поменять в профиле.")
    tg_nick = forms.CharField(label="Telegram-ник", max_length=64, help_text="Укажите Telegram-ник, который уже внесён в базу организации.")
    email = forms.EmailField(label="Электронная почта")
    birth_date = forms.DateField(label="Дата рождения", required=False, widget=DATE_WIDGET())
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повтор пароля", widget=forms.PasswordInput)
    agree_terms = forms.BooleanField(label="Я принимаю пользовательское соглашение",
                                     error_messages={"required": "Для регистрации нужно принять пользовательское соглашение."})
    agree_personal_data = forms.BooleanField(label="Я даю согласие на обработку персональных данных",
                                              error_messages={"required": "Для создания аккаунта нужно согласие на обработку персональных данных."})

    def clean_username(self):
        name = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=name).exists():
            raise ValidationError("Такой логин уже занят.")
        return name

    def clean_tg_nick(self):
        nick = clean_nick(self.cleaned_data["tg_nick"])
        person = Profile.objects.filter(tg_nick=nick).first()
        if person is None:
            raise ValidationError("Этого Telegram-ника нет в базе участников. Попросите руководителя добавить вас.")
        if person.user_id:
            raise ValidationError("Человек с этим Telegram-ником уже создан и у него есть аккаунт. Войдите в него.")
        return nick

    def clean(self):
        cd = super().clean()
        p1, p2 = cd.get("password1"), cd.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Пароли не совпадают.")
            else:
                try:
                    validate_password(p1)
                except ValidationError as e:
                    self.add_error("password1", e)
        return cd

    @transaction.atomic
    def save(self):
        cd = self.cleaned_data
        user = User.objects.create_user(username=cd["username"], email=cd["email"], password=cd["password1"])
        # если админ заранее внёс человека в базу — обновляем его строку, а не создаём новую
        profile = Profile.objects.filter(tg_nick=cd["tg_nick"]).first() or Profile(tg_nick=cd["tg_nick"])
        profile.user = user
        # Preserve the existing person's card; the login is only an authentication credential.
        if not profile.display_name:
            profile.display_name = user.username
        profile.birth_date = profile.birth_date or cd["birth_date"]
        profile.personal_data_consent_at = timezone.now()
        profile.terms_accepted_at = timezone.now()
        profile.save()
        return user


class ProfileForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(label="Убрать аватар", required=False)

    class Meta:
        model = Profile
        fields = ["avatar", "display_name", "tg_nick", "full_name", "birth_date"]
        widgets = {"avatar": forms.FileInput(attrs={"accept": "image/*"}), "birth_date": DATE_WIDGET()}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["display_name"].required = True
        self.fields["tg_nick"].required = True
        self.fields["tg_nick"].help_text = "Без @. По нему вас находит администратор."
        self.fields["avatar"].help_text = f"JPG или PNG, не больше {settings.MAX_AVATAR_MB} МБ."

    def clean_tg_nick(self):
        nick = clean_nick(self.cleaned_data["tg_nick"])
        if Profile.objects.filter(tg_nick=nick).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Этот ник уже занят.")
        return nick

    def save(self, commit=True):
        p = super().save(commit=False)
        if self.cleaned_data.get("remove_avatar") and "avatar" not in self.files:
            p.avatar = ""
        if commit:
            p.save()
        return p


class TaskForm(forms.ModelForm):
    subtasks = forms.CharField(label="Подзадачи", required=False, widget=forms.Textarea(attrs={"rows": 4}),
                               help_text="По одной в строке. Можно оставить пустым.")

    class Meta:
        model = Task
        fields = ["title", "description", "deadline", "image", "assignees"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "deadline": DATE_WIDGET(),
            "image": forms.FileInput(attrs={"accept": "image/*"}),
            "assignees": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *a, sub, **kw):
        super().__init__(*a, **kw)
        from .services import person_name
        qs = sub.participants().select_related("profile").annotate(
            _assignee_rank=Case(
                When(is_superuser=True, then=Value(0)),
                When(profile__role__in=[Profile.ROLE_CHAIR, Profile.ROLE_CENTER_HEAD], then=Value(1)),
                When(profile__role=Profile.ROLE_HEAD, then=Value(2)),
                default=Value(3), output_field=IntegerField(),
            )
        ).order_by("_assignee_rank", "username")
        self.fields["assignees"].queryset = qs
        self.fields["assignees"].label_from_instance = person_name
        self.fields["assignees"].label = "Ответственные"

    def save_with_subtasks(self, sub, author):
        task = self.save(commit=False)
        task.subdepartment, task.created_by = sub, author
        task.save()
        self.save_m2m()
        lines = [l.strip() for l in self.cleaned_data["subtasks"].splitlines() if l.strip()]
        SubTask.objects.bulk_create([SubTask(task=task, text=l[:200], order=i) for i, l in enumerate(lines)])
        return task


class SubdepartmentForm(forms.ModelForm):
    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.department = department or (self.instance.department if self.instance.pk else None)
        self.fields["slug"].help_text = "Короткий адрес латиницей, например general-chat."
        self.fields["emoji"].help_text = "Небольшой значок, который будет виден в карточке подотдела."

    class Meta:
        model = Subdepartment
        fields = ["name", "slug", "emoji", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if name.casefold() == "дни рождения" and Subdepartment.objects.filter(name__iexact="Дни рождения").exclude(pk=self.instance.pk).exists():
            raise ValidationError("Подотдел «Дни рождения» уже создан. Его можно создать только один раз.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        department = self.department
        if department and Subdepartment.objects.filter(department=department, slug=slug).exclude(pk=self.instance.pk).exists():
            raise ValidationError("В этом отделе уже есть подотдел с таким адресом.")
        return slug
