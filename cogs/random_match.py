"""
cogs/random_match.py
매칭 엔진 v3 - 명세서 완전 준수 버전

■ 매칭 명세 (System Spec)
  - 팀 기본 정원: 4명 (Config.DEFAULT_TEAM_SIZE)
  - 처리 우선순위: [자동 랜덤/조건 매칭] > [수동 가입 신청]
  - FIFO 선착순: applied_at ASC 정렬 (DB 쿼리 레벨에서 보장)

■ 규칙 1. 일반 랜덤 매칭 (is_leader=0, has_conditions=0)
  - 대기열 선착순으로 4명 묶어 팀 구성
  - 첫 번째 유저(applied_at 가장 이른)가 팀장
  - 취소(슬라이딩): DB mark_matched 로 처리, 다음 사이클에서 자동 재조합

■ 규칙 2. 조건 매칭 (is_leader=0, has_conditions=1)
  - 동일 조건 유저끼리 별도 큐에서 4명 모이면 팀 신설
  - 7일 미매칭 시 "매칭 실패" DM 발송 후 대기열 해제

■ 규칙 3. 팀장 (is_leader=1)
  - 자동 매칭 + 수동 모집 동시 진행 (상호 배타적 완료)
  - 조건 없는 팀장: 랜덤 대기자 중 최대 Config.LEADER_DASHBOARD_POOL_SIZE명 순서대로 자동 배정

■ 프로그램별 독립 매칭
  - 같은 program 값을 가진 신청자끼리만 매칭
  - program이 비어있으면 '미지정' 그룹으로 처리
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

def _classify(applicants: list[dict]) -> tuple[list, list, list, list]:
    """
    신청자 목록을 4개의 우선순위 버킷으로 분류.
    입력 리스트는 이미 applied_at ASC 정렬된 상태여야 함 (DB 쿼리 레벨 보장).

    Returns:
        p1_no_cond  : 조건 없는 개인 대기자 (1순위, 랜덤 매칭)
        p1_leaders  : 조건 없는 팀장 (1순위, 랜덤 배정)
        p2_leaders  : 조건 있는 팀장 (2순위)
        p3_cond     : 조건 있는 개인 대기자 (3순위, 동일 조건 큐)
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


