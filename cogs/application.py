"""
cogs/application.py
/신청 슬래시 커맨드 — 리디자인 UX

개선된 플로우:
  ① /신청 실행
     → ② 활동 드롭다운 선택
       → ③ 특기 카드 Select (이모지 + 특기명)
            ├ 일반 특기 선택 → ④ 나머지 정보 입력 Modal (이름/학번/학과)
            └ ✏️ 기타 선택  → ④-B 특기 직접 입력 Modal (이름/학번/학과/특기 모두)
              → ⑤ DB 저장 (72h TTL)
              → ⑥ 확인 임베드 + DM 발송
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("DSUMyTeam.Application")


# ─────────────────────────────────────────────
#  사전 정의된 특기 카드 목록
#  (이모지, 라벨, 설명)
# ─────────────────────────────────────────────
SKILL_OPTIONS: list[tuple[str, str, str]] = [
    ("🎨", "UI / UX 디자인",   "Figma, 와이어프레임, 프로토타입"),
    ("💻", "프론트엔드 개발",  "React, Vue, HTML/CSS/JS"),
    ("⚙️", "백엔드 개발",      "Python, Java, Node.js, DB"),
    ("📱", "앱 개발",          "iOS / Android / Flutter"),
    ("🤖", "AI / 데이터",      "머신러닝, 데이터 분석, 모델링"),
    ("📊", "기획 / PM",        "서비스 기획, 일정 관리, 문서"),
    ("🎬", "영상 / 미디어",    "영상 편집, 촬영, 모션그래픽"),
    ("📝", "발표 / PPT",       "발표 자료 제작, 스피치"),
    ("🔍", "QA / 테스트",      "테스트 계획, 버그 리포트"),
    ("🎮", "게임 개발",        "Unity, Unreal, 게임 로직"),
    ("🌐", "네트워크 / 인프라","서버, 클라우드, DevOps"),
    ("✏️", "기타 (직접 입력)", "목록에 없는 특기를 직접 입력"),
]

SKILL_SELECT_OPTIONS = [
    discord.SelectOption(
        emoji=emoji,
        label=label,
        value=label,
        description=desc,
    )
    for emoji, label, desc in SKILL_OPTIONS
]

CUSTOM_SKILL_VALUE = "✏️ 기타 (직접 입력)"


# ─────────────────────────────────────────────
#  Modal A: 이름 / 학번 / 학과 (특기 미리 선택된 경우)
# ─────────────────────────────────────────────
class InfoModal(discord.ui.Modal, title="🎓 MYDEX 팀 매칭 신청"):
    """특기가 카드로 미리 선택된 경우: 이름/학번/학과만 입력."""

    student_name = discord.ui.TextInput(
        label="이름",
        placeholder="홍길동",
        min_length=2,
        max_length=10,
        required=True,
    )
    student_id = discord.ui.TextInput(
        label="학번",
        placeholder="21011234  (8자리)",
        min_length=8,
        max_length=8,
        required=True,
    )
    department = discord.ui.TextInput(
        label="학과",
        placeholder="컴퓨터공학과",
        min_length=2,
        max_length=30,
        required=True,
    )

    def __init__(self, activity_id: int | None, preset_skill: str):
        super().__init__()
        self.activity_id = activity_id
        self.preset_skill = preset_skill

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await _save_and_confirm(
            interaction=interaction,
            username=self.student_name.value.strip(),
            student_id=self.student_id.value.strip(),
            department=self.department.value.strip(),
            skill=self.preset_skill,
            activity_id=self.activity_id,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.error(f"InfoModal 오류: {error}")
        await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# ─────────────────────────────────────────────
#  Modal B: 이름 / 학번 / 학과 / 특기 직접 입력
#  (기타 선택 시)
# ─────────────────────────────────────────────
class FullInfoModal(discord.ui.Modal, title="🎓 MYDEX 팀 매칭 신청 (기타 특기)"):
    """기타를 선택한 경우: 모든 필드 + 특기 직접 입력."""

    student_name = discord.ui.TextInput(
        label="이름",
        placeholder="홍길동",
        min_length=2,
        max_length=10,
        required=True,
    )
    student_id = discord.ui.TextInput(
        label="학번",
        placeholder="21011234  (8자리)",
        min_length=8,
        max_length=8,
        required=True,
    )
    department = discord.ui.TextInput(
        label="학과",
        placeholder="컴퓨터공학과",
        min_length=2,
        max_length=30,
        required=True,
    )
    skill = discord.ui.TextInput(
        label="특기 / 역할 (직접 입력)",
        placeholder="예) 3D 모델링, 번역, 회로 설계 등",
        style=discord.TextStyle.short,
        min_length=2,
        max_length=50,
        required=True,
    )

    def __init__(self, activity_id: int | None):
        super().__init__()
        self.activity_id = activity_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await _save_and_confirm(
            interaction=interaction,
            username=self.student_name.value.strip(),
            student_id=self.student_id.value.strip(),
            department=self.department.value.strip(),
            skill=self.skill.value.strip(),
            activity_id=self.activity_id,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.error(f"FullInfoModal 오류: {error}")
        await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)


# ─────────────────────────────────────────────
#  공통 DB 저장 + 확인 임베드 함수
# ─────────────────────────────────────────────
async def _save_and_confirm(
    interaction: discord.Interaction,
    username: str,
    student_id: str,
    department: str,
    skill: str,
    activity_id: int | None,
) -> None:
    """DB UPSERT → 확인 임베드 → DM 발송."""
    bot = interaction.client
    try:
        record = await bot.db.create_application(
            discord_id=str(interaction.user.id),
            username=username,
            student_id=student_id,
            department=department,
            skill=skill,
            activity_id=activity_id,
        )
    except Exception as e:
        log.error(f"DB 저장 오류: {e}")
        await interaction.response.send_message(
            "❌ 신청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            ephemeral=True,
        )
        return

    # 2) 구글 시트에 기록 (추가)
    if bot.gsheet:
        gsheet_success = await bot.gsheet.record_application({
            "discord_id": interaction.user.id,
            "username": username,
            "student_id": student_id,
            "department": department,
            "skill": skill
        })
        if not gsheet_success:
            log.warning(f"  ⚠️  구글 시트 기록 실패: {username} ({interaction.user.id})")
        else:
            log.info(f"  📊 구글 시트 기록 성공: {username}")

    expires_str = record["expires_at"].strftime("%Y-%m-%d %H:%M UTC")

    # 선택된 특기의 이모지를 찾아 표시
    skill_emoji = next(
        (e for e, l, _ in SKILL_OPTIONS if l == skill),
        "⭐"
    )

    embed = discord.Embed(
        title="✅ 팀 매칭 신청 완료!",
        description="72시간 동안 대기열에 등록됩니다.\n매칭이 확정되면 DM과 채널 초대로 알려드립니다.",
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.add_field(name="👤 이름",      value=username,   inline=True)
    embed.add_field(name="🎓 학번",      value=student_id, inline=True)
    embed.add_field(name="🏫 학과",      value=department, inline=True)
    embed.add_field(name=f"{skill_emoji} 특기", value=skill, inline=True)
    embed.add_field(name="⏰ 만료 시각", value=f"`{expires_str}`", inline=False)
    embed.set_footer(
        text=f"DSU My_team · {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

    try:
        await interaction.user.send(
            embed=embed.copy().set_author(name="신청 확인 DM")
        )
    except discord.Forbidden:
        pass


# ─────────────────────────────────────────────
#  Modal C: 기타 특기 직접 추가
# ─────────────────────────────────────────────
class CustomSkillModal(discord.ui.Modal, title="✏️ 기타 특기 직접 입력"):
    skill_input = discord.ui.TextInput(
        label="추가할 특기 / 역할",
        placeholder="예) 3D 모델링, 외국어 번역 등",
        min_length=2,
        max_length=20,
        required=True
    )

    def __init__(self, parent_view: 'SkillSelectView'):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        custom_skill = self.skill_input.value.strip()
        if custom_skill not in self.parent_view.selected_skills:
            self.parent_view.selected_skills.add(custom_skill)
            await self.parent_view.update_message(interaction)
        else:
            await interaction.response.send_message(f"이미 '{custom_skill}'이(가) 선택되어 있습니다.", ephemeral=True)

# ─────────────────────────────────────────────
#  Step 2: 복수 선택 가능한 카드형 버튼 View
# ─────────────────────────────────────────────
class SkillButton(discord.ui.Button):
    def __init__(self, emoji: str, label: str):
        super().__init__(
            label=f"{emoji} {label}",
            style=discord.ButtonStyle.secondary,
            row=None # 자동 배치
        )
        self.skill_label = label

    async def callback(self, interaction: discord.Interaction):
        view: SkillSelectView = self.view
        if self.skill_label in view.selected_skills:
            view.selected_skills.remove(self.skill_label)
            self.style = discord.ButtonStyle.secondary
        else:
            view.selected_skills.add(self.skill_label)
            self.style = discord.ButtonStyle.primary
        
        await view.update_message(interaction)

class SkillSelectView(discord.ui.View):
    def __init__(self, activity_id: int | None):
        super().__init__(timeout=180)
        self.activity_id = activity_id
        self.selected_skills: set[str] = set()

        # 1. 주요 10개 특기 버튼 추가
        for emoji, label, _ in SKILL_OPTIONS[:10]:
            self.add_item(SkillButton(emoji, label))

        # 2. [✏️ 기타] 버튼 추가
        other_btn = discord.ui.Button(label="✏️ 기타 (직접 입력)", style=discord.ButtonStyle.gray, row=2)
        other_btn.callback = self._on_other_click
        self.add_item(other_btn)

        # 3. [✅ 선택 완료] 버튼 추가
        done_btn = discord.ui.Button(label="✅ 선택 완료 (다음 단계)", style=discord.ButtonStyle.success, row=3)
        done_btn.callback = self._on_done_click
        self.add_item(done_btn)

    async def update_message(self, interaction: discord.Interaction):
        """메시지 상태 업데이트 (선택된 특기 목록 표시 및 버튼 스타일 반영)"""
        try:
            selected_text = ", ".join(sorted(self.selected_skills)) if self.selected_skills else "없음"
            content = (
                f"**②단계 — 특기 / 역할 복수 선택**\n"
                f"원하는 카드를 모두 눌러주세요. 다시 누르면 취소됩니다.\n\n"
                f"📍 **현재 선택됨:** `{selected_text}`"
            )
            # 이미 응답했는지 확인 후 처리
            if interaction.response.is_done():
                await interaction.edit_original_response(content=content, view=self)
            else:
                await interaction.response.edit_message(content=content, view=self)
        except Exception as e:
            log.error(f"UI 업데이트 오류: {e}")

    async def _on_other_click(self, interaction: discord.Interaction):
        # 모달은 defer 없이 바로 전송해야 함
        await interaction.response.send_modal(CustomSkillModal(self))

    async def _on_done_click(self, interaction: discord.Interaction):
        if not self.selected_skills:
            await interaction.response.send_message("❗ 최소 하나 이상의 특기를 선택해 주세요.", ephemeral=True)
            return
        
        # 이름/학번/학과 입력을 위한 Modal 표시
        all_skills = ", ".join(sorted(self.selected_skills))
        await interaction.response.send_modal(InfoModal(self.activity_id, all_skills))
        self.stop()

# ─────────────────────────────────────────────
#  Step 1: 활동 선택 View (유지하되 텍스트 수정)
# ─────────────────────────────────────────────
class ActivitySelectView(discord.ui.View):
    """신청할 활동을 선택하는 드롭다운."""

    def __init__(self, activities: list[dict]):
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(
                label=act["name"][:100],
                value=str(act["id"]),
                description=(act.get("description") or "")[:100],
            )
            for act in activities[:25]
        ] or [discord.SelectOption(label="등록된 활동 없음", value="0")]

        select = discord.ui.Select(
            placeholder="신청할 MYDEX 활동을 선택하세요 📋",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_activity_select
        self.add_item(select)

    async def _on_activity_select(self, interaction: discord.Interaction) -> None:
        activity_id_raw = int(interaction.data["values"][0])
        activity_id = activity_id_raw if activity_id_raw != 0 else None

        # 특기 카드 선택 단계로 전환
        skill_view = SkillSelectView(activity_id)
        await interaction.response.edit_message(
            content=(
                "**②단계 — 특기 / 역할 선택**\n"
                "아래 카드형 버튼들을 눌러 나의 특기를 모두 골라주세요 (중복 선택 가능).\n"
                "선택을 마친 후 **✅ 선택 완료** 버튼을 눌러주세요."
            ),
            view=skill_view,
        )
        self.stop()


# ─────────────────────────────────────────────
#  Cog 클래스
# ─────────────────────────────────────────────
class ApplicationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="신청", description="MYDEX 팀 매칭에 신청합니다 (72시간 유효)")
    async def apply(self, interaction: discord.Interaction) -> None:
        """
        /신청 슬래시 커맨드.
        활동 선택 → 특기 카드 선택 → Modal 입력 → DB 저장 흐름.
        """
        activities = await self.bot.db.get_active_activities()

        if not activities:
            # 활동 없으면 특기 카드 선택부터 바로 시작
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

    @app_commands.command(name="내신청", description="현재 신청 상태를 확인합니다")
    async def my_application(self, interaction: discord.Interaction) -> None:
        record = await self.bot.db.get_application(str(interaction.user.id))
        if not record:
            await interaction.response.send_message(
                "📭 현재 신청된 정보가 없습니다. `/신청` 으로 등록하세요.", ephemeral=True
            )
            return

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(record["expires_at"])
        remaining = expires - now
        hours, rem = divmod(int(remaining.total_seconds()), 3600)
        minutes = rem // 60

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

    @app_commands.command(name="신청취소", description="팀 매칭 신청을 취소합니다")
    async def cancel_application(self, interaction: discord.Interaction) -> None:
        record = await self.bot.db.get_application(str(interaction.user.id))
        if not record:
            await interaction.response.send_message("📭 취소할 신청 내역이 없습니다.", ephemeral=True)
            return
        await self.bot.db.delete_application(str(interaction.user.id))
        await interaction.response.send_message("🗑️ 팀 매칭 신청이 취소되었습니다.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ApplicationCog(bot))
