"""
Cog containing role assignment via message reactions
"""
import discord.ext.commands as commands
import discord
from discord import reaction

client = discord.Client()

from utils.log import get_logger

def setup(bot):
    "Adds the cog to the provided discord bot"
    bot.add_cog(AssignRoles(bot))


class AssignRoles(commands.Cog, name="AssignRoles"):
    def __init__(self, bot):
        self.logger = get_logger(__name__)
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        print("I am listening")

    @commands.Cog.listener()
    async def on_guild_join(self):
        Channel = client.get_channel(845040859476394067)
        if reaction.message.channel.id == 845040859476394067:
            return await ctx.send(
            "React to this message for roles"
        )
    @commands.Cog.listener()
    async def on_ready(self):
        Channel = client.get_channel(845040859476394067)
        Text= "added thumbs up"
        Moji = await client.send_message(Channel, Text)
        await client.add_reaction(Moji, emoji='thumbsup')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        Channel = client.get_channel(845040859476394067)
        if reaction.message.channel.id != 845040859476394067:
            return
        if reaction.emoji == "👀":
            Role = discord.utils.get(user.guild.roles, id=846190618748518400)
            await user.add_roles(Role)
            print("I added Eyes to " + user.name)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        Channel = client.get_channel(845040859476394067)
        if reaction.message.channel.id != 845040859476394067:
            return
        if reaction.emoji == "👀":
            Role = discord.utils.get(user.guild.roles, id=846190618748518400)
            await user.remove_roles(Role)
            print("I removed Eyes from " + user.name)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        Channel = client.get_channel(845040859476394067)
        if reaction.message.channel.id != 845040859476394067:
            return
        if reaction.emoji == "👀":
            Role = discord.utils.get(user.guild.roles, id=846190618748518400)
            await user.remove_roles(Role)
            print("I removed raw Eyes from " + user.name)