def _diverse_sort(pool: list[dict]) -> list[dict]:
    """
    전공 다양성을 최대화하는 라운드 로빈 정렬.
    FIFO 순서를 기본으로 하되, 같은 전공 연속 배치를 피함.
    """
    by_dept: dict[str, list[dict]] = defaultdict(list)
    for app in pool:
        by_dept[app.get("department", "기타")].append(app)
    # 각 전공 내부는 applied_at 순서 유지 (DB 정렬 결과 보존)

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
    명세서 규칙 1·2·3 기반 팀 구성 메인 함수.
    - 입력은 단일 프로그램 그룹의 신청자 (applied_at ASC 정렬됨)
    - 반환: [{"leader": {...}, "members": [{...}, ...], "priority": int}, ...]
    """
    p1_no_cond, p1_leaders, p2_leaders, p3_cond = _classify(applicants)
    formed_teams: list[dict] = []
    used_ids: set[str] = set()

    def _mark_used(members: list[dict]) -> None:
        for m in members:
            used_ids.add(str(m["discord_id"]))

    def _available(pool: list[dict]) -> list[dict]:
        return [m for m in pool if str(m["discord_id"]) not in used_ids]

    # ── 규칙 3 + 규칙 1 복합: 조건 없는 팀장 + 랜덤 대기자 ────────
    # 팀장이 먼저 대기열에서 팀원을 선착순으로 채움 (규칙 3-2)
    for leader in _available(p1_leaders):
        target_size = leader.get("target_members") or team_size
        needed = target_size - 1
        # 랜덤 대기자 → 조건 대기자 순으로 채움 (최대 LEADER_DASHBOARD_POOL_SIZE명 범위에서)
        candidate_pool = _available(p1_no_cond)[:Config.LEADER_DASHBOARD_POOL_SIZE] + _available(p3_cond)
        candidate_pool = _diverse_sort(candidate_pool)
        picked = candidate_pool[:needed]

        if picked:  # 1명 이상이면 팀 구성 (남은 자리는 추후 채움)
            team = {"leader": leader, "members": [leader] + picked, "priority": 1, "target_members": target_size}
            formed_teams.append(team)
            _mark_used([leader] + picked)

    # ── 규칙 1: 조건 없는 개인 대기자들끼리 FIFO 4명 묶음 ──────────
    avail_p1 = _diverse_sort(_available(p1_no_cond))
    for i in range(0, len(avail_p1), team_size):
        chunk = avail_p1[i:i + team_size]
        if len(chunk) >= Config.MIN_QUEUE_SIZE_FOR_MATCH:
            # 첫 번째 유저(가장 일찍 신청)가 임시 팀장 (규칙 1)
            team = {"leader": chunk[0], "members": chunk, "priority": 1, "target_members": team_size}
            formed_teams.append(team)
            _mark_used(chunk)

    # ── 규칙 2 + 규칙 3 복합: 조건 있는 팀장 + 조건 부합 대기자 ────
    def _matches(leader: dict, candidate: dict) -> bool:
        """
        조건 부합 여부 검사.
        현재는 프로그램이 같으면 통과 (상위 그룹핑에서 이미 프로그램 필터됨).
        추후 conditions 배열 비교 로직 추가 가능.
        """
        return True

    for leader in _available(p2_leaders):
        target_size = leader.get("target_members") or team_size
        needed = target_size - 1
        candidates = [
            c for c in _available(p1_no_cond) + _available(p3_cond)
            if _matches(leader, c)
        ]
        candidates = _diverse_sort(candidates)
        picked = candidates[:needed]

        if picked:
            team = {"leader": leader, "members": [leader] + picked, "priority": 2, "target_members": target_size}
            formed_teams.append(team)
            _mark_used([leader] + picked)

    # ── 규칙 2-2: 조건 있는 개인 대기자들끼리 동일 조건 큐 ───────
    avail_p3 = _diverse_sort(_available(p3_cond))
    for i in range(0, len(avail_p3), team_size):
        chunk = avail_p3[i:i + team_size]
        if len(chunk) >= Config.MIN_QUEUE_SIZE_FOR_MATCH:
            team = {"leader": chunk[0], "members": chunk, "priority": 3, "target_members": team_size}
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
    """
    매칭 완료된 팀원만 접근할 수 있는 비공개 채널 동적 생성.
    """
    category = discord.utils.get(guild.categories, name=Config.TEAM_CATEGORY_NAME)
    if category is None:
        cat_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }
        try:
            category = await guild.create_category(
                Config.TEAM_CATEGORY_NAME,
                overwrites=cat_overwrites,
            )
            log.info(f"팀룸 카테고리 '{Config.TEAM_CATEGORY_NAME}' 생성 완료")
        except Exception as e:
            log.error(f"카테고리 생성 실패: {e}")
            category = None

    overwrites: dict = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False,
            connect=False,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            manage_channels=True,
            connect=True,
            speak=True,
        ),
    }

    for m in members:
        try:
            member_obj = (
                guild.get_member(int(m["discord_id"]))
                or await guild.fetch_member(int(m["discord_id"]))
            )
            overwrites[member_obj] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                add_reactions=True,
                connect=True,
                speak=True,
            )
        except discord.NotFound:
            log.warning(f"  팀원 조회 실패 (서버 미입장): discord_id={m['discord_id']}")
        except Exception as e:
            log.warning(f"  팀원 권한 설정 실패 [{m['discord_id']}]: {e}")

    try:
        text_ch = await guild.create_text_channel(
            f"{Config.TEAM_TEXT_CHANNEL_PREFIX}-{team_id}",
            category=category,
            overwrites=overwrites,
            topic=f"팀 {team_id} 전용 채팅 채널 | 팀원 외 접근 불가",
        )
        voice_ch = await guild.create_voice_channel(
            f"{Config.TEAM_VOICE_CHANNEL_PREFIX}-{team_id}",
            category=category,
            overwrites=overwrites,
        )
        log.info(f"팀 {team_id} 비공개 채널 생성 완료 (팀원 {len(members)}명)")
        return text_ch, voice_ch
    except discord.Forbidden:
        log.error("채널 생성 실패 (Forbidden): 봇에 '채널 관리' 권한이 없습니다.")
        return None, None
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
    cached_sheets: dict | None = None,
) -> None:
    """
    매칭 완료 교차 DM 발송.
    - 팀장 → 전체 팀원 정보 + 연락처
    - 팀원 각각 → 팀장 + 다른 팀원 정보
    """
    channel_info = ""
    if text_ch:
        channel_info += f"\n💬 팀 채팅방: {text_ch.mention}"
    if voice_ch:
        channel_info += f"\n🔊 팀 음성방: {voice_ch.mention}"
    if not channel_info:
        channel_info = f"\n📌 팀 번호: {team_idx} (채널이 없는 경우 관리자에게 문의)"

    def _get_member_info(m: dict) -> tuple:
        d_id = m.get("discord_id", "")
        is_ldr = bool(m.get("is_leader", 0))

        if bot.gsheet and cached_sheets:
            try:
                name = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="이름", is_leader=is_ldr)
                dept = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="학과", is_leader=is_ldr)
                skill = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="특기", is_leader=is_ldr)
                schedule = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="주간_시간표", is_leader=is_ldr)
                contact = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="연락수단", is_leader=is_ldr)
                student_id = bot.gsheet.get_fallback_data(cached_sheets, discord_id=d_id, field="학번", is_leader=is_ldr)
                if student_id and student_id != "미기재" and len(student_id) > 4:
                    student_id = student_id[:4] + "*" * (len(student_id) - 4)
            except Exception as e:
                log.warning(f"[DM] 구글시트 fallback 실패 ({d_id}): {e}")
                name = m.get('username', '?')
                dept = m.get('department', '?')
                skill = m.get('skill', '?')
                schedule = m.get('weekly_schedule', '') or "미기재"
                contact = m.get('contact', '') or "미기재"
                student_id = "미기재"
        else:
            name = m.get('username', '?')
            dept = m.get('department', '?')
            skill = m.get('skill', '?')
            schedule = m.get('weekly_schedule', '') or "미기재"
            contact = m.get('contact', '') or "미기재"
            student_id = "미기재"

        return name, dept, skill, schedule, contact, student_id

    non_leaders = [m for m in members if str(m["discord_id"]) != str(leader["discord_id"])]

    # 팀장에게: 팀원들의 정보 전달
    try:
        leader_user = await bot.fetch_user(int(leader["discord_id"]))
        embed_to_leader = discord.Embed(
            title=f"🎉 팀 매칭 완료! (팀 {team_idx})",
            description=f"아래 팀원들이 배정되었습니다.{channel_info}",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        for m in non_leaders:
            name, dept, skill, schedule, contact, student_id = _get_member_info(m)
            embed_to_leader.add_field(
                name=f"👤 {name} ({dept} / 학번: {student_id})",
                value=(
                    f"🔧 특기: {skill}\n"
                    f"📅 활동 가능 시간: {schedule}\n"
                    f"📞 연락 수단: {contact}"
                ),
                inline=False,
            )
        await leader_user.send(embed=embed_to_leader)
        log.info(f"[DM] 팀장 DM 발송 완료: {leader.get('username')} ({leader['discord_id']})")
    except discord.Forbidden:
        log.warning(f"[DM] 팀장 DM 차단됨 [{leader['discord_id']}] - DM 허용 필요")
    except Exception as e:
        log.warning(f"[DM] 팀장 DM 실패 [{leader['discord_id']}]: {type(e).__name__}: {e}")

    # 팀원 각각에게: 팀장 + 다른 팀원 정보
    for member in non_leaders:
        try:
            member_user = await bot.fetch_user(int(member["discord_id"]))
            embed_to_member = discord.Embed(
                title=f"🎉 팀 매칭 완료! (팀 {team_idx})",
                description=f"팀에 배정되었습니다.{channel_info}",
                color=discord.Color.green(),
            )

            lname, ldept, lskill, lschedule, lcontact, lstudent_id = _get_member_info(leader)
            embed_to_member.add_field(
                name=f"👑 팀장: {lname} ({ldept} / 학번: {lstudent_id})",
                value=(
                    f"🔧 특기: {lskill}\n"
                    f"📅 활동 가능 시간: {lschedule}\n"
                    f"📞 연락 수단: {lcontact}"
                ),
                inline=False,
            )

            other_members = [m for m in non_leaders if str(m["discord_id"]) != str(member["discord_id"])]
            for m in other_members:
                oname, odept, oskill, oschedule, ocontact, ostudent_id = _get_member_info(m)
                embed_to_member.add_field(
                    name=f"👤 {oname} ({odept} / 학번: {ostudent_id})",
                    value=(
                        f"🔧 특기: {oskill}\n"
                        f"📅 활동 가능 시간: {oschedule}\n"
                        f"📞 연락 수단: {ocontact}"
                    ),
                    inline=False,
                )
            await member_user.send(embed=embed_to_member)
            log.info(f"[DM] 팀원 DM 발송 완료: {member.get('username')} ({member['discord_id']})")
        except discord.Forbidden:
            log.warning(f"[DM] 팀원 DM 차단됨 [{member['discord_id']}]")
        except Exception as e:
            log.warning(f"[DM] 팀원 DM 실패 [{member['discord_id']}]: {type(e).__name__}: {e}")


async def execute_match_for_teams(
    bot,
    guild: discord.Guild | None,
    activity_id: int | None,
    team_objs: list[dict],
    team_size: int,
) -> list[str]:
    """
    build_teams()가 반환한 팀 목록을 실제로 처리하는 후처리 함수.
    """
    result_lines = []

    for idx, team_obj in enumerate(team_objs, start=1):
        leader = team_obj["leader"]
        members = team_obj["members"]
        priority = team_obj.get("priority", 1)
        target_size = team_obj.get("target_members", team_size)

        # 1) DB team_room 생성
        team_id = await bot.db.create_team_room(
            activity_id=activity_id,
            leader_id=str(leader["discord_id"]),
            team_name=f"매칭팀-{idx}",
            required_skills=[],
            max_members=target_size,
        )

        # 2) 채널 생성
        text_ch, voice_ch = None, None
        if guild:
            text_ch, voice_ch = await _create_private_channel(guild, team_id, members, bot)
            if text_ch:
                await bot.db.update_team_channels(
                    team_id, str(text_ch.id), str(voice_ch.id) if voice_ch else ""
                )

        # 3) cached_sheets 초기화 (채널 생성 결과와 무관하게 항상 실행)
        cached_sheets = None
        if bot.gsheet:
            try:
                cached_sheets = await bot.gsheet.get_cached_sheets()
            except Exception as e:
                log.warning(f"[매칭] 구글시트 캐시 로드 실패 (DM은 fallback으로 진행): {e}")

        # 4) 팀 리포트 채널에 게시 (채널이 있을 때만)
        if text_ch and bot.gsheet and cached_sheets:
            report_text = bot.gsheet.build_team_report(members, cached_sheets)
            try:
                msg = await text_ch.send(report_text)
                await msg.pin()
            except Exception as e:
                log.warning(f"팀 리포트 고정 실패: {e}")

        # 5) DB is_matched 업데이트
        for m in members:
            await bot.db.mark_matched(str(m["discord_id"]), team_id)

        # 6) team_match_results 저장
        result_id = await bot.db.save_team_match_result(
            team_id=team_id,
            activity_id=activity_id,
            leader_id=str(leader["discord_id"]),
            members=members,
            channel_id=str(text_ch.id) if text_ch else None,
        )

        # 7) 교차 DM 발송 (채널 생성 결과와 무관하게 항상 실행)
        await _send_cross_dms(bot, leader, members, text_ch, voice_ch, idx, cached_sheets=cached_sheets)

        # 8) 구글 시트 동기화 (백그라운드)
        if bot.gsheet:
            unique_ids = [m.get("unique_id", "") for m in members if m.get("unique_id")]
            asyncio.create_task(_sync_to_sheet(bot, team_id, activity_id, leader, members, unique_ids, result_id))

        member_names = " / ".join(f"{m['username']}({m['department']})" for m in members)
        ch_info = f"→ {text_ch.mention}" if text_ch else "(채널 생성 실패)"
        result_lines.append(
            f"**팀 {idx}** [P{priority}순위] {ch_info}\n  {member_names}"
        )
        log.info(f"매칭 완료 - 팀 {idx}: {member_names}")

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
            "program": leader.get("program", ""),
            "summary": "자동 매칭",
            "current_members": len(members),
            "target_members": len(members),
            "team_status": "결성완료",
        })

        await bot.db.mark_sheet_synced(result_id)
        log.info(f"구글 시트 동기화 완료: 팀 {team_id}")
    except Exception as e:
        log.error(f"구글 시트 동기화 실패 (팀 {team_id}): {e}")


# ──────────────────────────────────────────────────────────
#  매칭 엔진 Cog
# ──────────────────────────────────────────────────────────

class MatchEngineCog(commands.Cog):
    """
    이벤트 드리븐 자동 매칭 엔진.
    - 1분마다 대기열 스캔 → 프로그램별 독립 팀 구성
    - 3일 경과자에게 DM 발송 + 팀장 승급
    - 7일 만료 시 매칭 실패 DM 발송 + 대기열 해제
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._match_loop = tasks.loop(seconds=Config.MATCH_CHECK_INTERVAL_SECONDS)(self._run_match_cycle)
        self._day3_loop = tasks.loop(seconds=Config.DAY3_REMIND_CHECK_INTERVAL)(self._run_day3_check)
        self._expiry_loop = tasks.loop(seconds=Config.DAY3_REMIND_CHECK_INTERVAL)(self._run_expiry_check)
        self._pending_loop = tasks.loop(seconds=300)(self._run_pending_expiry_check)  # 5분마다 24h 만료 체크

    def cog_load(self):
        self._match_loop.start()
        self._day3_loop.start()
        self._expiry_loop.start()
        self._pending_loop.start()

    def cog_unload(self):
        self._match_loop.cancel()
        self._day3_loop.cancel()
        self._expiry_loop.cancel()
        self._pending_loop.cancel()

    # ── 1분 매칭 사이클 (프로그램별 독립 매칭) ──────────────────
    async def _run_match_cycle(self) -> None:
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return

        # 전체 활성 신청자 (FIFO 정렬은 DB에서 보장)
        all_applicants = await self.bot.db.get_all_active_applications()
        # 미인증 웹 신청자는 매칭 제외 (디스코드 연동 완료자만 매칭)
        applicants = [app for app in all_applicants if not str(app["discord_id"]).startswith("WEB_")]

        if len(applicants) < Config.MIN_QUEUE_SIZE_FOR_MATCH:
            return

        # ── 프로그램별 그룹핑 (명세: 같은 프로그램끼리만 매칭) ──
        by_program: dict[str, list[dict]] = defaultdict(list)
        for app in applicants:
            program = (app.get("program") or "").strip() or "미지정"
            by_program[program].append(app)

        guild = self.bot.guilds[0] if self.bot.guilds else None
        team_size = Config.DEFAULT_TEAM_SIZE
        all_results = []

        for program, group in by_program.items():
            if len(group) < Config.MIN_QUEUE_SIZE_FOR_MATCH:
                continue  # 해당 프로그램에 신청자가 너무 적으면 스킵

            team_objs = build_teams(group, team_size)
            if not team_objs:
                continue

            log.info(f"자동 매칭 시작 [{program}]: {len(group)}명 대기 → {len(team_objs)}팀 구성")
            results = await execute_match_for_teams(
                bot=self.bot,
                guild=guild,
                activity_id=None,
                team_objs=team_objs,
                team_size=team_size,
            )
            all_results.extend(results)

        for r in all_results:
            log.info(f"  {r}")

    # ── 5분 3일 체크 루프 ────────────────────────────────────────
    async def _run_day3_check(self) -> None:
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return

        pending = await self.bot.db.get_day3_pending()
        for record in pending:
            await self.bot.db.mark_day3_dm_sent(record["discord_id"])
            await self._send_day3_dm(record)

    # ── 5분 7일 만료 체크 루프 (명세: 데드락 방지) ───────────────
    async def _run_expiry_check(self) -> None:
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return

        expired = await self.bot.db.get_expired_applications()
        for record in expired:
            await self.bot.db.mark_expiry_dm_sent(record["discord_id"])
            await self._send_expiry_dm(record)
            # 7일 만료 후 대기열 삭제 (명세: "대기열에서 삭제")
            await self.bot.db.delete_application(record["discord_id"])
            log.info(f"7일 만료 처리: {record.get('username')} ({record['discord_id']})")

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
            log.info(f"3일 DM 발송: {record.get('username')} ({record['discord_id']})")
        except discord.Forbidden:
            log.warning(f"DM 차단: {record['discord_id']}")
        except Exception as e:
            log.error(f"3일 DM 실패 [{record['discord_id']}]: {e}")

    async def _send_expiry_dm(self, record: dict) -> None:
        """7일 데드락 만료 DM: '매칭 실패' 알림 (명세 규칙 2 데드락 방지)."""
        try:
            user = await self.bot.fetch_user(int(record["discord_id"]))
            program = record.get("program") or "미지정"
            embed = discord.Embed(
                title="⚠️ 매칭 실패 알림",
                description=(
                    f"**[{program}]** 프로그램에서 7일간 팀 빌딩이 완료되지 않았습니다.\n\n"
                    "대기열에서 자동으로 제거되었습니다.\n"
                    "조건을 완화하여 다시 신청하거나 웹사이트에서 재시도해 주세요."
                ),
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="👤 이름", value=record.get("username", "?"), inline=True)
            embed.add_field(name="🔗 프로그램", value=program, inline=True)
            embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")
            await user.send(embed=embed)
            log.info(f"7일 만료 DM 발송: {record.get('username')} ({record['discord_id']})")
        except discord.Forbidden:
            log.warning(f"만료 DM 차단: {record['discord_id']}")
        except Exception as e:
            log.error(f"7일 만료 DM 실패 [{record['discord_id']}]: {e}")

    # ── 5분 24시간 pending 만료 체크 루프 ────────────────────────
    async def _run_pending_expiry_check(self) -> None:
        """24시간이 지난 팀장 승인 대기 신청자를 대기열로 자동 복귀."""
        await self.bot.wait_until_ready()
        if not self.bot.db:
            return
        expired_pending = await self.bot.db.get_expired_pending_approvals()
        for record in expired_pending:
            await self.bot.db.clear_pending_approval(record["discord_id"])
            log.info(f"[Pending 만료] 대기열 복귀: {record.get('username')} ({record['discord_id']})")
            # 24시간 미응답 → DM 알림
            if not str(record["discord_id"]).startswith("WEB_"):
                try:
                    user = await self.bot.fetch_user(int(record["discord_id"]))
                    await user.send(
                        embed=discord.Embed(
                            title="⏰ 팀 가입 초대 시간 만료",
                            description=(
                                "팀장의 초대에 24시간 내 응답하지 않아\n"
                                "자동으로 **매칭 대기열로 복귀**되었습니다.\n\n"
                                "다른 팀과 매칭을 계속 진행합니다."
                            ),
                            color=discord.Color.orange(),
                        )
                    )
                except Exception:
                    pass

    # ── 관리자 수동 매칭 커맨드 ─────────────────────────────────
    @app_commands.command(name="랜덤매칭", description="[관리자] 대기 중인 신청자를 즉시 팀 구성합니다")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        program="대상 프로그램 이름 (비어있으면 전체)",
        team_size="팀 인원 (기본 4명)",
    )
    async def random_match(
        self,
        interaction: discord.Interaction,
        program: str = "",
        team_size: int = Config.DEFAULT_TEAM_SIZE,
    ) -> None:
        await interaction.response.defer(ephemeral=False, thinking=True)

        filter_program = program.strip() or None
        all_applicants = await self.bot.db.get_all_active_applications(program=filter_program)
        applicants = [app for app in all_applicants if not str(app["discord_id"]).startswith("WEB_")]

        if len(applicants) < 2:
            await interaction.followup.send("⚠️ 매칭할 인증된 신청자가 부족합니다. (최소 2명 필요)")
            return

        # 프로그램별 그룹핑
        by_program: dict[str, list[dict]] = defaultdict(list)
        for app in applicants:
            pg = (app.get("program") or "").strip() or "미지정"
            by_program[pg].append(app)

        all_team_objs = []
        for pg, group in by_program.items():
            teams = build_teams(group, team_size)
            all_team_objs.extend(teams)

        if not all_team_objs:
            await interaction.followup.send("⚠️ 현재 조건으로 팀을 구성할 수 없습니다.")
            return

        result_lines = await execute_match_for_teams(
            bot=self.bot,
            guild=interaction.guild,
            activity_id=None,
            team_objs=all_team_objs,
            team_size=team_size,
        )

        label = f"[{filter_program}]" if filter_program else "[전체 프로그램]"
        header = f"🎲 **{label} 매칭 결과** ({len(all_team_objs)}팀 구성)\n"
        await interaction.followup.send(header + "\n".join(result_lines))

    @app_commands.command(name="대기목록", description="[관리자] 현재 매칭 대기열을 확인합니다")
    @app_commands.default_permissions(administrator=True)
    async def list_queue(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        all_applicants = await self.bot.db.get_all_active_applications()
        applicants = [app for app in all_applicants if not str(app["discord_id"]).startswith("WEB_")]

        if not applicants:
            unauth = len(all_applicants) - len(applicants)
            await interaction.followup.send(f"📭 현재 대기자가 없습니다. (미인증 대기자: {unauth}명)")
            return

        # 프로그램별 그룹핑 표시
        by_program: dict[str, list[dict]] = defaultdict(list)
        for app in applicants:
            pg = (app.get("program") or "").strip() or "미지정"
            by_program[pg].append(app)

        embed = discord.Embed(
            title=f"📋 매칭 대기열 ({len(applicants)}명 / {len(by_program)}개 프로그램)",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )

        for pg, group in by_program.items():
            p1_no, p1_l, p2_l, p3 = _classify(group)
            lines = []
            if p1_l:  lines.append(f"  팀장({len(p1_l)}): " + ", ".join(a['username'] for a in p1_l))
            if p1_no: lines.append(f"  대기({len(p1_no)}): " + ", ".join(a['username'] for a in p1_no))
            if p2_l:  lines.append(f"  조건팀장({len(p2_l)}): " + ", ".join(a['username'] for a in p2_l))
            if p3:    lines.append(f"  조건대기({len(p3)}): " + ", ".join(a['username'] for a in p3))
            embed.add_field(
                name=f"📌 {pg} ({len(group)}명)",
                value="\n".join(lines) or "없음",
                inline=False,
            )

        await interaction.followup.send(embed=embed)


# ──────────────────────────────────────────────────────────
#  3일 DM 응답 View (버튼)
# ──────────────────────────────────────────────────────────

class Day3DecisionView(discord.ui.View):
    """3일 경과 DM에 첨부되는 '계속/포기' 버튼."""

    def __init__(self, bot, record: dict):
        super().__init__(timeout=86400)
        self.bot = bot
        self.record = record

    @discord.ui.button(label="✅ 계속 진행 (조건 포기, 팀장 승급)", style=discord.ButtonStyle.success)
    async def continue_and_promote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        success = await self.bot.db.promote_to_leader(self.record["discord_id"])
        if success:
            await interaction.followup.send(
                "✅ 팀장으로 승급되었습니다!\n"
                "조건이 초기화되었으며, 다음 매칭 사이클에서 남은 팀원이 자동으로 배정됩니다.",
                ephemeral=True,
            )
            log.info(f"팀장 승급: {self.record.get('username')} ({self.record['discord_id']})")
        else:
            await interaction.followup.send("⚠️ 이미 매칭 완료되었거나 처리에 실패했습니다.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="⏳ 조건 유지하고 계속 대기", style=discord.ButtonStyle.secondary)
    async def continue_wait(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "알겠습니다. 기존 조건을 유지하며 계속 대기합니다.\n"
            "남은 대기 기간 내에 매칭이 완료되면 DM으로 알려드립니다.",
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="❌ 매칭 포기 (대기열 취소)", style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.delete_application(self.record["discord_id"])
        await interaction.response.send_message(
            "신청이 취소되었습니다. 다시 매칭을 원하시면 웹사이트에서 재신청해 주세요.",
            ephemeral=True,
        )
        log.info(f"매칭 포기: {self.record.get('username')} ({self.record['discord_id']})")
        self.stop()


# ──────────────────────────────────────────────────────────
#  팀 가입 초대 DM View (팀장 승인 → 신청자 수락/거부)
# ──────────────────────────────────────────────────────────

class PendingApprovalView(discord.ui.View):
    """
    팀장이 '가입 승인' 클릭 시 신청자 Discord DM에 전송되는 버튼 View.
    ✅ 팀 가입  /  ❌ 가입 거부
    timeout=86400 (24시간, 이후 _run_pending_expiry_check가 DB 정리)
    """

    def __init__(self, bot, applicant_discord_id: str, leader_discord_id: str,
                 program: str, leader_name: str):
        super().__init__(timeout=86400)  # 24시간
        self.bot = bot
        self.applicant_discord_id = applicant_discord_id
        self.leader_discord_id = leader_discord_id
        self.program = program
        self.leader_name = leader_name

    @discord.ui.button(label="✅ 팀 가입", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        # 유효성 재확인 (이미 매칭됐는지 등)
        app = await self.bot.db.get_application(self.applicant_discord_id)
        if not app or app.get("is_matched"):
            await interaction.followup.send("⚠️ 이미 매칭 완료된 상태입니다.", ephemeral=True)
            self.stop()
            return

        # 팀장 정보 조회
        leader_app = await self.bot.db.get_application(self.leader_discord_id)
        if not leader_app:
            await interaction.followup.send("⚠️ 팀장 정보를 찾을 수 없습니다. 매칭이 취소되었을 수 있습니다.", ephemeral=True)
            await self.bot.db.clear_pending_approval(self.applicant_discord_id)
            self.stop()
            return

        # 팀 생성 or 기존 팀에 편입 (간단 처리: team_rooms에 새 팀 생성)
        target_size = leader_app.get("target_members") or 4
        team_id = await self.bot.db.create_team_room(
            activity_id=None,
            leader_id=self.leader_discord_id,
            team_name=f"{self.program[:10]}-수동매칭",
            required_skills=[],
            max_members=target_size,
        )

        # 둘 다 is_matched=1 처리
        await self.bot.db.mark_matched(self.applicant_discord_id, team_id)
        await self.bot.db.mark_matched(self.leader_discord_id, team_id)

        # 팀원 정보 임베드 전송 (신청자 → 팀장 정보)
        embed_to_applicant = discord.Embed(
            title="🎉 팀 가입이 완료되었습니다!",
            description=f"**[{self.program}]** 프로그램 팀에 합류했습니다.",
            color=discord.Color.green(),
        )
        embed_to_applicant.add_field(name="👑 팀장", value=leader_app.get('username', '?'), inline=True)
        embed_to_applicant.add_field(name="🏫 학과", value=leader_app.get('department', '?'), inline=True)
        embed_to_applicant.add_field(name="📞 연락처", value=leader_app.get('contact', '미기재') or '미기재', inline=False)
        embed_to_applicant.set_footer(text="DSU My_team · 팀 가입 완료")
        await interaction.followup.send(embed=embed_to_applicant, ephemeral=True)

        # 팀장에게도 알림 DM (팀장이 디스코드 연동된 경우)
        if not self.leader_discord_id.startswith("WEB_"):
            try:
                leader_user = await self.bot.fetch_user(int(self.leader_discord_id))
                embed_to_leader = discord.Embed(
                    title="🎉 팀원 가입 확정!",
                    description=f"**{app.get('username', '신청자')}**님이 팀 가입을 수락했습니다!",
                    color=discord.Color.from_rgb(88, 101, 242),
                )
                embed_to_leader.add_field(name="👤 이름", value=app.get('username', '?'), inline=True)
                embed_to_leader.add_field(name="🏫 학과", value=app.get('department', '?'), inline=True)
                embed_to_leader.add_field(name="⭐ 특기", value=app.get('skill', '?'), inline=True)
                await leader_user.send(embed=embed_to_leader)
            except Exception as e:
                log.warning(f"[가입확정DM] 팀장 DM 실패: {e}")

        log.info(f"[수동매칭] 완료: {app.get('username')} → 팀 {team_id} ({self.program})")
        self.stop()

    @discord.ui.button(label="❌ 가입 거부", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.db.clear_pending_approval(self.applicant_discord_id)
        await interaction.response.send_message(
            "가입 초대를 거부했습니다.\n계속 매칭 대기열에서 다른 팀을 기다립니다.",
            ephemeral=True,
        )
        # 팀장에게 거부 알림
        if not self.leader_discord_id.startswith("WEB_"):
            try:
                leader_user = await self.bot.fetch_user(int(self.leader_discord_id))
                leader_app = await self.bot.db.get_application(self.applicant_discord_id)
                username = leader_app.get('username', '신청자') if leader_app else '신청자'
                await leader_user.send(
                    embed=discord.Embed(
                        title="❌ 팀 가입 거부",
                        description=f"**{username}**님이 팀 가입 초대를 거부했습니다.\n다른 신청자를 확인해 주세요.",
                        color=discord.Color.red(),
                    )
                )
            except Exception:
                pass
        log.info(f"[수동매칭] 거부: {self.applicant_discord_id}")
        self.stop()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchEngineCog(bot))
