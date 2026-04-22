from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.sql import func as sql_func

from app.db.models.admin_user import AdminUser

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def normalize_phone(phone: str) -> str:
    """Strip everything except digits from a phone number."""
    return "".join(c for c in phone if c.isdigit())


def phone_lookup_variants(phone_digits: str) -> set[str]:
    """Return phone variants used to match admin panel records."""
    variants = {phone_digits}
    if phone_digits.startswith("7") and len(phone_digits) == 11:
        variants.add("8" + phone_digits[1:])
        variants.add("+" + phone_digits)
    elif phone_digits.startswith("8") and len(phone_digits) == 11:
        variants.add("7" + phone_digits[1:])
        variants.add("+7" + phone_digits[1:])
    return variants


async def find_admin_user_by_phone(
    session: AsyncSession,
    phone: str,
) -> AdminUser | None:
    """Find an admin panel user by phone, trying common RU phone formats."""
    phone_digits = normalize_phone(phone)
    if not phone_digits:
        return None

    for variant in phone_lookup_variants(phone_digits):
        result = await session.execute(
            select(AdminUser)
            .where(
                sql_func.replace(
                    sql_func.replace(AdminUser.phone, "+", ""),
                    " ",
                    "",
                )
                == variant,
            )
            .limit(1),
        )
        admin_user = result.scalar_one_or_none()
        if admin_user is not None:
            return admin_user

    return None


async def search_admin_users_by_name(
    session: AsyncSession,
    query_text: str,
    *,
    limit: int,
) -> list[AdminUser]:
    """Search admin panel users by name or surname."""
    cleaned_query = query_text.strip()
    if not cleaned_query:
        return []

    pattern = f"%{cleaned_query}%"
    result = await session.execute(
        select(AdminUser)
        .where(
            or_(
                AdminUser.name.ilike(pattern),
                AdminUser.surname.ilike(pattern),
            ),
        )
        .order_by(AdminUser.name)
        .limit(limit),
    )
    return list(result.scalars().all())
