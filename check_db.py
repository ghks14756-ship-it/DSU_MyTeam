import asyncio
import aiosqlite
import json

async def check_db():
    db_path = "data/dsu_myteam.db"
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM applications") as cursor:
            rows = await cursor.fetchall()
            print(json.dumps([dict(r) for r in rows], ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check_db())
