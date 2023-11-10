# bot.py
from inspect import indentsize
import os
import time
import random
from discord import Game
from keep_alive import keep_alive

import discord
from dotenv import load_dotenv
intents = discord.Intents.default()
intents.auto_moderation = True
intents.auto_moderation_configuration = True
intents.auto_moderation_execution = True
intents.bans = True
intents.dm_messages = True
intents.dm_reactions = True
intents.dm_typing = True
intents.emojis = True
intents.emojis_and_stickers = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_scheduled_events = True
intents.guild_typing = True
intents.guilds = True
intents.integrations = True
intents.invites = True
intents.members = True
intents.message_content = True
intents.messages = True
intents.moderation = True
intents.presences = True
intents.reactions = True
intents.typing = True
intents.value = True
intents.voice_states = True
intents.webhooks = True

client = discord.Client(intents=intents)

keep_alive()
token = os.environ.get("DISCORD_BOT_SECRET")
client.run(token)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

@client.event
async def on_ready():
    print("bot has connected to discord!")

@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.listening, name='hi ! im hello kitty'))

client.run(TOKEN)  