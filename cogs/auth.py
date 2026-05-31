"""
cogs/auth.py
디스코드 신규 유저 인증 시스템 및 채널 셋업

■ 인증 철학
  - 인증은 오직 "신원 확인" 만 수행 → 채널 열람 권한은 절대 부여하지 않음.
  - 역할(마이덱스이용자)의 권한은 최소 수준으로 고정 (메시지 읽기/쓰기 수준).
  - 숨김 채널(@everyone view_channel=False)은 봇 코드 수준에서 절대 열지 않음.
  - 팀 채널은 오직 매칭 완료 시점에 random_match.py의 _create_private_channel()이
    해당 팀원만을 PermissionOverwrite 대상으로 지정하여 동적 생성.

■ 플로우
  - 봇 구동 시 #입장-및-인증 채널 자동 생성 (Read Only)
  - 튜토리얼 임베드 및 인증 버튼(Persistent View) 고정
  - 버튼 클릭 시 Modal(아이디/인증키) 팝업
  - 구글 시트 2단계 검증(Web_ID / Unique_ID / 인증키) 후 역할 부여
  - 구글 시트 Discord_ID 연동 + 환영 DM 발송
  - 비공개 채널 열람은 절대 허용하지 않음 (매칭 완료까지 잠금 유지)
"""

import asyncio
import logging
import discord
from discord.ext import commands

log = logging.getLogger("DSUMyTeam.Auth")

AUTH_CHANNEL_NAME = "입장-및-인증"
AUTH_ROLE_NAME    = "마이덱스이용자"
UNVERIFIED_ROLE_NAME = "미인증자"

# 인증된 유저에게 허용하는 최소 권한 (숨김 채널 접근 불가)
_AUTH_ROLE_PERMISSIONS = discord.Permissions(
    view_channel=True,          # 공개 채널만 볼 수 있음 (@everyone 오버라이드로 숨긴 채널은 여전히 비공개)
    send_messages=True,
    read_message_history=True,
    embed_links=True,
    attach_files=True,
    add_reactions=True,
    connect=True,               # 공개 음성 채널 접속 가능
    speak=True,
    use_application_commands=True,
    # ⛔ 아래 권한은 절대 포함하지 않음
    # administrator, manage_guild, manage_channels, manage_roles,
    # manage_messages, kick_members, ban_members, mention_everyone, ...
)

# 미인증자 권한: 인증 채널 글 읽기 전용
_UNVERIFIED_ROLE_PERMISSIONS = discord.Permissions(
    view_channel=True,
    read_message_history=True,
    # send_messages=False (기본 False, 명시 생략)
)


