import sys
import os
import asyncio

# sys.path에 프로젝트 루트 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gsheet_service import GoogleSheetService

async def main():
    gsheet = GoogleSheetService()
    
    # 이미지에서 추출한 데이터
    new_program = {
        "프로그램 내용": "글로벌 창업아이템 발굴, 창업마케팅 방안 수립과 창업 관련 캠프 & 경진대회",
        "신청일시": "2024-04-09(화) 09:00 ~ 2024-04-30(화) 18:00",
        "신청형태": "온라인",
        "운영일시": "2024-08-28(수) 09:00 ~ 2024-08-30(금) 18:00",
        "만족도 실시기간": "2024-08-30(금) 18:00 ~ 2024-09-12(목) 18:00 ※만족도조사 미실시 시 포인트 미지급",
        "최대학습포인트": "포인트없음",
        "신청대상": "제한없음",
        "신청구분": "개인",
        "프로그램 담당자": "LINC 3.0 사업단 김나영(320-1746)",
        "카테고리별 분류": "", # 사용자가 직접 시트에서 작성
        "카테고리": "",       # 사용자가 직접 시트에서 작성
        "첨부파일": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=400", # 임시 글로벌/팀 회의 관련 이미지
        "전달사항": ""
    }

    try:
        loop = asyncio.get_event_loop()
        client = await loop.run_in_executor(None, gsheet._get_client)
        sheet = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_programs)
        
        all_values = sheet.get_all_values()
        headers = all_values[0] if all_values else [
            "프로그램 내용", "신청일시", "신청형태", "운영일시", "만족도 실시기간",
            "최대학습포인트", "신청대상", "신청구분", "프로그램 담당자", "첨부파일", "전달사항"
        ]
        
        row = [new_program.get(h, "") for h in headers]
        sheet.append_row(row)
        print("프로그램을 성공적으로 구글 시트에 추가했습니다!")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
