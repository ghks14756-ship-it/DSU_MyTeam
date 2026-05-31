import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.gsheet_service import GoogleSheetService

async def main():
    service = GoogleSheetService()
    if not service._is_configured():
        return

    loop = asyncio.get_running_loop()
    client = await loop.run_in_executor(None, service._get_client)
    doc = client.open_by_key(service.spreadsheet_id)
    
    worksheets = [
        service.worksheet_users,       # 통합_사용자_관리
        service.worksheet_waiting,     # 매칭_대기_라인
        service.worksheet_team_line,   # 팀_관리_라인
        service.worksheet_members      # 회원_정보
    ]
    
    with open('scratch/sheet_headers.txt', 'w', encoding='utf-8') as f:
        for ws_name in worksheets:
            try:
                ws = doc.worksheet(ws_name)
                headers = ws.row_values(1)
                f.write(f"[{ws_name}] Headers:\n")
                f.write(", ".join(headers) + "\n")
                f.write("-" * 40 + "\n")
            except Exception as e:
                f.write(f"Error reading {ws_name}: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
