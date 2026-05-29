import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from config import Config
from database.db_manager import DatabaseManager
from services.gsheet_service import GoogleSheetService

async def main():
    db = DatabaseManager(Config.DATABASE_PATH)
    await db.init()
    gsheet = GoogleSheetService()
    
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        guild = client.guilds[0]
        
        # 1. 서버 권한 셋업 (미인증자는 특정 채널만, 인증자는 전부)
        print("--- Server Permissions Setup ---")
        everyone_role = guild.default_role
        unverified_role = discord.utils.get(guild.roles, name="미인증자")
        verified_role = discord.utils.get(guild.roles, name="마이덱스이용자")
        
        # everyone 권한에서 view_channel 제거 (모두 숨김)
        perms = everyone_role.permissions
        perms.update(view_channel=False)
        await everyone_role.edit(permissions=perms, reason="서버 비공개화 (인증 시스템)")
        print("Success: @everyone 역할의 '채널 보기' 권한을 해제했습니다.")
        
        if verified_role:
            v_perms = verified_role.permissions
            v_perms.update(view_channel=True)
            await verified_role.edit(permissions=v_perms, reason="인증된 유저 전체 채널 보기")
            print("Success: '마이덱스이용자' 역할에 '채널 보기' 권한을 부여했습니다.")

        # 허용할 3개 채널 오버라이드
        allowed_channels = ["입장-및-인증", "환영인사", "공지사항"]
        for ch_name in allowed_channels:
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if ch:
                # 미인증자(또는 everyone)가 볼 수 있게 허용, 채팅은 금지
                await ch.set_permissions(everyone_role, view_channel=True, send_messages=False, read_message_history=True)
                if unverified_role:
                    await ch.set_permissions(unverified_role, view_channel=True, send_messages=False, read_message_history=True)
                print(f"Success: #{ch_name} 채널을 미인증자에게 공개했습니다.")
        
        # 2. 테스트 유저 'ASFNIJGA' 상태 초기화
        print("--- Test User Reset ---")
        web_id = "ASFNIJGA"
        discord_id_to_reset = None
        
        # 구글 시트에서 찾기
        loop = asyncio.get_running_loop()
        g_client = await loop.run_in_executor(None, gsheet._get_client)
        sheet = g_client.open_by_key(gsheet.spreadsheet_id).worksheet(gsheet.worksheet_users)
        all_values = sheet.get_all_values()
        
        row_idx_to_update = -1
        for idx, row in enumerate(all_values):
            if len(row) > 2 and str(row[2]).strip() == web_id:
                row_idx_to_update = idx + 1
                if len(row) > 3:
                    discord_id_to_reset = str(row[3]).strip()
                break
                
        if row_idx_to_update != -1:
            sheet.update_cell(row_idx_to_update, 4, "") # Discord_ID 지우기
            sheet.update_cell(row_idx_to_update, 5, "미인증") # Auth_Status 되돌리기
            print(f"Success: 구글 시트에서 {web_id} 의 인증 상태를 초기화했습니다.")
        else:
            print(f"Warning: 구글 시트에서 {web_id} 를 찾을 수 없습니다.")

        if discord_id_to_reset:
            # 로컬 DB 되돌리기 (discord_id -> WEB_ASFNIJGA)
            temp_discord_id = f"WEB_{web_id}"
            await db._conn.execute(
                "UPDATE applications SET discord_id = ? WHERE discord_id = ?",
                (temp_discord_id, discord_id_to_reset)
            )
            await db._conn.commit()
            print(f"Success: 로컬 DB에서 {discord_id_to_reset} 의 상태를 {temp_discord_id} 로 되돌렸습니다.")
            
            # 디스코드 역할 뺏고 미인증자 부여하기
            member = guild.get_member(int(discord_id_to_reset))
            if not member:
                try:
                    member = await guild.fetch_member(int(discord_id_to_reset))
                except:
                    pass
            
            if member:
                if verified_role and verified_role in member.roles:
                    await member.remove_roles(verified_role)
                if unverified_role and unverified_role not in member.roles:
                    await member.add_roles(unverified_role)
                print(f"Success: 디스코드 멤버 {member.display_name} 님을 미인증자로 강등시켰습니다.")
            else:
                print("Warning: 해당 디스코드 유저가 서버에 없습니다.")
        else:
            print("Warning: 시트에 기록된 Discord ID가 없어서 DB/디스코드 롤 초기화를 건너뜁니다.")
            
        print("Done!")
        await client.close()

    await client.start(Config.BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
