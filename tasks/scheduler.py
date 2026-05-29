"""
tasks/scheduler.py
TTL 백그라운드 스케줄러

동작 원리:
  1. 5분마다 DB를 조회하여 expires_at이 지난 신청을 찾는다.
  2. 해당 유저에게 DM으로 만료 알림을 전송한다.
  3. DB에서 해당 레코드를 삭제한다.

  NOTE: 3일 DM 체크 및 자동 매칭 루프는 MatchEngineCog (cogs/random_match.py)에서 관리한다.
"""

import asyncio
import logging
from datetime import datetime, timezone

from discord.ext import tasks
import discord

from config import Config

log = logging.getLogger("DSUMyTeam.Scheduler")


class TTLScheduler:
    """7일 TTL 만료를 관리하는 백그라운드 태스크."""

    def __init__(self, bot):
        self.bot = bot
        self._task = tasks.loop(seconds=Config.TTL_CHECK_INTERVAL_SECONDS)(self._check_expired)

    def start(self) -> None:
        self._task.start()

    def cancel(self) -> None:
        self._task.cancel()

    async def _check_expired(self) -> None:
        """만료된 신청을 찾아 DM 알림 전송 후 DB에서 삭제."""
        await self.bot.wait_until_ready()

        if self.bot.db:
            expired_list = await self.bot.db.get_expired_applications()
            for record in expired_list:
                await self._send_expiry_dm(record["discord_id"], record)
                await self.bot.db.delete_application(record["discord_id"])
                log.info(f"  ✂️  DB 만료 삭제: {record['username']} ({record['discord_id']})")

            # 구글 시트 미동기화 결과가 있으면 재시도
            if self.bot.gsheet:
                unsynced = await self.bot.db.get_unsynced_results()
                for result in unsynced:
                    import json
                    try:
                        members = json.loads(result.get("members_json", "[]"))
                        unique_ids = [m.get("unique_id", "") for m in members if m.get("unique_id")]
                        if unique_ids:
                            await self.bot.gsheet.update_match_status(unique_ids, "매칭완료")
                        await self.bot.db.mark_sheet_synced(result["id"])
                        log.info(f"  📊 시트 재동기화 완료: result_id={result['id']}")
                    except Exception as e:
                        log.error(f"  ❌ 시트 재동기화 실패: {e}")

    async def _send_expiry_dm(self, discord_id: str, record: dict) -> None:
        """유저에게 7일 만료 DM 전송."""
        try:
            user = await self.bot.fetch_user(int(discord_id))
            if user is None:
                return

            embed = discord.Embed(
                title="⏰ 팀 매칭 신청이 만료되었습니다",
                description=(
                    "아래 신청 정보의 유효 기간(7일)이 종료되어 대기열에서 제거되었습니다.\n"
                    "팀 매칭을 원하시면 다시 등록해 주세요."
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="👤 이름", value=record.get("username", "?"), inline=True)
            embed.add_field(name="🏫 학과", value=record.get("department", "?"), inline=True)
            embed.add_field(name="⭐ 특기", value=record.get("skill", "?"), inline=True)
            embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")

            await user.send(embed=embed)

        except discord.Forbidden:
            log.warning(f"  ⚠️  DM 차단 유저: {discord_id}")
        except discord.NotFound:
            log.warning(f"  ⚠️  유저를 찾을 수 없음: {discord_id}")
        except Exception as e:
            log.error(f"  ❌ DM 전송 실패 [{discord_id}]: {e}")
