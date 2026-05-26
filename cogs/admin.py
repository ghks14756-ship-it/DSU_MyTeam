"""
cogs/admin.py
관리자 전용 명령어

  /최신화   : 구글 시트에서 활동 목록을 불러와 DB 갱신
  /대기목록  : 현재 매칭 대기 중인 신청자 현황 출력
  /활동목록  : 등록된 MYDEX 활동 목록 출력
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from services.gsheet_service import GoogleSheetService

log = logging.getLogger("DSUMyTeam.Admin")


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gsheet = GoogleSheetService()

    @app_commands.command(name="최신화", description="[관리자] 구글 시트에서 MYDEX 활동 및 신청 목록을 갱신합니다")
    @app_commands.default_permissions(administrator=True)
    async def refresh_activities(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # 1. 활동 목록 동기화
            activities = await self.gsheet.fetch_activities()
            act_count = await self.bot.db.upsert_activities(activities)
            
            # 2. 수동 입력된 신청 목록 동기화
            applications = await self.gsheet.fetch_applications()
            app_count = await self.bot.db.sync_applications_from_sheet(applications)
            
            await interaction.followup.send(
                f"✅ **{act_count}개** 활동 및 **{app_count}명**의 수동 대기 신청자가 갱신되었습니다!\n"
                f"드롭다운 메뉴는 다음 `/신청` 또는 `/방생성` 실행 시 자동 반영됩니다.",
                ephemeral=True,
            )
        except Exception as e:
            log.error(f"최신화 오류: {e}")
            await interaction.followup.send(
                f"❌ 갱신 실패: {e}\n"
                f"구글 시트 API 설정(`credentials.json`, `GSHEET_SPREADSHEET_ID`)을 확인해 주세요.",
                ephemeral=True,
            )

    # ── /대기목록 ─────────────────────────────────────────────────
    @app_commands.command(name="대기목록", description="[관리자] 현재 매칭 대기 중인 신청자 목록을 출력합니다")
    @app_commands.default_permissions(administrator=True)
    async def waiting_list(self, interaction: discord.Interaction) -> None:
        applicants = await self.bot.db.get_all_active_applications()

        if not applicants:
            await interaction.response.send_message("📭 현재 대기 중인 신청자가 없습니다.", ephemeral=True)
            return

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        embed = discord.Embed(
            title=f"📋 매칭 대기 목록 ({len(applicants)}명)",
            color=discord.Color.blurple(),
        )

        lines = []
        for i, app in enumerate(applicants[:20], 1):
            expires = datetime.fromisoformat(app["expires_at"])
            remaining_h = max(0, int((expires - now).total_seconds() // 3600))
            lines.append(
                f"`{i:02d}` **{app['username']}** | {app['department']} "
                f"| ⭐{app['skill']} | ⏰{remaining_h}h 남음"
            )

        embed.description = "\n".join(lines)
        if len(applicants) > 20:
            embed.set_footer(text=f"... 외 {len(applicants) - 20}명 더 있음")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /활동목록 ─────────────────────────────────────────────────
    @app_commands.command(name="활동목록", description="등록된 MYDEX 활동 목록을 확인합니다")
    async def activity_list(self, interaction: discord.Interaction) -> None:
        activities = await self.bot.db.get_active_activities()

        if not activities:
            await interaction.response.send_message(
                "📭 등록된 활동이 없습니다. 관리자에게 `/최신화`를 요청하세요.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📚 MYDEX 활동 목록",
            color=discord.Color.from_rgb(254, 231, 92),
        )
        for act in activities[:25]:
            deadline_str = act.get("deadline") or "미정"
            embed.add_field(
                name=f"📌 {act['name']}",
                value=f"마감: `{deadline_str}` | 최대 {act['max_members']}명",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
