from django.db import migrations


def keep_one_named_birthday_room(apps, schema_editor):
    Subdepartment = apps.get_model("core", "Subdepartment")
    alias = schema_editor.connection.alias
    rooms = Subdepartment.objects.using(alias).filter(name__iexact="Дни рождения").order_by("slug", "id")
    keep_id = rooms.filter(slug__iexact="birthdays").values_list("id", flat=True).first()
    if keep_id is None:
        keep_id = rooms.values_list("id", flat=True).first()
    Subdepartment.objects.using(alias).all().update(is_birthdays=False)
    if keep_id is not None:
        Subdepartment.objects.using(alias).filter(pk=keep_id).update(is_birthdays=True)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_profile_personal_data_consent_at_and_more"),
    ]

    operations = [
        migrations.RunPython(keep_one_named_birthday_room, migrations.RunPython.noop),
    ]
