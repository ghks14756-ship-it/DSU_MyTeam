import asyncio
import os
import sys

# 현재 디렉토리를 path에 추가하여 config를 불러올 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from config import Config

WELCOME_MSG = """**🎉 DSU MyTeam 서버에 오신 것을 환영합니다!**

본 서버는 동서대학교 MYDEX 프로젝트 팀 매칭을 위해 마련된 공간입니다. 
빠르고 성공적인 팀 매칭을 위해 아래 순서대로 진행해 주세요!

**1️⃣ 인증 채널로 이동하기**
- 왼쪽 채널 목록 최상단에 있는 <#입장-및-인증> 채널을 클릭하세요.
- `[✅ 인증하기]` 버튼을 누르고, 웹사이트에서 발급받은 아이디나 인증키를 입력하면 서버 이용 권한이 부여됩니다.

**2️⃣ 자동 매칭 대기**
- 인증이 완료되면 봇이 즉시 여러분의 조건에 맞는 팀을 찾기 시작합니다.
- 매칭은 백그라운드에서 자동 진행되니 편하게 기다려주세요! (최대 7일 대기, 3일 차에 계속 대기할지 묻는 알림이 갑니다.)

**3️⃣ 팀룸 입장 및 활동 시작**
- 4인 1조 매칭이 확정되면 봇이 여러분에게 DM(개인 메시지)으로 팀원들의 정보를 보내드립니다.
- 동시에 왼쪽 `🔒 MYDEX 팀룸` 카테고리 아래에 **우리 팀만의 비밀 텍스트/음성 채널**이 열립니다.
- 팀 채널에 고정된(📌) 팀원 스케줄표를 확인하고 첫인사를 건네보세요!"""

RULES_MSG = """**📜 DSU MyTeam 서버 이용 약관 및 필수 에티켓**

모든 팀원이 쾌적하고 안전하게 프로젝트에 집중할 수 있도록, 본 서버에 입장하신 모든 분들은 아래의 이용 수칙을 준수해야 합니다. 규정을 위반할 경우 매칭 시스템 이용 제한 및 서버 추방 조치가 취해질 수 있습니다.

**제 1조 [상호 존중 및 매너]**
① 모든 팀원에게 기본적으로 존댓말을 사용하며, 상호 존중하는 태도를 갖춥니다.
② 욕설, 비하, 성희롱, 차별적 발언 및 불쾌감을 조성하는 모든 언행은 엄격히 금지됩니다.

**제 2조 [책임감 있는 참여 (잠수 금지)]**
① 팀 매칭이 완료된 후, 특별한 사유 없이 연락을 두절하거나(잠수) 팀 활동에 지속적으로 불참하는 행위를 금지합니다.
② 탈퇴나 하차가 불가피할 경우, 반드시 팀원들에게 미리 상황을 공유하고 양해를 구해야 합니다.

**제 3조 [개인정보 보호]**
① 봇을 통해 전달받은 팀원들의 개인 연락처 및 신상 정보는 오직 '프로젝트 진행' 목적으로만 사용해야 합니다.
② 타인의 연락처나 프로필, 대화 내용을 본인의 동의 없이 서버 외부나 타인에게 유출해서는 안 됩니다.

**제 4조 [음성 채널(보이스챗) 에티켓]**
① 음성 채널 접속 시, 본인이 말하지 않을 때는 '마이크 음소거'를 하여 주변 소음이 팀원들의 소통을 방해하지 않도록 주의합니다.
② 하울링(에코) 방지를 위해 가급적 이어폰이나 헤드셋 사용을 권장합니다.

**제 5조 [서버 및 봇 이용]**
① 스팸 메시지 도배, 상업적 광고, 악성 링크 공유를 금지합니다.
② 매칭 봇의 버그나 오류를 악용하지 않으며, 문제 발견 시 즉시 관리자에게 제보합니다.

> ✅ *본 서버에서 활동을 시작함과 동시에 위 규칙에 동의한 것으로 간주합니다. 멋진 팀워크로 좋은 성과를 이루시길 응원합니다!*"""

class AnnounceBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        if not self.guilds:
            print("봇이 어떤 서버에도 참여하고 있지 않습니다.")
            await self.close()
            return
            
        guild = self.guilds[0]
        
        # 1. 환영인사 채널 세팅
        welcome_channel = discord.utils.get(guild.text_channels, name="환영인사")
        if not welcome_channel:
            welcome_channel = await guild.create_text_channel("환영인사", position=1)
            print("#환영인사 채널 생성됨")
        
        # 기존 메시지 삭제 (깔끔하게 덮어쓰기 위함)
        await welcome_channel.purge(limit=10)
        
        embed1 = discord.Embed(
            description=WELCOME_MSG,
            color=discord.Color.green()
        )
        await welcome_channel.send(embed=embed1)
        print("환영인사 메시지 전송 완료")
        
        # 2. 공지사항 채널 세팅
        rules_channel = discord.utils.get(guild.text_channels, name="공지사항")
        if not rules_channel:
            rules_channel = await guild.create_text_channel("공지사항", position=2)
            print("#공지사항 채널 생성됨")
            
        await rules_channel.purge(limit=10)
        
        embed2 = discord.Embed(
            description=RULES_MSG,
            color=discord.Color.red()
        )
        await rules_channel.send(embed=embed2)
        print("공지사항 메시지 전송 완료")
        
        await self.close()

if __name__ == "__main__":
    bot = AnnounceBot()
    bot.run(Config.BOT_TOKEN)
