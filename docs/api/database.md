# 🚲 База данных: Bikes

> **Единая БД:** `boontar_market`.
> Бот использует один async engine из `app/db/base.py` через
> `settings.database_url_market`.
>
> **Источник правды для Python-части:** модели в `app/db/models/`.
> DDL/миграции живут вне этого репозитория в Laravel-проекте market; локальный
> SQL-кусок для `store_ids` лежит в `docs/sql/add_supervisor_store_ids.sql`.

---

## Общая схема

```
boontar_market
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

boom_stores ───────────────┐
                           ├──► boom_bikes
boom_admin_users ──────────┤       │
                           │       ├──► boom_bike_usage_logs
                           │       ├──► boom_bike_breakdowns
                           │       │       └──► boom_bike_breakdown_photos
                           │       ├──► boom_bike_repairs
                           │       └──► boom_bike_alerts
                           │
boom_bike_bot_roles ───────┤
       │                   │
       └──► boom_bike_bot_role_admin_notifications

boom_shift_couriers ───────────► boom_shift_couriers_bike

boom_link_couriers_orders
boom_order_details
boom_orders_status_changes      читаются только для SLA по завершенной смене
boom_delivery_details
```

---

## Правила хранения времени

- В таблицах Bikes используются naive `DateTime` значения из `datetime.now()` или
  `func.now()`.
- Для показа пользователю время переводится в Якутск через `app/core/tz.py`:
  `now_display()` и `to_yakutsk()`.
- В документации ниже `created_at` / `updated_at` означает `DateTime` с
  `server_default=func.now()`, а `updated_at` дополнительно обновляется через
  `onupdate=func.now()`.

---

## Таблицы, которыми управляет Bikes-бот

### 1. `boom_bikes` — реестр байков

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `bike_number` | `String(50)`, unique | Номер байка |
| `model` | `String(255)` | Модель |
| `commissioned_at` | `Date` | Дата ввода в парк |
| `store_id` | `BigInteger` FK → `boom_stores.id` | Склад |
| `status` | enum | Текущий статус |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

**Статусы:**

| Значение | Описание |
|----------|----------|
| `online` | Байк доступен на линии |
| `inspection` | Байк на проверке после поломки |
| `repair` | Байк в ремонте |
| `decommissioned` | Байк списан |

Основные переходы:

- добавление байка создает статус `online`;
- фиксация поломки переводит `online` → `inspection`;
- забор в ремонт переводит байк в `repair`;
- завершение ремонта переводит `repair` → `online`;
- списание переводит байк в `decommissioned`.

---

### 2. `boom_bike_usage_logs` — лог использования байков

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `bike_id` | `BigInteger` FK → `boom_bikes.id`, `ON DELETE CASCADE` | Байк |
| `courier_id` | `BigInteger` FK → `boom_admin_users.id` | Курьер |
| `store_id` | `BigInteger` FK → `boom_stores.id` | Склад |
| `started_at` | `DateTime` | Начало использования |
| `ended_at` | `DateTime`, nullable | Конец использования; `NULL` = активная запись |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

Особенности:

- активная запись определяется как `ended_at IS NULL`;
- `app/bot/handlers/auto_close.py` закрывает записи старше 12 часов;
- последний `usage_log` используется для автоподстановки курьера при создании
  поломки.

---

### 3. `boom_bike_breakdowns` — карточки поломок

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `bike_id` | `BigInteger` FK → `boom_bikes.id`, `ON DELETE CASCADE` | Сломанный байк |
| `courier_id` | `BigInteger` FK → `boom_admin_users.id` | Курьер, связанный с поломкой |
| `store_id` | `BigInteger` FK → `boom_stores.id` | Склад |
| `reported_by` | `BigInteger` FK → `boom_admin_users.id` | Автор фиксации / ответственный сотрудник |
| `breakdown_type` | enum | Тип поломки |
| `description` | `Text`, nullable | Описание |
| `reported_at` | `DateTime` | Когда поломка зафиксирована |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

**Типы поломок:** `brakes`, `wheel`, `battery`, `motor`, `frame`,
`electronics`, `other`.

---

