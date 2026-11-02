import json
from datetime import timedelta
from functools import wraps
import secrets
import string

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.db.models import F, Max, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import ProfileForm, RegisterForm, SubdepartmentForm, TaskForm
from .news_forms import NewsForm
from .models import ChatState, Department, Message, News, Notification, Profile, SubTask, Subdepartment, Task


def sub_access(view):
    """Загружает подотдел и проверяет доступ: активист — только свои, руководство и админ — все."""
    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        prof = request.profile
        sub = get_object_or_404(prof.accessible_subdepartments().select_related("department"), pk=pk)
        return view(request, sub, *args, **kwargs)
    return login_required(wrapper)


def sub_ctx(request, sub, tab):
    return {"sub": sub, "tab": tab, "can_manage": request.profile.can_manage,
            "open_tasks": sub.tasks.filter(done=False).count()}


def body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


# ---------- страницы ----------
def home(request):
    deps = []
    if request.user.is_authenticated:
        prof = request.profile
        deps = list(prof.accessible_departments())
        for d in deps:
            d.n_subs = 0 if d.slug == "common" else prof.accessible_subdepartments(d).count()
    services.purge_expired_news()
    news_list = News.objects.filter(is_published=True).prefetch_related("images").filter(
        Q(delete_on__gt=timezone.localdate()) | Q(delete_on__isnull=True))
    news_list = news_list.order_by(*News._meta.ordering)
    return render(request, "core/home.html", {"departments": deps, "news_list": news_list})


def about(request):
    return render(request, "pages/about.html")


def results(request):
    return render(request, "pages/results.html")


def organization(request):
    if not request.user.is_authenticated:
        return render(request, "pages/organization_unavailable.html")
    return render(request, "pages/organization.html")


def documents(request):
    return render(request, "pages/documents.html")


def contacts(request):
    return render(request, "pages/contacts.html")


def privacy_policy(request):
    return render(request, "pages/privacy_policy.html")


def personal_data_agreement(request):
    return render(request, "pages/personal_data_agreement.html")


@login_required
def my_tasks(request):
    tasks = list(
        Task.objects.filter(assignees=request.user)
        .select_related("subdepartment__department")
        .order_by(F("deadline").asc(nulls_last=True), "done", "-created_at")
    )
    return render(request, "core/my_tasks.html", {
        "tasks": tasks,
        "open_count": sum(not task.done for task in tasks),
        "today": timezone.localdate(),
    })


