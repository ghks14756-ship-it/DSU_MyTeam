"""
cogs/team_room.py
조장 방 생성 + AI(Gemini) 매칭 적합도 리포트

플로우:
  /방생성 → 조장이 조건 입력
    → 활성 신청자 목록 조회
    → Gemini AI가 각 신청자의 적합도 분석
    → '매칭 적합도 리포트' 임베드 출력
    → 조장이 승인 버튼 클릭 → 채널 자동 생성
"""

import json
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Config

log = logging.getLogger("DSUMyTeam.TeamRoom")


# ─────────────────────────────────────────────
#  AI 리포트 생성 함수
# ─────────────────────────────────────────────
async def generate_match_report(
    team_name: str,
    required_skills: list[str],
    max_members: int,
    applicants: list[dict],
) -> str:
    """
    Google Gemini API를 통해 매칭 적합도 리포트를 생성한다.
    API Key가 없으면 간단한 규칙 기반 리포트를 반환.
    """
    if not Config.GEMINI_API_KEY:
        return _rule_based_report(team_name, required_skills, max_members, applicants)

    try:
        import google.generativeai as genai

        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
당신은 대학교 팀 매칭 전문 AI 어시스턴트입니다.
아래 조장의 조건과 신청자 목록을 분석하여 매칭 적합도 리포트를 작성해 주세요.

[팀 정보]
- 팀명: {team_name}
- 모집 인원: {max_members}명
- 원하는 특기: {', '.join(required_skills)}

[신청자 목록 (JSON)]
{json.dumps(applicants, ensure_ascii=False, indent=2)}

출력 형식:
1. 각 신청자에 대해 '적합도 점수(0~100)'와 '한 줄 평가' 작성
2. 최종 추천 멤버 TOP {max_members}명 선정 이유 설명
3. 전공/학번 밸런스 분석 한 줄 코멘트

