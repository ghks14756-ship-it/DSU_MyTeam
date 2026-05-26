"""
services/gsheet_service.py
구글 시트 API 연동 서비스

수행 기능:
  1. '활동목록' 탭에서 MYDEX 활동 데이터 로드
  2. '신청현황' 탭에 유저 신청서 기록
  3. '신청현황' 탭의 72시간 TTL 체크 및 자동 삭제/만료 로직
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

log = logging.getLogger("DSUMyTeam.GSheet")


class GoogleSheetService:
    """구글 시트 DB 연동 및 TTL 관리 서비스."""

    def __init__(self):
        from config import Config
        self.credentials_file = Config.GSHEET_CREDENTIALS_FILE
        self.spreadsheet_id = Config.GSHEET_SPREADSHEET_ID
        self.worksheet_activities = "활동목록"
        self.worksheet_applications = "신청현황"

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

    # ── 활동 목록 로드 ──────────────────────────────────────────
    async def fetch_activities(self) -> List[Dict[str, Any]]:
        """구글 시트의 '활동목록' 탭을 읽어와 반환."""
        if not self.spreadsheet_id or self.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
            log.warning("GSHEET_SPREADSHEET_ID 미설정 -> 샘플 데이터 반환")
            return self._sample_activities()

        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(None, self._get_client)
            
            def _fetch():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_activities)
                # 헤더가 2행에 있을 수 있으므로 head=2 지정
                # 하지만 gspread의 get_all_records는 1행을 헤더로 봄. 
                # 수동으로 처리 (2행을 헤더로 사용)
                all_values = sheet.get_all_values()
                if len(all_values) < 2: return []
                
                headers = all_values[1] # 2행 (인덱스 1)
                data_rows = all_values[2:] # 3행부터 데이터
                
                res = []
                for row in data_rows:
                    item = {}
                    for i, h in enumerate(headers):
                        if i < len(row): item[h] = row[i]
                    res.append(item)
                return res

            rows = await loop.run_in_executor(None, _fetch)
            
            activities = []
            for row in rows:
                name = str(row.get("활동명", "")).strip()
                if not name: continue
                activities.append({
                    "name": name,
                    "description": str(row.get("설명", "")),
                    "deadline": str(row.get("마감일", "")) or None,
                    "max_members": int(row.get("최대인원", 0) or 0),
                })
            return activities
        except Exception as e:
            log.error(f"활동 목록 로드 실패: {e}")
            return self._sample_activities()

    # ── 신청 목록 로드 (동기화용) ──────────────────────────────────
    async def fetch_applications(self) -> List[Dict[str, Any]]:
        """구글 시트의 '신청현황' 탭을 읽어와 반환."""
        if not self.spreadsheet_id or self.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
            return []

        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(None, self._get_client)
            
            def _fetch():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_applications)
                all_values = sheet.get_all_values()
                if len(all_values) < 2: return []
                
                headers = all_values[1] # 2행 (인덱스 1)
                data_rows = all_values[2:] # 3행부터 데이터
                
                res = []
                for row in data_rows:
                    item = {}
                    for i, h in enumerate(headers):
                        if i < len(row): item[h.strip()] = row[i]
                    res.append(item)
                return res

            rows = await loop.run_in_executor(None, _fetch)
            
            applications = []
            for row in rows:
                discord_id = str(row.get("디스코드ID", "")).strip()
                username = str(row.get("이름", "")).strip()
                if not discord_id or not username: continue
                
                # '희망 활동' 또는 '활동명' 열을 매핑
                activity_name = str(row.get("희망 활동", row.get("활동명", ""))).strip()
                
                applications.append({
                    "discord_id": discord_id,
                    "username": username,
                    "student_id": str(row.get("학번", "")).strip(),
                    "department": str(row.get("학과", "")).strip(),
                    "skill": str(row.get("특기", row.get("특기/역할", ""))).strip(),
                    "activity_name": activity_name,
                    "applied_at": str(row.get("신청시간", "")).strip(),
                    "expires_at": str(row.get("만료시간", "")).strip(),
                    "status": str(row.get("상태", "")).strip(),
                })
            return applications
        except Exception as e:
            log.error(f"신청 목록 로드 실패: {e}")
            return []

    # ── 신청서 기록 ──────────────────────────────────────────
    async def record_application(self, data: Dict[str, Any]) -> bool:
        """
        '신청현황' 탭에 새 신청서 행 추가. (B열부터 기록을 위해 A열은 비움 없이 바로 시작)
        형식: [B:신청시간, C:디스코드ID, D:이름, E:학번, F:학과, G:특기, H:만료시간, I:상태]
        주의: 시트 자체가 B열부터 데이터가 시작되는 구조이므로, append_row 시 주의가 필요.
        유저가 시트 전체를 B열 시작으로 맞췄으므로, gspread가 A열을 건너뛸 수 있도록 
        데이터 앞에 빈 문자열 하나만 유지하거나, 특정 범위를 지정해야 함.
        
        사용자 피드백에 따라 빈 문자열 하나일 때 C열로 밀린다면, 빈 문자열 없이 처리해보고
        그래도 밀린다면 범위를 명시하겠습니다. 일단 빈 문자열을 제거합니다.
        """
        if not self.spreadsheet_id or self.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
            return False

        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(None, self._get_client)

            # 데이터 준비
            now = datetime.now(timezone.utc)
            expires = now + timedelta(hours=72)
            
            row_data = [
                now.isoformat(),
                str(data['discord_id']),
                data['username'],
                data['student_id'],
                data['department'],
                data['skill'],
                expires.isoformat(),
                "대기"
            ]

            def _append():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_applications)
                # B열부터 시작하게 하기 위해 range를 지정하거나, 
                # append_row의 첫 요소를 "" 로 두어 A열을 비우는 것이 표준입니다.
                # 하지만 C열로 밀렸다면, 시트 자체가 A열이 숨겨져 있거나 다른 설정이 있을 수 있습니다.
                # 여기서는 빈 문자열 하나를 추가하여 [A="", B=time, ...] 가 되도록 하되,
                # 만약 이전에도 이랬는데 C로 밀렸다면 이번엔 빈 문자열 없이 시도해 보겠습니다.
                sheet.append_row(row_data, table_range="B2") 
                return True

            return await loop.run_in_executor(None, _append)
        except Exception as e:
            log.error(f"신청서 시트 기록 실패: {e}")
            return False

    # ── 72h TTL 스캔 및 처리 ─────────────────────────────────────
    async def process_ttl_check(self) -> List[Tuple[str, str]]:
        """
        만료된 행을 찾아 삭제하고, 해당 유저 ID와 이름을 반환 (DM 알림용).
        헤더가 2행인 구조 고려.
        """
        if not self.spreadsheet_id or self.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
            return []

        expired_users = []
        try:
            loop = asyncio.get_event_loop()
            client = await loop.run_in_executor(None, self._get_client)

            def _check_and_delete():
                sheet = client.open_by_key(self.spreadsheet_id).worksheet(self.worksheet_applications)
                all_values = sheet.get_all_values()
                if len(all_values) < 3: return [] # 데이터가 없음 (헤더 2행 + 데이터 0행)
                
                headers = all_values[1]
                now = datetime.now(timezone.utc)
                
                rows_to_delete = []
                # 3행(인덱스 2)부터 실제 데이터
                for i in range(2, len(all_values)):
                    row = all_values[i]
                    try:
                        # 헤더 위치 기반으로 데이터 추출
                        # B열(신청시간)은 인덱스 1, H열(만료시간)은 인덱스 7
                        expire_str = row[7] if len(row) > 7 else None
                        if not expire_str: continue
                        
                        expires = datetime.fromisoformat(expire_str)
                        if now > expires:
                            # 만료됨
                            discord_id = row[2] if len(row) > 2 else "알수없음"
                            username = row[3] if len(row) > 3 else "알수없음"
                            expired_users.append((str(discord_id), username))
                            rows_to_delete.append(i + 1) # 1-based sheet row
                    except Exception:
                        continue
                
                # 삭제 (역순)
                for row_idx in sorted(rows_to_delete, reverse=True):
                    sheet.delete_rows(row_idx)
                
                return expired_users

            return await loop.run_in_executor(None, _check_and_delete)
        except Exception as e:
            log.error(f"TTL 시트 체크 실패: {e}")
            return []

    def _sample_activities(self) -> List[Dict[str, Any]]:
        return [
            {"name": "캡스톤디자인 A반", "description": "졸업작품 팀 구성", "deadline": "2025-09-30", "max_members": 4},
            {"name": "창업경진대회", "description": "교내 스타트업 아이디어 공모전", "deadline": "2025-10-15", "max_members": 5},
        ]
