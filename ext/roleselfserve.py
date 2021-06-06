"""
Cog containing role assignment via message reactions
"""
import discord.ext.commands as commands
import discord
import emoji

from utils.log import get_logger

def setup(bot):
    "Adds the cog to the provided discord bot"
    bot.add_cog(RoleSelfServe(bot))


class RoleSelfServe(commands.Cog, name="RoleSelfServe"):
    def __init__(self, bot):
        self.logger = get_logger(__name__)
        self.bot = bot
        self.config = bot.ext_config['roleselfserve']
        self._carrier_messages = {}


    async def clear_carrier_channel(self, channel):
        '''
        Removes all messages from a channel
        '''
        deleted = await channel.purge()
        self.logger.debug('Purged channel {} len(deleted)={}'.format(channel.id, len(deleted)))

    @staticmethod
    def gen_carrier_text(guild, roles):
        '''
        Generates user-friendly text for the carrier message
        '''
        text = 'React with emoji to have role assigned:\n\n'
        for role in roles:
            role_obj = guild.get_role(role['id'])
            text += '{}: :{}:\n'.format(role_obj.name, role['emoji'])
        return text

    @staticmethod
    async def seed_reactions(guild, message, roles):
        '''
        Adds the relevant reactions to a message
        '''
        for role in roles:
            emoji_obj = discord.utils.get(guild.emojis, name=role['emoji'])
            if not emoji_obj:
                emoji_obj = emoji.emojize(':{}:'.format(role['emoji']), use_aliases=True)
            await message.add_reaction(emoji_obj)

    @commands.command()
    async def post_roles_messages(self, msg):
        self._carrier_messages = {}
        for carrier in self.config:
            guild = self.bot.get_guild(carrier['guild_id'])
            chan = self.bot.get_channel(carrier['carrier_channel_id'])

            await self.clear_carrier_channel(chan)

            text = self.gen_carrier_text(guild, carrier['role_relations'])
            msg = await chan.send(text)
            self._carrier_messages[msg.id] = carrier['role_relations']

            await self.seed_reactions(guild, msg, carrier['role_relations'])


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        '''
        This listener listens to emoji reactions.
        If the reaction happens to be to one of the carrier messages, a role toggle is triggered
        '''
        # Ignore own reactions
        if user.id == self.bot.user.id:
            return

        # Check if message that is reacted to is in carrier messages list
        msg_id = reaction.message.id
        if msg_id not in self._carrier_messages:
            return

        # If the reaction is in DMs, and not a server, ignore
        if not isinstance(user, discord.Member):
            return

        role_rels = self._carrier_messages[msg_id]

        # Get the canonical string for the emoji
        reaction_emoji_str = reaction.emoji
        if isinstance(reaction_emoji_str, str):
            reaction_emoji_str = emoji.demojize(reaction_emoji_str, use_aliases=True)
        else:
            reaction_emoji_str = reaction_emoji_str.name

        reaction_emoji_str = reaction_emoji_str[1:-1]

        role = next((x for x in role_rels if x['emoji'] == reaction_emoji_str), None)

        # If no role associated with emoji, ignore
        if not role:
            return

        # Toggle the role
        role_obj = discord.Object(id=role['id'])
        if role['id'] in map(lambda x: x.id, user.roles):
            await user.remove_roles(role_obj)
            self.logger.debug('Removed role {} for user {}'.format(role['id'], user.id))
        else:
            await user.add_roles(role_obj)
            self.logger.debug('Added role {} for user {}'.format(role['id'], user.id))

        # Finally, remove the reaction
        await reaction.message.remove_reaction(reaction.emoji, user)