def _require_news_manager(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.profile.sees_all:
        raise PermissionDenied("Публиковать новости может председатель или администратор.")
    return None


@login_required
def news_manage(request):
    denied = _require_news_manager(request)
    if denied:
        return denied
    services.purge_expired_news()
    return render(request, "core/news_manage.html", {"news_list": News.objects.all()})


def save_news_photos(item, request, uploaded):
    import json
    existing = {str(photo.pk): photo for photo in item.images.all()}
    raw_order = request.POST.get("photo_order")
    try:
        order = json.loads(raw_order) if raw_order is not None else None
        if not isinstance(order, list):
            order = None
    except (TypeError, ValueError):
        order = None
    if order is None:
        order = [f"id:{pk}" for pk in existing] + [f"new:{i}" for i in range(len(uploaded))]
    order = [str(token) for token in order]
    keep_ids = {token[3:] for token in order if token.startswith("id:") and token[3:] in existing}
    for pk, photo in existing.items():
        if pk not in keep_ids:
            photo.image.delete(save=False)
            photo.delete()
    for position, token in enumerate(order):
        if token.startswith("id:"):
            photo = existing.get(token[3:])
            if photo and token[3:] in keep_ids:
                photo.order = position
                photo.save(update_fields=["order"])
        elif token.startswith("new:"):
            try:
                photo = uploaded[int(token[4:])]
            except (ValueError, IndexError):
                continue
            item.images.create(image=photo, order=position)


@login_required
def news_create(request):
    denied = _require_news_manager(request)
    if denied:
        return denied
    form = NewsForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        save_news_photos(item, request, form.cleaned_data.get("images", []))
        messages.success(request, "Новость сохранена. Уведомления не отправлялись.")
        return redirect("news_manage")
    return render(request, "core/news_form.html", {"form": form, "page_title": "Создать новость"})


@login_required
def news_edit(request, pk):
    denied = _require_news_manager(request)
    if denied:
        return denied
    item = get_object_or_404(News, pk=pk)
    form = NewsForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        save_news_photos(item, request, form.cleaned_data.get("images", []))
        messages.success(request, "Изменения новости сохранены.")
        return redirect("news_manage")
    return render(request, "core/news_form.html", {"form": form, "page_title": "Редактировать новость", "news": item})


@login_required
@require_POST
def news_delete(request, pk):
    denied = _require_news_manager(request)
    if denied:
        return denied
    item = get_object_or_404(News, pk=pk)
    if item.image:
        item.image.delete(save=False)
    for photo in item.images.all():
        photo.image.delete(save=False)
    item.delete()
    messages.success(request, "Новость удалена.")
    return redirect("news_manage")


@login_required
@require_POST
def news_toggle_publish(request, pk):
    denied = _require_news_manager(request)
    if denied:
        return denied
    item = get_object_or_404(News, pk=pk)
    item.is_published = not item.is_published
    item.save(update_fields=["is_published", "updated_at"])
    status = "опубликована" if item.is_published else "снята с публикации"
    messages.success(request, f"Новость «{item.title}» {status}.")
    return redirect("news_manage")


def news_detail(request, pk):
    services.purge_expired_news()
    item = get_object_or_404(News.objects.filter(Q(delete_on__gt=timezone.localdate()) | Q(delete_on__isnull=True)), pk=pk, is_published=True)
    return render(request, "core/news_detail.html", {"news": item})


@login_required
def department(request, slug):
    prof = request.profile
    dep = get_object_or_404(prof.accessible_departments(), slug=slug)
    subs = list(prof.accessible_subdepartments(dep))
    states = {s.subdepartment_id: s for s in ChatState.objects.filter(user=request.user, subdepartment__in=subs)}
    for s in subs:
        st = states.get(s.pk)
        s.unread = Message.objects.filter(subdepartment=s, id__gt=st.last_read_id if st else 0).exclude(author=request.user).count()
        s.muted = bool(st and st.muted)
        s.my_open = Task.objects.filter(subdepartment=s, assignees=request.user, done=False).count()
    is_common = dep.slug == "common"
    return render(request, "core/department.html", {
        "dep": dep,
        "subs": [] if is_common else subs,
        "global_room": subs[0] if is_common and subs else None,
        "is_common": is_common,
        "can_manage_subdepartments": prof.can_manage,
    })


def _require_subdepartment_manager(request):
    if not request.profile.can_manage:
        raise PermissionDenied("Управлять подотделами могут руководители, председатель, руководитель Центра и администратор.")


@login_required
def department_subdepartments(request, slug):
    _require_subdepartment_manager(request)
    department = get_object_or_404(Department, slug=slug)
    return render(request, "core/subdepartment_manage.html", {
        "dep": department,
        "subdepartments": department.subdepartments.all(),
    })


@login_required
def subdepartment_create(request, slug):
    _require_subdepartment_manager(request)
    department = get_object_or_404(Department, slug=slug)
    form = SubdepartmentForm(request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        sub = form.save(commit=False)
        sub.department = department
        sub.save()
        messages.success(request, f"Подотдел «{sub.name}» создан. Для него сразу доступны задачи и чат.")
        return redirect("department_subdepartments", slug=slug)
    return render(request, "core/subdepartment_form.html", {"dep": department, "form": form, "page_title": "Новый подотдел"})


@login_required
def subdepartment_edit(request, pk):
    _require_subdepartment_manager(request)
    sub = get_object_or_404(Subdepartment, pk=pk)
    form = SubdepartmentForm(request.POST or None, instance=sub)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Подотдел сохранён.")
        return redirect("department_subdepartments", slug=sub.department.slug)
    return render(request, "core/subdepartment_form.html", {"dep": sub.department, "sub": sub, "form": form, "page_title": "Изменить подотдел"})


@login_required
def subdepartment_delete(request, pk):
    _require_subdepartment_manager(request)
    sub = get_object_or_404(Subdepartment.objects.select_related("department"), pk=pk)
    session_key = f"delete_subdepartment_{sub.pk}"
    if request.method == "GET":
        token = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        request.session[session_key] = token
        return render(request, "core/subdepartment_delete.html", {"sub": sub, "token": token})
    if request.method != "POST":
        return HttpResponse(status=405)
    expected = request.session.pop(session_key, "")
    if not expected or request.POST.get("confirmation", "").strip().upper() != expected:
        messages.error(request, "Код не совпал. Подотдел не удалён.")
        return redirect("subdepartment_delete", pk=sub.pk)
    department_slug = sub.department.slug
    sub.delete()
    messages.success(request, "Подотдел и связанные с ним чат и задачи удалены.")
    return redirect("department_subdepartments", slug=department_slug)


@sub_access
def sub_chat(request, sub):
    state = ChatState.for_user(request.user, sub)
    prof = request.profile
    members = []
    for u in sub.participants().select_related("profile").order_by("username"):
        p = getattr(u, "profile", None)
        full_name = (p.full_name or "").strip() if p else ""
        name_parts = full_name.split()
        if name_parts:
            label = name_parts[0]
            initials = [part.rstrip(".")[0].upper() + "." for part in name_parts[1:] if part.rstrip(".")]
            if initials:
                label += " " + "".join(initials)
        else:
            label = p.tg_nick if p and p.tg_nick else u.username
        members.append({"handle": p.tg_nick if p and p.tg_nick else u.username,
                        "name": label, "avatar": services.person_avatar(u)})
    cfg = {"members": members, "me": [h for h in {prof.tg_nick, request.user.username.lower()} if h],
           "myId": request.user.pk, "muted": state.muted, "label": state.mute_label}
    return render(request, "core/chat.html", {**sub_ctx(request, sub, "chat"), "cfg": cfg, "n_members": len(members)})


@sub_access
def chat_messages(request, sub):
    after = int(request.GET.get("after") or 0)
    qs = sub.messages.select_related("author__profile")
    msgs = list(qs.filter(id__gt=after)[:200]) if after else list(qs.order_by("-id")[:100])[::-1]
    if msgs:
        services.mark_read(request.user, sub)
    data = []
    for m in msgs:
        t = timezone.localtime(m.created_at)
        data.append({"id": m.id, "uid": m.author_id, "author": services.person_name(m.author),
                     "avatar": services.person_avatar(m.author), "text": m.text,
                     "time": t.strftime("%H:%M"), "day": t.strftime("%d.%m.%Y"),
                     "can_delete": request.profile.sees_all or m.author_id == request.user.pk})
    return JsonResponse({"messages": data})


@require_POST
@sub_access
def chat_delete(request, sub, mid):
    message = get_object_or_404(Message, pk=mid, subdepartment=sub)
    if not (request.profile.sees_all or message.author_id == request.user.pk):
        raise PermissionDenied("Вы можете удалить только своё сообщение.")
    message.delete()
    return JsonResponse({"ok": True})


@require_POST
@sub_access
def chat_send(request, sub):
    text = (body(request).get("text") or "").strip()[:2000]
    if not text:
        return JsonResponse({"error": "Пустое сообщение"}, status=400)
    services.post_message(sub, request.user, text)
    return JsonResponse({"ok": True})


@require_POST
@sub_access
def chat_mute(request, sub):
    """minutes: 0 — включить звук, -1 — навсегда, N — на N минут."""
    try:
        minutes = int(body(request).get("minutes", 0))
    except (TypeError, ValueError):
        minutes = 0
    state = ChatState.for_user(request.user, sub)
    state.muted_forever = minutes < 0
    state.muted_until = timezone.now() + timedelta(minutes=minutes) if minutes > 0 else None
    state.save()
    return JsonResponse({"muted": state.muted, "label": state.mute_label})


@sub_access
def sub_tasks(request, sub):
    mine = bool(request.GET.get("mine"))
    qs = sub.tasks.prefetch_related("subtasks", "assignees__profile")
    if mine:
        qs = qs.filter(assignees=request.user)
    tasks = list(qs.order_by("done", F("deadline").asc(nulls_last=True), "-created_at"))
    for t in tasks:
        t.can_tick = can_tick(request, t)
    return render(request, "core/tasks.html", {**sub_ctx(request, sub, "tasks"), "tasks": tasks, "mine": mine})


@sub_access
def task_new(request, sub):
    if not request.profile.can_manage:
        raise PermissionDenied
    form = TaskForm(request.POST or None, request.FILES or None, sub=sub)
    if request.method == "POST" and form.is_valid():
        task = form.save_with_subtasks(sub, request.user)
        for u in task.assignees.exclude(pk=request.user.pk):
            when = f" Дедлайн: {task.deadline:%d.%m.%Y}." if task.deadline else ""
            place = f"Отдел «{sub.department.name}»." if sub.department.slug == "common" else f"Подотдел «{sub.name}»."
            services.notify(u, "task", f"Вам назначена задача: {task.title}", f"{place}{when}",
                            task.get_absolute_url(), key=f"task:{task.pk}:{u.pk}")
        messages.success(request, "Задача создана.")
        return redirect("sub_tasks", pk=sub.pk)
    return render(request, "core/task_form.html", {**sub_ctx(request, sub, "tasks"), "form": form})


@sub_access
def sub_birthdays(request, sub):
    if not sub.is_birthdays:
        raise Http404
    today = timezone.localdate()
    rows = []
    for p in Profile.objects.exclude(birth_date=None):
        nxt = p.next_birthday(today)
        rows.append({"p": p, "date": p.birth_date, "days": (nxt - today).days, "turns": p.turns(nxt)})
    upcoming = sorted(rows, key=lambda r: r["days"])
    by_month = {}
    for r in sorted(rows, key=lambda r: (r["date"].month, r["date"].day)):
        by_month.setdefault(r["date"].month, []).append(r)
    ctx = {**sub_ctx(request, sub, "birthdays"), "next": upcoming[0] if upcoming else None, "total": len(rows),
           "by_month": list(by_month.values()), "responsible": sub.responsible.all()}
    return render(request, "core/birthdays.html", ctx)


# ---------- задачи (JSON) ----------
def can_tick(request, task):
    return request.profile.is_chair or task.assignees.filter(pk=request.user.pk).exists()


def _task_or_error(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not request.profile.accessible_subdepartments().filter(pk=task.subdepartment_id).exists() or not can_tick(request, task):
        return None
    return task


@require_POST
@login_required
def toggle_subtask(request, pk, sid):
    task = _task_or_error(request, pk)
    if not task:
        return JsonResponse({"error": "Отмечать подзадачи может только ответственный."}, status=403)
    sub = get_object_or_404(SubTask, pk=sid, task=task)
    sub.done = not sub.done
    sub.save(update_fields=["done"])
    subs = list(task.subtasks.all())
    task.done = bool(subs) and all(s.done for s in subs)
    task.save(update_fields=["done"])
    n_done = sum(1 for s in subs if s.done)
    return JsonResponse({"done": sub.done, "task_done": task.done, "sub_done": n_done, "sub_total": len(subs),
                         "percent": round(100 * n_done / len(subs))})


@require_POST
@login_required
def toggle_task(request, pk):
    task = _task_or_error(request, pk)
    if not task or task.subtasks.exists():
        return JsonResponse({"error": "Нельзя изменить эту задачу."}, status=403)
    task.done = not task.done
    task.save(update_fields=["done"])
    return JsonResponse({"done": task.done})


@require_POST
@login_required
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not request.profile.can_manage:
        raise PermissionDenied
    sub_id = task.subdepartment_id
    task.delete()
    messages.success(request, "Задача удалена.")
    return redirect("sub_tasks", pk=sub_id)


# ---------- уведомления ----------
@login_required
def notifications(request):
    return render(request, "core/notifications.html", {"items": request.user.notifications.all()[:100]})


@require_POST
@login_required
def notification_delete(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    return redirect("notifications")


@require_POST
@login_required
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")


@login_required
def notification_go(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect(n.url or "notifications")


@login_required
def poll(request):
    services.maybe_run_reminders()
    after = int(request.GET.get("after") or 0)
    qs = request.user.notifications
    items = [{"id": n.id, "title": n.title, "text": n.text, "url": reverse("notification_go", args=[n.pk])}
             for n in qs.filter(id__gt=after).order_by("id")[:10]]
    from .context_processors import bell_hue
    count = qs.filter(is_read=False).count()
    return JsonResponse({"count": count, "hue": bell_hue(count), "items": items,
                         "max_id": qs.aggregate(m=Max("id"))["m"] or 0})


# ---------- аккаунт ----------
def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Аккаунт успешно создан. Не забудьте включить уведомления: наведите курсор на аватар и нажмите на колокольчик.",
                         extra_tags="cta")
        return redirect("home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    pform, pwform = ProfileForm(instance=request.profile), PasswordChangeForm(request.user)
    if request.method == "POST":
        if request.POST.get("form") == "password":
            pwform = PasswordChangeForm(request.user, request.POST)
            if pwform.is_valid():
                update_session_auth_hash(request, pwform.save())
                messages.success(request, "Пароль изменён.")
                return redirect("profile")
        else:
            pform = ProfileForm(request.POST, request.FILES, instance=request.profile)
            if pform.is_valid():
                pform.save()
                messages.success(request, "Профиль сохранён.")
                return redirect("profile")
    return render(request, "accounts/profile.html", {"pform": pform, "pwform": pwform})


def service_worker(request):
    js = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then(list => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus(); } }
    return clients.openWindow(url);
  }));
});
"""
    return HttpResponse(js, content_type="application/javascript")
