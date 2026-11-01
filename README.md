# Sozidai

Закрытый сайт отдела «Внутреннее развитие»: отделы и подотделы, чаты с отметками и мутом, задачи с подзадачами и дедлайнами, дни рождения, уведомления.

## Запуск

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py createsuperuser
python manage.py runserver
```

Если PowerShell запрещает активацию окружения, можно запускать Python напрямую: `.\.venv\Scripts\python.exe manage.py runserver`.

### Linux / Raspberry Pi

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Сайт: http://127.0.0.1:8000, админка: http://127.0.0.1:8000/admin. Миграции уже находятся в `core/migrations`; при обычном запуске выполняйте `migrate`. `makemigrations` нужен только после изменения моделей в коде. Если у вас уже есть рабочая база данных, не удаляйте `db.sqlite3`.

## База людей (делает админ)

В админке откройте **Люди** и добавьте строки: Telegram-ник, ФИО, дата рождения, роль, отделы и подотделы.
Когда человек регистрируется с тем же ником, строка **обновляется** (ФИО и доступы уже на месте), новая не создаётся.
Массовый импорт из CSV (колонки `tg_nick, full_name, birth_date, role, subdepartments`; подотделы через `|`):

```bash
python manage.py import_profiles people.csv
```

Ответственных за подотдел (например, за «Дни рождения») выбирайте в админке: **Подотделы → Ответственные**.
Новый отдел: **Отделы → Добавить** (подотделы можно добавить там же).

## Роли

| Роль | Что может |
|---|---|
| Админ (суперпользователь) | всё, включая админку |
| Председатель | видит и может всё: создаёт задачи и дедлайны, отмечает чужие подзадачи |
| Руководитель | видит всё, создаёт задачи и дедлайны |
| Активист | видит только свои отделы и подотделы |

Права собраны в `Profile` (`sees_all`, `can_manage`, `is_chair`) в `core/models.py`.

## Как добавить отдел через код

Откройте `core/management/commands/seed.py` и добавьте словарь в список `DEPARTMENTS`. Укажите уникальный латинский `slug`, название, эмодзи, описание и список подотделов. Подотдел задаётся кортежем `(slug, название, эмодзи, описание, is_birthdays)`, например:

```python
{
    "slug": "volunteers",
    "name": "Волонтёры",
    "emoji": "🙌",
    "description": "Работа волонтёрской команды",
    "subdepartments": [
        ("general", "Общий чат", "💬", "Общие вопросы", False),
    ],
},
```

Затем выполните `python manage.py seed`: команда создаст или обновит перечисленные отделы и подотделы, не удаляя остальные. Свежим пользователям откройте доступ к отделу или подотделам через поля доступа в профиле.

## Напоминания и уведомления

Команда `python manage.py send_reminders` один раз запускает фоновую проверку. Она:

- создаёт уведомления ответственным за задачи, срок которых наступит завтра;
- создаёт поздравления за день до дня рождения и в сам день: активистам подотдела «Дни рождения» и руководителю отдела, назначенному в отделе или ответственным за подотдел; председатель и сам именинник исключены;
- удаляет новости, срок хранения которых истёк.

Команда не запускает сайт и не отправляет сама по себе push в закрытый браузер. В локальной разработке проверка также вызывается автоматически, пока сайт открыт и браузер обращается к нему. Всплывающие уведомления проверяются примерно раз в 15 секунд, пока сайт открыт (в том числе в фоновой вкладке) и у браузера есть разрешение.

Колокольчик сохраняет уведомления в базе. При полностью закрытом сайте cron может создать запись, но системное всплывающее уведомление браузер не получит, пока сайт снова не откроют. Для push при закрытом сайте потребуется отдельно внедрить Web Push: HTTPS, VAPID-ключи, хранение подписок устройств и отправку push-сообщений.

На хостинге добавьте запуск команды по расписанию, например раз в час:

```cron
0 * * * * cd /srv/sozidai && /srv/sozidai/.venv/bin/python manage.py send_reminders >> /srv/sozidai/reminders.log 2>&1
```

На хостинге, где нет доступа к cron, используйте встроенный планировщик фоновых задач и задайте ту же команду с путём к Python из виртуального окружения.

## Размещение на хостинге: Ubuntu VPS

Ниже пример для собственного VPS с Ubuntu, доменом и SSH-доступом. В примере проект находится в `/srv/sozidai`, домен — `example.ru`. Замените их на свои значения. На обычном хостинге с панелью управления вместо настройки Nginx и systemd используйте соответствующие поля панели.

### 1. Подготовьте сервер и загрузите проект

Направьте DNS-записи домена на IP сервера. Подключитесь по SSH, установите системные пакеты и создайте каталог проекта:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
sudo mkdir -p /srv/sozidai
```

Загрузите файлы проекта в `/srv/sozidai` через Git или SFTP. Не загружайте локальную папку `.venv`; виртуальное окружение создаётся заново на сервере.

```bash
sudo chown -R www-data:www-data /srv/sozidai
cd /srv/sozidai
sudo -u www-data python3 -m venv .venv
sudo -u www-data .venv/bin/python -m pip install --upgrade pip
sudo -u www-data .venv/bin/python -m pip install -r requirements.txt
sudo -u www-data .venv/bin/python -m pip install gunicorn
```

