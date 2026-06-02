import asyncio
from services.gsheet_service import GSheetService

async def main():
    s = GSheetService()
    p = await s.get_programs()
    categories = [x.get('카테고리별 분류') for x in p]
    print(categories)

asyncio.run(main())
