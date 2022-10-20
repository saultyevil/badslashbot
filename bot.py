#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Slashbot is another discord bot, using slash command.

The sole purpose of this bot is now to annoy Gareth.
"""

import logging
import os
import pickle
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import aiohttp
import disnake
import requests
from disnake.ext import commands

import cogs.admin
import cogs.content
import cogs.info
import cogs.music
import cogs.remind
import cogs.spam
import cogs.users
import cogs.videos
import cogs.weather
import config
from markovify import markovify  # pylint: disable=import-error

# Set up logger ----------------------------------------------------------------

logger = logging.getLogger(config.LOGGER_NAME)
formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)8s : %(message)s (%(filename)s:%(lineno)d)", "%Y-%m-%d %H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
file_handler = RotatingFileHandler(filename=config.LOGFILE_NAME, encoding="utf-8", maxBytes=int(5e5), backupCount=5)
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Bot(commands.InteractionBot):
    """Bot class, with changes for clean up on close."""

    def __init__(self, **kwargs):
        """Initialize the class."""
        super().__init__(**kwargs)
        self.cleanup_functions = []

    def add_to_cleanup(self, name, function, args):
        """Add a function to the cleanup list.

        Parameters
        ----------
        function: function
            The function to add to the clean up routine.
        args: tuple
            The arguments to pass to the function.
        """
        self.cleanup_functions.append({"name": name, "function": function, "args": args})

    async def close(self):
        """Clean up things on close."""
        for function in self.cleanup_functions:
            print(f"{function['name']}")
            if function["args"]:
                await function["function"](*function["args"])
            else:
                await function["function"]()
        await super().close()


def create_and_run_bot() -> None:  # pylint: disable=too-many-locals too-many-statements
    """Create the bot and run it."""
    start = time.time()

    # Load in the markov chain and various other data --------------------------

    markov_chain = markovify.Text("Jack is a naughty boy.", state_size=2)
    if os.path.exists("data/chain.pickle"):
        with open("data/chain.pickle", "rb") as file_in:
            markov_chain.chain = pickle.load(file_in)

    with open(config.BAD_WORDS_FILE, "r", encoding="utf-8") as file_in:
        bad_words = file_in.readlines()[0].split()

    with open(config.GOD_WORDS_FILE, "r", encoding="utf-8") as file_in:
        god_words = file_in.read().splitlines()

    # Check for files which don't exist, and create empty files if they dont

    for file in config.ALL_FILES:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as file_in:
                file_in.write("{}")

    # Set up the bot and cogs --------------------------------------------------

    intents = disnake.Intents.default()
    intents.members = True  # pylint: disable=assigning-non-slot
    intents.invites = True  # pylint: disable=assigning-non-slot

    # Create bot and the various different cogs
    bot = Bot(intents=intents)
    spam = cogs.spam.Spam(bot, markov_chain, bad_words, god_words)
    info = cogs.info.Info(bot, spam.generate_sentence, bad_words, god_words)
    reminder = cogs.remind.Reminder(bot, spam.generate_sentence)
    content = cogs.content.Content(bot, spam.generate_sentence)
    weather = cogs.weather.Weather(bot, spam.generate_sentence)
    videos = cogs.videos.Videos(bot, bad_words, spam.generate_sentence)
    users = cogs.users.Users(bot)
    admin = cogs.admin.Admin(bot, config.LOGFILE_NAME)

    # Add all the cogs to the bot
    bot.add_cog(spam)
    bot.add_cog(info)
    bot.add_cog(reminder)
    bot.add_cog(content)
    bot.add_cog(weather)
    bot.add_cog(videos)
    bot.add_cog(users)
    bot.add_cog(admin)

    # This part is adding various clean up functions to run when the bot
    # closes, e.g. on keyboard interrupt
    bot.add_to_cleanup("Updating markov chains on close", spam.learn, [None])

    # Bot events ---------------------------------------------------------------

    @bot.event
    async def on_ready():
        """Information to print on bot launch."""
        logger.info("Logged in as %s in the current servers:", bot.user)
        for n_server, server in enumerate(bot.guilds):
            logger.info("\t%d). %s (%d)", n_server, server.name, server.id)
        logger.info("Started in %.2f seconds", time.time() - start)

    @bot.event
    async def on_slash_command_error(inter, error):
        """Handle different types of errors.

        Parameters
        ----------
        error: Exception
            The error that occurred.
        """
        logger.info("%s for %s failed with error:", inter.application_command.name, inter.author.name)
        logger.info(error)

        if isinstance(error, commands.errors.CommandOnCooldown):
            return await inter.response.send_message("This command is on cool down for you.", ephemeral=True)

    # This finally runs the bot

    bot.run(os.environ["BOT_TOKEN"])


# Run the bot ------------------------------------------------------------------
# Do it in a loop like this, as on connection lost to the internet we'll keep
# re-trying to start the bot until eventually a connection is established

if __name__ == "__main__":
    while True:
        try:
            create_and_run_bot()
            break  # exit for other errors
        except (ConnectionError, aiohttp.ClientConnectorError, requests.exceptions.ConnectionError):
            logger.error("No network connection, attempting to restart in 10s")
            time.sleep(10)
