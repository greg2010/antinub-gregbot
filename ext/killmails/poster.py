import typing

import tinydb
import discord
from discord.ext import commands

from utils.esicog import EsiCog
from utils.kvtable import KeyValueTable
from utils.log import get_logger

ESI_SWAGGER_JSON = 'https://esi.evetech.net/latest/swagger.json'


def setup(bot: commands.Bot):
    bot.add_cog(KillmailPoster(bot))


class KillmailPoster(EsiCog):
    def __init__(self, bot: commands.Bot):
        super(KillmailPoster, self).__init__(bot)

        self.logger = get_logger(__name__, bot)
        self.bot = bot
        self.config_table = KeyValueTable(self.bot.tdb, "killmails.config")
        self.relevancy_table = self.bot.tdb.table("killmails.relevancies")
        self.relevancy = tinydb.Query()

    async def on_killmail(self, package: dict, **dummy_kwargs):
        if not await self.is_relevant(package):
            self.logger.debug("Ignoring irrelevant killmail")
            return
            # Flags 92, 93, 94 are rig slots
        embed = self.generate_embed(package)
        message = await self.bot.send_message(
            self.config_table["channel"], embed=embed)
        await self.add_reactions(message)

    async def add_reactions(self, message: discord.Message):
        pass

    def generate_embed(self, package: dict) -> discord.Embed:
        pass

    async def is_relevant(self, package: dict) -> bool:
        victim = package["killmail"]["victim"]
        if await self.is_corporation_relevant(victim["corporation_id"]):
            #  Mark killmail as a loss
            package["colour"] = discord.Colour.dark_red()
            return True

        for attacker in package["killmail"]["attackers"]:
            if "corporation_id" not in attacker:
                continue  # Some NPCs do not have a corporation.
            if await self.is_corporation_relevant("corporation_id"):
                #  Mark killmail as a kill
                package["colour"] = discord.Colour.dark_green()
                return True

        return False

    async def is_corporation_relevant(self, corporation_id: int) -> bool:
        if corporation_id in await self.get_relevant_corporations():
            return True

        if corporation_id in await self.get_relevant_alliances():
            return True

        return False

    async def get_relevant_corporations(self) -> typing.List[int]:
        corps = self.relevancy_table.search(
            self.relevancy.type == "corporation")
        return [entry["value"] for entry in corps]

    async def get_relevant_alliances(self) -> typing.List[int]:
        corp_ids = set()
        alliances = self.relevancy_table.search(
            self.relevancy.type == "alliance")
        alliance_ids = [entry["value"] for entry in alliances]

        for alliance_id in alliance_ids:
            alliance_corp_ids = await self.get_alliance_corporations(
                alliance_id)
            corp_ids.update(alliance_corp_ids)

        return list(corp_ids)

    async def get_alliance_corporations(self,
                                        alliance_id: int) -> typing.List[int]:
        esi_app = await self.get_esi_app()
        operation = esi_app.op["get_alliances_alliance_id_corporations"](
            alliance_id=alliance_id)

        esi_client = await self.get_esi_client()
        # response = esi_client.request(operation)
        response = await self.esi_request(self.bot.loop, esi_client, operation)
        return response.data
