import asyncio
from typing import Any, Dict, List
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.gsheet_service import GoogleSheetService

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("InitPrograms")

async def init_programs():
    gsheet = GoogleSheetService()
    
    programs = [
        [
            "부산의 지리적 특성을 활용한 해양 스포츠 관련 취업 진로 현장실습(스포츠건강산업사 과정/담당교수: 최현희)",
            "2026-05-11(월) 16:00 ~ 2026-05-29(금) 12:59",
            "온라인",
            "2026-05-29(금) 13:00 ~ 2026-05-29(금) 18:00",
            "2026-05-29(금) 18:00 ~ 2026-06-11(목) 18:00\n※만족도조사 미실시 시 포인트 미지급",
            "2점",
            "학년 : 1, 2, 3, 4학년\n학적 : 재학\n학과 : 민석교양대학 자유전공학부\n바이오헬스융합대학 운동처방학과\n바이오헬스융합대학 임상병리학과",
            "개인",
            "운동처방학과 이소현(320-1684)",
            "",
            ""
        ],
        [
            "현장에 바로 적용할 수 있는 사회복지실무 단기 특강(3회차 - 공문서, 기안서, 기록 등의 실제)",
            "2026-05-15(금) 14:00 ~ 2026-05-29(금) 13:00",
            "온라인",
            "2026-05-29(금) 13:00 ~ 2026-05-29(금) 15:00",
            "2026-05-29(금) 15:00 ~ 2026-06-05(금) 15:00\n※만족도조사 미실시 시 포인트 미지급",
            "1점",
            "학년 : 3, 4학년\n학적 : 재학\n학과 : 경영사회과학대학 사회복지학과",
            "개인",
            "사회복지학과 김현호(320-1908)",
            "",
            ""
        ],
        [
            "실제 임상 환경을 반영한 실습 중심 교육을 통해 현장 적응력 및 즉시 활용 가능한 실무능력 강화할 수 있는 특강",
            "2026-05-26(화) 10:00 ~ 2026-05-28(목) 18:00",
            "온라인",
            "2026-05-28(목) 18:00 ~ 2026-05-28(목) 20:00",
            "2026-05-28(목) 20:00 ~ 2026-06-05(금) 20:00\n※만족도조사 미실시 시 포인트 미지급",
            "1점",
            "학년 : 3학년\n학적 : 재학\n학과 : 바이오헬스융합대학 치위생학과",
            "개인",
            "치위생학과 차지인(320-4811)",
            "",
            "치위생학과 3학년 대상 프로그램입니다."
        ]
    ]

    try:
        loop = asyncio.get_event_loop()
        client = await loop.run_in_executor(None, gsheet._get_client)
        
        def _insert():
            sheet = client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_programs)
            
            # Clear existing data except headers
            existing = sheet.get_all_values()
            if len(existing) > 1:
                # delete_rows might be better, or just clear and rewrite headers
                sheet.clear()
                headers = [
                    "프로그램 내용", "신청일시", "신청형태", "운영일시", "만족도 실시기간", 
                    "최대학습포인트", "신청대상", "신청구분", "프로그램 담당자", "첨부파일", "전달사항"
                ]
                sheet.append_row(headers)
            
            for p in programs:
                sheet.append_row(p)
            return True
            
        await loop.run_in_executor(None, _insert)
        log.info("프로그램 삽입 성공!")
    except Exception as e:
        log.error(f"실패: {e}")

if __name__ == "__main__":
    asyncio.run(init_programs())
