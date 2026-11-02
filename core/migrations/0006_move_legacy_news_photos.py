from django.db import migrations

def move_legacy(apps, schema_editor):
    News = apps.get_model("core", "News")
    NewsImage = apps.get_model("core", "NewsImage")
    db = schema_editor.connection.alias
    for news in News.objects.using(db).exclude(image="").iterator():
        if not NewsImage.objects.using(db).filter(news_id=news.pk).exists():
            NewsImage.objects.using(db).create(news_id=news.pk, image=news.image.name, order=0)
        news.image = ""
        news.save(using=db, update_fields=["image"])

class Migration(migrations.Migration):
    dependencies = [("core", "0005_newsimage")]
    operations = [migrations.RunPython(move_legacy, migrations.RunPython.noop)]
