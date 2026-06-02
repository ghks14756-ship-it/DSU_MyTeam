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

    async def get_cached_sheets(self) -> dict:
        """Fallback Search를 위해 주요 시트 데이터를 일괄 캐싱."""
        if not self._is_configured():
            return {}
        loop = asyncio.get_running_loop()
        client = await loop.run_in_executor(None, self._get_client)
        def _fetch():
            doc = client.open_by_key(self.spreadsheet_id)
            return {
                "users": doc.worksheet(self.worksheet_users).get_all_records(),
                "waiting": doc.worksheet(self.worksheet_waiting).get_all_records(),
                "team_line": doc.worksheet(self.worksheet_team_line).get_all_records(),
                "members": doc.worksheet(self.worksheet_members).get_all_records()
            }
        try:
            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            log.error(f"[get_cached_sheets] 일괄 캐싱 실패: {e}")
            return {}

    def get_fallback_data(self, cached_sheets: dict, discord_id: str = None, unique_id: str = None, field: str = "", is_leader: bool = False) -> str:
        """역할에 따른 순차적 조건부 조회 (Fallback Search) 로직"""
        # 1. Unique_ID 찾기 (통합_사용자_관리 -> 회원_정보 순)
        if not unique_id and discord_id:
            for r in cached_sheets.get("users", []):
                if str(r.get("Discord_ID", "")).strip() == discord_id:
                    unique_id = str(r.get("Unique_ID", "")).strip()
                    break
            if not unique_id:
                for r in cached_sheets.get("members", []):
                    if str(r.get("Discord_ID", "")).strip() == discord_id:
                        unique_id = str(r.get("Unique_ID", "")).strip()
                        break
        
        if not unique_id:
            return "미기재"

        # 2. 역할에 따른 시트 탐색 순서 (1순위 -> 2순위 -> 3순위)
        if is_leader:
            order = [
                ("team_line", "Leader_Unique_ID"),
                ("users", "Unique_ID"),
                ("members", "Unique_ID")
            ]
        else:
            order = [
                ("waiting", "Unique_ID"),
                ("users", "Unique_ID"),
                ("members", "Unique_ID")
            ]

        # 3. 논리적 필드명에 해당하는 실제 시트 컬럼명 매핑 (우선순위 순)
        field_map = {
            "이름": ["이름", "팀장_이름", "닉네임"],
            "학번": ["학번"],
            "학과": ["학과", "팀장_학과"],
            "특기": ["전문분야_특기"],
            "연락수단": ["연락수단", "이메일"],
            "주간_시간표": ["주간_활동_가능_시간"]
        }
        possible_cols = field_map.get(field, [field])

        # 4. 순차적 조회 (Fallback)
        for sheet_name, uid_col in order:
            sheet_data = cached_sheets.get(sheet_name, [])
            row = next((r for r in sheet_data if str(r.get(uid_col, "")).strip() == unique_id), None)
            if row:
                for col in possible_cols:
                    if col in row:
                        val = str(row.get(col, "")).strip()
                        if val and val.lower() != "none" and val != "":
                            return val

        return "미기재"

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
                def _parse_int(val):
                    try:
                        return int(str(val).replace('점', '').strip())
                    except ValueError:
                        return 0

                result.append({
                    "name": name,
                    "description": p.get("전달사항", ""),
                    "deadline": p.get("신청일시", ""),
                    "max_members": _parse_int(p.get("최대학습포인트", 0)),
                    "카테고리별 분류": p.get("카테고리별 분류", ""),
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

    async def check_user_status(self, search_id: str) -> dict:
        """
        [신규] 관리자용 상태조회: 특정 유저의 인증/매칭 상태를 반환.
        통합_사용자_관리 및 매칭_대기_라인에서 조회.
        """
        if not self._is_configured():
            return {"error": "구글 시트 미연동"}
        
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _fetch():
                # 1. 통합_사용자_관리에서 인증 상태 조회
                sheet_users = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_users)
                user_records = sheet_users.get_all_records()
                user_info = next((r for r in user_records if str(r.get("Unique_ID", "")) == search_id or str(r.get("Discord_ID", "")) == search_id), None)

                # 2. 매칭_대기_라인에서 매칭 상태 조회
                sheet_waiting = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_waiting)
                waiting_records = sheet_waiting.get_all_records()
                waiting_info = next((r for r in waiting_records if str(r.get("Unique_ID", "")) == search_id), None)

                return {
                    "user_info": user_info,
                    "waiting_info": waiting_info
                }

            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            log.error(f"[check_user_status] 실패: {e}")
            return {"error": str(e)}

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
                now,
                ""  # [신규] K열(인증키) 예약 공간. routes.py에서 나중에 채워짐.
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
                
                users_header = ws_users.row_values(1)
                waiting_header = ws_waiting.row_values(1)
                if len(user_row) != len(users_header):
                    raise ValueError(f"통합_사용자_관리 컬럼 불일치: 헤더 {len(users_header)}개 vs 데이터 {len(user_row)}개")
                if len(waiting_row) != len(waiting_header):
                    raise ValueError(f"매칭_대기_라인 컬럼 불일치: 헤더 {len(waiting_header)}개 vs 데이터 {len(waiting_row)}개")
                
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

    async def update_last_login(self, identifier: str, is_web_id: bool = True) -> bool:
        """[신규] 로그인 성공 시 회원_정보 탭의 최근_접속일시 업데이트"""
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)
            now = datetime.now(timezone.utc).isoformat()

            def _update():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_members)
                records = sheet.get_all_records()
                for i, row in enumerate(records):
                    match_val = str(row.get("Web_ID", "") if is_web_id else row.get("Unique_ID", ""))
                    if match_val == identifier:
                        # 8번째 컬럼이 최근_접속일시 (A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8)
                        # 컬럼 개수: Web_ID, 닉네임, Unique_ID, Discord_ID, 연동_코드, Auth_Status, 가입일자, 최근_접속일시
                        sheet.update_cell(i + 2, 8, now)
                        return True
                return False

            return await loop.run_in_executor(None, _update)
        except Exception as e:
            log.error(f"[update_last_login] 실패: {e}")
    async def get_user_profile(self, unique_id: str) -> Dict[str, Any] | None:
        """
        내정보 화면용 통합 데이터 조회
        이름(통합_사용자_관리), 닉네임/이메일/Web_ID(회원_정보), 스케줄(매칭_대기_라인)
        """
        if not self._is_configured():
            return None
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _fetch():
                doc = client.open_by_key(self.spreadsheet_id)
                # 1. 통합_사용자_관리 (이름 조회)
                users_ws = doc.worksheet(self.worksheet_users)
                users = users_ws.get_all_records()
                user_info = next((r for r in users if str(r.get("Unique_ID", "")).strip() == unique_id), None)
                if not user_info:
                    return None
                
                # 2. 회원_정보 (Web_ID, 닉네임, 이메일)
                members_ws = doc.worksheet(self.worksheet_members)
                members = members_ws.get_all_records()
                member_info = next((r for r in members if str(r.get("Unique_ID", "")).strip() == unique_id), {})
                
                # 3. 매칭_대기_라인 (스케줄)
                wait_ws = doc.worksheet(self.worksheet_waiting)
                waits = wait_ws.get_all_records()
                wait_info = next((r for r in waits if str(r.get("Unique_ID", "")).strip() == unique_id), {})
                
                return {
                    "unique_id": unique_id,
                    "name": user_info.get("이름", ""),
                    "web_id": member_info.get("Web_ID", ""),
                    "nickname": member_info.get("닉네임", ""),
                    "email": member_info.get("이메일", ""),
                    "schedule": wait_info.get("주간_활동_가능_시간", "")
                }

            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            log.error(f"[get_user_profile] 실패: {e}")
            return None

    async def update_user_profile(self, unique_id: str, nickname: str, email: str, schedule: str) -> bool:
        """내정보 업데이트 (회원_정보 및 매칭_대기_라인)"""
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _update():
                doc = client.open_by_key(self.spreadsheet_id)
                
                # 1. 회원_정보 업데이트 (닉네임, 이메일)
                # 컬럼: 1:Web_ID, 2:닉네임, 3:Unique_ID, ..., 9:이메일, 10:프로필이미지
                members_ws = doc.worksheet(self.worksheet_members)
                members = members_ws.get_all_records()
                for i, row in enumerate(members):
                    if str(row.get("Unique_ID", "")).strip() == unique_id:
                        members_ws.update_cell(i + 2, 2, nickname)
                        members_ws.update_cell(i + 2, 9, email)
                        break
                        
                # 2. 매칭_대기_라인 업데이트 (스케줄)
                # 컬럼: 1:Unique_ID, ..., 8:주간_활동_가능_시간
                wait_ws = doc.worksheet(self.worksheet_waiting)
                waits = wait_ws.get_all_records()
                for i, row in enumerate(waits):
                    if str(row.get("Unique_ID", "")).strip() == unique_id:
                        wait_ws.update_cell(i + 2, 8, schedule)
                        break
                        
                return True

            return await loop.run_in_executor(None, _update)
        except Exception as e:
            log.error(f"[update_user_profile] 실패: {e}")
            return False

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
        통합_사용자_관리 탭의 해당 Unique_ID 행에 6자리 인증키를 생성하여 K열(인증키)에 저장.
        행이 없으면 None 반환.
        """
        if not self._is_configured():
            return None
            
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(6))
        
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _update():
                # 통합_사용자_관리 시트
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_users)
                all_values = sheet.get_all_values()
                if len(all_values) < 2:
                    return False
                # 1행(헤더) 제외
                for idx, row in enumerate(all_values[1:], start=2):
                    # A열(인덱스 0) = Unique_ID
                    if len(row) > 0 and str(row[0]).strip().upper() == unique_id.upper():
                        sheet.update_cell(idx, 11, code)  # K열(열 11): 인증키
                        return True
                return False

            success = await loop.run_in_executor(None, _update)
            return code if success else None
        except Exception as e:
            log.error(f"[generate_link_code] 실패: {e}")
            return None

    async def verify_link_code(self, auth_input: str) -> str | None:
        """
        디스코드 인증 시 auth_input 검증 (2단계 조회).

        1단계: 통합_사용자_관리 시트에서 Unique_ID(A열) 또는 인증키(K열) 일치 확인
        2단계: 1단계 실패 시 회원_정보 시트에서 Web_ID(A열) 일치 → 매핑된 Unique_ID(C열) 반환

        이를 통해 사용자가 Web_ID(웹 아이디), Unique_ID(DUS-...), 인증키(6자리) 중
        어느 것으로든 디스코드 인증을 통과할 수 있다.
        """
        if not self._is_configured():
            return None

        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _verify():
                doc = client.open_by_key(self.spreadsheet_id)

                # ── 1단계: 통합_사용자_관리 — Unique_ID 또는 인증키 조회 ──────────
                sheet_users = doc.worksheet(self.worksheet_users)
                all_values = sheet_users.get_all_values()
                if len(all_values) >= 2:
                    for row in all_values[1:]:
                        # A(0):Unique_ID | K(10):인증키
                        if len(row) > 0:
                            uid = str(row[0]).strip()
                            code = str(row[10]).strip() if len(row) > 10 else ""
                            if uid and (
                                auth_input.upper() == uid.upper()
                                or (code and auth_input.upper() == code.upper())
                            ):
                                log.info(f"[verify_link_code] 1단계 인증 성공 (Unique_ID/인증키): {uid}")
                                return uid

                # ── 2단계: 회원_정보 — Web_ID로 Unique_ID 역참조 ──────────────────
                # 컬럼: A=Web_ID, B=닉네임, C=Unique_ID, D=Discord_ID, E=연동_코드, F=Auth_Status, G=가입일자, ...
                sheet_members = doc.worksheet(self.worksheet_members)
                member_values = sheet_members.get_all_values()
                if len(member_values) >= 2:
                    for row in member_values[1:]:
                        if len(row) > 0:
                            web_id = str(row[0]).strip()
                            mapped_uid = str(row[2]).strip() if len(row) > 2 else ""
                            if web_id and auth_input.strip() == web_id and mapped_uid:
                                log.info(f"[verify_link_code] 2단계 인증 성공 (Web_ID → Unique_ID): {web_id} → {mapped_uid}")
                                return mapped_uid

                log.warning(f"[verify_link_code] 인증 실패: 입력값 '{auth_input}'와 일치하는 항목 없음")
                return None

            return await loop.run_in_executor(None, _verify)
        except Exception as e:
            log.error(f"[verify_link_code] 실패: {e}")
            return None

    # ══════════════════════════════════════════════════════════════
    #  Phase 1 - 매칭 결과 구글 시트 동기화
    # ══════════════════════════════════════════════════════════════

    async def update_match_status(
        self,
        unique_ids: list[str],
        status: str = "매칭완료",
    ) -> bool:
        """
        매칭 완료 시 매칭_대기_라인의 Match_Status를 일괄 갱신.
        unique_ids: 매칭된 유저들의 Unique_ID 목록
        status: '매칭완료' | '대기' 등
        """
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _update():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_waiting)
                all_values = sheet.get_all_values()
                if len(all_values) < 2:
                    return False
                header = all_values[0]
                try:
                    uid_col = header.index("Unique_ID") + 1
                    status_col = header.index("Match_Status") + 1
                except ValueError:
                    uid_col, status_col = 1, 9  # fallback

                updated = 0
                for i, row in enumerate(all_values[1:], start=2):
                    if len(row) >= uid_col and str(row[uid_col - 1]).strip() in unique_ids:
                        sheet.update_cell(i, status_col, status)
                        updated += 1
                return updated > 0

            return await loop.run_in_executor(None, _update)
        except Exception as e:
            log.error(f"[update_match_status] 실패: {e}")
            return False

    async def record_team_result(self, team_data: dict) -> bool:
        """
        매칭 완료된 팀 정보를 팀_관리_라인에 기록.
        team_data 키:
          team_id, leader_unique_id, leader_name, department, program,
          summary, description, current_members, target_members, team_status
        """
        if not self._is_configured():
            return False
        try:
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self._get_client)
            now = datetime.now(timezone.utc).isoformat()

            team_row = [
                team_data.get("team_id", ""),
                team_data.get("leader_unique_id", ""),
                team_data.get("leader_name", ""),
                team_data.get("department", ""),
                team_data.get("program", ""),
                team_data.get("summary", "자동 매칭"),
                team_data.get("description", ""),
                team_data.get("current_members", 1),
                team_data.get("target_members", 4),
                team_data.get("team_status", "결성완료"),
                now,
            ]

            def _append():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_team_line)
                sheet.append_row(team_row)
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"[record_team_result] 실패: {e}")
            return False

    def build_team_report(self, members: list[dict], cached_sheets: dict) -> str:
        """
        매칭 완료 후 팀 채널에 게시할 팀 리포트 텍스트 생성.
        순차적 조건부 조회 (Fallback Search)를 이용해 구글 시트에서 최신 데이터를 가져옴.
        """
        lines = ["📋 **팀 구성 리포트**\n"]
        for i, m in enumerate(members, start=1):
            d_id = m.get("discord_id", "")
            is_leader = bool(m.get("is_leader", 0))
            
            # Fallback 데이터 조회
            name = self.get_fallback_data(cached_sheets, discord_id=d_id, field="이름", is_leader=is_leader)
            dept = self.get_fallback_data(cached_sheets, discord_id=d_id, field="학과", is_leader=is_leader)
            skill = self.get_fallback_data(cached_sheets, discord_id=d_id, field="특기", is_leader=is_leader)
            schedule_str = self.get_fallback_data(cached_sheets, discord_id=d_id, field="주간_시간표", is_leader=is_leader)
            contact_str = self.get_fallback_data(cached_sheets, discord_id=d_id, field="연락수단", is_leader=is_leader)
            student_id = self.get_fallback_data(cached_sheets, discord_id=d_id, field="학번", is_leader=is_leader)

            # 학번 마스킹 로직 (ex: 20230750 -> 2023****)
            if student_id != "미기재" and len(student_id) > 4:
                student_id_masked = student_id[:4] + "*" * (len(student_id) - 4)
            else:
                student_id_masked = student_id if student_id != "미기재" else "미기재"

            lines.append(
                f"**{i}. {name}** ({dept} / 학번: {student_id_masked})\n"
                f"   🔧 특기: {skill}\n"
                f"   📅 활동 가능 시간: {schedule_str}\n"
                f"   📞 연락 수단: {contact_str}"
            )
        return "\n\n".join(lines)
