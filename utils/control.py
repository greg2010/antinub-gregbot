'''
Main helper cog made for antinub-gregbot project.

Contains several commands useful for controlling/debugging the bot
'''
import logging
import os
from collections import deque

import discord.ext.commands as commands

import config
from . import checks


def setup(bot):
    'Adds the cog to the provided discord bot'
    bot.add_cog(Control(bot))


def paginate(string, formatting='```\n', max_length=2000, sep='\n'):
    'Chops a string into even chunks of max_length around the given separator'
    max_size = max_length - 2*len(formatting)

    str_length = len(string)
    if str_length <= max_size:
        return [formatting + string + formatting]
    else:
        split = string.rfind(sep, 0, max_size) + 1
        if split:
            return ([formatting + string[:split] + formatting]
                    + paginate(string[split:], formatting, max_length, sep))
        else:
            return ([formatting + string[:max_size] + formatting]
                    + paginate(string[max_size:], formatting, max_length, sep))


class Control:
    '''A cog defining commands for controlling the
    bot's operation such as stopping the bot'''
    def __init__(self, bot):
        self.logger = logging.getLogger(__name__)
        self.bot = bot

    async def on_command_error(self, exception, ctx):
        'Assign a handler for errors raised by commands'
        logger = self.logger if not ctx.cog else ctx.cog.logger

        if isinstance(exception, commands.CheckFailure):
            logger.warning('{} {} attempted to use {} command'.format(
                ctx.message.author.name,
                ctx.message.author.mention, ctx.command))
        elif isinstance(exception, commands.CommandNotFound):
            logger.debug(exception)
        else:
            logger.exception(exception)

    @commands.command()
    @commands.check(checks.is_owner)
    async def stop(self):
        'Logs the bot out of discord and stops it'
        self.logger.info('Unloading extensions')
        extensions = self.bot.extensions.copy()
        for extension in extensions.keys():
            self.bot.unload_extension(extension)
        await self.bot.say('до свидания')
        self.logger.info('Logging out')
        await self.bot.logout()

    @commands.command()
    @commands.check(checks.is_owner)
    async def log(self, logname: str='error', n_lines: int=10):
        'The bot posts the last n (default 10) lines of the specified logfile'
        try:
            n_lines = int(logname)
            logname = 'error'
        except ValueError:
            pass

        if n_lines <= 0:
            await self.bot.say('Invalid number of lines to display')
            return

        try:
            path = os.path.join(config.LOG_PATH, '{}.log'.format(logname))
            with open(path, 'rt') as log:
                lines = deque(log, n_lines)
            pref_str = 'Here are the last {} lines of the {} log:\n'
            pref = pref_str.format(n_lines, logname)
            body = ''.join(lines)

            if len(body) > 0:  # Only continue if there is anything to show
                responses = paginate(body)

                await self.bot.say(pref)
                for response in responses:
                    await self.bot.say(response)
            else:
                await self.bot.say('{} log is empty'.format(logname))
        except FileNotFoundError:
            await self.bot.say('Specified log file does not exist')

    def get_health(self):
        'Returns a string describing the status of this cog'
        if self.bot.is_logged_in:
            return '\n  \u2714 Logged in as {}, id: {}'.format(
                self.bot.user.name, self.bot.user.id)
        else:
            return '\n  \u2716 Bot is not currently logged in'

    @commands.command()
    @commands.check(checks.is_owner)
    async def healthcheck(self, *args: str):
        'Returns the status of the named cog(s)'
        if len(args) == 0:
            args = self.bot.cogs

        response = ''
        for name in args:
            name = name.capitalize()
            if name in self.bot.cogs:
                cog = self.bot.cogs[name]
                try:
                    report = cog.get_health()
                    response += '{}: {}\n'.format(name, report)
                except AttributeError as exc:
                    self.logger.warning(exc)
            else:
                response += '{}:\n  \u2716 No such extension\n'.format(name)

        for page in paginate(response):
            await self.bot.say(page)

    @commands.group(pass_context=True, invoke_without_command=True)
    @commands.check(checks.is_owner)
    async def ext(self):
        'Group of commands regarding loading and unloading of extensions'
        await self.bot.say(self.bot.extensions.keys())

    @ext.command()
    async def load(self, name: str=None):
        'Attempt to load the specified extension'
        if name is not None:
            if name.startswith('ext.'):
                plain_name = name[4:]
                lib_name = name
            else:
                plain_name = name
                lib_name = 'ext.{}'.format(name)

            if lib_name not in self.bot.extensions:
                try:
                    self.bot.load_extension(lib_name)
                    self.logger.info('Successfully loaded extension: %s',
                                     plain_name)
                    await self.bot.say('Successfully loaded extension: {}'
                                       .format(plain_name))
                except ImportError as exc:
                    await self.bot.say('Extension not found: {}'
                                       .format(plain_name))
                except Exception as exc:
                    await self.bot.say('Failed to load extension: {} - {}'
                                       .format(plain_name, exc))
                    self.logger.warning('Failed to load extension: %s',
                                        plain_name)
                    raise exc
            else:
                await self.bot.say('{} extension is already loaded'
                                   .format(plain_name))
        else:
            await self.bot.say('You must specify an extension to load')

    @ext.command()
    async def unload(self, name: str=None):
        'Attempt to unload the specified extension'
        if name is None:
            await self.bot.say('You must specify an extension to unload')
        else:
            if name.startswith('ext.'):
                plain_name = name[4:]
                lib_name = name
            else:
                plain_name = name
                lib_name = 'ext.{}'.format(name)

            if lib_name in self.bot.extensions:
                self.bot.unload_extension(lib_name)
                self.logger.info('Successfully unloaded extension: %s',
                                 plain_name)
                await self.bot.say('Successfully unloaded extension: {}'
                                   .format(plain_name))
            else:
                await self.bot.say('{} extension is not loaded'
                                   .format(plain_name))

    @ext.command(name='reload')
    async def reload_extension(self, name: str=None):
        'Attempt to unload then load the specified extension'
        if name is not None:
            if name.startswith('ext.'):
                plain_name = name[4:]
                lib_name = name
            else:
                plain_name = name
                lib_name = 'ext.{}'.format(name)

            if lib_name in self.bot.extensions:
                self.bot.unload_extension(lib_name)
                self.logger.info('Successfully unloaded extension: %s',
                                 plain_name)
                try:
                    self.bot.load_extension(lib_name)
                    self.logger.info('Successfully loaded extension: %s',
                                     plain_name)
                    await self.bot.say('Successfully reloaded extension: {}'
                                       .format(plain_name))
                except Exception as exc:
                    self.logger.warning('Failed to reload extension: %s - %s',
                                        plain_name, exc)
                    await self.bot.say('Failed to reload extension: {}'
                                       .format(plain_name))
                    raise exc
            else:
                await self.bot.say('{} extension is not loaded'
                                   .format(plain_name))
        else:
            await self.bot.say('You must specify an extension to reload')
