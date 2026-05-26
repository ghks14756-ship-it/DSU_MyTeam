import asyncio
import aiosqlite
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

async def migrate():
    try:
        # 1. DB에서 신청자 가져오기
        db_path = "data/dsu_myteam.db"
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM applications WHERE is_matched = 0") as cursor:
                rows = await cursor.fetchall()
                applicants = [dict(r) for r in rows]

        if not applicants:
            print("No applicants to migrate.")
            return

        # 2. 구글 시트 연결
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key("1UNw2YaTiGZ8GsOlXL0_GxsZycbDDp-axtyqQ48JLC7I")
        ws = ss.worksheet("신청현황")

        # 3. 데이터 전송 (B열부터 시작하므로 앞에 빈 칸 하나 추가)
        count = 0
        for app in applicants:
            row_data = [
                "", # A열 비움
                app.get("applied_at", ""),
                app.get("discord_id", ""),
                app.get("username", ""),
                app.get("student_id", ""),
                app.get("department", ""),
                app.get("skill", ""),
                app.get("expires_at", ""),
                "대기"
            ]
            ws.append_row(row_data)
            print(f"Migrated: {app['username']}")
            count += 1
        print(f"Successfully migrated {count} entries.")

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
