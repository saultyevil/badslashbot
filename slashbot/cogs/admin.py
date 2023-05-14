#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Admin commands for the bot."""

import logging
import os
import sys
from pathlib import Path
from types import coroutine

import disnake
import requests
from disnake.ext import commands

from slashbot import __version__
from slashbot.config import App
from slashbot.custom_cog import CustomCog

cd_user = commands.BucketType.user
logger = logging.getLogger(App.config("LOGGER_NAME"))


class AdminCommands(CustomCog):
    """Admin tools for the bot."""

    def __init__(self, bot: commands.InteractionBot, log_path: Path):
        """Initialize the class."""
        super().__init__()
        self.bot = bot
        self.log_path = Path(log_path)

    # Commands -----------------------------------------------------------------

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), cd_user)
    @commands.slash_command(name="version", description="get the version number of the bot")
    @commands.default_member_permissions(administrator=True)
    async def check_version(self, inter: disnake.ApplicationCommandInteraction) -> coroutine:
        """Check the version of the bot in use"""
        await inter.response.send_message(f"Version {__version__}", ephemeral=True)

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), cd_user)
    @commands.slash_command(name="logfile", description="get the tail of the logfile")
    @commands.default_member_permissions(administrator=True)
    async def log_tail(
        self,
        inter: disnake.ApplicationCommandInteraction,
        file: str = commands.Param(
            default="slashbot",
            description="The log file to tail, slashbot or disnake.",
            choices=["slashbot", "disnake"],
        ),
        num_lines: int = commands.Param(
            default=10,
            description="The number of lines to include in the tail of the log file.",
            max_value=50,
            min_value=1,
        ),
    ) -> coroutine:
        """Print the tail of the log file.

        TODO: reading in the file may need optimizing in the future, e.g.:
              https://stackoverflow.com/questions/136168/get-last-n-lines-of-a-file-similar-to-tail

        Parameters
        ----------
        file: str
            The name of the file to look at
        num_lines: int
            The number of lines to print.
        """
        await inter.response.defer(ephemeral=True)

        if file == "slashbot":
            file_name = self.log_path
        else:
            file_name = self.log_path.with_name("disnake.log")

        with open(file_name, "r", encoding="utf-8") as file_in:
            log_lines = file_in.readlines()

        # iterate backwards over log_lines, until either n_lines is reached or
        # the character limit is reached

        tail = []
        num_chars = 0

        for i in range(1, num_lines + 1):
            try:
                num_chars += len(log_lines[-i])
            except IndexError:
                break

            if num_chars > App.config("MAX_CHARS"):
                break
            tail.append(log_lines[-i])

        return await inter.edit_original_message(f"```{''.join(tail[::-1])}```")

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), cd_user)
    @commands.slash_command(name="ip", description="get the external ip address for the bot")
    @commands.default_member_permissions(administrator=True)
    async def external_ip_address(self, inter: disnake.ApplicationCommandInteraction):
        """Get the external IP of the bot."""
        if inter.author.id != App.config("ID_USER_SAULTYEVIL"):
            return await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)

        ip_addr = requests.get("https://api.ipify.org", timeout=5).content.decode("utf-8")
        await inter.response.send_message(f"```{ip_addr}```", ephemeral=True)

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), cd_user)
    @commands.slash_command(name="restart_bot", description="restart the bot")
    @commands.default_member_permissions(administrator=True)
    async def restart_bot(self, inter: disnake.ApplicationCommandInteraction):
        """Restart the bot."""
        if inter.author.id != App.config("ID_USER_SAULTYEVIL"):
            return await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)

        logger.info("restarting bot with new process")
        await inter.response.send_message("Restarting the bot...", ephemeral=True)

        os.execv(sys.executable, ["python"] + sys.argv)