응답은 한국어로 간결하게 작성하세요. 총 길이는 Discord 임베드 필드 제한(1024자)을 고려하세요.
"""
        response = await model.generate_content_async(prompt)
        return response.text

    except Exception as e:
        log.error(f"Gemini API 오류: {e}")
        return _rule_based_report(team_name, required_skills, max_members, applicants)


def _rule_based_report(
    team_name: str,
    required_skills: list[str],
    max_members: int,
    applicants: list[dict],
) -> str:
    """Gemini 없을 때 사용하는 규칙 기반 간이 리포트."""
    lines = [f"📊 **'{team_name}' 매칭 적합도 리포트** (규칙 기반)\n"]
    scored = []
    for app in applicants:
        score = 50
        for skill in required_skills:
            if skill.lower() in app.get("skill", "").lower():
                score += 30
        scored.append((score, app))

    scored.sort(key=lambda x: x[0], reverse=True)

    for i, (score, app) in enumerate(scored[:10]):
        lines.append(
            f"{'⭐' if i < max_members else '  '} {app['username']} "
            f"({app['department']}) — 적합도 **{score}점** | 특기: {app['skill']}"
        )

    lines.append(f"\n✅ **추천 멤버**: 상위 {max_members}명 (⭐ 표시)")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  조장 조건 입력 Modal
# ─────────────────────────────────────────────
class TeamRoomModal(discord.ui.Modal, title="🏠 팀 방 생성"):
    team_name = discord.ui.TextInput(
        label="팀 이름",
        placeholder="예) 알파팀, 우리팀",
        max_length=20,
        required=True,
    )
    required_skills = discord.ui.TextInput(
        label="원하는 특기 (쉼표로 구분)",
        placeholder="예) UI 디자인, 백엔드 개발",
        max_length=100,
        required=True,
    )
    max_members = discord.ui.TextInput(
        label="모집 인원",
        placeholder="4",
        max_length=1,
        required=True,
        default="4",
    )

    def __init__(self, activity_id: int):
        super().__init__()
        self.activity_id = activity_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot = interaction.client

        try:
            max_mem = int(self.max_members.value.strip())
        except ValueError:
            max_mem = 4

        skills = [s.strip() for s in self.required_skills.value.split(",") if s.strip()]

        # 팀 방 DB 생성
        team_id = await bot.db.create_team_room(
            activity_id=self.activity_id,
            leader_id=str(interaction.user.id),
            team_name=self.team_name.value.strip(),
            required_skills=skills,
            max_members=max_mem,
        )

        # 신청자 목록 조회
        applicants = await bot.db.get_all_active_applications(self.activity_id)

        if not applicants:
            await interaction.followup.send(
                "⚠️ 현재 대기 중인 신청자가 없습니다. 잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )
            return

        # AI 리포트 생성
        report_text = await generate_match_report(
            self.team_name.value.strip(), skills, max_mem, applicants
        )

        embed = discord.Embed(
            title=f"🤖 AI 매칭 적합도 리포트",
            description=f"팀: **{self.team_name.value}** | 모집: {max_mem}명",
            color=discord.Color.from_rgb(114, 137, 218),
        )
        embed.add_field(name="분석 결과", value=report_text[:1020], inline=False)
        embed.set_footer(text=f"팀 ID: {team_id} · /채널생성 으로 채널을 개설하세요")

        # 조장 픽업 View
        view = TeamRoomPickView(team_id=team_id, applicants=applicants, max_mem=max_mem)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────────
#  승인 버튼 View
# ─────────────────────────────────────────────
class TeamRoomPickView(discord.ui.View):
    def __init__(self, team_id: int, applicants: list[dict], max_mem: int):
        super().__init__(timeout=300)
        self.team_id = team_id
        self.applicants = applicants
        self.max_mem = max_mem

        options = []
        for app in applicants[:25]:
            label = f"{app['username']} ({app['department']})"
            desc = app.get("skill", "")[:50]
            options.append(discord.SelectOption(label=label, value=str(app["discord_id"]), description=desc))

        select_max = min(len(options), max_mem - 1)
        if select_max > 0:
            self.select_menu = discord.ui.Select(
                placeholder=f"팀원을 선택하세요 (최대 {select_max}명, 랜덤 대기자 포함)",
                min_values=1,
                max_values=select_max,
                options=options
            )
            self.select_menu.callback = self.select_callback
            self.add_item(self.select_menu)
        else:
            self.add_item(discord.ui.Button(label="대기 중인 신청자가 없습니다.", disabled=True))

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot = interaction.client
        guild = interaction.guild

        if guild is None:
            await interaction.followup.send("❌ 서버 내에서만 사용할 수 있습니다.", ephemeral=True)
            return

        selected_ids = self.select_menu.values

        # 1순위 랜덤 매칭 방어 (Lock/Check)
        valid_apps = []
        for discord_id in selected_ids:
            app_data = await bot.db.get_application(discord_id)
            if app_data and app_data["is_matched"] == 0:
                valid_apps.append(app_data)
            else:
                await interaction.followup.send(
                    "⚠️ 선택하신 멤버 중 방금 다른 팀(또는 랜덤 팀)에 매칭된 인원이 있습니다. 창을 닫고 다시 시도해 주세요.",
                    ephemeral=True
                )
                return

        # 채널 생성 로직
        category = discord.utils.get(guild.categories, name=Config.TEAM_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(Config.TEAM_CATEGORY_NAME)

        members_to_invite = []
        for app in valid_apps:
            try:
                member = guild.get_member(int(app["discord_id"])) or await guild.fetch_member(int(app["discord_id"]))
                members_to_invite.append(member)
            except Exception:
                pass

        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
        }
        for m in members_to_invite:
            overwrites[m] = discord.PermissionOverwrite(view_channel=True)

        try:
            text_ch = await guild.create_text_channel(
                f"{Config.TEAM_TEXT_CHANNEL_PREFIX}-{self.team_id}",
                category=category,
                overwrites=overwrites,
            )
            voice_ch = await guild.create_voice_channel(
                f"{Config.TEAM_VOICE_CHANNEL_PREFIX}-{self.team_id}",
                category=category,
                overwrites=overwrites,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ 채널 생성 실패 (권한 부족 등): {e}", ephemeral=True)
            return

        await bot.db.update_team_channels(self.team_id, str(text_ch.id), str(voice_ch.id))

        for app in valid_apps:
            await bot.db.mark_matched(app["discord_id"], self.team_id, app.get("username"))
            try:
                user = await bot.fetch_user(int(app["discord_id"]))
                await user.send(
                    f"🎉 팀 매칭이 확정되었습니다!\n"
                    f"채팅방: {text_ch.mention}\n음성방: {voice_ch.mention}"
                )
            except Exception:
                pass

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.followup.send(
            f"✅ 채널 생성 및 초대 완료!\n💬 {text_ch.mention}\n🔊 {voice_ch.mention}",
            ephemeral=True,
        )
        self.stop()


# ─────────────────────────────────────────────
#  Cog 클래스
# ─────────────────────────────────────────────
class TeamRoomCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="방생성", description="조장이 팀 방을 생성하고 AI 매칭 분석을 요청합니다")
    async def create_room(self, interaction: discord.Interaction) -> None:
        activities = await self.bot.db.get_active_activities()
        if not activities:
            await interaction.response.send_message(
                "⚠️ 등록된 MYDEX 활동이 없습니다. `/최신화`로 목록을 갱신해 주세요.", ephemeral=True
            )
            return

        # 활동 선택 드롭다운
        options = [
            discord.SelectOption(label=a["name"][:100], value=str(a["id"]))
            for a in activities[:25]
        ]

        class ActivitySelect(discord.ui.View):
            @discord.ui.select(placeholder="방을 생성할 활동을 선택하세요", options=options)
            async def select(self, sel_interaction: discord.Interaction, select: discord.ui.Select):
                await sel_interaction.response.send_modal(
                    TeamRoomModal(activity_id=int(select.values[0]))
                )
                self.stop()

        await interaction.response.send_message(
            "📋 방을 생성할 활동을 선택해 주세요.", view=ActivitySelect(), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TeamRoomCog(bot))
