# Push-уведомления при закрытом сайте

> Это руководство описывает, как добавить Web Push в текущий Django-проект. Сам файл ничего не включает: сейчас сайт получает уведомления через опрос `/api/poll/`, пока страница открыта. В текущем `sw.js` есть обработчик клика по уведомлению, но нет обработчика события `push`.

## Что получится

После настройки браузер пользователя подпишется на push-уведомления. Django сохранит подписку и сможет отправлять сообщение через push-службу браузера. Она разбудит service worker даже после закрытия вкладки и передаст ему событие `push`; service worker покажет системное уведомление.

Закрытая вкладка или отсутствие открытой страницы сайта не мешают Web Push. Если полностью завершить браузер или устройство, фактическая доставка зависит от браузера, операционной системы и их настроек фоновой работы; сайт не может гарантировать показ уведомления при отключённых системных уведомлениях, режиме энергосбережения или отсутствии сети.

Поток выглядит так:

1. Пользователь входит в аккаунт и нажимает кнопку включения уведомлений.
2. Браузер запрашивает разрешение и создаёт `PushSubscription`.
3. Сайт сохраняет подписку в базе, связав её с аккаунтом и устройством.
4. Когда Django создаёт запись `Notification`, сервер отправляет push на каждую подписку пользователя.
5. Service worker принимает событие `push` и вызывает `showNotification()`.

## Требования

- Сайт должен работать по HTTPS. Исключение для разработки — `localhost`.
- Разрешение на уведомления запрашивайте только после нажатия пользователем кнопки.
- Service worker должен быть доступен с корневого пути сайта. В проекте уже есть маршрут `/sw.js`; его нужно дополнить обработчиком `push`.
- На устройстве и в браузере должны быть разрешены уведомления; режим «Не беспокоить» или системные настройки могут скрывать их.
- Чтобы получать уведомления, пока сайт не открыт, браузер и операционная система должны разрешать фоновую доставку и системные уведомления. Поведение при полном выходе из браузера различается между платформами.
- На iPhone и iPad сайт должен быть добавлен на экран «Домой»; Web Push поддерживается для веб-приложений на iOS/iPadOS 16.4 и новее.

## 1. Установите библиотеку и создайте VAPID-ключи

Добавьте `pywebpush` в `requirements.txt`, затем установите зависимости в виртуальное окружение:

```bash
python -m pip install pywebpush
```

Для production ключи создавайте на сервере и храните вне каталога сайта. Пример для расположения проекта `/srv/sozidai` и пользователя службы `www-data`:

```bash
sudo install -d -o www-data -g www-data -m 700 /etc/sozidai/push
sudo -u www-data sh -c 'cd /etc/sozidai/push && /srv/sozidai/.venv/bin/vapid --gen'
sudo -u www-data sh -c 'cd /etc/sozidai/push && /srv/sozidai/.venv/bin/vapid --applicationServerKey'
```

Команда `--gen` создаёт `private_key.pem` и `public_key.pem`. `--applicationServerKey` выводит публичный ключ для браузерного JavaScript. Сохраните этот вывод: он нужен для подписки браузера.

Добавьте в `/etc/sozidai.env`:

```dotenv
WEBPUSH_PRIVATE_KEY=/etc/sozidai/push/private_key.pem
WEBPUSH_PUBLIC_KEY=ВСТАВЬТЕ_ВЫВОД_vapid_--applicationServerKey
WEBPUSH_SUBJECT=mailto:molsoz@yandex.ru
```

Закрытый ключ нельзя отправлять в браузер, коммитить в Git или публиковать. В браузер передаётся только публичный ключ. Не меняйте пару ключей после подключения подписок без плана повторной подписки устройств.

В локальной разработке можно создать отдельную пару в локальном каталоге `.secrets/`, исключить его из Git и использовать публичный ключ для локального тестирования.

## 2. Добавьте модель подписки

Создайте модель, которая хранит подписку браузера и владельца. Подписок у одного пользователя может быть несколько — например, телефон и ноутбук.

Минимальные поля:

```python
class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=2048, unique=True)
    subscription = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

`subscription` — полный объект, возвращённый `PushSubscription.toJSON()`. В нём находятся `endpoint` и ключи `p256dh` и `auth`, нужные для шифрования push-сообщения. Данные подписки и `endpoint` следует считать секретными.

После изменения модели создайте миграцию **в разработке** и примените её:

```bash
python manage.py makemigrations core
python manage.py migrate
```

На хостинге загружайте созданный файл миграции и выполняйте только `python manage.py migrate`.

## 3. Добавьте API для подписки и отписки

Создайте два маршрута, доступных только вошедшему пользователю:

- `POST /api/push/subscribe/` — принимает JSON из `subscription.toJSON()`, проверяет наличие `endpoint`, сохраняет подписку за `request.user`; повторный запрос обновляет существующую запись.
- `POST /api/push/unsubscribe/` — принимает `endpoint` и удаляет только подписку текущего пользователя.

Оба маршрута должны проверять CSRF-токен. Не принимайте `user_id` из тела запроса как владельца подписки — владельцем должен быть только `request.user`. Удаляйте подписки, когда push-служба сообщает, что endpoint больше не существует (обычно ответ 404 или 410).

## 4. Подключите кнопку включения на сайте

В проекте уже есть кнопка `#notif-toggle` и функция `NOTIF.toggle()` в `core/static/core/js/app.js`. После согласия пользователя измените её поведение:

