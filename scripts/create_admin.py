import asyncio
import os
import sys

# 상위 디렉토리를 시스템 경로에 추가하여 config를 불러옴
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from config import Config

class AdminSetupBot(discord.Client):
    def __init__(self):
        # 멤버 정보를 읽어오기 위해 members 인텐트 필수
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        if not self.guilds:
            print("봇이 어떤 서버에도 참여하고 있지 않습니다.")
            await self.close()
            return
            
        guild = self.guilds[0]
        print(f"서버 '{guild.name}' 에 접속했습니다.")
        
        # 1. 관리자 역할 찾기 또는 생성
        admin_role = discord.utils.get(guild.roles, name="관리자")
        if not admin_role:
            try:
                # 관리자 권한을 가진 역할 생성
                permissions = discord.Permissions(administrator=True)
                admin_role = await guild.create_role(
                    name="관리자", 
                    permissions=permissions, 
                    color=discord.Color.gold(),
                    hoist=True, # 우측 멤버 목록에서 따로 분리해서 보여줌
                    reason="초기 관리자 셋업 스크립트 실행"
                )
                print("Success: '관리자' 역할을 새로 생성했습니다.")
            except Exception as e:
                print(f"Error: 역할 생성 실패: {e}")
                await self.close()
                return
        else:
            print("Success: '관리자' 역할이 이미 존재합니다.")

        # 2. 본인(서버 소유자)과 '새싹'님 찾아서 부여하기
        target_members = []
        
        # 서버 소유자는 무조건 관리자
        if guild.owner:
            target_members.append(guild.owner)
            
        # 모든 멤버를 순회하면서 이름에 '새싹'이 포함된 사람 찾기
        for member in guild.members:
            name_fields = [member.name, member.nick, member.global_name]
            if any(name and "새싹" in name for name in name_fields):
                if member not in target_members:
                    target_members.append(member)

        if not target_members:
            print("Warning: 관리자 역할을 부여할 대상(서버 소유자 및 새싹)을 찾지 못했습니다.")
        
        # 3. 역할 부여
        for member in target_members:
            if admin_role not in member.roles:
                try:
                    await member.add_roles(admin_role)
                    print(f"Success: {member.display_name} 님에게 관리자 역할을 부여했습니다!")
                except Exception as e:
                    print(f"Error: 역할 부여 실패 ({member.display_name}): {e}")
            else:
                print(f"Info: {member.display_name} 님은 이미 관리자 역할을 가지고 있습니다.")
                
        await self.close()

if __name__ == "__main__":
    bot = AdminSetupBot()
    bot.run(Config.BOT_TOKEN)
