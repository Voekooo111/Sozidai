from django.core.management.base import BaseCommand

from core.models import Department, Subdepartment

DEPARTMENTS = [
    {
        "slug": "common",
        "name": "Общий",
        "emoji": "🌐",
        "description": "Общие задачи и чат для всех участников",
        "subdepartments": [
            ("all-members", "Общий", "🌐", "Задачи и чат для всех участников", False),
        ],
    },
    {
        "slug": "directorate",
        "name": "Дирекция студенческой организации",
        "emoji": "🏛️",
        "description": "",
        "subdepartments": [
            ("directorate-general", "Общий", "💬", "Общий чат и задачи дирекции", False),
        ],
    },
    {
        "slug": "leaders-council",
        "name": "Совет руководителей",
        "emoji": "🤝",
        "description": "",
        "subdepartments": [
            ("leaders-council-general", "Общий", "💬", "Общий чат и задачи Совета руководителей", False),
        ],
    },
    {
        "slug": "project-commission",
        "name": "Проектная комиссия",
        "emoji": "📋",
        "description": "",
        "subdepartments": [
            ("project-commission-general", "Общий", "💬", "Общий чат и задачи Проектной комиссии", False),
        ],
    },
    {
        "slug": "scientific-support",
        "name": "Отдел научного сопровождения",
        "emoji": "🔬",
        "description": "",
        "subdepartments": [
            ("scientific-support-general", "Общий", "💬", "Общий чат и задачи отдела", False),
        ],
    },
    {
        "slug": "quality-management",
        "name": "Отдел системы менеджмента качества",
        "emoji": "✅",
        "description": "",
        "subdepartments": [
            ("quality-management-general", "Общий", "💬", "Общий чат и задачи отдела", False),
        ],
    },
    {
        "slug": "internal-documentation",
        "name": "Отдел внутреннего делопроизводства",
        "emoji": "🗂️",
        "description": "",
        "subdepartments": [
            ("internal-documentation-general", "Общий", "💬", "Общий чат и задачи отдела", False),
        ],
    },
    {
        "slug": "promotion-information",
        "name": "Отдел продвижения и информации",
        "emoji": "📣",
        "description": "",
        "subdepartments": [
            ("promotion-information-general", "Общий", "💬", "Общий чат и задачи отдела", False),
        ],
    },
    {
        "slug": "external-relations",
        "name": "Отдел внешних связей",
        "emoji": "🌐",
        "description": "",
        "subdepartments": [
            ("external-relations-general", "Общий", "💬", "Общий чат и задачи отдела", False),
        ],
    },
    {
        "slug": "internal",
        "name": "Внутреннее развитие",
        "emoji": "🌱",
        "description": "Мероприятия, адаптация и развитие участников",
        "subdepartments": [
            ("general", "Общий", "💬", "Общие вопросы и новости отдела", False),
            ("birthdays", "Дни рождения", "🎂", "Список именинников и поздравления", True),
            ("excursions", "Экскурсии", "🚌", "Выезды и экскурсии", False),
            ("teambuilding", "Тимбилдинги", "🤝", "Командные мероприятия", False),
            ("onboarding", "Онбординг", "🚀", "Встреча и адаптация новичков", False),
            ("masterclasses", "Мастер-классы", "🎓", "Обучающие встречи", False),
            ("curiosities", "Интересности", "✨", "Находки и идеи для отдела", False),
            ("internships", "Стажировки", "🧭", "Стажировки и практики", False),
            ("mentors", "Наставники", "🧑‍🏫", "Наставники и подопечные", False),
            ("activists", "Отбор активистов", "🏅", "Отбор и работа с активистами", False),
        ],
    },
    {
        "slug": "advisors",
        "name": "Группа советников",
        "emoji": "💡",
        "description": "",
        "subdepartments": [
            ("advisors-general", "Общий", "💬", "Общий чат и задачи Группы советников", False),
        ],
    },
]


class Command(BaseCommand):
    help = "Создаёт и обновляет отделы и подотделы, перечисленные в DEPARTMENTS"

    def handle(self, *args, **opts):
        total_subs = 0
        for order, item in enumerate(DEPARTMENTS):
            dep, _ = Department.objects.update_or_create(
                slug=item["slug"],
                defaults={"name": item["name"], "emoji": item["emoji"], "order": order,
                          "description": item["description"]},
            )
            for sub_order, (slug, name, emoji, desc, is_birthdays) in enumerate(item["subdepartments"]):
                Subdepartment.objects.update_or_create(
                    department=dep, slug=slug,
                    defaults={"name": name, "emoji": emoji, "description": desc, "order": sub_order,
                              "is_birthdays": is_birthdays},
                )
                total_subs += 1
        self.stdout.write(self.style.SUCCESS(f"Готово: отделов: {len(DEPARTMENTS)}, подотделов: {total_subs}"))
