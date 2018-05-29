import functools
import typing
from datetime import datetime
from enum import Enum

import tinydb
import discord
from discord.ext import commands

from utils.esicog import EsiCog
from utils.kvtable import KeyValueTable
from utils.log import get_logger

ZKILLBOARD_BASE_URL = "https://zkillboard.com/kill/{:d}/"
EVE_IMAGESERVER_BASE_URL = "https://imageserver.eveonline.com/Type/{:d}_64.png"
REGIONAL_INDICATOR_F = "\U0001F1EB"


def setup(bot: commands.Bot):
    bot.add_cog(KillmailPoster(bot))


class Relevancy(Enum):
    def __repr__(self):
        return '<%s.%s>' % (self.__class__.__name__, self.name)

    @property
    def colour(self):
        return self.value["colour"]  # pylint: disable=unsubscriptable-object

    IRRELEVANT = {}
    LOSSMAIL = {"colour": discord.Colour(0x7a0000)}
    KILLMAIL = {"colour": discord.Colour(0x007a00)}


class KillmailPoster(EsiCog):
    def __init__(self, bot: commands.Bot):
        super(KillmailPoster, self).__init__(bot)

        self.logger = get_logger(__name__, bot)
        self.bot = bot
        self.config_table = KeyValueTable(self.bot.tdb, "killmails.config")
        self.relevancy_table = self.bot.tdb.table("killmails.relevancies")
        self.relevancy = tinydb.Query()

    async def on_killmail(self, package: dict, **dummy_kwargs):
        package["relevancy"] = await self.is_relevant(package)
        if package["relevancy"] is Relevancy.IRRELEVANT:
            self.logger.debug("Ignoring irrelevant killmail")
            return
        self.logger.info("Posting %s",
                         ZKILLBOARD_BASE_URL.format(package["killID"]))
        package["data"] = await self.fetch_data(package)
        embed = await self.generate_embed(package)
        message = await self.bot.send_message(
            self.bot.get_channel(self.config_table["channel"]), embed=embed)
        await self.add_reactions(message, package)

    async def add_reactions(self, message: discord.Message, package: dict):
        relevancy = package["relevancy"]
        if relevancy is Relevancy.LOSSMAIL:
            await self.bot.add_reaction(message, REGIONAL_INDICATOR_F)

        data = package["data"]
        # Flags 92, 93, 94 are rig slots, 1137 is number of rig slots
        pass

    async def generate_embed(self, package: dict) -> discord.Embed:
        embed = discord.Embed()
        data = package["data"]
        names = [val["name"] for val in data.values()]

        identity = names["affiliation"]
        if "character" in names:
            identity = "{0[character]} ({0[affiliation]})".format(names)

        embed.title = "{0[solar_system]} | {0[ship_type]} | {identity}".format(
            names, identity=identity)
        embed.description = ("{identity} lost their {0[ship_type]} in "
                             "{0[solar_system]} ({0[region]})\n"
                             "Total Value: {1:,} ISK\n"
                             "\u200b").format(
                                 names,
                                 package["zkb"]["totalValue"],
                                 identity=identity)
        embed.url = ZKILLBOARD_BASE_URL.format(package["killID"])
        embed.timestamp = datetime.strptime(
            package["killmail"]["killmail_time"], "%Y-%m-%dT%H:%M:%SZ")
        embed.colour = package["relevancy"].colour
        ship_type_id = package["killmail"]["victim"]["ship_type_id"]
        embed.set_thumbnail(url=EVE_IMAGESERVER_BASE_URL.format(ship_type_id))

        return embed

    async def fetch_data(self, package: dict) -> dict:
        esi_app = await self.get_esi_app()
        esi_client = await self.get_esi_client()
        esi_request = functools.partial(self.esi_request, self.bot.loop,
                                        esi_client)
        data = {}

        operation = esi_app.op["get_universe_systems_system_id"](
            system_id=package["killmail"]["solar_system_id"])
        response = await esi_request(operation)
        data["solar_system"] = response.data

        operation = esi_app.op["get_universe_constellations_constellation_id"](
            constellation_id=response.data["constellation_id"])
        response = await esi_request(operation)
        operation = esi_app.op["get_universe_regions_region_id"](
            region_id=response.data["region_id"])
        response = await esi_request(operation)
        data["region"] = response.data

        operation = esi_app.op["get_universe_types_type_id"](
            type_id=package["killmail"]["victim"]["ship_type_id"])
        response = await esi_request(operation)
        data["ship_type"] = response.data

        data["character"] = ""  # Structures have no character_id
        if "character_id" in package["killmail"]["victim"]:
            operation = esi_app.op["get_characters_character_id"](
                character_id=package["killmail"]["victim"]["character_id"])
            response = await esi_request(operation)
            data["character"] = response.data

        if "alliance_id" in package["killmail"]["victim"]:
            operation = esi_app.op["get_alliances_alliance_id"](
                alliance_id=package["killmail"]["victim"]["alliance_id"])
            response = await esi_request(operation)
            data["affiliation"] = response.data
        else:
            operation = esi_app.op["get_corporations_corporation_id"](
                corporation_id=package["killmail"]["victim"]["corporation_id"])
            response = await esi_request(operation)
            data["affiliation"] = response.data

        return data

    async def is_relevant(self, package: dict) -> Relevancy:
        victim = package["killmail"]["victim"]
        if await self.is_corporation_relevant(victim["corporation_id"]):
            return Relevancy.LOSSMAIL

        for attacker in package["killmail"]["attackers"]:
            if "corporation_id" not in attacker:
                continue  # Some NPCs do not have a corporation.
            if await self.is_corporation_relevant(attacker["corporation_id"]):
                return Relevancy.KILLMAIL

        return Relevancy.IRRELEVANT

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
        response = await self.esi_request(self.bot.loop, esi_client, operation)
        return response.data
