import sys
import os
import asyncio
from datetime import datetime

# sys.path에 프로젝트 루트 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gsheet_service import GoogleSheetService

async def main():
    gsheet = GoogleSheetService()
    
    # 프로그램 데이터 준비
    programs = [
        {
            "프로그램 내용": "현장실습대비 치과 임상 기본 술기 실습 특강",
            "신청일시": "2026.05.28 까지",
            "신청형태": "마이덱스 신청",
            "운영일시": "2026.05.28(목)",
            "만족도 실시기간": "운영 종료 후 1주일",
            "최대학습포인트": "1",
            "신청대상": "치위생학과 3학년 대상",
            "신청구분": "비교과",
            "프로그램 담당자": "윤수연 치위생사",
            "첨부파일": "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?auto=format&fit=crop&w=400",
            "전달사항": "장소: 글로벌빌리지 311"
        },
        {
            "프로그램 내용": "RISE 취업스쿨 [사회복지실무강화 프로그램]",
            "신청일시": "2026.05.22 까지",
            "신청형태": "MYDEX 신청",
            "운영일시": "2026.05.22(금) ~ 06.05(금)",
            "만족도 실시기간": "운영 종료 후 1주일",
            "최대학습포인트": "5",
            "신청대상": "사회복지학과 3, 4학년",
            "신청구분": "비교과",
            "프로그램 담당자": "사회복지학과",
            "첨부파일": "https://images.unsplash.com/photo-1577896851231-70ef18881754?auto=format&fit=crop&w=400",
            "전달사항": "운영장소: 어문관 6308호. 창의적 사고 기반 문제해결형 실무인재 양성."
        },
        {
            "프로그램 내용": "스포츠건강산업사 과정 지역사회 연계 프로그램 (SUP & SURFING)",
            "신청일시": "2026.05.29 까지",
            "신청형태": "MYDEX 필수 신청",
            "운영일시": "2026.05.29(금) 13:00~18:00",
            "만족도 실시기간": "운영 종료 후 1주일",
            "최대학습포인트": "2",
            "신청대상": "운동처방학과 MD 수강생",
            "신청구분": "비교과",
            "프로그램 담당자": "운동처방학과",
            "첨부파일": "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=400",
            "전달사항": "장소: 광안리 크레이지서퍼스. 준비물: 개인 여벌 옷 및 샤워도구."
        }
    ]

    try:
        loop = asyncio.get_event_loop()
        client = await loop.run_in_executor(None, gsheet._get_client)
        sheet = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_programs)
        
        # 기존 데이터 삭제 (헤더 제외)
        all_values = sheet.get_all_values()
        if len(all_values) > 1:
            sheet.delete_rows(2, len(all_values))
            print("기존 프로그램 데이터를 초기화했습니다.")

        # 새 데이터 삽입
        rows_to_insert = []
        headers = all_values[0] if all_values else [
            "프로그램 내용", "신청일시", "신청형태", "운영일시", "만족도 실시기간",
            "최대학습포인트", "신청대상", "신청구분", "프로그램 담당자", "첨부파일", "전달사항"
        ]
        
        for prog in programs:
            row = [prog.get(h, "") for h in headers]
            rows_to_insert.append(row)
            
        if rows_to_insert:
            sheet.append_rows(rows_to_insert)
            print(f"{len(rows_to_insert)}개의 프로그램을 성공적으로 추가했습니다!")
            
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
