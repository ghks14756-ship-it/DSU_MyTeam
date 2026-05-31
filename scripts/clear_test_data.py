import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database.db_manager import DatabaseManager
from services.gsheet_service import GoogleSheetService

async def main():
    db = DatabaseManager(Config.DATABASE_PATH)
    await db.init()
    
    # 1. Clear local DB
    await db._conn.execute("DELETE FROM applications")
    await db._conn.execute("DELETE FROM team_rooms")
    await db._conn.execute("DELETE FROM team_match_results")
    await db._conn.commit()
    print("Local DB tables cleared.")

    # 2. Clear Google Sheets
    gsheet = GoogleSheetService()
    loop = asyncio.get_running_loop()
    client = await loop.run_in_executor(None, gsheet._get_client)
    
    # Clear 매칭_대기_라인
    try:
        sheet = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_waiting)
        # Check rows count to avoid errors when deleting
        rows = len(sheet.get_all_values())
        if rows > 1:
            sheet.delete_rows(2, rows)
            print("매칭_대기_라인 시트 데이터 삭제 완료.")
    except Exception as e:
        print(f"매칭_대기_라인 삭제 중 오류: {e}")

    # Clear 팀_관리_라인
    try:
        sheet2 = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_team_line)
        rows = len(sheet2.get_all_values())
        if rows > 1:
            sheet2.delete_rows(2, rows)
            print("팀_관리_라인 시트 데이터 삭제 완료.")
    except Exception as e:
        print(f"팀_관리_라인 삭제 중 오류: {e}")

    # Reset 회원_정보 Auth_Status & Discord_ID
    try:
        sheet3 = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_members)
        all_values = sheet3.get_all_values()
        for i, row in enumerate(all_values[1:], start=2):
            sheet3.update_cell(i, 4, "") # Discord_ID
            sheet3.update_cell(i, 6, "미인증") # Auth_Status
        print("회원_정보 시트 인증 정보 초기화 완료.")
    except Exception as e:
        print(f"회원_정보 초기화 중 오류: {e}")

    print("All test data cleared.")

if __name__ == "__main__":
    asyncio.run(main())
