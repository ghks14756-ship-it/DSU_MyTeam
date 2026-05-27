import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("DSUMyTeam.Auth")

class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 발급된 역할 이름 (서버 환경에 맞게 수정 필요)
        self.auth_role_name = "MYDEX Member"

    @app_commands.command(name="인증", description="웹페이지에서 발급받은 고유 ID를 입력하여 디스코드 권한을 부여받습니다.")
    @app_commands.describe(unique_id="발급받은 고유 ID (예: DUS-9A2X-B7QW-P4M1-V5Z8)")
    async def auth_command(self, interaction: discord.Interaction, unique_id: str):
        unique_id = unique_id.strip().upper()
        
        # 1. DB에서 해당 unique_id를 가진 신청 내역 조회
        # 임시로 discord_id 에 'WEB_{unique_id}' 로 저장했다고 가정.
        temp_discord_id = f"WEB_{unique_id}"
        
        async with self.bot.db._conn.execute(
            "SELECT id FROM applications WHERE discord_id = ?", 
            (temp_discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            await interaction.response.send_message(
                f"❌ 일치하는 고유 ID(`{unique_id}`)를 찾을 수 없습니다. 올바르게 입력했는지 확인해주세요.", 
                ephemeral=True
            )
            return
            
        # 2. 디스코드 ID 업데이트 및 Auth_Status 변경 (로컬 DB 업데이트)
        app_id = row[0]
        actual_discord_id = str(interaction.user.id)
        
        await self.bot.db._conn.execute(
            "UPDATE applications SET discord_id = ? WHERE id = ?",
            (actual_discord_id, app_id)
        )
        await self.bot.db._conn.commit()
        
        # 3. 디스코드 역할 부여 (서버에 해당 역할이 존재해야 함)
        role = discord.utils.get(interaction.guild.roles, name=self.auth_role_name)
        if role:
            try:
                await interaction.user.add_roles(role)
            except Exception as e:
                log.error(f"역할 부여 실패: {e}")
        else:
            log.warning(f"서버에 '{self.auth_role_name}' 역할이 없습니다. 역할 부여를 생략합니다.")
        
        # 4. 구글 시트에도 디스코드 ID와 인증 상태 업데이트 (동기화)
        # 구글 시트를 전체 순회하여 고유 ID를 찾아 업데이트해야 하므로 약간의 비용 발생.
        # 현 단계에서는 "봇이 기록해 둔다"는 기획 의도에 맞춰 비동기 태스크로 넘겨 처리 가능.
        asyncio.ensure_future(self.update_gsheet_auth(unique_id, actual_discord_id))

        await interaction.response.send_message(
            f"✅ 인증이 완료되었습니다! 이제 모든 채널을 이용하실 수 있습니다.\n"
            f"(고유 ID: `{unique_id}` 가 성공적으로 연동되었습니다.)", 
            ephemeral=True
        )

    async def update_gsheet_auth(self, unique_id: str, discord_id: str):
        """구글 시트에서 unique_id를 찾아 디스코드ID와 인증상태(Auth_Status)를 업데이트"""
        try:
            if not self.bot.gsheet.spreadsheet_id or self.bot.gsheet.spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
                return
            
            import asyncio
            loop = asyncio.get_running_loop()
            client = await loop.run_in_executor(None, self.bot.gsheet._get_client)
            
            def _update():
                sheet = client.open_by_key(self.bot.gsheet.spreadsheet_id).worksheet(self.bot.gsheet.worksheet_users)
                all_values = sheet.get_all_values()
                if len(all_values) < 2: return
                
                # A열(Unique_ID), C열(Discord_ID), D열(Auth_Status)
                # Unique_ID가 일치하는 행 찾기
                for idx, row in enumerate(all_values):
                    if row and str(row[0]).strip() == unique_id:
                        row_num = idx + 1 # 1-based index
                        # C열(Discord_ID)와 D열(Auth_Status) 업데이트
                        sheet.update_cell(row_num, 3, discord_id)
                        sheet.update_cell(row_num, 4, "인증완료")
                        break
                        
            await loop.run_in_executor(None, _update)
            log.info(f"구글 시트 인증 정보 업데이트 완료: {unique_id} -> {discord_id}")
        except Exception as e:
            log.error(f"구글 시트 인증 업데이트 실패: {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuthCog(bot))