### 2. Настройте домен и секретный ключ

Создайте случайный секретный ключ и сохраните его значение:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
sudo nano /etc/sozidai.env
```

В `/etc/sozidai.env` укажите домен и ключ. Впишите вместо `ВСТАВЬТЕ_СГЕНЕРИРОВАННЫЙ_КЛЮЧ` результат предыдущей команды:

```dotenv
DJANGO_SECRET_KEY=ВСТАВЬТЕ_СГЕНЕРИРОВАННЫЙ_КЛЮЧ
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=example.ru,www.example.ru
DJANGO_CSRF_ORIGINS=https://example.ru,https://www.example.ru
```

Сохраните файл и ограничьте доступ к нему:

```bash
sudo chown root:www-data /etc/sozidai.env
sudo chmod 640 /etc/sozidai.env
```

### 3. Подготовьте базу данных и файлы сайта

```bash
cd /srv/sozidai
sudo -u www-data .venv/bin/python manage.py migrate
sudo -u www-data .venv/bin/python manage.py seed
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
sudo -u www-data bash -c 'set -a; . /etc/sozidai.env; set +a; cd /srv/sozidai; .venv/bin/python manage.py check --deploy'
sudo -u www-data .venv/bin/python manage.py createsuperuser
```

`createsuperuser` запускайте только при первой установке, если администратор ещё не создан. При переносе существующего сайта скопируйте его базу `db.sqlite3` и папку `media/` на сервер до запуска миграций. Не удаляйте и не заменяйте рабочую базу пустой.

Проект сейчас использует SQLite. Размещайте `db.sqlite3` на постоянном диске сервера и регулярно делайте резервные копии базы и `media/`. Для платформы, которая удаляет файлы при перезапуске, или для нескольких серверных процессов настройте PostgreSQL до запуска сайта.

### 4. Запустите Django через Gunicorn и systemd

Создайте службу:

```bash
sudo nano /etc/systemd/system/sozidai.service
```

Вставьте конфигурацию:

```ini
[Unit]
Description=Sozidai Django site
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/sozidai
EnvironmentFile=/etc/sozidai.env
ExecStart=/srv/sozidai/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 sozidai.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустите службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sozidai
sudo systemctl status sozidai
```

### 5. Настройте Nginx

```bash
sudo nano /etc/nginx/sites-available/sozidai
```

Вставьте конфигурацию, заменив домен на свой:

```nginx
server {
    listen 80;
    server_name example.ru www.example.ru;

    location /static/ {
        alias /srv/sozidai/staticfiles/;
    }

    location /media/ {
        alias /srv/sozidai/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт и проверьте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/sozidai /etc/nginx/sites-enabled/sozidai
sudo nginx -t
sudo systemctl reload nginx
```

После того как DNS домена указывает на сервер, подключите HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.ru -d www.example.ru
```

### 6. Включите напоминания по расписанию

Добавьте cron для пользователя `www-data`:

```bash
sudo crontab -u www-data -e
```

Добавьте строку и сохраните файл:

```cron
0 * * * * cd /srv/sozidai && /srv/sozidai/.venv/bin/python manage.py send_reminders >> /srv/sozidai/reminders.log 2>&1
```

Проверьте журнал команды:

```bash
tail -n 50 /srv/sozidai/reminders.log
```

### 7. Обновление сайта после изменений

После загрузки нового кода выполните:

```bash
cd /srv/sozidai
sudo -u www-data .venv/bin/python -m pip install -r requirements.txt
sudo -u www-data .venv/bin/python manage.py migrate
sudo -u www-data .venv/bin/python manage.py seed
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart sozidai
```

`seed` запускайте, если менялся список отделов или подотделов в `core/management/commands/seed.py`. Если менялись модели, сначала создайте миграцию в разработке командой `python manage.py makemigrations core`, загрузите файл миграции на сервер и выполните там `python manage.py migrate`.

## Перед публикацией

Задайте `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` и `DJANGO_CSRF_ORIGINS`, включите HTTPS, раздавайте `staticfiles/` и `media/` через Nginx и настройте резервные копии базы и загруженных файлов.
Текст соглашения: `templates/agreement.html`. Название сайта и лимиты файлов: `sozidai/settings.py`.


## Новости

- После входа опубликованные новости показываются карточками выше списка отделов; сортировка — сначала по приоритету, затем по дате создания.
- Создание и редактирование доступны председателю и администратору: `/news/manage/`.
- В форме новости можно приложить картинку, выбрать приоритет и указать дату удаления. Картинки до 5 МБ хранятся в `media/news/`.
- Черновики не видны пользователям. Команда `send_reminders` удаляет просроченные новости и картинки; настройте её запуск по расписанию на хостинге, как указано выше.
- Новости не создают записи в `Notification` и не отправляются через Web Push.
- Также новости можно создавать в Django Admin в разделе «Новости».

При обычном обновлении кода применяйте существующие миграции командой `python manage.py migrate`, затем собирайте статику и перезапускайте службу по шагам выше. `makemigrations` выполняйте в разработке только после изменения моделей. Если в старой базе уже есть данные, не удаляйте и не заменяйте `db.sqlite3`.
"# Sozidai" 