### 4. `boom_bike_breakdown_photos` — фото поломок

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `breakdown_id` | `BigInteger` FK → `boom_bike_breakdowns.id`, `ON DELETE CASCADE` | Поломка |
| `photo_url` | `String(500)` | Сейчас хранится Telegram `file_id` / URL-совместимая строка |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

---

### 5. `boom_bike_repairs` — ремонты

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `bike_id` | `BigInteger` FK → `boom_bikes.id`, `ON DELETE CASCADE` | Байк |
| `breakdown_id` | `BigInteger` FK → `boom_bike_breakdowns.id`, nullable, `ON DELETE SET NULL` | Связанная поломка |
| `mechanic_id` | `BigInteger`, nullable | Логическая ссылка на `boom_bike_bot_roles.id`; FK в модели нет |
| `mechanic_name` | `String(255)`, nullable | Денормализованное имя мастера |
| `store_id` | `BigInteger` FK → `boom_stores.id` | Склад |
| `picked_up_at` | `DateTime` | Когда мастер забрал байк |
| `completed_at` | `DateTime`, nullable | Когда ремонт завершен; `NULL` = в работе |
| `work_description` | `Text`, nullable | Что сделано |
| `repair_duration_minutes` | `Integer`, nullable | Длительность ремонта в минутах |
| `cost` | `Numeric(10, 2)`, nullable | Стоимость |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

---

### 6. `boom_bike_alerts` — сохраненные алерты по парку

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `bike_id` | `BigInteger` FK → `boom_bikes.id`, nullable, `ON DELETE CASCADE` | Байк, если алерт про конкретный байк |
| `store_id` | `BigInteger` FK → `boom_stores.id`, nullable, `ON DELETE SET NULL` | Склад, если алерт про склад |
| `alert_type` | enum | Тип алерта |
| `message` | `Text` | HTML-текст уведомления |
| `is_read` | `Boolean`, default `false` | Прочитано |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

**Типы:** `low_bikes`, `repair_too_long`, `frequent_breakdowns`.

Дедупликация: бот не создает повторный непрочитанный алерт того же типа для того
же байка/склада, если похожий алерт уже создан за последние 24 часа.

Отдельный сигнал `check_no_online_couriers` не пишет строку в
`boom_bike_alerts`: он отправляет прямые Telegram-сообщения админам и
супервайзерам.

---

### 7. `boom_bike_bot_roles` — пользователи и роли Bikes-бота

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Автоинкремент |
| `telegram_id` | `BigInteger`, unique, index | Telegram ID пользователя |
| `admin_user_id` | `BigInteger`, nullable | Логическая ссылка на `boom_admin_users.id`; FK в модели нет |
| `name` | `String(255)` | Имя для показа в боте |
| `role` | `String(20)` | Роль |
| `store_ids` | `String(255)`, nullable | JSON-массив ID складов для супервайзера |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

**Роли:**

| Значение | Описание |
|----------|----------|
| `admin` | Админ |
| `supervisor` | Супервайзер |
| `mechanic` | Мастер |
| `courier` | Курьер |
| `pending` | Ожидает одобрения |

Правила `store_ids`:

- используется только для супервайзеров;
- `NULL` означает отсутствие ограничения по складам;
- `"[]"` означает пустой доступ;
- значения сериализуются через `app/core/store_ids.py` как отсортированный
  JSON-массив без дублей.

Регистрация:

1. Пользователь нажимает `/start` и отправляет свой контакт.
2. Бот ищет сотрудника в `boom_admin_users` по нормализованному телефону.
3. Создается запись `boom_bike_bot_roles` с `role = 'pending'`.
4. Всем админам отправляется заявка.
5. Админ одобряет пользователя и выбирает роль.
6. Для роли `supervisor` админ дополнительно выбирает доступные склады.

---

### 8. `boom_bike_bot_role_admin_notifications` — сообщения админам по заявкам

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | Автоинкремент |
| `bot_user_id` | FK → `boom_bike_bot_roles.id`, `ON DELETE CASCADE`, index | Заявка пользователя |
| `admin_telegram_id` | `BigInteger`, index | Telegram ID админа |
| `message_id` | `BigInteger` | ID сообщения с заявкой у этого админа |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

Ограничение уникальности:

```sql
UNIQUE (bot_user_id, admin_telegram_id)
```

Таблица нужна, чтобы после одобрения/отклонения заявки обновить или убрать
одинаковые pending-сообщения у всех админов.

