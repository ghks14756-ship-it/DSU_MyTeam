import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.gsheet_service import GoogleSheetService

async def main():
    gsheet = GoogleSheetService()
    
    admin_data = {
        "web_id": "admin",
        "nickname": "최고관리자",
        "unique_id": "ADMIN-0000"
    }
    
    print("관리자 계정을 구글 시트에 등록합니다...")
    success = await gsheet.register_member(admin_data)
    if success:
        print("✅ 관리자 계정 생성 완료!")
        print("  - 아이디: admin")
        print("  - 닉네임: 최고관리자")
        print("  - 인증키: ADMIN-0000")
    else:
        print("❌ 실패했습니다.")

if __name__ == "__main__":
    asyncio.run(main())
