"""
cogs/random_match.py
매칭 엔진 v2 - 이벤트 드리븐 + 3단계 우선순위 큐

■ 매칭 우선순위 (Priority Queue)
  1순위: 조건 없는 개인 대기자들 간 매칭 OR 조건 없이 모집하는 팀장에게 랜덤 배정
  2순위: 조건 있는 팀장의 조건에 부합하는 지원자 배정
  3순위: 조건 있는 개인 대기자들 간의 매칭

■ 대기열 라이프사이클
  - 신청 후 7일이 만료 시한
  - 3일 경과 → DM 발송 "계속 진행하겠습니까?"
    - 계속 + 조건 포기 → 팀장으로 승급(is_leader=1), 1순위 큐에서 남은 인원 자동 배정
    - 계속 (조건 유지) → 현재 큐 유지
    - 포기 → 대기열 삭제

■ 매칭 완료 후처리
  - 디스코드 비공개 채널 자동 생성 + 팀원 초대
  - 팀 채널에 구성 리포트 고정 (스케줄/연락처 포함)
  - 팀장에게 ← 팀원 정보 DM, 팀원에게 ← 팀장 정보 DM (교차 발송)
  - 구글 시트 매칭_대기_라인 상태 갱신 + 팀_관리_라인 결과 기록
"""

import asyncio
import logging
import random
from collections import defaultdict
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config

log = logging.getLogger("DSUMyTeam.MatchEngine")

# ──────────────────────────────────────────────────────────
#  우선순위 분류
# ──────────────────────────────────────────────────────────

def _classify(applicants: list[dict]) -> tuple[list, list, list]:
    """
    신청자 목록을 3개의 우선순위 버킷으로 분류.

    Returns:
        p1_no_cond  : 조건 없는 개인 대기자 (1순위)
        p1_leaders  : 조건 없이 팀원 모집하는 팀장 (1순위)
        p2_leaders  : 조건 있는 팀장 (2순위)
        p3_cond     : 조건 있는 개인 대기자 (3순위)
    """
    p1_no_cond: list[dict] = []
    p1_leaders: list[dict] = []
    p2_leaders: list[dict] = []
    p3_cond: list[dict] = []

    for app in applicants:
        is_leader = bool(app.get("is_leader", 0))
        has_cond = bool(app.get("has_conditions", 0))

        if is_leader and not has_cond:
            p1_leaders.append(app)
        elif is_leader and has_cond:
            p2_leaders.append(app)
        elif not has_cond:
            p1_no_cond.append(app)
        else:
            p3_cond.append(app)

    return p1_no_cond, p1_leaders, p2_leaders, p3_cond


def _round_robin_by_dept(pool: list[dict]) -> list[dict]:
    """전공 다양성을 최대화하는 라운드 로빈 정렬."""
    by_dept: dict[str, list[dict]] = defaultdict(list)
    for app in pool:
        by_dept[app.get("department", "기타")].append(app)
    for lst in by_dept.values():
        random.shuffle(lst)

    result: list[dict] = []
    dept_lists = list(by_dept.values())
    max_len = max((len(d) for d in dept_lists), default=0)
    for i in range(max_len):
        for lst in dept_lists:
            if i < len(lst):
                result.append(lst[i])
    return result


