# Bikes Bot

Продакшн Telegram-бот на стеке **Python 3.14 + aiogram 3 + SQLAlchemy 2 (async) + Alembic + pydantic-settings + loguru + asyncmy**.

## Быстрый старт

```bash
# 1. Создать виртуальное окружение
python -m venv .venv && source .venv/bin/activate

# 2. Установить зависимости
make install

# 3. Настроить окружение
cp .env.example .env
# Отредактировать .env — указать BOT_TOKEN и параметры БД

# 4. Поднять MySQL (опционально, через Docker)
docker compose up -d mysql

# 5. Применить миграции
make migrate

# 6. Запустить бота
make run
```

## Структура проекта

```
app/
├── __main__.py          # Точка входа
├── core/
│   ├── config.py        # Конфигурация (pydantic-settings)
│   └── logging.py       # Настройка loguru
├── db/
│   ├── base.py          # Async engine + session
│   └── models/          # SQLAlchemy-модели
├── bot/
│   ├── __init__.py      # Создание Dispatcher
│   └── handlers/        # Хэндлеры команд
└── middlewares/
    └── db.py            # Middleware для сессий БД
```

## Команды

| Команда | Описание |
|---------|----------|
| `make install` | Установить зависимости |
| `make run` | Запустить бота |
| `make migrate` | Применить миграции |
| `make revision msg="описание"` | Создать миграцию |
| `make lint` | Проверить код |
| `make format` | Отформатировать код |

## Docker

```bash
docker compose up -d          # Запустить всё
docker compose up -d mysql    # Только MySQL
docker compose logs -f bot    # Логи бота
```
