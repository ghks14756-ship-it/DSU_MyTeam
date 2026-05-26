"""
cogs/group_apply.py
그룹 신청 시스템 (초대 코드 기반)

플로우:
  코드 생성자가 /그룹생성 → 6자리 초대 코드 발급
  친구들이 /그룹참가 {코드} 입력 → 그룹 합류
  /그룹신청 으로 팀방에 일괄 신청
"""

import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("DSUMyTeam.GroupApply")


class GroupApplyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="그룹생성", description="친구들과 함께 신청할 그룹을 만들고 초대 코드를 생성합니다")
    async def create_group(self, interaction: discord.Interaction) -> None:
        activities = await self.bot.db.get_active_activities()

        if not activities:
            await interaction.response.send_message(
                "⚠️ 활동 목록이 비어있습니다. `/최신화`를 먼저 실행해 주세요.", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=a["name"][:100], value=str(a["id"]))
            for a in activities[:25]
        ]

        class ActivitySelect(discord.ui.View):
            @discord.ui.select(placeholder="그룹 신청할 활동 선택", options=options)
            async def select(self, sel_interaction: discord.Interaction, select: discord.ui.Select):
                activity_id = int(select.values[0])
                code = await sel_interaction.client.db.create_group_invite(
                    creator_id=str(sel_interaction.user.id),
                    activity_id=activity_id,
                )
                embed = discord.Embed(
                    title="🎫 그룹 초대 코드 발급",
                    description=(
                        f"아래 코드를 친구들에게 공유하세요!\n\n"
                        f"## `{code}`\n\n"
                        f"친구들은 `/그룹참가 {code}` 로 합류할 수 있습니다.\n"
                        f"코드 유효 기간: **72시간**"
                    ),
                    color=discord.Color.from_rgb(87, 242, 135),
                )
                embed.set_footer(text="그룹 멤버가 모두 모이면 /그룹신청 으로 조장에게 신청하세요!")
                await sel_interaction.response.send_message(embed=embed, ephemeral=True)
                self.stop()

        await interaction.response.send_message(
            "활동을 선택하면 초대 코드를 발급합니다.", view=ActivitySelect(), ephemeral=True
        )

    @app_commands.command(name="그룹참가", description="초대 코드로 친구 그룹에 합류합니다")
    @app_commands.describe(code="6자리 초대 코드")
    async def join_group(self, interaction: discord.Interaction, code: str) -> None:
        code = code.strip().upper()
        success, message = await self.bot.db.join_group(
            code=code, discord_id=str(interaction.user.id)
        )
        color = discord.Color.green() if success else discord.Color.red()
        icon = "✅" if success else "❌"

        await interaction.response.send_message(
            f"{icon} {message}", ephemeral=True
        )

        if success:
            # 그룹 생성자에게 DM 알림
            invite = await self.bot.db.get_group_invite(code)
            if invite:
                try:
                    creator = await self.bot.fetch_user(int(invite["creator_id"]))
                    members = json.loads(invite["members"])
                    await creator.send(
                        f"👥 **그룹 `{code}`** 에 새 멤버가 참가했습니다!\n"
                        f"참가자: {interaction.user.display_name} | 현재 {len(members)}명"
                    )
                except Exception:
                    pass

    @app_commands.command(name="그룹상태", description="내가 속한 그룹의 현재 멤버를 확인합니다")
    @app_commands.describe(code="확인할 그룹 초대 코드")
    async def group_status(self, interaction: discord.Interaction, code: str) -> None:
        code = code.strip().upper()
        invite = await self.bot.db.get_group_invite(code)

        if not invite:
            await interaction.response.send_message("❌ 해당 코드의 그룹을 찾을 수 없습니다.", ephemeral=True)
            return

        members = json.loads(invite["members"])
        member_lines = []
        for uid in members:
            try:
                user = await self.bot.fetch_user(int(uid))
                member_lines.append(f"• {user.display_name}")
            except Exception:
                member_lines.append(f"• (알 수 없는 유저: {uid})")

        embed = discord.Embed(
            title=f"👥 그룹 `{code}` 현황",
            description="\n".join(member_lines) or "멤버 없음",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"총 {len(members)}명 | /그룹신청 으로 일괄 신청하세요")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GroupApplyCog(bot))
