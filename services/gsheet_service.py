"""
services/gsheet_service.py
구글 시트 API 연동 서비스

수행 기능:
  1. '활동_프로그램_관리' 탭에서 프로그램 데이터 로드/추가
  2. '통합_사용자_관리', '매칭_대기_라인', '팀_관리_라인' 탭에 유저/팀 신청서 기록
  3. '회원_정보' 탭 — 웹 회원가입/로그인/디스코드 연동 코드 관리 (내일 구현 예정)
  4. '매칭_대기_라인' 탭에서 대기자 목록 조회 (fetch_applications)
"""

import logging
import asyncio
import secrets
import string
from datetime import datetime, timezone
from typing import List, Dict, Any

log = logging.getLogger("DSUMyTeam.GSheet")


class GoogleSheetService:
    """구글 시트 DB 연동 서비스."""

    def __init__(self):
        from config import Config
        self.credentials_file = Config.GSHEET_CREDENTIALS_FILE
        self.spreadsheet_id = Config.GSHEET_SPREADSHEET_ID
        self.worksheet_users = "통합_사용자_관리"
        self.worksheet_waiting = "매칭_대기_라인"
        self.worksheet_team_line = "팀_관리_라인"
        self.worksheet_programs = "활동_프로그램_관리"
        self.worksheet_members = "회원_정보"  # [신규] 웹 회원 테이블

    def _get_client(self):
        """gspread 클라이언트 생성 (동기)"""
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            self.credentials_file, scope
        )
        return gspread.authorize(creds)

    def _is_configured(self) -> bool:
        """구글 시트 연동이 설정되어 있는지 확인."""
        return bool(self.spreadsheet_id and self.spreadsheet_id != "YOUR_SPREADSHEET_ID_HERE")

    # ══════════════════════════════════════════════════════════════
    #  프로그램 (활동_프로그램_관리)
    # ══════════════════════════════════════════════════════════════

    async def get_programs(self) -> List[Dict[str, str]]:
        """웹 캐러셀용 프로그램 목록 반환."""
        if not self._is_configured():
            return []
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _fetch():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_programs)
                return sheet.get_all_records()

            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            log.error(f"[get_programs] 실패: {e}")
            return []

    async def add_program(self, data: Dict[str, str]) -> bool:
        """
        [신규] 관리자 /최신화 Modal → 활동_프로그램_관리 탭에 신규 행 추가.
        """
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            headers = [
                "프로그램 내용", "신청일시", "신청형태", "운영일시", "만족도 실시기간",
                "최대학습포인트", "신청대상", "신청구분", "프로그램 담당자", "첨부파일", "전달사항"
            ]
            row = [data.get(h, "") for h in headers]

            def _append():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_programs)
                sheet.append_row(row)
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"[add_program] 실패: {e}")
            return False

    async def fetch_activities(self) -> List[Dict[str, Any]]:
        """
        [신규] 활동_프로그램_관리 탭 → SQLite activities 테이블 upsert용 데이터 반환.
        /최신화 명령어 (구버전 방향) 또는 수동 동기화 시 사용.
        """
        if not self._is_configured():
            return []
        try:
            programs = await self.get_programs()
            result = []
            for p in programs:
                name = p.get("프로그램 내용", "").strip()
                if not name:
                    continue
                result.append({
                    "name": name,
                    "description": p.get("전달사항", ""),
                    "deadline": p.get("신청일시", ""),
                    "max_members": int(p.get("최대학습포인트", 0) or 0),
                })
            return result
        except Exception as e:
            log.error(f"[fetch_activities] 실패: {e}")
            return []

    # ══════════════════════════════════════════════════════════════
    #  매칭 대기자 (매칭_대기_라인)
    # ══════════════════════════════════════════════════════════════

    async def fetch_applications(self) -> List[Dict[str, Any]]:
        """
        [신규] 매칭_대기_라인 탭의 전체 대기자 목록 반환.
        /대기목록 명령어에서 사용.
        """
        if not self._is_configured():
            return []
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _fetch():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_waiting)
                return sheet.get_all_records()

            records = await loop.run_in_executor(None, _fetch)
            # Match_Status가 '대기'인 항목만 반환
            return [r for r in records if r.get("Match_Status", "") == "대기"]
        except Exception as e:
            log.error(f"[fetch_applications] 실패: {e}")
            return []

    async def record_application(self, data: Dict[str, Any]) -> bool:
        """개인 매칭 신청 → 통합_사용자_관리 + 매칭_대기_라인 시트 기록."""
        if not self._is_configured():
            return False

        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            now = datetime.now(timezone.utc).isoformat()

            user_row = [
                data.get('unique_id', ''),
                "대기자",
                data.get('discord_id', ''),
                data.get('auth_status', '미인증'),
                data.get('username', ''),
                data.get('student_id', ''),
                data.get('department', ''),
                data.get('skill', ''),
                data.get('program', '미정'),
                now
            ]

            waiting_row = [
                data.get('unique_id', ''),
                data.get('username', ''),
                data.get('department', ''),
                data.get('skill', ''),
                data.get('condition_1', ''),
                data.get('condition_2', ''),
                data.get('condition_3', ''),
                data.get('program', '미정'),
                data.get('match_status', '대기'),
                now,
                data.get('weekly_schedule', ''),   # [신규] JSON 직렬화 시간표
                data.get('contact', ''),            # [신규] 연락수단
            ]

            def _append():
                doc = client.open_by_key(self.spreadsheet_id)
                ws_users = doc.worksheet(self.worksheet_users)
                ws_waiting = doc.worksheet(self.worksheet_waiting)
                ws_users.append_row(user_row)
                ws_waiting.append_row(waiting_row)
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"[record_application] 실패: {e}")
            return False

    async def record_recruitment(self, data: Dict[str, Any]) -> bool:
        """팀 모집 등록 → 통합_사용자_관리 + 팀_관리_라인 시트 기록."""
        if not self._is_configured():
            return False

        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            now = datetime.now(timezone.utc).isoformat()

            user_row = [
                data.get('leader_unique_id', ''),
                "팀장",
                "",
                "미인증",
                data.get('leader_name', '웹 조장 유저'),
                data.get('leader_student_id', '0000000'),
                data.get('department', ''),
                "팀장",
                data.get('program', '미정'),
                now
            ]

            team_row = [
                data.get('team_id', ''),
                data.get('leader_unique_id', ''),
                data.get('leader_name', '웹 조장 유저'),
                data.get('department', ''),
                data.get('program', ''),
                data.get('summary', ''),
                data.get('description', ''),
                1,
                data.get('target_members', 4),
                data.get('team_status', '모집중'),
                now
            ]

            def _append():
                doc = client.open_by_key(self.spreadsheet_id)
                ws_users = doc.worksheet(self.worksheet_users)
                ws_team = doc.worksheet(self.worksheet_team_line)
                ws_users.append_row(user_row)
                ws_team.append_row(team_row)
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"[record_recruitment] 실패: {e}")
            return False

    # ══════════════════════════════════════════════════════════════
    #  팀 목록 (팀_관리_라인)
    # ══════════════════════════════════════════════════════════════

    async def get_teams(self) -> List[Dict[str, Any]]:
        """현황 페이지용 팀 목록 반환."""
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)
            if not client:
                return []

            def _fetch():
                doc = client.open_by_key(self.spreadsheet_id)
                ws = doc.worksheet(self.worksheet_team_line)
                return ws.get_all_records()

            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            log.error(f"[get_teams] 실패: {e}")
            return []

    # ══════════════════════════════════════════════════════════════
    #  인증 업데이트 (통합_사용자_관리)
    # ══════════════════════════════════════════════════════════════

    async def update_auth_status(self, unique_id: str, discord_id: str) -> bool:
        """디스코드 /인증 완료 시 통합_사용자_관리의 Discord_ID와 Auth_Status 업데이트."""
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _update():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_users)
                all_values = sheet.get_all_values()
                if len(all_values) < 2:
                    return False
                for idx, row in enumerate(all_values):
                    if row and str(row[0]).strip() == unique_id:
                        row_num = idx + 1
                        sheet.update_cell(row_num, 3, discord_id)   # C열: Discord_ID
                        sheet.update_cell(row_num, 4, "인증완료")   # D열: Auth_Status
                        return True
                return False

            return await loop.run_in_executor(None, _update)
        except Exception as e:
            log.error(f"[update_auth_status] 실패: {e}")
            return False

    # ══════════════════════════════════════════════════════════════
    #  회원 시스템 (회원_정보) — 내일 구현 예정
    # ══════════════════════════════════════════════════════════════

    async def find_unique_id(self, unique_id: str) -> Dict[str, Any] | None:
        """
        통합_사용자_관리에서 unique_id가 존재하는지 확인.
        회원가입 시 발급된 인증키 유효성 검증에 사용.
        """
        if not self._is_configured():
            return None
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _find():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_users)
                records = sheet.get_all_records()
                for r in records:
                    if str(r.get("Unique_ID", "")).strip() == unique_id:
                        return r
                return None

            return await loop.run_in_executor(None, _find)
        except Exception as e:
            log.error(f"[find_unique_id] 실패: {e}")
            return None

    async def register_member(self, data: Dict[str, Any]) -> bool:
        """
        회원_정보 탭에 신규 회원 등록.
        data 키: web_id, nickname, unique_id, 가입일자
        """
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            now = datetime.now(timezone.utc).isoformat()
            row = [
                data.get('web_id', ''),
                data.get('nickname', ''),
                data.get('unique_id', ''),
                '',        # Discord_ID (인증 전 비어있음)
                '',        # 연동_코드 (생성 전 비어있음)
                '미인증',
                data.get('가입일자', now),
            ]

            def _append():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_members)
                sheet.append_row(row)
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"[register_member] 실패: {e}")
            return False

    async def get_member_by_id(self, web_id: str) -> Dict[str, Any] | None:
        """
        Web_ID로 회원_정보 탭 조회 → 로그인 검증에 사용.
        """
        if not self._is_configured():
            return None
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _find():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_members)
                records = sheet.get_all_records()
                for r in records:
                    if str(r.get("Web_ID", "")).strip() == web_id:
                        return r
                return None

            return await loop.run_in_executor(None, _find)
        except Exception as e:
            log.error(f"[get_member_by_id] 실패: {e}")
            return None

    async def get_member_by_unique_id(self, unique_id: str) -> Dict[str, Any] | None:
        """
        Unique_ID로 회원_정보 탭 조회 → 인증키 로그인 검증에 사용.
        """
        if not self._is_configured():
            return None
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _find():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_members)
                records = sheet.get_all_records()
                for r in records:
                    if str(r.get("Unique_ID", "")).strip() == unique_id:
                        return r
                return None

            return await loop.run_in_executor(None, _find)
        except Exception as e:
            log.error(f"[get_member_by_unique_id] 실패: {e}")
            return None

    async def get_user_status(self, unique_id: str) -> Dict[str, Any]:
        """
        unique_id 기반 매칭 진행 3단계 상태 반환.
        
        반환 형식:
        {
            "stage": 1|2|3,
            "label": "대기 중" | "매칭 완료" | "팀 결성",
            "detail": "...",
            "team_info": {...} | None
        }
        """
        if not self._is_configured():
            return {"stage": 0, "label": "미신청", "detail": "시트 설정 오류", "team_info": None}
            
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)
            
            def _check():
                doc = client.open_by_key(self.spreadsheet_id)
                # 1, 2단계: 매칭 대기 라인 확인
                ws_wait = doc.worksheet(self.worksheet_waiting)
                wait_records = ws_wait.get_all_records()
                user_wait = next((r for r in wait_records if str(r.get("Unique_ID", "")).strip() == unique_id), None)
                
                # 3단계: 팀 관리 라인 확인
                ws_team = doc.worksheet(self.worksheet_team_line)
                team_records = ws_team.get_all_records()
                user_team = next((r for r in team_records if str(r.get("Leader_Unique_ID", "")).strip() == unique_id), None)

                if user_team and user_team.get("Team_Status", "") == "결성완료":
                    return {
                        "stage": 3,
                        "label": "🎉 팀 결성",
                        "detail": f"팀 '{user_team.get('Team_ID')}' 결성 완료",
                        "team_info": user_team
                    }
                elif user_wait:
                    status = user_wait.get("Match_Status", "")
                    if status == "매칭완료":
                        return {
                            "stage": 2,
                            "label": "✅ 매칭 완료",
                            "detail": "팀에 배정되었습니다. 팀장의 초대를 기다리세요.",
                            "team_info": None
                        }
                    else:
                        return {
                            "stage": 1,
                            "label": "🕐 대기 중",
                            "detail": "조건에 맞는 팀을 찾고 있습니다.",
                            "team_info": None
                        }
                return {"stage": 0, "label": "미신청", "detail": "신청 내역이 없습니다.", "team_info": None}

            return await loop.run_in_executor(None, _check)
        except Exception as e:
            log.error(f"[get_user_status] 실패: {e}")
            return {"stage": 0, "label": "조회 실패", "detail": "서버 오류", "team_info": None}

    async def generate_link_code(self, unique_id: str) -> str | None:
        """
        디스코드 연동용 1회용 코드 생성 (예: A7X9-B2) 후 회원_정보 탭에 저장.
        반환: 생성된 코드 문자열 또는 None(실패)
        """
        if not self._is_configured():
            return None
            
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(6))
        
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _update():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_members)
                all_values = sheet.get_all_values()
                if len(all_values) < 2:
                    return False
                for idx, row in enumerate(all_values):
                    # Unique_ID는 C열 (인덱스 2)
                    if len(row) > 2 and str(row[2]).strip() == unique_id:
                        row_num = idx + 1
                        sheet.update_cell(row_num, 5, code)   # E열: 연동_코드
                        return True
                return False

            success = await loop.run_in_executor(None, _update)
            return code if success else None
        except Exception as e:
            log.error(f"[generate_link_code] 실패: {e}")
            return None
