"""
╔══════════════════════════════════════════════════════════════════╗
║            DSU My_team - 동서대학교 MYDEX 팀 매칭 봇              ║
║                     Discord.py 기반 메인 봇                       ║
╚══════════════════════════════════════════════════════════════════╝

실행: python main.py
의존: pip install -r requirements.txt
"""

import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config import Config
from database.db_manager import DatabaseManager
from services.gsheet_service import GoogleSheetService
from tasks.scheduler import TTLScheduler

# ─────────────────────────────────────────────
#  로깅 설정
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("DSUMyTeam")


# ─────────────────────────────────────────────
#  봇 클래스 정의
# ─────────────────────────────────────────────
class DSUMyTeamBot(commands.Bot):
    """DSU My_team 메인 봇 클래스."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",          # 슬래시 커맨드 우선 → prefix는 fallback
            intents=intents,
            description="동서대학교 MYDEX 팀 매칭 시스템",
        )
        self.db: DatabaseManager | None = None
        self.gsheet: GoogleSheetService = GoogleSheetService()
        self.ttl_scheduler: TTLScheduler | None = None

    # ── 초기화 (on_ready 이전에 실행됨) ──────────────────────────
    async def setup_hook(self) -> None:
        """
        봇 로그인 직후 한 번 실행되는 초기화 훅.
        DB 연결 → 스케줄러 시작 → Cog 로드 → 슬래시 커맨드 동기화 순서로 진행.
        """
        log.info("⚙️  초기화 시작...")

        # 1. DB 초기화
        self.db = DatabaseManager(Config.DATABASE_PATH)
        await self.db.init()
        log.info("✅ 데이터베이스 초기화 완료")

        # 2. 72시간 TTL 스케줄러 시작
        self.ttl_scheduler = TTLScheduler(self)
        self.ttl_scheduler.start()
        log.info("✅ TTL 스케줄러 시작 완료 (만료 체크 주기: 5분)")

        # 3. Cog(기능 모듈) 로드
        await self._load_cogs()

        # 4. 슬래시 커맨드 동기화
        # 전역 sync (배포용, 최대 1시간 딜레이)
        synced = await self.tree.sync()
        log.info(f"✅ 슬래시 커맨드 전역 동기화 완료: {len(synced)}개")

        # 5. 웹 API 서버 구동 (aiohttp)
        try:
            from aiohttp import web
            from api.routes import setup_api
            
            self.web_app = web.Application()
            setup_api(self.web_app, self)
            
            self.runner = web.AppRunner(self.web_app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', 8080)
            await self.site.start()
            log.info("✅ 웹 API 서버(aiohttp) 구동 완료 (포트: 8080)")
        except Exception as e:
            log.error(f"❌ 웹 API 서버 구동 실패: {e}")

    async def _load_cogs(self) -> None:
        """cogs/ 디렉토리 내 모든 Cog를 자동 로드."""
        cog_dir = Path("cogs")
        cog_files = [
            "menu",           # 카드 버튼 메인 메뉴 (/메뉴, /공지메뉴)
            "application",    # /신청 명령어 + Modal + 특기 카드 Select
            "team_room",      # 조장 방 생성 + AI 리포트
            "random_match",   # 매칭 엔진 v2 (이벤트 드리븐 + 우선순위 큐)
            "group_apply",    # 그룹 신청 (초대코드)
            "admin",          # /최신화 등 관리자 명령어
            "auth",           # 고유 ID 인증
        ]
        for cog_name in cog_files:
            try:
                await self.load_extension(f"cogs.{cog_name}")
                log.info(f"  📦 Cog 로드: cogs.{cog_name}")
            except Exception as e:
                log.error(f"  ❌ Cog 로드 실패 [{cog_name}]: {e}")

    # ── 이벤트 핸들러 ─────────────────────────────────────────────
    async def on_ready(self) -> None:
        log.info(f"🚀 봇 온라인: {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="팀 매칭 대기 중 👀",
            )
        )

        # 길드(서버) 단위 즉시 동기화 — 새 명령어가 수 초 내 채팅 목록에 표시됨
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                guild_synced = await self.tree.sync(guild=guild)
                log.info(f"✅ [{guild.name}] 길드 명령어 즉시 동기화: {len(guild_synced)}개")
            except Exception as e:
                log.error(f"❌ [{guild.name}] 길드 명령어 동기화 실패: {e}")

    async def on_command_error(self, ctx, error) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        log.error(f"명령어 오류 [{ctx.command}]: {error}")

    async def close(self) -> None:
        """봇 종료 시 정리."""
        if hasattr(self, 'site') and self.site:
            await self.site.stop()
        if hasattr(self, 'runner') and self.runner:
            await self.runner.cleanup()
            
        if self.ttl_scheduler:
            self.ttl_scheduler.cancel()
        if self.db:
            await self.db.close()
        await super().close()
        log.info("봇 종료 완료.")


# ─────────────────────────────────────────────
#  엔트리포인트
# ─────────────────────────────────────────────
async def main():
    bot = DSUMyTeamBot()
    async with bot:
        await bot.start(Config.BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
