from django.contrib import admin

from .models import ChatState, Department, Message, News, Notification, Profile, SubTask, Subdepartment, Task


class SubdepartmentInline(admin.TabularInline):
    model = Subdepartment
    extra = 0
    fields = ("name", "slug", "emoji", "order")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    inlines = [SubdepartmentInline]


@admin.register(Subdepartment)
class SubdepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_birthdays", "order")
    list_filter = ("department",)
    readonly_fields = ("is_birthdays",)
    filter_horizontal = ("responsible",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("tg_nick", "full_name", "display_name", "birth_date", "role", "user")
    list_filter = ("role", "departments", "subdepartments")
    search_fields = ("tg_nick", "full_name", "display_name", "user__username")
    filter_horizontal = ("departments", "subdepartments")


class SubTaskInline(admin.TabularInline):
    model = SubTask
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "subdepartment", "deadline", "done")
    list_filter = ("done", "subdepartment")
    filter_horizontal = ("assignees",)
    inlines = [SubTaskInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "subdepartment", "author", "text")
    list_filter = ("subdepartment",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "title", "is_read")
    list_filter = ("kind", "is_read")


admin.site.register(ChatState)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "priority", "is_published", "delete_on", "created_at", "updated_at")
    list_filter = ("is_published", "created_at")
    search_fields = ("title", "content")
    list_editable = ("is_published",)