def build_teams(applicants: list[dict], team_size: int) -> list[dict]:
    """
    우선순위 큐 기반 팀 구성 메인 함수.
    반환: [{"leader": {...}, "members": [{...}, ...]}, ...]
    """
    p1_no_cond, p1_leaders, p2_leaders, p3_cond = _classify(applicants)
    formed_teams: list[dict] = []
    used_ids: set[str] = set()

    def _mark_used(members: list[dict]) -> None:
        for m in members:
            used_ids.add(m["discord_id"])

    def _available(pool: list[dict]) -> list[dict]:
        return [m for m in pool if m["discord_id"] not in used_ids]

    # ── 1순위-A: 조건 없는 팀장 + 랜덤 대기자 ─────────────────
    for leader in _available(p1_leaders):
        needed = team_size - 1
        # p1_no_cond → p3_cond 순으로 채움
        pool = _available(p1_no_cond) + _available(p3_cond)
        pool = _round_robin_by_dept(pool)
        picked = pool[:needed]

        if picked:
            team = {"leader": leader, "members": [leader] + picked, "priority": 1}
            formed_teams.append(team)
            _mark_used([leader] + picked)

    # ── 1순위-B: 조건 없는 개인 대기자들끼리 팀 구성 ──────────
    avail_p1 = _round_robin_by_dept(_available(p1_no_cond))
    for i in range(0, len(avail_p1), team_size):
        chunk = avail_p1[i:i + team_size]
        if len(chunk) >= Config.MIN_QUEUE_SIZE_FOR_MATCH:
            # 첫 번째를 임시 팀장으로 지정
            team = {"leader": chunk[0], "members": chunk, "priority": 1}
            formed_teams.append(team)
            _mark_used(chunk)

    # ── 2순위: 조건 있는 팀장 + 조건 부합 지원자 ───────────────
    # NOTE: 현재 조건 세부 스펙이 미정이므로 "틀"만 구현.
    # 실제 필터링 로직은 conditions 필드 스펙이 확정되면 아래 _matches() 함수에 추가.
    def _matches(leader: dict, candidate: dict) -> bool:
        """
        [STUB] 조건 부합 여부 검사.
        현재는 항상 True 반환 (조건 스펙 미정).
        추후 leader['conditions'] 배열과 candidate 데이터를 비교해 구현.
        """
        return True

    for leader in _available(p2_leaders):
        needed = team_size - 1
        candidates = [
            c for c in _available(p1_no_cond) + _available(p3_cond)
            if _matches(leader, c)
        ]
        candidates = _round_robin_by_dept(candidates)
        picked = candidates[:needed]

        if picked:
            team = {"leader": leader, "members": [leader] + picked, "priority": 2}
            formed_teams.append(team)
            _mark_used([leader] + picked)

    # ── 3순위: 조건 있는 개인 대기자들끼리 ───────────────────
    avail_p3 = _round_robin_by_dept(_available(p3_cond))
    for i in range(0, len(avail_p3), team_size):
        chunk = avail_p3[i:i + team_size]
        if len(chunk) >= Config.MIN_QUEUE_SIZE_FOR_MATCH:
            team = {"leader": chunk[0], "members": chunk, "priority": 3}
            formed_teams.append(team)
            _mark_used(chunk)

    return formed_teams


# ──────────────────────────────────────────────────────────
#  매칭 완료 후처리 헬퍼
# ──────────────────────────────────────────────────────────

