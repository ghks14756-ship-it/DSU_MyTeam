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
    # ── /상태조회 ─────────────────────────────────────────────────
    @app_commands.command(name="상태조회", description="[관리자] 특정 유저의 인증 및 매칭 상태를 조회합니다")
    @app_commands.describe(search_id="Unique_ID(DUS-...) 또는 Discord_ID 입력")
    @app_commands.default_permissions(administrator=True)
    async def user_status(self, interaction: discord.Interaction, search_id: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        status_data = await self.bot.gsheet.check_user_status(search_id.strip())
        
        if "error" in status_data:
            await interaction.followup.send(f"❌ 조회 중 오류 발생: {status_data['error']}", ephemeral=True)
            return
            
        user_info = status_data.get("user_info")
        waiting_info = status_data.get("waiting_info")
        
        if not user_info and not waiting_info:
            await interaction.followup.send(f"❌ '{search_id}' 에 해당하는 유저 기록을 찾을 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔍 유저 상태 조회: {search_id}",
            color=discord.Color.green() if user_info and user_info.get("Auth_Status") == "인증완료" else discord.Color.orange()
        )
        
        if user_info:
            uid = user_info.get("Unique_ID", "N/A")
            name = user_info.get("이름", "N/A")
            auth_status = user_info.get("Auth_Status", "미인증")
            discord_id = user_info.get("Discord_ID", "미연동")
            
            val = f"**이름**: {name}\n**Unique ID**: {uid}\n**Discord ID**: {discord_id}\n**인증 상태**: `{auth_status}`"
            embed.add_field(name="👤 통합 사용자 관리 (기본 정보)", value=val, inline=False)
            
        if waiting_info:
            match_status = waiting_info.get("Match_Status", "알 수 없음")
            req_date = waiting_info.get("신청일시", "N/A")
            
            val = f"**매칭 상태**: `{match_status}`\n**신청 일시**: {req_date}"
            embed.add_field(name="🕒 매칭 대기 라인", value=val, inline=False)
        else:
            embed.add_field(name="🕒 매칭 대기 라인", value="대기열 기록 없음 (매칭 완료되었거나 신청하지 않음)", inline=False)

        # 로컬 DB 조회
        try:
            async with self.bot.db._conn.execute(
                "SELECT discord_id, is_matched, created_at FROM applications WHERE discord_id = ? OR discord_id = ?",
                (search_id, f"WEB_{search_id}")
            ) as cursor:
                db_row = await cursor.fetchone()
                
            if db_row:
                val = f"**DB ID**: {db_row[0]}\n**매칭 완료 여부**: {'예 (1)' if db_row[1] else '대기중 (0)'}\n**생성일**: {db_row[2]}"
                embed.add_field(name="💾 로컬 캐시 DB", value=val, inline=False)
            else:
                embed.add_field(name="💾 로컬 캐시 DB", value="DB에 해당 ID로 등록된 정보 없음", inline=False)
        except Exception as e:
            log.error(f"DB 조회 오류: {e}")
            embed.add_field(name="💾 로컬 캐시 DB", value="조회 실패", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /팀룸초기화 ───────────────────────────────────────────────
    @app_commands.command(
        name="팀룸초기화",
        description="[관리자] 🔒 MYDEX 팀룸 카테고리 안의 더미 채널을 모두 삭제합니다"
    )
    @app_commands.default_permissions(administrator=True)
    async def clear_team_rooms(self, interaction: discord.Interaction) -> None:
        """팀룸 카테고리 내 채널 목록을 미리 보여주고 확인 후 전체 삭제."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        category = discord.utils.get(guild.categories, name=Config.TEAM_CATEGORY_NAME)
        if not category:
            await interaction.followup.send(
                f"⚠️ `{Config.TEAM_CATEGORY_NAME}` 카테고리를 찾을 수 없습니다.",
                ephemeral=True,
            )
            return

        channels = category.channels
        if not channels:
            await interaction.followup.send(
                f"📭 `{Config.TEAM_CATEGORY_NAME}` 카테고리에 삭제할 채널이 없습니다.",
                ephemeral=True,
            )
            return

        # 삭제 대상 목록 미리 보여주기
        ch_list = "\n".join(f"  • `{ch.name}`" for ch in channels)
        embed = discord.Embed(
            title="🗑️ 팀룸 채널 전체 삭제 확인",
            description=(
                f"**`{Config.TEAM_CATEGORY_NAME}`** 카테고리 내\n"
                f"아래 채널 **{len(channels)}개**를 모두 삭제합니다.\n\n"
                f"{ch_list}\n\n"
                "⚠️ 이 작업은 되돌릴 수 없습니다."
            ),
            color=discord.Color.red(),
        )

        view = ConfirmClearView(category=category, channels=channels)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ── 확인 View ─────────────────────────────────────────────────────────────────
class ConfirmClearView(discord.ui.View):
    def __init__(self, category: discord.CategoryChannel, channels: list):
        super().__init__(timeout=30)
        self.category = category
        self.channels = list(channels)

    @discord.ui.button(label="✅ 전체 삭제 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        deleted, failed = 0, 0
        for ch in self.channels:
            try:
                await ch.delete(reason=f"팀룸초기화 명령어 ({interaction.user})")
                deleted += 1
                log.info(f"🗑️ 채널 삭제: #{ch.name}")
            except Exception as e:
                failed += 1
                log.error(f"채널 삭제 실패 [{ch.name}]: {e}")

        # 카테고리 안이 비었으면 카테고리도 삭제
        try:
            remaining = self.category.channels
            if not remaining:
                await self.category.delete(reason="팀룸초기화 후 빈 카테고리 자동 삭제")
                cat_msg = f"\n📁 빈 카테고리 `{self.category.name}`도 삭제되었습니다."
            else:
                cat_msg = f"\n📁 카테고리에 채널 {len(remaining)}개가 남아 있어 카테고리는 유지합니다."
        except Exception as e:
            cat_msg = f"\n⚠️ 카테고리 삭제 실패: {e}"

        result_lines = [f"✅ 삭제 완료: **{deleted}개**"]
        if failed:
            result_lines.append(f"❌ 삭제 실패: **{failed}개** (권한 문제일 수 있음)")
        result_lines.append(cat_msg)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.followup.send("\n".join(result_lines), ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("취소되었습니다.", ephemeral=True)
        self.stop()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