1. В обработчике клика запросите `Notification.requestPermission()`.
2. Если разрешение выдано, зарегистрируйте `/sw.js` и дождитесь `navigator.serviceWorker.ready`.
3. Получите существующую подписку через `registration.pushManager.getSubscription()` либо создайте её вызовом:

```javascript
registration.pushManager.subscribe({
  userVisibleOnly: true,
  applicationServerKey: urlBase64ToUint8Array(PUBLIC_VAPID_KEY),
});
```

4. Отправьте `subscription.toJSON()` на `/api/push/subscribe/` методом POST, с `credentials: "same-origin"`, `Content-Type: application/json` и CSRF-заголовком `X-CSRFToken`.
5. При отключении уведомлений удалите эту подписку на сервере и вызовите `subscription.unsubscribe()`.

`applicationServerKey` — публичный VAPID-ключ в формате Base64 URL-safe. Перед передачей в `subscribe()` его обычно преобразуют из Base64 URL-safe строки в `Uint8Array`. Запрос разрешения и `subscribe()` выполняйте в прямом обработчике нажатия: браузеры ограничивают запросы без действия пользователя.

Текущий флаг `localStorage` сам по себе не отключает push на сервере. Если пользователь выключил уведомления, удалите подписку или сохраните отдельный серверный признак отключения.

## 5. Дополните service worker

Маршрут `/sw.js` реализован функцией `service_worker()` в `core/views.py`. Добавьте туда обработчик `push`, сохранив существующий обработчик `notificationclick`:

```javascript
self.addEventListener("push", event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_) {
    data = { body: event.data ? event.data.text() : "" };
  }

  const target = new URL(data.url || "/notifications/", self.location.origin);
  const safeUrl = target.origin === self.location.origin
    ? target.pathname + target.search + target.hash
    : "/notifications/";

  event.waitUntil(self.registration.showNotification(data.title || "Созидай", {
    body: data.body || "У вас новое уведомление",
    icon: "/static/core/img/logo.jpg",
    badge: "/static/core/img/logo.jpg",
    tag: data.tag || "sozidai-notification",
    data: { url: safeUrl },
  }));
});
```

Показывайте уведомление через `event.waitUntil()`, чтобы браузер не остановил service worker до завершения операции. Текущий `notificationclick` уже открывает URL из `notification.data.url`; оставьте проверку, что открываемая ссылка относится к вашему домену.

## 6. Отправляйте push при создании записи Notification

Отправлять push нужно только после успешного сохранения `Notification`. В проекте общий помощник находится в `core/services.py` в функции `notify()`:

- если функция вернула `None`, запись с таким ключом уже была создана — push повторно не отправляйте;
- если функция вернула новый объект уведомления, отправьте payload на все `push_subscriptions` этого пользователя;
- используйте URL из `Notification.url`, чтобы клик открывал нужный чат, задачу или страницу уведомлений.

Пример вызова `pywebpush`:

```python
import json
from django.conf import settings
from pywebpush import WebPushException, webpush


def send_web_push(subscription, notification):
    payload = {
        "title": notification.title,
        "body": notification.text,
        "url": notification.url or "/notifications/",
        "tag": f"sozidai-{notification.pk}",
    }
    try:
        webpush(
            subscription_info=subscription.subscription,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.WEBPUSH_PRIVATE_KEY,
            vapid_claims={"sub": settings.WEBPUSH_SUBJECT},
            ttl=60 * 60 * 24,
        )
    except WebPushException as exc:
        # Для HTTP 404/410 удалите просроченную подписку.
        # Другие ошибки запишите в лог; не теряйте запись Notification.
        raise
```

Подключите приватный ключ и subject из переменных окружения в `sozidai/settings.py`. Не отправляйте персональные или конфиденциальные сведения в теле push: текст может показываться на заблокированном экране. Отправка по сети может замедлить запрос пользователя; для большого количества устройств вынесите доставку в очередь задач. Для текущего небольшого сайта можно сначала отправлять её после фиксации записи в базе и логировать ошибки, не откатывая само уведомление.

Так как задачи, упоминания и напоминания уже создают записи через `services.notify()`, подключение отправки в этой точке охватит их все. Команда `send_reminders` по-прежнему нужна: она создаёт уведомления о датах по расписанию, после чего те же подписки получают push.

## 7. Проверьте работу

1. Разверните сайт на HTTPS-домене и перезапустите Django после установки `pywebpush` и миграции.
2. Войдите в аккаунт в браузере, нажмите кнопку уведомлений и разрешите их.
3. Убедитесь, что API сохранил подписку для текущего пользователя.
4. Закройте вкладку сайта и отправьте тестовое уведомление этому аккаунту с сервера.
5. Проверьте, что системное уведомление появилось, а клик по нему открыл внутреннюю страницу сайта.
6. Повторите тест отдельно на телефоне. На iPhone/iPad сначала добавьте сайт на экран «Домой».
7. Проверьте отключение: после отписки новые уведомления на этом устройстве приходить не должны.

Если push не приходит, проверьте HTTPS, разрешение браузера, наличие подписки в базе, доступ сервера к внешним push-службам, HTTP-код ответа push-службы и логи Django. Рассылка из сервера возможна только пока хостинг доступен; расписание `send_reminders` и push-отправка решают разные задачи.

## Официальные материалы

- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [MDN: PushManager.subscribe()](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe)
- [pywebpush: README и примеры отправки](https://github.com/web-push-libs/pywebpush/blob/main/README.rst)
- [VAPID: генерация и applicationServerKey](https://github.com/web-push-libs/vapid/blob/main/python/README.rst)
- [Apple: Web Push в Safari и веб-приложениях](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
