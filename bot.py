#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Badderbot is another discord bot.

The sole purpose of this bot is to annoy Gareth.
"""

import os
import time
import pickle

import disnake
from disnake.ext import commands

import cogs.info
import cogs.music
import cogs.remind
import cogs.spam
import config
from markovify import markovify

# Create the bot class, with extra clean up functionality ----------------------

start = time.time()

class Bot(commands.Bot):
    """Bot class, with changes for clean up on close."""
    def __init__(self, **kwargs):
        """Initialize the class."""
        commands.Bot.__init__(self, **kwargs)
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


# Load in the markov chain and various other data ------------------------------

markovchain = markovify.Text("Jack is a naughty boy.", state_size=2)
if os.path.exists("data/chain.pickle"):
    with open("data/chain.pickle", "rb") as fp:
        markovchain.chain = pickle.load(fp)

with open("data/badwords.txt", "r") as fp:
    badwords = fp.readlines()[0].split()

with open("data/godwords.txt", "r") as fp:
    godwords = fp.read().splitlines()

for file in ["data/users.json", "data/reminders.json"]:
    if not os.path.exists(file):
        with open(file, "w") as fp:
            fp.write("{}")

# Set up the bot and cogs ------------------------------------------------------

intents = disnake
intents = disnake.Intents.default()
intents.members = True
intents.invites = True

bot = Bot(command_prefix=config.symbol, intents=intents)
spam = cogs.spam.Spam(bot, markovchain, badwords, godwords)
info = cogs.info.Info(bot, spam.generate_sentence, badwords, godwords)
reminder = cogs.remind.Reminder(bot, spam.generate_sentence)
music = cogs.music.Music(bot)

bot.add_cog(spam)
bot.add_cog(info)
bot.add_cog(reminder)
bot.add_cog(music)
bot.add_to_cleanup("Updating markov chains on close", spam.learn, [None])

# Functions --------------------------------------------------------------------


@bot.event
async def on_ready():
    """Information to print on bot launch."""
    message = f"Logged in as {bot.user} in the current servers:"
    for n, server in enumerate(bot.guilds):
        message += "\n  {0}). {1.name} ({1.id})".format(n, server)
    print(message)
    print(f"Started in {time.time() - start:.2f} seconds.")


@bot.event
async def on_slash_command_error(ctx, error):
    """Handle different types of errors.

    Parameters
    ----------
    error: Exception
        The error that occurred.
    """

    print("\n", "-" * 80, f"\n {ctx.application_command.name} for {ctx.author.name} failed with error:\n\n", error)

    if isinstance(error, disnake.errors.InteractionTimedOut):
        error = "The interaction timed out, as it took > 3 seconds to run"
    elif isinstance(error, commands.errors.CommandOnCooldown):
        return await ctx.response.send_message("This command is on cooldown for you.", ephemeral=True)

    try:
        if not ctx.response.is_done():
            await ctx.response.send_message(f"Oh no, there was an error! {error}.", ephemeral=True)
    except (AttributeError, disnake.errors.InterationResponded):
        print("\nuser informed by another error message, as something had no attribute")

    print("\n\n", "-" * 80)

# Run the bot ------------------------------------------------------------------

bot.run(os.environ["BOT_TOKEN"])
