import asyncio
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GSheetInit")

# 새롭게 정의된 시트와 헤더 구조
SHEETS_SCHEMA = {
    "통합_사용자_관리": [
        "Unique_ID", "역할_상태", "Discord_ID", "Auth_Status", "이름", "학번", 
        "학과", "전문분야_특기", "신청_프로그램", "가입시간"
    ],
    "매칭_대기_라인": [
        "Unique_ID", "이름", "학과", "전문분야_특기", "희망조건_1", "희망조건_2",
        "희망조건_3", "신청_프로그램", "Match_Status", "신청시간",
        "주간_활동_가능_시간", "연락수단"  # [2026-05-28 신규] 달력 JSON, 연락수단 문자열
    ],
    "팀_관리_라인": [
        "Team_ID", "Leader_Unique_ID", "팀장_이름", "팀장_학과", "프로그램_선택", 
        "모집_요약", "모집_상세내용", "현재_매칭_인원", "모집_인원_수", "Team_Status", "생성시간"
    ],
    "활동_프로그램_관리": [
        "프로그램 내용", "신청일시", "신청형태", "운영일시", "만족도 실시기간",
        "최대학습포인트", "신청대상", "신청구분", "프로그램 담당자", "첨부파일", "전달사항"
    ],
    # [2026-05-28 신규] 웹 회원 시스템테이블
    "회원_정보": [
        "Web_ID", "닉네임", "Unique_ID", "Discord_ID",
        "연동_코드", "Auth_Status", "가입일자", "최근_접속일시", "이메일", "프로필이미지"
    ]
}

def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(Config.GSHEET_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        log.error(f"구글 API 인증 실패 (credentials.json 확인 요망): {e}")
        return None

async def init_google_sheets():
    log.info("📊 구글 시트 자동 세팅 및 초기화 시작...")
    
    if not Config.GSHEET_SPREADSHEET_ID or Config.GSHEET_SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        log.error("환경 변수(또는 config.py)에 GSHEET_SPREADSHEET_ID가 설정되지 않았습니다.")
        return

    client = get_gspread_client()
    if not client:
        return

    try:
        # 스프레드시트 열기
        spreadsheet = client.open_by_key(Config.GSHEET_SPREADSHEET_ID)
        log.info(f"✅ 스프레드시트 접근 성공: {spreadsheet.title}")

        existing_worksheets = {ws.title: ws for ws in spreadsheet.worksheets()}

        for title, headers in SHEETS_SCHEMA.items():
            if title in existing_worksheets:
                # 이미 존재하는 탭인 경우 헤더만 점검/업데이트
                ws = existing_worksheets[title]
                log.info(f"🔹 [{title}] 시트가 이미 존재합니다. 헤더를 검증합니다.")
                
                # 기존 데이터 보호를 위해 첫 번째 행(1행)만 가져옴
                existing_headers = ws.row_values(1)
                
                if existing_headers != headers:
                    log.warning(f"⚠️ [{title}] 시트의 헤더가 기획안과 다릅니다. 헤더를 덮어씁니다.")
                    # 헤더 덮어쓰기 (A1부터 시작)
                    cell_range = f"A1:{chr(65 + len(headers) - 1)}1"
                    ws.update(cell_range, [headers])
            else:
                # 존재하지 않는 탭 생성
                log.info(f"✨ [{title}] 시트가 없습니다. 새로 생성합니다...")
                ws = spreadsheet.add_worksheet(title=title, rows="1000", cols=str(len(headers)))
                
                # 헤더 입력
                cell_range = f"A1:{chr(65 + len(headers) - 1)}1"
                ws.update(cell_range, [headers])
                
                # 헤더 서식 지정 (굵게, 배경색)
                ws.format(cell_range, {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "textFormat": {"bold": True}
                })
                log.info(f"✅ [{title}] 시트 생성 및 헤더 입력 완료.")

        # 기본으로 만들어지는 '시트1' 등 더미 시트가 있고 비어있다면 삭제 시도
        if "시트1" in existing_worksheets:
            try:
                spreadsheet.del_worksheet(existing_worksheets["시트1"])
                log.info("🗑️ 기본 더미 시트('시트1')를 삭제했습니다.")
            except:
                pass
            
        log.info("🎉 구글 시트 자동 세팅이 완벽하게 끝났습니다!")

    except gspread.exceptions.APIError as api_err:
        log.error(f"❌ 구글 시트 API 오류 발생: {api_err}")
    except Exception as e:
        log.error(f"❌ 알 수 없는 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(init_google_sheets())
