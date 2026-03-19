# 🛠 Dev Notes

## Подключение к БД

- **MySQL**: локальный, `mysql -u root` без пароля
- **База market**: `boontar_market`
- **База bot**: `bikes_bot`

## Реальная схема внешних таблиц

### `boom_stores`

Поле для названия — `title` (не `name`!).

```
id               bigint unsigned PK auto_increment
title            varchar(255) NOT NULL
address          varchar(255)
city             varchar(255)
phone            varchar(255)
...и другие поля (position, delivery_type, photos, geo и т.д.)
```

### `boom_admin_users`

```
id               bigint unsigned PK auto_increment
name             varchar(255) NOT NULL
email            varchar(255) NOT NULL UNIQUE
phone            varchar(20)
role             varchar(255) NOT NULL default 'none'
...и другие поля (surname, middle_name, avatar, status и т.д.)
```

> [!IMPORTANT]
> При добавлении новых полей в read-only модели — всегда сверяйтесь с реальной БД:
> ```bash
> mysql -u root -e "DESCRIBE boontar_market.<table_name>;"
> ```

---

## Фильтрация магазинов

- **Фильтр**: бот показывает только магазины с `main_id = 'express'`
- **Название**: для отображения используется поле `street` (с фолбэком на `title`)
- **Property**: `Store.display_name` → `street or title`

