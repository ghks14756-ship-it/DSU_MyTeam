"""
config.py - 환경 변수 및 전역 설정 관리
.env 파일에서 민감한 정보를 로드한다.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 자동 로드


class Config:
    # ── Discord ──────────────────────────────────
    BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "YOUR_TOKEN_HERE")

    # ── Database ─────────────────────────────────
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/dsu_myteam.db")

    # ── Google Sheets (선택 사항) ─────────────────
    GSHEET_CREDENTIALS_FILE: str = os.getenv("GSHEET_CREDENTIALS", "credentials.json")
    GSHEET_SPREADSHEET_ID: str = os.getenv("GSHEET_SPREADSHEET_ID", "")
    # ── AI (Google Gemini) ────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── TTL 설정 ──────────────────────────────────
    APPLICATION_TTL_HOURS: int = 168         # 신청 유효 시간 = 7일(168h)
    TTL_CHECK_INTERVAL_SECONDS: int = 300    # 만료 체크 주기 (5분)

    # ── 매칭 시스템 ───────────────────────────────
    MATCH_CHECK_INTERVAL_SECONDS: int = 60   # 이벤트 드리븐 매칭 체크 주기 (1분)
    DAY3_REMIND_HOURS: int = 72              # 3일 경과 시 DM 알림 (72h)
    DAY3_REMIND_CHECK_INTERVAL: int = 300    # 3일 체크 주기 (5분)
    MIN_QUEUE_SIZE_FOR_MATCH: int = 2        # 자동 매칭 최소 대기자 수

    # ── 채널/역할 이름 템플릿 ─────────────────────
    TEAM_TEXT_CHANNEL_PREFIX: str = "팀-텍스트"
    TEAM_VOICE_CHANNEL_PREFIX: str = "팀-보이스"
    TEAM_CATEGORY_NAME: str = "🔒 MYDEX 팀룸"

    # ── 랜덤 매칭 ─────────────────────────────────
    DEFAULT_TEAM_SIZE: int = 4               # 기본 팀 인원
    DEADLINE_WARNING_HOURS: int = 6          # 마감 N시간 전 경고

    # ── 테스트 모드 ───────────────────────────────
    # TODO(테스트 종료 시 반드시 False로 변경할 것!)
    ALLOW_MULTIPLE_APPLICATIONS: bool = True # 1인 1신청(중복 신청) 허용 여부 토글
