from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import ROLE_CAPABILITIES, ROLE_LABELS, register_custom_roles
from app.models.role import Role


async def refresh_role_cache(db: AsyncSession) -> None:
    rows = list((await db.execute(select(Role).where(Role.builtin.is_(False)))).scalars())
    register_custom_roles(rows)


async def ensure_builtin_roles(db: AsyncSession) -> None:
    for slug, caps in ROLE_CAPABILITIES.items():
        statewide = "statewide" in caps
        row = await db.scalar(select(Role).where(Role.slug == slug))
        if row is None:
            db.add(
                Role(
                    slug=slug,
                    name=ROLE_LABELS[slug],
                    description=ROLE_LABELS[slug],
                    capabilities=sorted(caps),
                    statewide=statewide,
                    builtin=True,
                )
            )
            continue
        row.name = ROLE_LABELS[slug]
        row.description = row.description or ROLE_LABELS[slug]
        row.capabilities = sorted(caps)
        row.statewide = statewide
        row.builtin = True
    await db.flush()
    await refresh_role_cache(db)
