import asyncio
import os
import sys

import asyncpg


async def wait() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    for i in range(40):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print("database ready", flush=True)
            return
        except Exception as exc:
            print(f"waiting for database ({i}) {exc}", flush=True)
            await asyncio.sleep(1)
    sys.exit("database not ready")


if __name__ == "__main__":
    asyncio.run(wait())
