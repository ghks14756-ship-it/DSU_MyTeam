"""
cogs/random_match.py
랜덤 매칭 (마감 임박 시 자동 팀 구성)

알고리즘:
  1. 매칭되지 않은 신청자를 전공 및 입학년도(학번 앞 2자리) 기준으로 그룹화
  2. 전공 다양성을 최대화하는 방식으로 팀 구성
  3. 팀 확정 후 채널 자동 생성 + 멤버 DM 전송
"""

import logging
import random
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from config import Config

log = logging.getLogger("DSUMyTeam.RandomMatch")


def balance_teams(applicants: list[dict], team_size: int) -> list[list[dict]]:
    """
    전공/입학년도 밸런스를 고려한 팀 구성 알고리즘.
    라운드 로빈 방식으로 다양한 전공을 섞는다.
    """
    by_dept: dict[str, list[dict]] = defaultdict(list)
    for app in applicants:
        dept = app.get("department", "기타")
        by_dept[dept].append(app)

    # 전공별 셔플 (같은 전공 내 순서 랜덤화)
    for dept_list in by_dept.values():
        random.shuffle(dept_list)

    # 라운드 로빈으로 팀 배분
    pool: list[dict] = []
    dept_lists = list(by_dept.values())
    max_len = max(len(d) for d in dept_lists) if dept_lists else 0

    for i in range(max_len):
        for dept_list in dept_lists:
            if i < len(dept_list):
                pool.append(dept_list[i])

    # 팀 분할
    teams: list[list[dict]] = []
    for i in range(0, len(pool), team_size):
        chunk = pool[i:i + team_size]
        if chunk:
            teams.append(chunk)

    return teams


class RandomMatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="랜덤매칭", description="[관리자] 대기 중인 신청자를 전공 밸런스에 맞춰 자동으로 팀 구성합니다")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        activity_id="대상 활동 ID",
        team_size="팀 인원 (기본 4명)",
    )
    async def random_match(
        self,
        interaction: discord.Interaction,
        activity_id: int,
        team_size: int = Config.DEFAULT_TEAM_SIZE,
    ) -> None:
        await interaction.response.defer(ephemeral=False, thinking=True)

        applicants = await self.bot.db.get_all_active_applications(activity_id)
        if len(applicants) < 2:
            await interaction.followup.send("⚠️ 매칭할 신청자가 부족합니다. (최소 2명 필요)")
            return

        teams = balance_teams(applicants, team_size)
        guild = interaction.guild

        result_lines = [f"🎲 **랜덤 매칭 결과** ({len(teams)}개 팀)\n"]

        for idx, team in enumerate(teams, start=1):
            team_id = await self.bot.db.create_team_room(
                activity_id=activity_id,
                leader_id=str(interaction.user.id),
                team_name=f"랜덤팀-{idx}",
                required_skills=[],
                max_members=team_size,
            )

            # 채널 생성
            text_ch, voice_ch = None, None
            if guild:
                category = discord.utils.get(guild.categories, name=Config.TEAM_CATEGORY_NAME)
                if category is None:
                    category = await guild.create_category(Config.TEAM_CATEGORY_NAME)

                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                for app in team:
                    try:
                        member = guild.get_member(int(app["discord_id"])) or \
                                 await guild.fetch_member(int(app["discord_id"]))
                        overwrites[member] = discord.PermissionOverwrite(view_channel=True)
                    except Exception:
                        pass

                text_ch = await guild.create_text_channel(
                    f"{Config.TEAM_TEXT_CHANNEL_PREFIX}-{team_id}",
                    category=category, overwrites=overwrites,
                )
                voice_ch = await guild.create_voice_channel(
                    f"{Config.TEAM_VOICE_CHANNEL_PREFIX}-{team_id}",
                    category=category, overwrites=overwrites,
                )
                await self.bot.db.update_team_channels(team_id, str(text_ch.id), str(voice_ch.id))

            # 매칭 처리 & DM
            member_names = []
            for app in team:
                await self.bot.db.mark_matched(app["discord_id"], team_id)
                member_names.append(f"{app['username']}({app['department']})")
                try:
                    user = await self.bot.fetch_user(int(app["discord_id"]))
                    msg = f"🎉 **랜덤 팀 매칭이 완료되었습니다!** (팀 {idx})\n"
                    if text_ch:
                        msg += f"💬 채팅방: {text_ch.mention}\n"
                    if voice_ch:
                        msg += f"🔊 음성방: {voice_ch.mention}"
                    await user.send(msg)
                except Exception:
                    pass

            channel_info = f"→ {text_ch.mention}" if text_ch else ""
            result_lines.append(
                f"**팀 {idx}** {channel_info}\n  " + " / ".join(member_names)
            )

        await interaction.followup.send("\n".join(result_lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RandomMatchCog(bot))
