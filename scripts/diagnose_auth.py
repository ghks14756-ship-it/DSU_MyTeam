"""
통합_사용자_관리와 매칭_대기_라인 시트에서 ASFNIJGA를 찾는 진단 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gsheet_service import GoogleSheetService

async def main():
    gsheet = GoogleSheetService()
    loop = asyncio.get_running_loop()
    client = await loop.run_in_executor(None, gsheet._get_client)

    sheets_to_check = ["통합_사용자_관리", "매칭_대기_라인", "회원_정보"]
    
    for sheet_name in sheets_to_check:
        print(f"\n=== {sheet_name} ===")
        def _read(sn=sheet_name):
            sheet = client.open_by_key(gsheet.spreadsheet_id).worksheet(sn)
            return sheet.get_all_values()
        try:
            rows = await loop.run_in_executor(None, _read)
            print(f"  총 {len(rows)}행")
            for i, row in enumerate(rows[:8]):
                print(f"  행 {i+1}: {row}")
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
