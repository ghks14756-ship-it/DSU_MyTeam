"""
기존 인증 채널의 메시지를 모두 지우고 새 버전(입력 1개)의 인증 버튼을 재게시한다.
모달 버전 혼재(1개/2개 입력칸) 문제 해결용 스크립트.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands
from config import Config

AUTH_CHANNEL_NAME = "입장-및-인증"

class AuthModal(discord.ui.Modal, title="DSU MyTeam 서버 인증"):
    auth_input = discord.ui.TextInput(
        label="아이디 또는 인증키",
        placeholder="웹사이트 발급 아이디(예: DUS-...) 또는 인증키(예: A7X9B2)",
        min_length=3,
        max_length=50,
        required=True
    )
    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("인증 창이 정상적으로 열렸습니다. (이 스크립트는 UI 테스트 전용입니다.)", ephemeral=True)


class AuthButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.success, custom_id="auth_btn_v3")
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AuthModal())


class RefreshBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        guild = self.guilds[0]

        channel = discord.utils.get(guild.text_channels, name=AUTH_CHANNEL_NAME)
        if not channel:
            print(f"Error: #{AUTH_CHANNEL_NAME} 채널을 찾을 수 없습니다.")
            await self.close()
            return

        # 기존 봇 메시지 전체 삭제 (버전 혼재 해소)
        deleted = await channel.purge(limit=20, check=lambda m: m.author == self.user)
        print(f"Info: 기존 메시지 {len(deleted)}개 삭제 완료.")

        # 새 임베드 + 버튼 게시
        embed = discord.Embed(
            title="DSU MyTeam 서버 인증 안내",
            description=(
                "서버의 모든 기능을 이용하고 팀 채널에 입장하려면, "
                "웹사이트에서 발급받은 **[아이디]** 또는 **[인증키]** 중 "
                "하나를 아래 버튼을 눌러 입력해주세요."
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="버튼을 클릭하면 인증 창이 열립니다.")
        await channel.send(embed=embed, view=AuthButtonView())
        print("Success: 새 인증 메시지 게시 완료! 이제 모달 입력칸이 항상 1개로 통일됩니다.")
        await self.close()


if __name__ == "__main__":
    bot = RefreshBot()
    bot.run(Config.BOT_TOKEN)
