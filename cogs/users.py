#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Commands for remembering user info."""

import json
import logging
from types import coroutine
from typing import List

import disnake
from config import App
from disnake.ext import commands

logger = logging.getLogger(App.config("LOGGER_NAME"))
cd_user = commands.BucketType.user
remember_options = ["location", "country", "badword", "fxtwitter"]


async def autocomplete_remember_choices(inter: disnake.ApplicationCommandInteraction, _: str) -> List[str]:
    """Autocompletion for choices for the remember command.

    Returns
    -------
    choice: Union[str, List[str]]
        The converted choice.
    """
    thing_chosen = inter.filled_options["thing"]
    return ["enable", "disable"] if thing_chosen == "fxtwitter" else ""


async def convert_fxtwitter_input(inter, choice: str) -> str:
    """Convert the fxtwitter option (enable/disable) to a bool.

    Parameters
    ----------
    choice: str
        The choice to convert.

    Returns
    -------
    choice: Union[str, bool]
        The converted choice.
    """
    if inter.filled_options["thing"] == "fxtwitter":
        return choice == "enable"

    return choice


class Users(commands.Cog):
    """Cog for commands used to save user data."""

    def __init__(self, bot: commands.InteractionBot) -> None:
        """Initialize the cog.

        Parameters
        ----------
        bot: commands.InteractionBot
            The bot object.
        """
        self.bot = bot
        self.user_data = App.config("USER_INFO_FILE_STREAM")

    # Before command invoke ----------------------------------------------------

    async def cog_before_slash_command_invoke(
        self, inter: disnake.ApplicationCommandInteraction
    ) -> disnake.ApplicationCommandInteraction:
        """Reset the cooldown for some users and servers.

        Parameters
        ----------
        inter: disnake.ApplicationCommandInteraction
            The interaction to possibly remove the cooldown from.
        """
        if inter.guild and inter.guild.id != App.config("ID_SERVER_ADULT_CHILDREN"):
            return inter.application_command.reset_cooldown(inter)

        if inter.author.id in App.config("NO_COOL_DOWN_USERS"):
            return inter.application_command.reset_cooldown(inter)

    # Commands -----------------------------------------------------------------

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), cd_user)
    @commands.slash_command(name="set_info", description="set info to remember about you")
    async def set_info(
        self,
        inter: disnake.ApplicationCommandInteraction,
        thing: str = commands.Param(description="The type of thing to be remembered.", choices=remember_options),
        value: str = commands.Param(
            description="What to remember.",
            autocomplete=autocomplete_remember_choices,
            converter=convert_fxtwitter_input,
        ),
    ) -> coroutine:
        """Set some user variables for a user.

        Parameters
        ----------
        inter: disnake.ApplicationCommandInteraction
            The interaction to possibly remove the cooldown from.
        thing: str
            The thing to set.
        value: str
            The value of the thing to set.
        """
        await inter.response.defer(ephemeral=True)

        value = value.lower() if isinstance(value, str) else value

        try:
            self.user_data[str(inter.author.id)][thing] = value
        except KeyError:
            self.user_data[str(inter.author.id)] = {thing: value}

        logger.info("%s has set %s to %s", inter.author.name, thing, value)

        with open(App.config("USERS_FILE"), "w", encoding="utf-8") as file_in:
            json.dump(self.user_data, file_in)

        return await inter.edit_original_message(content=f"{thing.capitalize()} has been set to {value}.")
