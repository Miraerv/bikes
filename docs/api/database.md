# 🚲 База данных: Система учёта байков

> **Единая БД:** `boontar_market` — все таблицы с префиксом `boom_`
> Миграции: `boontar-market-back/database/migrations/`

---

## Схема связей

```
boontar_market
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

boom_stores ─────────┐
                     ├──► boom_bikes
boom_admin_users ────┤       │
  (name, surname,    │       ├──► boom_bike_usage_logs
   phone)            │       ├──► boom_bike_breakdowns ──► boom_bike_breakdown_photos
                     │       ├──► boom_bike_repairs
                     │       └──► boom_bike_alerts
                     │
boom_bike_bot_roles  │    boom_shift_couriers ──► boom_shift_couriers_bike
  (telegram_id, role,│
   admin_user_id)────┘
```

---

## Наши таблицы

### 1. `boom_bikes` — Реестр байков

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | Автоинкремент |
| `bike_number` | varchar(50), unique | Номер байка |
| `model` | varchar(255) | Модель |
| `commissioned_at` | date | Дата ввода |
| `store_id` | bigint FK → `boom_stores` | Склад |
| `status` | enum | Текущий статус |
| `created_at` / `updated_at` | timestamp | |

**Статусы:**

| Значение | Иконка | Описание |
|----------|--------|----------|
| `online` | 🟢 | На линии |
| `inspection` | 🟡 | На проверке |
| `repair` | 🔴 | В ремонте |
| `decommissioned` | ⚫ | Списан |

---

### 2. `boom_bike_usage_logs` — Лог использования (смены)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `bike_id` | bigint FK → `boom_bikes` | Какой байк |
| `courier_id` | bigint FK → `boom_admin_users` | Какой курьер |
| `store_id` | bigint FK → `boom_stores` | С какого склада |
| `started_at` | datetime | Начало смены |
| `ended_at` | datetime, nullable | Конец (null = на смене) |
| `created_at` / `updated_at` | timestamp | |

---

### 3. `boom_bike_breakdowns` — Поломки

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `bike_id` | bigint FK → `boom_bikes` | Сломанный байк |
| `courier_id` | bigint FK → `boom_admin_users` | Последний курьер |
| `store_id` | bigint FK → `boom_stores` | Склад |
| `reported_by` | bigint FK → `boom_admin_users` | Супервайзер |
| `breakdown_type` | enum | Категория |
| `description` | text, nullable | Описание |
| `reported_at` | datetime | Когда обнаружена |
| `created_at` / `updated_at` | timestamp | |

**Типы поломок:** `brakes`, `wheel`, `battery`, `motor`, `frame`, `electronics`, `other`

---

### 4. `boom_bike_breakdown_photos` — Фотофиксация

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `breakdown_id` | bigint FK → `boom_bike_breakdowns` | К поломке |
| `photo_url` | varchar(500) | URL фото |
| `created_at` / `updated_at` | timestamp | |

---

### 5. `boom_bike_repairs` — Ремонт

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `bike_id` | bigint FK → `boom_bikes` | Какой байк |
| `breakdown_id` | bigint FK → breakdowns, nullable | Связанная поломка |
| `mechanic_id` | bigint, nullable | ID мастера (без FK) |
| `mechanic_name` | varchar(255), nullable | Имя мастера (денормализация) |
| `store_id` | bigint FK → `boom_stores` | Склад |
| `picked_up_at` | datetime | Мастер забрал |
| `completed_at` | datetime, nullable | Завершён (null = в работе) |
| `work_description` | text, nullable | Что сделано |
| `repair_duration_minutes` | unsigned int, nullable | Время (мин) |
| `cost` | decimal(10,2), nullable | Стоимость |
| `created_at` / `updated_at` | timestamp | |

> `mechanic_id` не имеет FK — мастера берутся из `boom_bike_bot_roles`.

---

### 6. `boom_bike_alerts` — Уведомления

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `bike_id` | bigint FK, nullable | |
| `store_id` | bigint FK, nullable | |
| `alert_type` | enum | Тип алерта |
| `message` | text | Текст |
| `is_read` | boolean, default false | Прочитано |
| `created_at` / `updated_at` | timestamp | |

**Типы:** `low_bikes`, `repair_too_long`, `frequent_breakdowns`

---

### 7. `boom_bike_bot_roles` — Роли бот-пользователей

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | Автоинкремент |
| `telegram_id` | bigint, unique | Telegram ID |
| `admin_user_id` | bigint, nullable | Связь с `boom_admin_users` |
| `name` | varchar(255) | Имя пользователя |
| `role` | varchar(20) | Роль в боте |
| `created_at` / `updated_at` | timestamp | |

**Роли:**

| Значение | Иконка | Описание |
|----------|--------|----------|
| `admin` | 👑 | Супер-администратор |
| `supervisor` | 📋 | Супервайзер |
| `mechanic` | 🔧 | Мастер |
| `courier` | 🚚 | Курьер |
| `pending` | ⏳ | Ожидает одобрения |

**Регистрация:**
1. `/start` → «Отправить заявку» → шарит контакт
2. Бот ищет в `boom_admin_users` по `phone` → привязывает `admin_user_id`
3. Создаёт запись с `role=pending`
4. Админ одобряет + выбирает роль

---

## Внешние таблицы (read-only)

### `boom_stores` — Склады

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `title` | varchar(255) | Название |
| `main_id` | varchar(255), nullable | Тип (бот фильтрует `express`) |
| `street` | varchar(255), nullable | Адрес (используется как `display_name`) |

> **Фильтрация:** бот показывает только `main_id = 'express'`
> **Скрытые склады:** ID 63, 66 — неактивные, исключены через `settings.hidden_store_ids`

---

### `boom_admin_users` — Курьеры / сотрудники

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `name` | varchar(255) | Имя |
| `surname` | varchar(255), nullable | Фамилия |
| `email` | varchar(255) | Email |
| `phone` | varchar(20), nullable | Телефон |

> **Отображение:** `display_name` = «Имя Фамилия • 📱 телефон»
> Используется для `courier_id`, `reported_by`, `mechanic_id`

---

### `boom_shift_couriers` — Смены курьеров

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `admin_user_id` | bigint FK → `boom_admin_users` | Курьер |
| `store_ids` | varchar(255) | JSON-массив ID складов |
| `courier_type` | varchar(255), nullable | Тип курьера |
| `status` | varchar(255) | `online` / `offline` |
| `shift_start` | timestamp | Начало смены |
| `shift_end` | timestamp, nullable | Конец (null = активная) |
| `duration` | bigint, nullable | Длительность (сек) |
| `auto_closed` | boolean | Автозакрытие |
| `created_at` / `updated_at` | timestamp | |

> **Активная смена:** `status = 'online'` AND `shift_end IS NULL`
> Бот проверяет наличие активной смены перед тем как курьер возьмёт байк

---

### `boom_shift_couriers_bike` — Байки в смене курьера

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | |
| `shift_id` | bigint FK → `boom_shift_couriers` | Смена |
| `bike_number` | varchar(255) | Номер байка |
| `type` | varchar(10) | `start` / `end` |
| `photo_url` | varchar(512) | Фото |
| `checklist` | varchar(2000) | JSON чеклист |
| `created_at` / `updated_at` | timestamp | |

---

## Timezone

- **В БД:** серверное время (`datetime.now()`)
- **Отображение:** Якутск UTC+9 (`app/core/tz.py` → `now_display()`, `to_yakutsk()`)
