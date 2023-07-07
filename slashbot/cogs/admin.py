#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""This cog contains admin commands for Slashbot."""

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
from slashbot.custom_cog import SlashbotCog
from slashbot.markov import MARKOV_MODEL
from slashbot.markov import generate_sentences_for_seed_words

COOLDOWN_USER = commands.BucketType.user
logger = logging.getLogger(App.config("LOGGER_NAME"))


class Admin(SlashbotCog):
    """Admin commands and tools for Slashbot.

    The most useful command is to look at the logfile, or to restart the bot
    when changes have been made.
    """

    def __init__(self, bot: commands.InteractionBot, logfile_path: Path | str):
        super().__init__()
        self.bot = bot
        self.logfile_path = Path(logfile_path)

        self.markov_sentences = (
            generate_sentences_for_seed_words(
                MARKOV_MODEL,
                ["unban"],
                1,
            )
            if self.bot.markov_gen_on
            else {"unban": []}
        )

    # Commands -----------------------------------------------------------------

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="version", description="Print the current version number of the bot")
    async def print_version(self, inter: disnake.ApplicationCommandInteraction) -> coroutine:
        """Print the current version number of the bot."""
        await inter.response.send_message(f"Current version: {__version__}", ephemeral=True)

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="logfile", description="get the tail of the logfile")
    async def print_logfile(
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

        Parameters
        ----------
        file: str
            The name of the file to look at
        num_lines: int
            The number of lines to print.
        """
        await inter.response.defer(ephemeral=True)

        if file == "slashbot":
            file_name = self.logfile_path
        else:
            file_name = self.logfile_path.with_name("disnake.log")

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

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="ip", description="get the external ip address for the bot")
    async def print_ip_address(self, inter: disnake.ApplicationCommandInteraction):
        """Get the external IP of the bot."""
        if inter.author.id != App.config("ID_USER_SAULTYEVIL"):
            return await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)

        try:
            ip_addr = requests.get("https://api.ipify.org", timeout=5).content.decode("utf-8")
            await inter.response.send_message(f"```{ip_addr}```", ephemeral=True)
        except requests.exceptions.Timeout:
            await inter.response.send_message("The IP request timed out.", ephemeral=True)

    @commands.cooldown(App.config("COOLDOWN_RATE"), App.config("COOLDOWN_STANDARD"), COOLDOWN_USER)
    @commands.slash_command(name="restart_bot", description="restart the bot")
    async def restart_bot(
        self,
        inter: disnake.ApplicationCommandInteraction,
        disable_markov: bool = commands.Param(
            choices=["True", "False"],
            default="False",
            description="Disable Markov sentence generation for faster load times",
            converter=lambda _, user_input: user_input == "True",
        ),
    ):
        """Restart the bot."""
        if inter.author.id != App.config("ID_USER_SAULTYEVIL"):
            return await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)

        arguments = ["run.py"]

        if disable_markov:
            arguments.append("--disable-auto-markov-gen")

        await inter.response.send_message("Restarting the bot...", ephemeral=True)
        logger.info("Restarting with new process with arguments %s", arguments)

        os.execv(sys.executable, ["python"] + arguments)
