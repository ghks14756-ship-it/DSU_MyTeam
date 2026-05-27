"""
cogs/admin.py
관리자 전용 명령어

  /최신화   : 디스코드 Modal로 새 활동 프로그램을 직접 입력하여 구글 시트에 등록
  /대기목록  : 구글 시트 매칭_대기_라인 기반 현재 대기 중인 신청자 현황 출력
  /활동목록  : 등록된 MYDEX 활동 목록 출력
"""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import Config

log = logging.getLogger("DSUMyTeam.Admin")


# ─────────────────────────────────────────────
#  /최신화 — 활동 프로그램 등록 Modal
# ─────────────────────────────────────────────
class AddProgramModal(discord.ui.Modal, title="📋 새 활동 프로그램 등록"):
    """
    관리자가 디스코드 Modal로 새 프로그램을 입력하면
    구글 시트 '활동_프로그램_관리' 탭에 신규 행으로 추가됩니다.
    """

    program_name = discord.ui.TextInput(
        label="프로그램명",
        placeholder="예) 캡스톤 디자인 특강",
        max_length=100,
        required=True,
    )
    apply_deadline = discord.ui.TextInput(
        label="신청일시 (마감)",
        placeholder="예) 2026.06.30 까지",
        max_length=50,
        required=True,
    )
    operation_date = discord.ui.TextInput(
        label="운영일시",
        placeholder="예) 2026.07.01(수) 14:00~16:00",
        max_length=100,
        required=True,
    )
    manager = discord.ui.TextInput(
        label="프로그램 담당자",
        placeholder="예) 소프트웨어학과 김교수",
        max_length=50,
        required=True,
    )
    notes = discord.ui.TextInput(
        label="전달사항 (선택)",
        placeholder="장소, 준비물 등 기타 안내사항",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot = interaction.client

        data = {
            "프로그램 내용": self.program_name.value.strip(),
            "신청일시": self.apply_deadline.value.strip(),
            "신청형태": "MYDEX 신청",
            "운영일시": self.operation_date.value.strip(),
            "만족도 실시기간": "운영 종료 후 1주일",
            "최대학습포인트": "",
            "신청대상": "",
            "신청구분": "비교과",
            "프로그램 담당자": self.manager.value.strip(),
            "첨부파일": "",
            "전달사항": self.notes.value.strip() if self.notes.value else "",
        }

        try:
            success = await bot.gsheet.add_program(data)
            if success:
                await interaction.followup.send(
                    f"✅ **'{self.program_name.value}'** 프로그램이 구글 시트에 성공적으로 등록되었습니다!\n"
                    f"> 웹사이트 캐러셀에 즉시 반영됩니다.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ 구글 시트 연동이 설정되지 않았습니다. `.env`의 `GSHEET_SPREADSHEET_ID`를 확인해 주세요.",
                    ephemeral=True,
                )
        except Exception as e:
            log.error(f"프로그램 등록 실패: {e}")
            await interaction.followup.send(f"❌ 등록 실패: {e}", ephemeral=True)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /최신화 ──────────────────────────────────────────────────
    @app_commands.command(name="최신화", description="[관리자] 새 MYDEX 활동 프로그램을 직접 입력하여 구글 시트에 등록합니다")
    @app_commands.default_permissions(administrator=True)
    async def refresh_activities(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AddProgramModal())

    # ── /대기목록 ─────────────────────────────────────────────────
    @app_commands.command(name="대기목록", description="[관리자] 현재 매칭 대기 중인 신청자 목록을 출력합니다")
    @app_commands.default_permissions(administrator=True)
    async def waiting_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            applicants = await self.bot.gsheet.fetch_applications()
        except Exception as e:
            log.error(f"대기목록 로드 실패: {e}")
            applicants = []

        # 구글 시트 실패 시 로컬 DB fallback
        if not applicants:
            applicants = await self.bot.db.get_all_active_applications()

        if not applicants:
            await interaction.followup.send("📭 현재 대기 중인 신청자가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 매칭 대기 목록 ({len(applicants)}명)",
            color=discord.Color.blurple(),
        )
        lines = []
        for i, app in enumerate(applicants[:20], 1):
            name = app.get("이름") or app.get("username", "?")
            dept = app.get("학과") or app.get("department", "?")
            skill = app.get("전문분야_특기") or app.get("skill", "?")
            lines.append(f"`{i:02d}` **{name}** | {dept} | ⭐{skill}")

        embed.description = "\n".join(lines)
        if len(applicants) > 20:
            embed.set_footer(text=f"... 외 {len(applicants) - 20}명 더 있음")

        await interaction.followup.send(embed=embed, ephemeral=True)

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
