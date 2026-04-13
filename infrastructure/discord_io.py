"""
infrastructure/discord_io.py
Discord Webhook送信
"""
import os
import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

async def send_webhook(name, text):
    if isinstance(text, list):
        text_str = "".join([t.get("text", "") if isinstance(t, dict) else str(t) for t in text])
    else:
        text_str = str(text)

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
        chunk_size = 1900
        for i in range(0, len(text_str), chunk_size):
            chunk = text_str[i:i+chunk_size]
            if chunk.strip():
                await webhook.send(content=chunk, username=name)