---

## Интеграционные таблицы market / shopper

### `boom_stores` — склады

Read-only модель для существующей таблицы market.

| Поле | Тип в модели | Описание |
|------|--------------|----------|
| `id` | PK | ID склада |
| `title` | `String(255)` | Название |
| `main_id` | `String(255)`, nullable | Тип / группа склада |
| `street` | `String(255)`, nullable | Основное имя для показа |
| `address` | `String(255)`, nullable | Адрес |

Правила использования:

- бот показывает только `main_id = 'express'`;
- скрытые склады из `settings.hidden_store_ids` исключаются в выборках
  (по умолчанию `63`, `66`);
- `Store.display_name` = `street or title`.

---

### `boom_admin_users` — сотрудники / курьеры

Read-only модель для существующей таблицы market.

| Поле | Тип в модели | Описание |
|------|--------------|----------|
| `id` | PK | ID сотрудника |
| `name` | `String(255)` | Имя |
| `surname` | `String(255)`, nullable | Фамилия |
| `email` | `String(255)` | Email |
| `phone` | `String(20)`, nullable | Телефон |

Используется для регистрации через контакт, выбора курьера при поломке и
отображения имени. `AdminUser.display_name` собирает строку
`Имя Фамилия • 📱 телефон`.

---

### `boom_shift_couriers` — смены курьеров

Read-only модель для существующей таблицы shopper/market.

| Поле | Тип в модели | Описание |
|------|--------------|----------|
| `id` | `BigInteger` PK | ID смены |
| `admin_user_id` | `BigInteger` | Курьер из `boom_admin_users` |
| `store_ids` | `String(255)` | JSON-массив ID складов смены |
| `status` | `String(255)` | Например, `online` / `offline` |
| `courier_type` | `String(255)`, nullable | Тип курьера |
| `shift_start` | `DateTime` | Начало смены |
| `shift_end` | `DateTime`, nullable | Конец смены |
| `duration` | `BigInteger`, nullable | Длительность |
| `auto_closed` | `Boolean` | Признак автозакрытия |

Активная смена для курьера:

```sql
status = 'online'
AND shift_end IS NULL
```

Сигнал `check_no_online_couriers` проверяет, что на контрольное время у каждого
видимого express-склада есть хотя бы одна online-смена, чей `store_ids` содержит
ID этого склада.

---

### `boom_shift_couriers_bike` — байки внутри смены курьера

Интеграционная таблица: бот читает ее и дописывает записи `start` / `end`.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `BigInteger` PK | Автоинкремент |
| `shift_id` | `BigInteger` FK → `boom_shift_couriers.id`, `ON DELETE CASCADE` | Смена |
| `photo_url` | `String(512)` | В текущем flow бот пишет пустую строку |
| `checklist` | `String(2000)` | В текущем flow бот пишет `{}` |
| `bike_number` | `String(255)` | Номер байка, не FK на `boom_bikes` |
| `type` | `String(10)` | `start` = взял, `end` = вернул |
| `created_at` / `updated_at` | `DateTime` | Системные timestamps |

Как определяется «байк еще у курьера»:

1. Берутся строки `type = 'start'` для активной смены.
2. Берутся строки `type = 'end'` для той же смены.
3. Активными считаются `start`, для которых нет `end` с тем же `bike_number`.

---

## Внешние таблицы для SLA по завершенной смене

`app/internal_api.py` обрабатывает сигнал `shift_ended` и читает дополнительные
таблицы `boontar_market` без SQLAlchemy-моделей:

| Таблица | Как используется |
|---------|------------------|
| `boom_link_couriers_orders` | Связь курьера и заказа (`admin_user_id`, `order_id`) |
| `boom_order_details` | Фильтр заказов: `type = 'customer'` и `status = 'completed'` |
| `boom_orders_status_changes` | Время принятия и завершения заказа (`accepted_at`, `completed_at`) |
| `boom_delivery_details` | Слой доставки `layer` |

Запрос считает заказы курьера, завершенные между `shift_start` и `shift_end`.
SLA считается только для `layer IN (1, 2)`:

| `layer` | Лимит |
|---------|-------|
| `1` | 45 минут |
| `2` | 60 минут |
