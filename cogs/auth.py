"""
cogs/auth.py
디스코드 신규 유저 인증 시스템 및 채널 셋업

- 봇 구동 시 #입장-및-인증 채널 자동 생성 (Read Only)
- 튜토리얼 임베드 및 인증 버튼(Persistent View) 고정 
- 버튼 클릭 시 Modal(아이디, 인증키) 팝업
- 구글 시트 검증 후 역할 부여, 구글 시트에 Discord_ID 연동, 매칭된 팀 채널 열람 권한 지급, 환영 DM 발송
"""

import asyncio
import logging
import discord
from discord.ext import commands

log = logging.getLogger("DSUMyTeam.Auth")

AUTH_CHANNEL_NAME = "입장-및-인증"
AUTH_ROLE_NAME = "마이덱스이용자"
UNVERIFIED_ROLE_NAME = "미인증자"

class AuthModal(discord.ui.Modal, title="🛡️ DSU MyTeam 서버 인증"):
    auth_input = discord.ui.TextInput(
        label="아이디 또는 인증키",
        placeholder="웹사이트 발급 아이디(예: DUS-...) 또는 인증키(예: A7X9B2)",
        min_length=6,
        max_length=50,
        required=True
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # 대소문자 구분 없이 비교하기 위해 .strip()만 적용 (.upper() 제거)
        user_input = self.auth_input.value.strip()

        if not self.bot.gsheet:
            await interaction.followup.send("⚠️ 구글 시트가 연결되어 있지 않아 인증할 수 없습니다.")
            return

        # 1. 구글 시트(회원_정보 탭)에서 아이디 또는 인증키 검증
        uid = await self.bot.gsheet.verify_link_code(user_input)
        if not uid:
            await interaction.followup.send("❌ 아이디 또는 인증키가 일치하지 않습니다. 다시 확인해주세요.")
            return

        discord_id = str(interaction.user.id)
        guild = interaction.guild

        # 2. 기본 역할 부여 및 미인증자 역할 제거
        role = discord.utils.get(guild.roles, name=AUTH_ROLE_NAME)
        if not role:
            try:
                role = await guild.create_role(
                    name=AUTH_ROLE_NAME,
                    color=discord.Color.blue(),
                    reason="인증 시스템 자동 생성"
                )
            except Exception as e:
                log.error(f"역할 생성 실패: {e}")
        
        if role:
            try:
                await interaction.user.add_roles(role)
            except discord.Forbidden:
                log.error(f"역할 부여 실패 (Forbidden): 봇의 역할(Role) 순위가 '{AUTH_ROLE_NAME}' 보다 낮거나 '역할 관리' 권한이 없습니다.")
                await interaction.followup.send("⚠️ 인증은 성공했으나, 서버 설정(봇 권한) 문제로 채널 이용 권한을 부여받지 못했습니다. 관리자에게 문의하세요.", ephemeral=True)
            except discord.HTTPException as e:
                log.error(f"역할 부여 실패 (HTTPException): {e}")
            except Exception as e:
                log.error(f"역할 부여 실패 (알 수 없는 오류): {e}")
        else:
            log.error(f"역할 찾기 실패: '{AUTH_ROLE_NAME}' 역할을 서버에서 찾을 수 없습니다. (Role=None)")

        # 미인증자 역할이 있다면 제거
        unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
        if unverified_role and unverified_role in interaction.user.roles:
            try:
                await interaction.user.remove_roles(unverified_role)
            except discord.Forbidden:
                log.error(f"미인증자 역할 제거 실패 (Forbidden): 봇의 역할(Role) 순위 문제 또는 권한 부족.")
            except discord.HTTPException as e:
                log.error(f"미인증자 역할 제거 실패 (HTTPException): {e}")
            except Exception as e:
                log.error(f"미인증자 역할 제거 실패 (알 수 없는 오류): {e}")

        # 3. 로컬 DB의 임시 discord_id (WEB_uid)를 실제 discord_id로 업데이트
        # 이렇게 해야 인증된 유저만 매칭 엔진(random_match)의 대상이 됨
        temp_id = f"WEB_{uid}"
        try:
            await self.bot.db._conn.execute(
                "UPDATE applications SET discord_id = ? WHERE discord_id = ?",
                (discord_id, temp_id)
            )
            await self.bot.db._conn.commit()
        except Exception as e:
            log.error(f"DB discord_id 업데이트 실패: {e}")

        # 4. 구글 시트에 Discord_ID 업데이트 (비동기)
        asyncio.create_task(self._update_gsheet_auth(uid, discord_id))

        # 5. (선택적) 이미 팀 채널 권한 부여 (매칭 로직이 인증 후로 바뀌어 보통 빈 배열)
        team_channel_mentions = await self._grant_team_access(guild, discord_id)

        # 6. 결과 안내 (DM 및 Ephemeral)
        welcome_msg = (
            f"✅ **인증 완료!** 환영합니다, `{uid}` 님.\n\n"
            "이제 서버의 모든 기능을 이용하실 수 있습니다."
        )
        if team_channel_mentions:
            welcome_msg += f"\n\n👥 배정된 팀 채널에 입장할 수 있습니다: {', '.join(team_channel_mentions)}"

        await interaction.followup.send(welcome_msg)
        
        # 환영 DM 발송
        try:
            embed = discord.Embed(
                title="🎉 DSU MyTeam 인증 완료!",
                description=welcome_msg,
                color=discord.Color.green()
            )
            embed.set_footer(text="DSU My_team · 동서대학교 MYDEX 팀 매칭 시스템")
            await interaction.user.send(embed=embed)
        except Exception:
            pass # DM 차단 무시

    async def _update_gsheet_auth(self, unique_id: str, discord_id: str):
        """구글 시트 통합_사용자_관리에서 unique_id를 찾아 Discord_ID와 Auth_Status 업데이트"""
        try:
            if not self.bot.gsheet.spreadsheet_id:
                return
            
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self.bot.gsheet._get_client)
            
            def _update():
                # 통합_사용자_관리 시트 (worksheet_users)
                sheet = client.open_by_key(self.bot.gsheet.spreadsheet_id).worksheet(self.bot.gsheet.worksheet_users)
                all_values = sheet.get_all_values()
                if len(all_values) < 2: return
                
                for idx, row in enumerate(all_values[1:], start=2):
                    # A열(인덱스 0) = Unique_ID
                    if len(row) > 0 and str(row[0]).strip().upper() == unique_id.upper():
                        sheet.update_cell(idx, 3, discord_id)   # C열(col 3): Discord_ID
                        sheet.update_cell(idx, 4, "인증완료")    # D열(col 4): Auth_Status
                        break
                        
            await loop.run_in_executor(None, _update)
            log.info(f"[Auth] 구글 시트 연동 완료: {unique_id} -> {discord_id}")
        except Exception as e:
            log.error(f"[Auth] 구글 시트 인증 업데이트 실패: {e}")

    async def _grant_team_access(self, guild: discord.Guild, discord_id: str) -> list[str]:
        """DB를 확인하여 소속된 팀이 있다면 채널(텍스트/음성) 권한 부여"""
        if not self.bot.db:
            return []
        
        mentions = []
        try:
            async with self.bot.db._conn.execute(
                """
                SELECT t.text_channel_id, t.voice_channel_id 
                FROM applications a
                JOIN team_rooms t ON a.team_id = t.id
                WHERE a.discord_id = ? AND a.is_matched = 1
                """,
                (discord_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                
            member_obj = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
            
            for row in rows:
                txt_id, voc_id = row[0], row[1]
                if txt_id:
                    ch = guild.get_channel(int(txt_id))
                    if ch:
                        await ch.set_permissions(member_obj, view_channel=True, send_messages=True, read_message_history=True)
                        mentions.append(ch.mention)
                if voc_id:
                    ch = guild.get_channel(int(voc_id))
                    if ch:
                        await ch.set_permissions(member_obj, view_channel=True, connect=True, speak=True)
        except Exception as e:
            log.error(f"팀 채널 권한 부여 실패: {e}")
        
        return mentions


class AuthButtonView(discord.ui.View):
    """지속적(Persistent)으로 동작하는 인증 버튼 뷰"""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="auth_btn_v3")
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼 클릭 시 모달 띄우기
        await interaction.response.send_modal(AuthModal(self.bot))


class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        # 봇 재시작 시에도 버튼이 동작하도록 View 등록
        self.bot.add_view(AuthButtonView(self.bot))
        self.bot.loop.create_task(self._setup_auth_channel())

    async def _setup_auth_channel(self):
        """봇 구동 시 #입장-및-인증 채널과 임베드가 없으면 자동 생성"""
        await self.bot.wait_until_ready()
        
        if not self.bot.guilds:
            return
        
        guild = self.bot.guilds[0] # 단일 서버 기준
        
        # 미인증자 역할 자동 생성 로직 (없으면 생성)
        unverified_role = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE_NAME)
        if not unverified_role:
            try:
                unverified_role = await guild.create_role(
                    name=UNVERIFIED_ROLE_NAME,
                    color=discord.Color.dark_grey(),
                    reason="초기 셋업 자동 생성"
                )
                log.info(f"✨ '{UNVERIFIED_ROLE_NAME}' 역할을 생성했습니다.")
            except Exception as e:
                log.error(f"미인증자 역할 생성 실패: {e}")

        # 1. 채널 찾기 또는 생성
        channel = discord.utils.get(guild.text_channels, name=AUTH_CHANNEL_NAME)
        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            }
            try:
                # 리스트의 최상단에 생성되도록 포지션 0 권장 (옵션)
                channel = await guild.create_text_channel(
                    name=AUTH_CHANNEL_NAME, 
                    overwrites=overwrites,
                    topic="DSU MyTeam 웹사이트 인증을 위한 채널입니다.",
                    position=0
                )
                log.info(f"✨ #{AUTH_CHANNEL_NAME} 채널을 자동 생성했습니다.")
            except Exception as e:
                log.error(f"채널 생성 실패: {e}")
                return

        # 2. 튜토리얼 임베드 및 버튼 게시 여부 확인
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
                    "서버의 모든 기능을 이용하고 팀 채널에 입장하려면, "
                    "웹사이트에서 발급받은 **[아이디]** 또는 **[인증키]** 중 하나를 입력해야 합니다.\n\n"
                    "아래 버튼을 눌러 정보를 입력해주세요."
                ),
                color=discord.Color.blurple()
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
        """새로운 멤버가 들어오면 무조건 '미인증자' 역할 부여"""
        if member.bot:
            return
            
        unverified_role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE_NAME)
        if unverified_role:
            try:
                await member.add_roles(unverified_role)
                log.info(f"👤 {member.name} 님에게 '{UNVERIFIED_ROLE_NAME}' 역할을 부여했습니다.")
            except Exception as e:
                log.error(f"미인증자 역할 부여 실패 ({member.name}): {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthCog(bot))
