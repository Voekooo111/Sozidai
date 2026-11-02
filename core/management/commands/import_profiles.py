import csv
import io
from datetime import datetime

from django.core.management.base import BaseCommand

from core.models import Profile, Subdepartment, normalize_nick

ROLES = {"chair": "chair", "председатель": "chair", "head": "head", "руководитель": "head", "руководитель центра": "center_head", "директор": "center_head", "fresh": "fresh", "активист": "fresh", "фрешик": "fresh"}


def parse_date(s):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


class Command(BaseCommand):
    help = ("Импорт базы людей из CSV. Колонки: tg_nick, full_name, birth_date (дд.мм.гггг), role, "
            "subdepartments (адреса или названия через |)")

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, path, **opts):
        raw = open(path, "rb").read()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Excel on Windows may save CSV in the local Windows-1251 encoding.
            content = raw.decode("cp1251")
        f = io.StringIO(content, newline="")
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except csv.Error:
            dialect = csv.excel
        n = 0
        for row in csv.DictReader(f, dialect=dialect):
            nick = normalize_nick(row.get("tg_nick"))
            if not nick:
                continue
            p, _ = Profile.objects.get_or_create(tg_nick=nick)
            p.full_name = (row.get("full_name") or p.full_name).strip()
            p.birth_date = parse_date(row.get("birth_date") or "") or p.birth_date
            p.role = ROLES.get((row.get("role") or "").strip().lower(), p.role)
            p.save()
            for token in filter(None, (t.strip() for t in (row.get("subdepartments") or "").split("|"))):
                sd = (Subdepartment.objects.filter(slug__iexact=token) | Subdepartment.objects.filter(name__iexact=token)).first()
                if sd:
                    p.subdepartments.add(sd)
                    p.departments.add(sd.department)
                else:
                    self.stderr.write(f"{nick}: подотдел «{token}» не найден")
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Обработано людей: {n}"))
