"""
cogs/menu.py
카드 버튼 메인 메뉴

/메뉴 명령어 하나로 모든 기능을 버튼 카드로 접근할 수 있는
대시보드 임베드를 표시한다.
슬래시 커맨드를 직접 입력할 필요 없이 버튼 클릭만으로 진행.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("DSUMyTeam.Menu")


# ─────────────────────────────────────────────
#  메인 메뉴 버튼 View
# ─────────────────────────────────────────────
class MainMenuView(discord.ui.View):
    """
    각 기능으로 진입하는 버튼 카드 모음.
    timeout=None → 봇 재시작 전까지 유지.
    """

    def __init__(self):
        super().__init__(timeout=None)  # 영구 지속

    # ── 신청 버튼 ─────────────────────────────────────────────────
    @discord.ui.button(
        label="팀 매칭 신청",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="menu:apply",
        row=0,
    )
    async def btn_apply(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """/신청 과 동일한 흐름 시작."""
        from cogs.application import ActivitySelectView, SkillSelectView

        activities = await interaction.client.db.get_active_activities()
        if not activities:
            view = SkillSelectView(activity_id=None)
            await interaction.response.send_message(
                "**특기 / 역할을 선택해 주세요** 🌟\n목록에 없다면 **✏️ 기타**를 선택하세요.",
                view=view,
                ephemeral=True,
            )
            return
        view = ActivitySelectView(activities)
        await interaction.response.send_message(
            "**① 단계 — 활동 선택**\n참가할 MYDEX 활동을 골라주세요 📋",
            view=view,
            ephemeral=True,
        )

    # ── 내 신청 확인 버튼 ─────────────────────────────────────────
    @discord.ui.button(
        label="내 신청 확인",
        emoji="🔍",
        style=discord.ButtonStyle.secondary,
        custom_id="menu:my_apply",
        row=0,
    )
    async def btn_my_apply(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        record = await interaction.client.db.get_application(str(interaction.user.id))
        if not record:
            await interaction.response.send_message(
                "📭 현재 신청된 정보가 없습니다.\n**📝 팀 매칭 신청** 버튼으로 등록해 주세요.",
                ephemeral=True,
            )
            return

        from datetime import datetime, timezone
        from cogs.application import SKILL_OPTIONS
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(record["expires_at"])
        hours = max(0, int((expires - now).total_seconds() // 3600))
        minutes = max(0, int(((expires - now).total_seconds() % 3600) // 60))
        skill_emoji = next((e for e, l, _ in SKILL_OPTIONS if l == record["skill"]), "⭐")

        embed = discord.Embed(
            title="📋 내 팀 매칭 신청 현황",
            color=discord.Color.green() if hours > 12 else discord.Color.orange(),
        )
        embed.add_field(name="👤 이름",   value=record["username"],   inline=True)
        embed.add_field(name="🎓 학번",   value=record["student_id"], inline=True)
        embed.add_field(name="🏫 학과",   value=record["department"], inline=True)
        embed.add_field(name=f"{skill_emoji} 특기", value=record["skill"], inline=True)
        embed.add_field(name="⏳ 남은 시간", value=f"`{hours}시간 {minutes}분`", inline=True)
        embed.add_field(
            name="🔗 매칭 상태",
            value="✅ 매칭 완료" if record["is_matched"] else "🔄 대기 중",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 신청 취소 버튼 ────────────────────────────────────────────
    @discord.ui.button(
        label="신청 취소",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="menu:cancel_apply",
        row=0,
    )
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        record = await interaction.client.db.get_application(str(interaction.user.id))
        if not record:
            await interaction.response.send_message("📭 취소할 신청 내역이 없습니다.", ephemeral=True)
            return

        # 취소 확인 View
        confirm = CancelConfirmView(record)
        await interaction.response.send_message(
            f"⚠️ **신청을 정말 취소하시겠습니까?**\n"
            f"> 이름: {record['username']} | 특기: {record['skill']}",
            view=confirm,
            ephemeral=True,
        )

    # ── 그룹 생성 버튼 ────────────────────────────────────────────
    @discord.ui.button(
        label="그룹 코드 생성",
        emoji="👥",
        style=discord.ButtonStyle.success,
        custom_id="menu:group_create",
        row=1,
    )
    async def btn_group_create(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """그룹 초대 코드 생성 흐름 시작."""
        activities = await interaction.client.db.get_active_activities()
        if not activities:
            await interaction.response.send_message(
                "⚠️ 활동 목록이 없습니다. 관리자에게 `/최신화`를 요청해 주세요.", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=a["name"][:100], value=str(a["id"]))
            for a in activities[:25]
        ]

        class ActivitySelect(discord.ui.View):
            @discord.ui.select(placeholder="그룹 신청할 활동 선택", options=options)
            async def select(self_inner, sel_interaction: discord.Interaction, sel: discord.ui.Select):
                activity_id = int(sel.values[0])
                code = await sel_interaction.client.db.create_group_invite(
                    creator_id=str(sel_interaction.user.id),
                    activity_id=activity_id,
                )
                embed = discord.Embed(
                    title="🎫 그룹 초대 코드 발급",
                    description=(
                        f"아래 코드를 친구들에게 공유하세요!\n\n"
                        f"## `{code}`\n\n"
                        f"친구들이 **그룹 코드 참가** 버튼 또는 `/그룹참가 {code}` 로 합류할 수 있습니다.\n"
                        f"코드 유효 기간: **72시간**"
                    ),
                    color=discord.Color.from_rgb(87, 242, 135),
                )
                embed.set_footer(text="멤버가 모이면 조장에게 일괄 신청됩니다!")
                await sel_interaction.response.send_message(embed=embed, ephemeral=True)
                self_inner.stop()

        await interaction.response.send_message(
            "활동을 선택하면 초대 코드를 발급합니다.", view=ActivitySelect(), ephemeral=True
        )

    # ── 그룹 참가 버튼 ────────────────────────────────────────────
    @discord.ui.button(
        label="그룹 코드 참가",
        emoji="🔑",
        style=discord.ButtonStyle.success,
        custom_id="menu:group_join",
        row=1,
    )
    async def btn_group_join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(GroupCodeModal())

    # ── 팀 방 생성 버튼 (조장용) ──────────────────────────────────
    @discord.ui.button(
        label="팀 방 생성 (조장)",
        emoji="🏠",
        style=discord.ButtonStyle.primary,
        custom_id="menu:create_room",
        row=2,
    )
    async def btn_create_room(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """조장 팀 방 생성 흐름 시작."""
        activities = await interaction.client.db.get_active_activities()
        if not activities:
            await interaction.response.send_message(
                "⚠️ 등록된 활동이 없습니다. `/최신화`로 목록을 갱신해 주세요.", ephemeral=True
            )
            return

        from cogs.team_room import TeamRoomModal
        options = [
            discord.SelectOption(label=a["name"][:100], value=str(a["id"]))
            for a in activities[:25]
        ]

        class RoomActivitySelect(discord.ui.View):
            @discord.ui.select(placeholder="방을 생성할 활동 선택", options=options)
            async def select(self_inner, sel_interaction: discord.Interaction, sel: discord.ui.Select):
                await sel_interaction.response.send_modal(TeamRoomModal(int(sel.values[0])))
                self_inner.stop()

        await interaction.response.send_message(
            "📋 방을 생성할 활동을 선택해 주세요.", view=RoomActivitySelect(), ephemeral=True
        )

    # ── 활동 목록 버튼 ────────────────────────────────────────────
    @discord.ui.button(
        label="활동 목록",
        emoji="📚",
        style=discord.ButtonStyle.secondary,
        custom_id="menu:activities",
        row=2,
    )
    async def btn_activities(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        activities = await interaction.client.db.get_active_activities()
        if not activities:
            await interaction.response.send_message(
                "📭 등록된 활동이 없습니다. 관리자에게 문의해 주세요.", ephemeral=True
            )
            return

        embed = discord.Embed(title="📚 MYDEX 활동 목록", color=discord.Color.from_rgb(254, 231, 92))
        for act in activities[:25]:
            embed.add_field(
                name=f"📌 {act['name']}",
                value=f"마감: `{act.get('deadline') or '미정'}` | 최대 {act['max_members']}명",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  취소 확인 View
# ─────────────────────────────────────────────
class CancelConfirmView(discord.ui.View):
    def __init__(self, record: dict):
        super().__init__(timeout=30)
        self.record = record

    @discord.ui.button(label="네, 취소합니다", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.client.db.delete_application(str(interaction.user.id))
        await interaction.response.edit_message(content="🗑️ 신청이 취소되었습니다.", view=None)
        self.stop()

    @discord.ui.button(label="아니오", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="✅ 취소 요청이 철회되었습니다.", view=None)
        self.stop()


# ─────────────────────────────────────────────
#  그룹 코드 입력 Modal
# ─────────────────────────────────────────────
class GroupCodeModal(discord.ui.Modal, title="🔑 그룹 초대 코드 입력"):
    code = discord.ui.TextInput(
        label="초대 코드 (6자리)",
        placeholder="예) A3F2B1",
        min_length=6,
        max_length=6,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        import json
        raw_code = self.code.value.strip().upper()
        success, message = await interaction.client.db.join_group(
            code=raw_code, discord_id=str(interaction.user.id)
        )
        icon = "✅" if success else "❌"
        await interaction.response.send_message(f"{icon} {message}", ephemeral=True)

        if success:
            invite = await interaction.client.db.get_group_invite(raw_code)
            if invite:
                try:
                    creator = await interaction.client.fetch_user(int(invite["creator_id"]))
                    members = json.loads(invite["members"])
                    await creator.send(
                        f"👥 **그룹 `{raw_code}`** 에 새 멤버가 참가했습니다!\n"
                        f"참가자: {interaction.user.display_name} | 현재 {len(members)}명"
                    )
                except Exception:
                    pass


# ─────────────────────────────────────────────
#  Cog 클래스
# ─────────────────────────────────────────────
class MenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇 재시작 후에도 버튼이 작동하도록 영구 View 등록
        bot.add_view(MainMenuView())

    @app_commands.command(name="메뉴", description="DSU My_team 기능 메뉴를 버튼으로 엽니다")
    async def menu(self, interaction: discord.Interaction) -> None:
        """모든 기능을 버튼 카드로 한눈에 접근할 수 있는 메인 메뉴."""
        embed = discord.Embed(
            title="🏫 DSU My_team — MYDEX 팀 매칭",
            description=(
                "동서대학교 MYDEX 팀 매칭 시스템입니다.\n"
                "아래 버튼을 클릭하여 원하는 기능을 사용하세요!"
            ),
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(
            name="📝  팀 매칭 신청",
            value="활동 선택 → 특기 카드 선택 → 정보 입력 (72시간 유효)",
            inline=False,
        )
        embed.add_field(
            name="👥  그룹 신청",
            value="친구끼리 초대 코드로 묶어 조장에게 일괄 신청",
            inline=False,
        )
        embed.add_field(
            name="🏠  팀 방 생성",
            value="조장이 조건 설정 → AI 적합도 분석 → 채널 자동 생성",
            inline=False,
        )
        embed.set_footer(text="DSU My_team · 24h 운영 · 72시간 데이터 TTL")

        await interaction.response.send_message(
            embed=embed,
            view=MainMenuView(),
            ephemeral=True,
        )

    @app_commands.command(name="공지메뉴", description="[관리자] 채널에 영구 메뉴 임베드를 게시합니다")
    @app_commands.default_permissions(administrator=True)
    async def post_public_menu(self, interaction: discord.Interaction) -> None:
        """
        관리자가 특정 채널에 영구 버튼 메뉴를 게시.
        봇을 재시작해도 버튼이 유지됨 (custom_id 기반).
        """
        embed = discord.Embed(
            title="🏫 DSU My_team — MYDEX 팀 매칭 시스템",
            description=(
                "아래 버튼을 클릭하면 텍스트 명령어 입력 없이\n"
                "모든 기능을 바로 사용할 수 있습니다! 👇"
            ),
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(name="📝 팀 매칭 신청", value="72시간 TTL · 언제든 재신청 가능", inline=True)
        embed.add_field(name="👥 그룹 신청",    value="초대 코드로 친구와 함께 신청", inline=True)
        embed.add_field(name="🏠 팀 방 생성",   value="조장 전용 · AI 매칭 리포트 포함", inline=True)
        embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")

        await interaction.channel.send(embed=embed, view=MainMenuView())
        await interaction.response.send_message("✅ 메뉴가 채널에 게시되었습니다.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MenuCog(bot))