class AuthModal(discord.ui.Modal, title="🛡️ DSU MyTeam 서버 인증"):
    auth_input = discord.ui.TextInput(
        label="아이디 또는 인증키",
        placeholder="웹 아이디 / Unique_ID(DUS-...) / 6자리 인증키 중 하나",
        min_length=4,
        max_length=50,
        required=True,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        user_input = self.auth_input.value.strip()

        if not self.bot.gsheet:
            await interaction.followup.send(
                "⚠️ 구글 시트가 연결되어 있지 않아 인증할 수 없습니다.", ephemeral=True
            )
            return

        # ── 1. 2단계 검증 (Web_ID → Unique_ID 역참조 포함) ─────────────────
        uid = await self.bot.gsheet.verify_link_code(user_input)
        if not uid:
            await interaction.followup.send(
                "❌ 아이디 또는 인증키가 일치하지 않습니다.\n"
                "웹 아이디, DUS 인증키, 6자리 인증코드 중 하나를 정확히 입력해주세요.",
                ephemeral=True,
            )
            return

        discord_id = str(interaction.user.id)
        guild = interaction.guild

        # ── 2. 역할 부여 (최소 권한, 비공개 채널 접근 없음) ────────────────
        auth_role = discord.utils.get(guild.roles, name=AUTH_ROLE_NAME)
        if not auth_role:
            try:
                auth_role = await guild.create_role(
                    name=AUTH_ROLE_NAME,
                    color=discord.Color.blue(),
                    permissions=_AUTH_ROLE_PERMISSIONS,   # ← 명시적 최소 권한
                    reason="인증 시스템 자동 생성",
                )
                log.info(f"✨ '{AUTH_ROLE_NAME}' 역할 생성 완료 (최소 권한)")
            except Exception as e:
                log.error(f"역할 생성 실패: {e}")
        else:
            # 기존 역할 권한이 과다한 경우 자동 리셋
            if auth_role.permissions != _AUTH_ROLE_PERMISSIONS:
                try:
                    await auth_role.edit(
                        permissions=_AUTH_ROLE_PERMISSIONS,
                        reason="인증 역할 권한 최소화 자동 리셋",
                    )
                    log.info(f"🔧 '{AUTH_ROLE_NAME}' 역할 권한 자동 리셋 완료")
                except Exception as e:
                    log.warning(f"역할 권한 리셋 실패 (무시): {e}")

        if auth_role:
            try:
                await interaction.user.add_roles(auth_role, reason="DSU MyTeam 인증 완료")
            except discord.Forbidden:
                log.error("역할 부여 실패 (Forbidden): 봇의 역할 순위가 '마이덱스이용자'보다 낮습니다.")
                await interaction.followup.send(
                    "⚠️ 인증은 성공했으나 서버 설정 문제로 역할을 부여받지 못했습니다. 관리자에게 문의하세요.",
                    ephemeral=True,
                )
            except Exception as e:
                log.error(f"역할 부여 실패: {e}")

        # ── 3. 미인증자 역할 제거 ───────────────────────────────────────────
        unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
        if unverified_role and unverified_role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(unverified_role, reason="인증 완료")
            except Exception as e:
                log.warning(f"미인증자 역할 제거 실패: {e}")

        # ── 4. 로컬 DB: 임시 WEB_ discord_id → 실제 discord_id 업데이트 ────
        temp_id = f"WEB_{uid}"
        try:
            await self.bot.db._conn.execute(
                "UPDATE applications SET discord_id = ? WHERE discord_id = ?",
                (discord_id, temp_id),
            )
            await self.bot.db._conn.commit()
        except Exception as e:
            log.error(f"DB discord_id 업데이트 실패: {e}")

        # ── 5. 구글 시트 Discord_ID / Auth_Status 업데이트 (백그라운드) ─────
        asyncio.create_task(self._update_gsheet_auth(uid, discord_id))

        # ── 6. 완료 안내 (비공개 채널 입장은 '매칭 완료 후' 자동 처리됨) ────
        cached_sheets = await self.bot.gsheet.get_cached_sheets()
        user_name = self.bot.gsheet.get_fallback_data(cached_sheets, unique_id=uid, field="이름")
        display_name = user_name if user_name != "미기재" else uid

        welcome_msg = (
            f"✅ **인증 완료!** 환영합니다, `{display_name}` 님.\n\n"
            "📋 **다음 단계**: 매칭 신청이 완료되고 팀이 구성되면 봇이 자동으로 **전용 팀 채널**을 만들어 드립니다.\n"
            "팀 채널은 매칭 완료 시점에 해당 팀원에게만 공개됩니다."
        )
        await interaction.followup.send(welcome_msg, ephemeral=True)

        # 환영 DM
        try:
            embed = discord.Embed(
                title="🎉 DSU MyTeam 인증 완료!",
                description=welcome_msg,
                color=discord.Color.green(),
            )
            embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")
            await interaction.user.send(embed=embed)
        except Exception:
            pass  # DM 차단 무시

    async def _update_gsheet_auth(self, unique_id: str, discord_id: str):
        """구글 시트 통합_사용자_관리에서 unique_id를 찾아 Discord_ID와 Auth_Status 업데이트"""
        try:
            if not self.bot.gsheet.spreadsheet_id:
                return

            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self.bot.gsheet._get_client)

            def _update():
                sheet = client.open_by_key(self.bot.gsheet.spreadsheet_id).worksheet(
                    self.bot.gsheet.worksheet_users
                )
                all_values = sheet.get_all_values()
                if len(all_values) < 2:
                    return

                for idx, row in enumerate(all_values[1:], start=2):
                    if len(row) > 0 and str(row[0]).strip().upper() == unique_id.upper():
                        sheet.update_cell(idx, 3, discord_id)   # C열: Discord_ID
                        sheet.update_cell(idx, 4, "인증완료")    # D열: Auth_Status
                        break

            await loop.run_in_executor(None, _update)
            log.info(f"[Auth] 구글 시트 연동 완료: {unique_id} → {discord_id}")
        except Exception as e:
            log.error(f"[Auth] 구글 시트 인증 업데이트 실패: {e}")


class AuthButtonView(discord.ui.View):
    """지속적(Persistent)으로 동작하는 인증 버튼 뷰"""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="auth_btn_v3")
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AuthModal(self.bot))