async def _create_private_channel(
    guild: discord.Guild,
    team_id: int,
    members: list[dict],
    bot,
) -> tuple[discord.TextChannel | None, discord.VoiceChannel | None]:
    """팀원만 볼 수 있는 비공개 채널 생성."""
    category = discord.utils.get(guild.categories, name=Config.TEAM_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(Config.TEAM_CATEGORY_NAME)

    # 기본 비공개 + 팀원 개별 열람 허용
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for m in members:
        try:
            member_obj = guild.get_member(int(m["discord_id"])) or \
                         await guild.fetch_member(int(m["discord_id"]))
            overwrites[member_obj] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
        except Exception:
            pass

    try:
        text_ch = await guild.create_text_channel(
            f"{Config.TEAM_TEXT_CHANNEL_PREFIX}-{team_id}",
            category=category,
            overwrites=overwrites,
        )
        voice_ch = await guild.create_voice_channel(
            f"{Config.TEAM_VOICE_CHANNEL_PREFIX}-{team_id}",
            category=category,
            overwrites=overwrites,
        )
        return text_ch, voice_ch
    except Exception as e:
        log.error(f"채널 생성 실패: {e}")
        return None, None


async def _send_cross_dms(
    bot,
    leader: dict,
    members: list[dict],
    text_ch: discord.TextChannel | None,
    voice_ch: discord.VoiceChannel | None,
    team_idx: int,
) -> None:
    """
    매칭 완료 교차 DM 발송.
    - 팀장 → 전체 팀원 정보 + 연락처 수신
    - 팀원 각각 → 팀장 정보 + 연락처 수신
    """
    channel_info = ""
    if text_ch:
        channel_info += f"\n💬 팀 채팅방: {text_ch.mention}"
    if voice_ch:
        channel_info += f"\n🔊 팀 음성방: {voice_ch.mention}"
    if not channel_info:
        channel_info = f"\n📌 팀 번호: {team_idx} (채널 생성 실패 시 관리자에게 문의)"

    non_leaders = [m for m in members if m["discord_id"] != leader["discord_id"]]

    # 팀장에게: 팀원들의 정보 전달
    try:
        leader_user = await bot.fetch_user(int(leader["discord_id"]))
        embed_to_leader = discord.Embed(
            title=f"🎉 팀 매칭 완료! (팀 {team_idx})",
            description=f"아래 팀원들이 배정되었습니다.{channel_info}",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        for m in non_leaders:
            embed_to_leader.add_field(
                name=f"👤 {m.get('username', '?')} ({m.get('department', '?')})",
                value=(
                    f"🔧 특기: {m.get('skill', '?')}\n"
                    f"📞 연락처: {m.get('contact', '미기재') or '미기재'}"
                ),
                inline=False,
            )
        await leader_user.send(embed=embed_to_leader)
    except Exception as e:
        log.warning(f"팀장 DM 실패 [{leader['discord_id']}]: {e}")

    # 팀원 각각에게: 팀장 + 다른 팀원 정보 전달
    for member in non_leaders:
        try:
            member_user = await bot.fetch_user(int(member["discord_id"]))
            embed_to_member = discord.Embed(
                title=f"🎉 팀 매칭 완료! (팀 {team_idx})",
                description=f"팀에 배정되었습니다.{channel_info}",
                color=discord.Color.green(),
            )
            embed_to_member.add_field(
                name=f"👑 팀장: {leader.get('username', '?')} ({leader.get('department', '?')})",
                value=(
                    f"🔧 특기: {leader.get('skill', '?')}\n"
                    f"📞 연락처: {leader.get('contact', '미기재') or '미기재'}"
                ),
                inline=False,
            )
            other_members = [m for m in non_leaders if m["discord_id"] != member["discord_id"]]
            for m in other_members:
                embed_to_member.add_field(
                    name=f"👤 {m.get('username', '?')} ({m.get('department', '?')})",
                    value=f"🔧 특기: {m.get('skill', '?')}\n📞 연락처: {m.get('contact', '미기재') or '미기재'}",
                    inline=False,
                )
            await member_user.send(embed=embed_to_member)
        except Exception as e:
            log.warning(f"팀원 DM 실패 [{member['discord_id']}]: {e}")


async def execute_match_for_teams(
    bot,
    guild: discord.Guild | None,
    activity_id: int | None,
    team_objs: list[dict],
    team_size: int,
) -> list[str]:
    """
    build_teams()가 반환한 팀 목록을 실제로 처리하는 후처리 함수.
    - DB is_matched 업데이트
    - 채널 생성
    - 교차 DM 발송
    - 팀 리포트 채널 고정
    - 구글 시트 동기화 (비동기 큐)
    반환: 결과 요약 문자열 리스트
    """
    result_lines = []

    for idx, team_obj in enumerate(team_objs, start=1):
        leader = team_obj["leader"]
        members = team_obj["members"]
        priority = team_obj.get("priority", 1)

        # 1) DB team_room 생성
        team_id = await bot.db.create_team_room(
            activity_id=activity_id,
            leader_id=str(leader["discord_id"]),
            team_name=f"매칭팀-{idx}",
            required_skills=[],
            max_members=team_size,
        )

        # 2) 채널 생성
        text_ch, voice_ch = None, None
        if guild:
            text_ch, voice_ch = await _create_private_channel(guild, team_id, members, bot)
            if text_ch:
                await bot.db.update_team_channels(
                    team_id, str(text_ch.id), str(voice_ch.id) if voice_ch else ""
                )

        # 3) 팀 리포트 채널에 게시
        if text_ch and bot.gsheet:
            report_text = bot.gsheet.build_team_report(members)
            try:
                msg = await text_ch.send(report_text)
                await msg.pin()
            except Exception as e:
                log.warning(f"팀 리포트 고정 실패: {e}")

        # 4) DB is_matched 업데이트
        for m in members:
            await bot.db.mark_matched(m["discord_id"], team_id)

        # 5) team_match_results 저장
        result_id = await bot.db.save_team_match_result(
            team_id=team_id,
            activity_id=activity_id,
            leader_id=str(leader["discord_id"]),
            members=members,
            channel_id=str(text_ch.id) if text_ch else None,
        )

        # 6) 교차 DM 발송
        await _send_cross_dms(bot, leader, members, text_ch, voice_ch, idx)

        # 7) 구글 시트 동기화 (백그라운드)
        if bot.gsheet:
            unique_ids = [m.get("unique_id", "") for m in members if m.get("unique_id")]
            asyncio.create_task(_sync_to_sheet(bot, team_id, activity_id, leader, members, unique_ids, result_id))

        member_names = " / ".join(f"{m['username']}({m['department']})" for m in members)
        ch_info = f"→ {text_ch.mention}" if text_ch else ""
        result_lines.append(
            f"**팀 {idx}** [P{priority}순위] {ch_info}\n  {member_names}"
        )

    return result_lines


async def _sync_to_sheet(bot, team_id, activity_id, leader, members, unique_ids, result_id):
    """구글 시트 동기화 비동기 태스크 (실패해도 메인 플로우 영향 없음)."""
    try:
        if unique_ids:
            await bot.gsheet.update_match_status(unique_ids, "매칭완료")

        await bot.gsheet.record_team_result({
            "team_id": f"TEAM-{team_id}",
            "leader_unique_id": leader.get("unique_id", ""),
            "leader_name": leader.get("username", ""),
            "department": leader.get("department", ""),
            "program": "",
            "summary": "자동 매칭",
            "current_members": len(members),
            "target_members": len(members),
            "team_status": "결성완료",
        })

        await bot.db.mark_sheet_synced(result_id)
        log.info(f"✅ 구글 시트 동기화 완료: 팀 {team_id}")
    except Exception as e:
        log.error(f"❌ 구글 시트 동기화 실패 (팀 {team_id}): {e}")


# ──────────────────────────────────────────────────────────
#  매칭 엔진 Cog
# ──────────────────────────────────────────────────────────

class MatchEngineCog(commands.Cog):
    """
    이벤트 드리븐 자동 매칭 엔진.
    - 1분마다 대기열을 스캔하여 팀 구성 가능한 경우 즉시 매칭
    - 3일 경과자에게 DM 발송 + 승급 처리
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._match_loop = tasks.loop(seconds=Config.MATCH_CHECK_INTERVAL_SECONDS)(self._run_match_cycle)
        self._day3_loop = tasks.loop(seconds=Config.DAY3_REMIND_CHECK_INTERVAL)(self._run_day3_check)

    def cog_load(self):
        self._match_loop.start()
        self._day3_loop.start()

    def cog_unload(self):
        self._match_loop.cancel()
        self._day3_loop.cancel()

    # ── 1분 매칭 사이클 ─────────────────────────────────────────
    async def _run_match_cycle(self) -> None:
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return

        applicants = await self.bot.db.get_all_active_applications()
        if len(applicants) < Config.MIN_QUEUE_SIZE_FOR_MATCH:
            return

        team_size = Config.DEFAULT_TEAM_SIZE
        team_objs = build_teams(applicants, team_size)
        if not team_objs:
            return

        guild = None
        if self.bot.guilds:
            guild = self.bot.guilds[0]

        log.info(f"🔀 자동 매칭 시작: {len(applicants)}명 대기 → {len(team_objs)}팀 구성")

        results = await execute_match_for_teams(
            bot=self.bot,
            guild=guild,
            activity_id=None,
            team_objs=team_objs,
            team_size=team_size,
        )
        for r in results:
            log.info(f"  ✅ {r}")

    # ── 5분 3일 체크 루프 ───────────────────────────────────────
    async def _run_day3_check(self) -> None:
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return

        pending = await self.bot.db.get_day3_pending()
        for record in pending:
            await self.bot.db.mark_day3_dm_sent(record["discord_id"])
            await self._send_day3_dm(record)

    async def _send_day3_dm(self, record: dict) -> None:
        """3일 경과 DM: '계속 진행' 또는 '포기' 버튼 포함."""
        try:
            user = await self.bot.fetch_user(int(record["discord_id"]))
            view = Day3DecisionView(self.bot, record)
            embed = discord.Embed(
                title="⏰ 팀 매칭 대기 3일째입니다",
                description=(
                    "아직 매칭이 완료되지 않았습니다.\n"
                    "아래에서 계속 진행 여부를 선택해 주세요.\n\n"
                    "**'계속 진행 (조건 포기)'** 를 선택하면\n"
                    "→ 조건이 초기화되고 **팀장**으로 승급되어 남은 인원이 즉시 배정됩니다."
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="👤 이름", value=record.get("username", "?"), inline=True)
            embed.add_field(name="🏫 학과", value=record.get("department", "?"), inline=True)
            embed.add_field(name="⭐ 특기", value=record.get("skill", "?"), inline=True)
            embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")
            await user.send(embed=embed, view=view)
            log.info(f"📨 3일 DM 발송: {record.get('username')} ({record['discord_id']})")
        except discord.Forbidden:
            log.warning(f"⚠️ DM 차단: {record['discord_id']}")
        except Exception as e:
            log.error(f"❌ 3일 DM 실패 [{record['discord_id']}]: {e}")

    # ── 관리자 수동 매칭 커맨드 (유지) ─────────────────────────
    @app_commands.command(name="랜덤매칭", description="[관리자] 대기 중인 신청자를 우선순위 큐에 맞춰 즉시 팀 구성합니다")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        activity_id="대상 활동 ID (0 = 전체)",
        team_size="팀 인원 (기본 4명)",
    )
    async def random_match(
        self,
        interaction: discord.Interaction,
        activity_id: int = 0,
        team_size: int = Config.DEFAULT_TEAM_SIZE,
    ) -> None:
        await interaction.response.defer(ephemeral=False, thinking=True)

        act_id = activity_id if activity_id > 0 else None
        applicants = await self.bot.db.get_all_active_applications(act_id)

        if len(applicants) < 2:
            await interaction.followup.send("⚠️ 매칭할 신청자가 부족합니다. (최소 2명 필요)")
            return

        team_objs = build_teams(applicants, team_size)
        if not team_objs:
            await interaction.followup.send("⚠️ 현재 조건으로 팀을 구성할 수 없습니다.")
            return

        result_lines = await execute_match_for_teams(
            bot=self.bot,
            guild=interaction.guild,
            activity_id=act_id,
            team_objs=team_objs,
            team_size=team_size,
        )

        header = f"🎲 **매칭 결과** ({len(team_objs)}팀 구성)\n"
        await interaction.followup.send(header + "\n".join(result_lines))

    @app_commands.command(name="대기목록", description="[관리자] 현재 매칭 대기열을 확인합니다")
    @app_commands.default_permissions(administrator=True)
    async def list_queue(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        applicants = await self.bot.db.get_all_active_applications()
        if not applicants:
            await interaction.followup.send("📭 현재 대기자가 없습니다.")
            return

        p1_no, p1_l, p2_l, p3 = _classify(applicants)
        embed = discord.Embed(
            title=f"📋 매칭 대기열 ({len(applicants)}명)",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name=f"1순위 개인 ({len(p1_no)}명)", value="\n".join(f"• {a['username']}({a['department']})" for a in p1_no) or "없음", inline=False)
        embed.add_field(name=f"1순위 팀장 ({len(p1_l)}명)", value="\n".join(f"• {a['username']}({a['department']})" for a in p1_l) or "없음", inline=False)
        embed.add_field(name=f"2순위 팀장 ({len(p2_l)}명)", value="\n".join(f"• {a['username']}({a['department']})" for a in p2_l) or "없음", inline=False)
        embed.add_field(name=f"3순위 개인 ({len(p3)}명)", value="\n".join(f"• {a['username']}({a['department']})" for a in p3) or "없음", inline=False)
        await interaction.followup.send(embed=embed)


# ──────────────────────────────────────────────────────────
#  3일 DM 응답 View (버튼)
# ──────────────────────────────────────────────────────────

class Day3DecisionView(discord.ui.View):
    """3일 경과 DM에 첨부되는 '계속/포기' 버튼."""

    def __init__(self, bot, record: dict):
        super().__init__(timeout=86400)  # 24시간 응답 대기
        self.bot = bot
        self.record = record

    @discord.ui.button(label="✅ 계속 진행 (조건 포기, 팀장 승급)", style=discord.ButtonStyle.success)
    async def continue_and_promote(self, interaction: discord.Interaction, button: discord.ui.Button):
        """조건 포기 + 팀장 승급."""
        await interaction.response.defer(ephemeral=True)
        success = await self.bot.db.promote_to_leader(self.record["discord_id"])
        if success:
            await interaction.followup.send(
                "✅ 팀장으로 승급되었습니다!\n"
                "조건이 초기화되었으며, 다음 매칭 사이클에서 남은 팀원이 자동으로 배정됩니다.",
                ephemeral=True,
            )
            log.info(f"👑 팀장 승급: {self.record.get('username')} ({self.record['discord_id']})")
        else:
            await interaction.followup.send("⚠️ 이미 매칭 완료되었거나 처리에 실패했습니다.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="⏳ 조건 유지하고 계속 대기", style=discord.ButtonStyle.secondary)
    async def continue_wait(self, interaction: discord.Interaction, button: discord.ui.Button):
        """조건 유지, 현재 큐 유지."""
        await interaction.response.send_message(
            "알겠습니다. 기존 조건을 유지하며 계속 대기합니다.\n"
            "남은 대기 기간 내에 매칭이 완료되면 DM으로 알려드립니다.",
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="❌ 매칭 포기 (대기열 취소)", style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        """대기열 취소."""
        await self.bot.db.delete_application(self.record["discord_id"])
        await interaction.response.send_message(
            "신청이 취소되었습니다. 다시 매칭을 원하시면 `/신청` 명령어로 등록해 주세요.",
            ephemeral=True,
        )
        log.info(f"❌ 매칭 포기: {self.record.get('username')} ({self.record['discord_id']})")
        self.stop()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchEngineCog(bot))