class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        self.bot.add_view(AuthButtonView(self.bot))
        self.bot.loop.create_task(self._setup_auth_channel())

    async def _setup_auth_channel(self):
        """봇 구동 시 #입장-및-인증 채널과 임베드가 없으면 자동 생성"""
        await self.bot.wait_until_ready()

        if not self.bot.guilds:
            return

        guild = self.bot.guilds[0]

        # ── 미인증자 역할 생성/관리 ──────────────────────────────────────────
        unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
        if not unverified_role:
            try:
                unverified_role = await guild.create_role(
                    name=UNVERIFIED_ROLE_NAME,
                    color=discord.Color.dark_grey(),
                    permissions=_UNVERIFIED_ROLE_PERMISSIONS,  # ← 최소 권한
                    reason="초기 셋업 자동 생성",
                )
                log.info(f"✨ '{UNVERIFIED_ROLE_NAME}' 역할 생성 완료")
            except Exception as e:
                log.error(f"미인증자 역할 생성 실패: {e}")

        # ── 인증 채널 생성 ───────────────────────────────────────────────────
        channel = discord.utils.get(guild.text_channels, name=AUTH_CHANNEL_NAME)
        if not channel:
            # @everyone: 읽기만 허용 (쓰기 금지)
            # 봇: 쓰기 가능
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                ),
            }
            try:
                channel = await guild.create_text_channel(
                    name=AUTH_CHANNEL_NAME,
                    overwrites=overwrites,
                    topic="DSU MyTeam 웹사이트 인증을 위한 채널입니다.",
                    position=0,
                )
                log.info(f"✨ #{AUTH_CHANNEL_NAME} 채널을 자동 생성했습니다.")
            except Exception as e:
                log.error(f"채널 생성 실패: {e}")
                return

        # ── 튜토리얼 임베드 & 버튼 게시 (중복 방지) ──────────────────────────
        has_auth_msg = False
        try:
            async for msg in channel.history(limit=10):
                if msg.author == self.bot.user and msg.components:
                    has_auth_msg = True
                    break
        except Exception:
            pass

        if not has_auth_msg:
            embed = discord.Embed(
                title="🛡️ DSU MyTeam 서버 인증 안내",
                description=(
                    "서버의 공개 채널을 이용하려면 웹사이트에서 발급받은\n"
                    "**[웹 아이디]** / **[DUS 인증키]** / **[6자리 인증코드]** 중 하나로 인증하세요.\n\n"
                    "✅ 인증 후 팀 매칭이 완료되면 **팀 전용 채널**이 자동 생성됩니다.\n"
                    "팀 채널은 해당 팀원에게만 공개됩니다.\n\n"
                    "아래 버튼을 눌러 인증을 시작하세요."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text="버튼을 클릭하면 인증 창이 열립니다.")

            try:
                await channel.send(embed=embed, view=AuthButtonView(self.bot))
                log.info(f"📌 #{AUTH_CHANNEL_NAME} 채널에 인증 튜토리얼을 게시했습니다.")
            except Exception as e:
                log.error(f"인증 튜토리얼 게시 실패: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """새로운 멤버가 들어오면 '미인증자' 역할 부여"""
        if member.bot:
            return

        unverified_role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE_NAME)
        if unverified_role:
            try:
                await member.add_roles(unverified_role, reason="신규 입장 자동 부여")
                log.info(f"👤 {member.name} 님에게 '{UNVERIFIED_ROLE_NAME}' 역할 부여")
            except Exception as e:
                log.error(f"미인증자 역할 부여 실패 ({member.name}): {e}")

    # ── 관리자 명령어: 역할 권한 긴급 리셋 ────────────────────────────────────
    from discord import app_commands as _apc

    @_apc.command(name="역할초기화", description="[관리자] 마이덱스이용자 역할 권한을 최소값으로 강제 리셋합니다")
    @_apc.default_permissions(administrator=True)
    async def reset_role_permissions(self, interaction: discord.Interaction):
        """기존에 과다 부여된 마이덱스이용자 역할 권한을 즉시 최소화."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        results = []

        for role_name, perms in [
            (AUTH_ROLE_NAME, _AUTH_ROLE_PERMISSIONS),
            (UNVERIFIED_ROLE_NAME, _UNVERIFIED_ROLE_PERMISSIONS),
        ]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                try:
                    await role.edit(permissions=perms, reason=f"관리자 /역할초기화 명령어 실행")
                    results.append(f"✅ `{role_name}` 권한 리셋 완료")
                    log.info(f"[역할초기화] '{role_name}' 권한 리셋 완료 by {interaction.user}")
                except Exception as e:
                    results.append(f"❌ `{role_name}` 리셋 실패: {e}")
            else:
                results.append(f"⚠️ `{role_name}` 역할을 찾을 수 없음")

        await interaction.followup.send("\n".join(results), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthCog(bot))
